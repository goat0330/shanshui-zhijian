"""
RS-00 契约 — TaskAssetBinding + InputSlotSpec + TaskSpec + InferenceTask + RunContext
"""

import hashlib
from typing import Any
from pydantic import BaseModel, Field, field_validator
from . import AssetRole, Modality, TaskType


class TaskAssetBinding(BaseModel):
    """将 AssetRef 与任务中的语义角色绑定。"""
    asset_ref: str = Field(..., min_length=1, description="引用 AssetRef 的 asset_id")
    role: AssetRole
    sequence_index: int | None = Field(None, ge=0, description="同角色顺序索引（多时相标记）")


class InputSlotSpec(BaseModel):
    """描述一个输入槽位的约束。"""
    role: AssetRole
    modalities: list[Modality] = Field(..., min_length=1, description="允许的 modality 列表")
    min_items: int = Field(1, ge=0)
    max_items: int = Field(1, ge=0)

    @field_validator("max_items")
    @classmethod
    def max_gte_min(cls, v: int, info: Any) -> int:
        min_val = info.data.get("min_items", 1)
        if v != 0 and v < min_val:
            raise ValueError(f"max_items ({v}) 必须 >= min_items ({min_val})，或为 0（不限）")
        return v


class TaskSpec(BaseModel):
    """一类任务的规则定义。不携带具体资产，不携带工具参数。"""
    schema_version: str = Field("rs-contract.v0.3", pattern=r"^rs-contract\.v[\d.]+$")
    task_spec_id: str = Field(..., min_length=1, description="规则 ID，如 sar-temporal-change-v1")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="语义版本")
    task_type: TaskType
    task_fingerprint: str = Field("", description="task_spec_id + version 的 sha256 前缀，可在 __init__ 后手动计算")
    input_slots: list[InputSlotSpec] = Field(..., min_length=1)
    output_contract: dict = Field(default_factory=dict)
    validation_policy: dict = Field(default_factory=dict)

    def compute_fingerprint(self) -> str:
        raw = f"{self.task_spec_id}@{self.version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class InferenceTask(BaseModel):
    """比赛评测链的输入单元。携带具体样本上下文和资产绑定。"""
    schema_version: str = Field("rs-contract.v0.3", pattern=r"^rs-contract\.v[\d.]+$")
    task_id: str = Field(..., min_length=1, description="系统内任务 ID")
    sample_id: str = Field(..., min_length=1, description="样本标识")
    task_order: int = Field(..., ge=0, description="内部顺序，从 0 开始；提交时由 Exporter 映射")
    task_spec_ref: str = Field(..., min_length=1, description="引用 TaskSpec，如 sar-temporal-change-v1@1.0.0")
    asset_bindings: list[TaskAssetBinding] = Field(..., min_length=1)
    idempotency_key: str | None = None


class RunContext(BaseModel):
    """工具运行时的配置、版本和输出目录。"""
    schema_version: str = Field("rs-contract.v0.3", pattern=r"^rs-contract\.v[\d.]+$")
    run_id: str = Field(..., min_length=1)
    run_fingerprint: str = Field("", description="tool_config + model_version 的 sha256 前缀，可在 __init__ 后手动计算")
    tool_config: dict = Field(default_factory=dict, description="工具参数，如 Otsu 网格/最小面积/滤波器")
    model_version: str | None = None
    output_dir: str | None = None

    def compute_fingerprint(self) -> str:
        raw = str(self.tool_config) + str(self.model_version or "")
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
