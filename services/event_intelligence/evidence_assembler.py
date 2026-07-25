"""
C2 — EvidenceAssembler

输入: Candidate Fixture + Candidate evidence_refs + Fixture 资产引用 + 模态缺失信息
输出: Evidence[] → EvidenceBundle

要求:
- 同一输入重复构建 Bundle ID 稳定
- S1 有效、S2 缺失时允许形成 Bundle
- 缺失 S2 必须记录 unavailable
- Evidence 立场显式
- Evidence 质量不能压缩为单一 good/bad
- 不生成不存在的证据
- 不将算法 Candidate 说成现场确认
"""

import hashlib, json
from datetime import datetime
from typing import Any

from core.schemas.contracts.evidence import Evidence, EvidenceBundle
from core.schemas.contracts.candidate import DetectionCandidate
from services.repositories.interfaces import Repository


class EvidenceAssemblerError(Exception):
    pass


class EvidenceAssembler:
    """证据组装器。

    从 Candidate 的 evidence_refs 和 Fixture 资产引用构建 Evidence[] 和 EvidenceBundle。
    支持单模态 Bundle（另一模态缺失时记录 unavailable）。
    """

    VERSION = "1.0.0"

    def __init__(self, repository: Repository):
        self.repo = repository

    @staticmethod
    def _compute_bundle_id(candidate_id: str) -> str:
        """生成稳定的 Bundle ID。"""
        raw = f"evidence_bundle:v1:{candidate_id}"
        return f"bnd_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"

    @staticmethod
    def _compute_evidence_id(candidate_id: str, asset_ref: str) -> str:
        """生成稳定的 Evidence ID。"""
        raw = f"evidence:v1:{candidate_id}:{asset_ref}"
        return f"evd_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"

    def assemble(
        self,
        candidate: DetectionCandidate,
        assets: list[dict],
        modalities_present: list[str] | None = None,
        modalities_missing: list[str] | None = None,
        missing_context_notes: str | None = None,
        evidence_refs: list[str] | None = None,
    ) -> tuple[list[Evidence], EvidenceBundle]:
        """组装 Evidence 和 EvidenceBundle。

        参数:
            candidate: 已校验的 DetectionCandidate
            assets: Fixture 中的资产引用列表
            modalities_present: 存在的模态列表
            modalities_missing: 缺失的模态列表（不能解释为正常）
            missing_context_notes: 缺失上下文说明
            evidence_refs: 证据引用 ID 列表（从 Fixture 提取，候选 v0.3 不内联此字段）

        返回: (EvidenceList, EvidenceBundle)
        """
        evidence_list: list[Evidence] = []
        asset_map = {a.get("asset_id", ""): a for a in assets}

        # (G1.1-C) Strict ref validation: all evidence_refs must exist in assets
        refs = evidence_refs or []
        for ref in refs:
            if ref not in asset_map:
                raise EvidenceAssemblerError(
                    f"证据引用 {ref} 在 Fixture assets 中不存在。"
                    f" 可用 asset_ids: {list(asset_map.keys())}"
                )

        # 从 evidence_refs 构建 Evidence
        for ref in refs:
            asset = asset_map.get(ref, {})
            modality = asset.get("modality", "unknown")
            source_modality = self._modality_to_source(modality)

            evidence = Evidence(
                evidence_id=self._compute_evidence_id(candidate.candidate_id, ref),
                evidence_type=self._infer_evidence_type(asset),
                source_modality=source_modality,
                source_asset_ref=ref,
                candidate_ref=candidate.candidate_id,
                geometry=candidate.geometry,
                stance="supporting",
                quality_summary=None,
                provenance={"assembler_version": self.VERSION, "candidate_id": candidate.candidate_id},
            )
            evidence_list.append(evidence)

        # 为缺失的模态创建 unavailable Evidence
        missing = modalities_missing or []
        for missing_mod in missing:
            evd_id = self._compute_evidence_id(
                candidate.candidate_id, f"unavailable_{missing_mod}"
            )
            evidence = Evidence(
                evidence_id=evd_id,
                evidence_type="unavailable_modality",
                source_modality=missing_mod,
                source_asset_ref=f"unavailable_{missing_mod}",
                candidate_ref=candidate.candidate_id,
                stance="unavailable",
                unavailable_reason=(
                    f"模态 {missing_mod} 不可用"
                    + (f"：{missing_context_notes}" if missing_context_notes else "")
                ),
                provenance={"assembler_version": self.VERSION},
            )
            evidence_list.append(evidence)

        # 保存所有 Evidence
        for evd in evidence_list:
            self.repo.save_evidence(evd)

        # 构建 Bundle
        bundle = EvidenceBundle(
            bundle_id=self._compute_bundle_id(candidate.candidate_id),
            candidate_ref=candidate.candidate_id,
            evidence_refs=[e.evidence_id for e in evidence_list],
            modalities_present=modalities_present or [],
            modalities_missing=modalities_missing or [],
            spatial_summary={"has_geometry": candidate.geometry is not None},
            temporal_summary=candidate.temporal_extent.model_dump(),
            quality_summary=candidate.quality_summary,
            assembler_version=self.VERSION,
        )

        # 保存 Bundle
        self.repo.save_evidence_bundle(bundle)
        return evidence_list, bundle

    @staticmethod
    def _modality_to_source(modality: str) -> str:
        mapping = {
            "sar": "SAR_C",
            "optical": "OPTICAL_MULTI",
            "dem": "DEM",
            "mask": "SAR_C",
            "video": "VIDEO",
        }
        return mapping.get(modality, "UNKNOWN")

    @staticmethod
    def _infer_evidence_type(asset: dict) -> str:
        """从资产元数据推断 evidence_type。"""
        bands = asset.get("bands", [])
        modality = asset.get("modality", "")
        if modality == "sar":
            if "VH" in bands:
                return "sar_vh"
            return "sar_vv"
        elif modality == "optical":
            return "rgb_tile"
        elif modality == "dem":
            return "dem"
        elif modality == "mask":
            return "change_mask"
        return "unknown"
