"""
RS-00 — CompetitionInputAdapter

由 Manifest 或明确配置确定任务语义，不得通过文件名猜测。
Manifest 是一个 JSON 文件，描述 assets + inference_task。

输入: manifest 路径或 dict
输出: list[InferenceTask]
"""

import json
from pathlib import Path
from core.schemas.contracts.task import InferenceTask, TaskAssetBinding
from core.schemas.contracts.asset import AssetRef


class CompetitionInputAdapter:
    """比赛输入适配器。从 manifest 读取资产和任务描述。"""

    def __init__(self, manifest_root: str | Path | None = None):
        self.manifest_root = Path(manifest_root) if manifest_root else None

    def parse_manifest(self, manifest: str | Path | dict) -> tuple[list[AssetRef], list[InferenceTask]]:
        """
        解析 manifest → AssetRef[] + InferenceTask[]

        manifest 可以是:
        - dict: 直接使用
        - str/Path: 从文件读取
        """
        if isinstance(manifest, (str, Path)):
            path = Path(manifest)
            if not path.exists():
                raise FileNotFoundError(f"Manifest 文件不存在: {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = manifest

        # 解析 assets
        assets: list[AssetRef] = []
        for a in data.get("assets", []):
            assets.append(AssetRef(**a))

        # 解析 inference_task
        task_data = data.get("inference_task")
        if not task_data:
            raise ValueError("manifest 缺少 inference_task")

        bindings = [TaskAssetBinding(**b) for b in task_data.get("asset_bindings", [])]
        it = InferenceTask(
            task_id=task_data["task_id"],
            sample_id=task_data.get("sample_id", task_data["task_id"]),
            task_order=task_data.get("task_order", 0),
            task_spec_ref=task_data["task_spec_ref"],
            asset_bindings=bindings,
        )

        return assets, [it]

    def parse_manifest_batch(self, manifest_list: list[str | Path | dict]) -> tuple[list[AssetRef], list[InferenceTask]]:
        """批量解析多个 manifest。"""
        all_assets: list[AssetRef] = []
        all_tasks: list[InferenceTask] = []
        for m in manifest_list:
            assets, tasks = self.parse_manifest(m)
            all_assets.extend(assets)
            all_tasks.extend(tasks)
        return all_assets, all_tasks
