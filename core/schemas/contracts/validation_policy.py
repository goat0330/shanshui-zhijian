"""
RS-01B-1 — SarValidationPolicy

任务规格中的 SAR 验证策略定义。
用于 TaskSpec.validation_policy 字段。
"""

from enum import Enum
from pydantic import BaseModel, Field


class PolicyMode(str, Enum):
    STRICT = "strict"
    WARN = "warn"
    TRUST = "trust_preprocessed_input"


class OrbitPolicy(str, Enum):
    SAME = "same"
    ALLOW_CROSS = "allow_cross"


class OrbitDirectionPolicy(str, Enum):
    SAME = "same"
    ALLOW_ANY = "allow_any"


class MissingOrbitMetadata(str, Enum):
    REJECT = "reject"
    WARN = "warn"
    IGNORE = "ignore"


class RegistrationPolicy(str, Enum):
    CHECK = "check"
    IGNORE = "ignore"


class MissingRequiredBand(str, Enum):
    REJECT = "reject"
    WARN = "warn"


class SarValidationPolicy(BaseModel):
    """SAR 时相变化检测的验证策略。

    用于 TaskSpec.validation_policy。
    """

    mode: PolicyMode = Field(PolicyMode.STRICT, description="验证模式: strict / warn / trust")

    # 轨道
    orbit_policy: OrbitPolicy = Field(OrbitPolicy.SAME, description="同轨/允许跨轨")
    orbit_direction_policy: OrbitDirectionPolicy = Field(OrbitDirectionPolicy.SAME, description="同轨方向/任意")
    missing_orbit_metadata: MissingOrbitMetadata = Field(MissingOrbitMetadata.REJECT, description="缺失轨道元数据时行为")

    # 极化
    required_polarizations: list[str] = Field(default_factory=lambda: ["VV", "VH"], description="必需极化")
    incidence_angle_tolerance_deg: float = Field(5.0, ge=0.0, description="入射角容差 (度)")

    # 空间
    minimum_spatial_overlap_ratio: float = Field(0.5, ge=0.0, le=1.0, description="最小空间重叠比")
    minimum_valid_pixel_ratio: float = Field(0.1, ge=0.0, le=1.0, description="最小有效像元比")

    # 配准
    registration_policy: RegistrationPolicy = Field(RegistrationPolicy.CHECK, description="配准检查策略")

    # 波段
    missing_required_band: MissingRequiredBand = Field(MissingRequiredBand.REJECT, description="缺失必需波段时行为")

    def allows_rejection(self) -> bool:
        return self.mode in (PolicyMode.STRICT, PolicyMode.WARN)

    def rejects_on(self) -> bool:
        return self.mode == PolicyMode.STRICT

    @classmethod
    def default_strict(cls) -> "SarValidationPolicy":
        return cls(mode=PolicyMode.STRICT)

    @classmethod
    def default_warn(cls) -> "SarValidationPolicy":
        return cls(mode=PolicyMode.WARN)

    @classmethod
    def trust_only(cls) -> "SarValidationPolicy":
        """trust_preprocessed_input: 不做输入验证，直接运行。"""
        return cls(mode=PolicyMode.TRUST)
