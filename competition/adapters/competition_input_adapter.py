"""
B3 — CompetitionInputAdapter 增强

支持：
- 单个 manifest 内多个 InferenceTask
- 多个 manifest 批量解析
- 稳定 task_order 排序
- sample_id 唯一、task_id 唯一、Asset ID 唯一
- 同 ID 同内容可去重，同 ID 不同内容报错
- Task 引用的 Asset 必须存在
- TaskSpec 引用不能为空
- asset_bindings role 合法性
- sequence_index 连续
- 明确空样本
- 输入顺序变化后按 task_order 稳定输出
- 不通过文件名猜测任务语义
"""

import json
from pathlib import Path
from typing import Any

from core.schemas.contracts.asset import AssetRef
from core.schemas.contracts.task import InferenceTask, TaskAssetBinding
from core.schemas.contracts import AssetRole


class ManifestError(Exception):
    """Manifest 解析错误。"""
    pass


class DuplicateIdError(ManifestError):
    """重复 ID 错误。"""
    pass


class MissingAssetError(ManifestError):
    """引用的 Asset 不存在。"""
    pass


class EmptyManifestError(ManifestError):
    """空 Manifest 错误。"""
    pass


class CompetitionInputAdapter:
    """比赛输入适配器（B3 增强版）。

    从 manifest 读取资产和任务描述，支持批量、去重、排序和引用校验。
    """

    def __init__(self, manifest_root: str | Path | None = None):
        self.manifest_root = Path(manifest_root) if manifest_root else None

    def _load_manifest(self, manifest: str | Path | dict) -> dict:
        """加载 manifest 为 dict。"""
        if isinstance(manifest, (str, Path)):
            path = Path(manifest)
            if not path.exists():
                raise FileNotFoundError(f"Manifest 文件不存在: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return manifest

    def parse_manifest(self, manifest: str | Path | dict) -> tuple[list[AssetRef], list[InferenceTask]]:
        """
        解析单个 manifest → AssetRef[] + InferenceTask[]。

        manifest 可以是 dict、str 或 Path。
        支持单个 inference_task 对象或 inference_tasks 数组。
        """
        data = self._load_manifest(manifest)
        return self._parse(data)

    def _parse(self, data: dict) -> tuple[list[AssetRef], list[InferenceTask]]:
        """内部解析方法（供 parse_manifest 和批量解析使用）。"""
        # 解析 assets
        assets_raw = data.get("assets", [])
        assets: list[AssetRef] = []
        asset_ids: set[str] = set()
        asset_contents: dict[str, dict] = {}

        for a in assets_raw:
            aid = a.get("asset_id", "")
            if not aid:
                raise ManifestError("Asset asset_id 不能为空")
            if aid in asset_contents:
                # 检查同 ID 内容是否一致
                prev = json.dumps(asset_contents[aid], sort_keys=True, ensure_ascii=False)
                curr = json.dumps(a, sort_keys=True, ensure_ascii=False)
                if prev != curr:
                    raise DuplicateIdError(
                        f"Asset ID '{aid}' 被重复使用但内容不同")
            asset_contents[aid] = a
            if aid not in asset_ids:
                assets.append(AssetRef(**a))
                asset_ids.add(aid)

        # 解析 inference_tasks（支持单个或数组）
        tasks_raw = data.get("inference_tasks", data.get("inference_task", []))
        if isinstance(tasks_raw, dict):
            tasks_raw = [tasks_raw]
        if not tasks_raw:
            raise EmptyManifestError("Manifest 中没有 inference_tasks")

        tasks: list[InferenceTask] = []
        sample_ids: set[str] = set()
        task_ids: set[str] = set()

        for td in tasks_raw:
            # 校验 task_id 和 sample_id
            tid = td.get("task_id", "")
            if not tid:
                raise ManifestError("InferenceTask task_id 不能为空")
            if tid in task_ids:
                raise DuplicateIdError(f"InferenceTask task_id '{tid}' 重复")
            task_ids.add(tid)

            sid = td.get("sample_id", tid)
            if sid in sample_ids:
                raise DuplicateIdError(f"sample_id '{sid}' 重复")
            sample_ids.add(sid)

            # 校验 TaskSpec 引用
            tsr = td.get("task_spec_ref", "")
            if not tsr:
                raise ManifestError(f"task '{tid}' 的 task_spec_ref 不能为空")

            # 解析 asset_bindings
            bindings_raw = td.get("asset_bindings", [])
            if not bindings_raw:
                raise ManifestError(f"task '{tid}' 的 asset_bindings 不能为空")

            bindings: list[TaskAssetBinding] = []
            for b in bindings_raw:
                bref = b.get("asset_ref", "")
                if bref not in asset_ids:
                    raise MissingAssetError(
                        f"task '{tid}' 引用的 asset '{bref}' 不在 assets 中")
                bindings.append(TaskAssetBinding(**b))

            # Validate sequence_index per role
            from collections import defaultdict
            by_role: dict[str, list[int | None]] = defaultdict(list)
            for b in bindings_raw:
                role_str = b.get("role", "")
                seq = b.get("sequence_index")
                by_role[role_str].append(seq)

            for role_str, indices in by_role.items():
                non_none = [s for s in indices if s is not None]
                if len(non_none) == 0:
                    continue  # All None - OK for single-asset roles
                if len(non_none) > 1 and None in indices:
                    raise ManifestError(
                        f"role='{role_str}' in task '{tid}': multiple bindings with mixed None/non-None sequence_index")
                if len(non_none) > 1:
                    if len(set(non_none)) != len(non_none):
                        raise ManifestError(
                            f"role='{role_str}' in task '{tid}': duplicate sequence_index: {non_none}")
                    sorted_idx = sorted(non_none)
                    if sorted_idx[0] != 0:
                        raise ManifestError(
                            f"role='{role_str}' in task '{tid}': sequence_index must start from 0, got {sorted_idx[0]}")
                    expected = list(range(sorted_idx[0], sorted_idx[0] + len(sorted_idx)))
                    if sorted_idx != expected:
                        raise ManifestError(
                            f"role='{role_str}' in task '{tid}': sequence_index not continuous: {sorted_idx}, expected {expected}")

            tasks.append(InferenceTask(
                task_id=tid,
                sample_id=sid,
                task_order=td.get("task_order", len(tasks)),
                task_spec_ref=tsr,
                asset_bindings=bindings,
                idempotency_key=td.get("idempotency_key"),
            ))

        # 按 task_order 稳定排序
        tasks.sort(key=lambda t: (t.task_order, t.task_id))

        return assets, tasks

    def parse_manifest_batch(
        self, manifest_list: list[str | Path | dict]
    ) -> tuple[list[AssetRef], list[InferenceTask]]:
        """批量解析多个 manifest，稳定排序，ID 全局唯一。"""
        all_assets: list[AssetRef] = []
        all_tasks: list[InferenceTask] = []
        global_asset_ids: set[str] = set()
        global_task_ids: set[str] = set()
        global_sample_ids: set[str] = set()

        for m in manifest_list:
            assets, tasks = self.parse_manifest(m)

            for a in assets:
                if a.asset_id in global_asset_ids:
                    # Check content consistency across manifests
                    existing = next(x for x in all_assets if x.asset_id == a.asset_id)
                    if a.model_dump(mode="json") != existing.model_dump(mode="json"):
                        raise DuplicateIdError(
                            f"Asset ID '{a.asset_id}' 跨 manifest 内容不一致")
                    continue  # 去重
                global_asset_ids.add(a.asset_id)
                all_assets.append(a)

            for t in tasks:
                if t.task_id in global_task_ids:
                    raise DuplicateIdError(f"跨 manifest 重复 task_id: {t.task_id}")
                global_task_ids.add(t.task_id)
                if t.sample_id in global_sample_ids:
                    raise DuplicateIdError(f"跨 manifest 重复 sample_id: {t.sample_id}")
                global_sample_ids.add(t.sample_id)
                all_tasks.append(t)

        all_tasks.sort(key=lambda t: (t.task_order, t.task_id))
        return all_assets, all_tasks
