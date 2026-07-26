"""
C1 — Candidate Intake

从 Candidate Fixture 读取并校验 Candidate，生成稳定 idempotency key。
同一 Candidate 重复输入不重复创建 Event。
"""

import hashlib, json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.compatibility.candidate_adapter import CandidateCompatibilityAdapter
from core.schemas.contracts.candidate import DetectionCandidate
from services.repositories.interfaces import Repository


class CandidateIntakeError(Exception):
    pass


class IncompatibleSchemaError(CandidateIntakeError):
    pass


class CandidateIntake:
    """Candidate 摄入服务。

    职责:
    1. 读取 Candidate 数据（dict 或 Fixture 文件）
    2. 校验 candidate_id
    3. 校验 observation_refs 非空
    4. 生成稳定 intake idempotency key
    5. 同一 Candidate 重复输入不重复处理（由 Repository 幂等保证）
    """

    SUPPORTED_SCHEMA_VERSIONS = {
        "rs-contract.v0.2",
        "candidate.v0.2",
        "candidate.v0.3",
    }

    def __init__(self, repository: Repository):
        self.repo = repository

    @staticmethod
    def _compute_idempotency_key(candidate_id: str) -> str:
        """生成稳定的幂等键。"""
        raw = f"candidate_intake:v1:{candidate_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def _validate_schema(data: dict) -> None:
        """验证 Schema 版本兼容性。"""
        schema_version = data.get("schema_version", "")
        if schema_version and schema_version not in CandidateIntake.SUPPORTED_SCHEMA_VERSIONS:
            raise IncompatibleSchemaError(
                f"不兼容的 Schema 版本: {schema_version}。"
                f" 支持的版本: {CandidateIntake.SUPPORTED_SCHEMA_VERSIONS}"
            )

    def ingest_candidate_dict(self, candidate_data: dict) -> tuple[str, DetectionCandidate]:
        """从 dict 摄入 Candidate。

        返回: (idempotency_key, DetectionCandidate)
        """
        # Schema 兼容性检查
        self._validate_schema(candidate_data)

        # 提取 Candidate
        raw = dict(candidate_data.get("candidate", candidate_data))
        if "schema_version" not in raw:
            raw["schema_version"] = (
                "candidate.v0.2"
                if candidate_data.get("schema_version") == "rs-contract.v0.2"
                else "candidate.v0.3"
            )
        candidate = CandidateCompatibilityAdapter.to_detection_candidate(raw)

        # 校验
        if not candidate.candidate_id:
            raise CandidateIntakeError("candidate_id 不能为空")
        if not candidate.observation_refs:
            raise CandidateIntakeError("observation_refs 不能为空")

        # 生成幂等键
        idem_key = self._compute_idempotency_key(candidate.candidate_id)

        # 检查幂等（调用者处理 Event 创建去重）
        existing = self.repo.get_idempotency_result(idem_key)
        if existing:
            return idem_key, candidate

        # 保存幂等键
        self.repo.save_idempotency_key(idem_key, candidate.candidate_id)
        return idem_key, candidate

    def ingest_candidate_file(self, file_path: str | Path) -> tuple[str, DetectionCandidate]:
        """从 Fixture JSON 文件摄入 Candidate。"""
        path = Path(file_path)
        if not path.exists():
            raise CandidateIntakeError(f"Fixture 文件不存在: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self.ingest_candidate_dict(data)

    def get_modalities_info(self, data: dict) -> dict[str, list[str]]:
        """从 Fixture dict 提取模态信息。"""
        return {
            "modalities_expected": data.get("modalities_expected", []),
            "modalities_present": data.get("modalities_present", []),
            "modalities_missing": data.get("modalities_missing", []),
        }
