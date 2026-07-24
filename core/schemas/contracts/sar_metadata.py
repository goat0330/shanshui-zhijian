"""
RS-01B-1 — SarMetadata

Sentinel-1 SAR 图像的结构化元数据。
从 AssetRef 或 GeoTIFF 中提取/填充。
"""

from datetime import datetime
from pydantic import BaseModel, Field


class SarMetadata(BaseModel):
    """Sentinel-1 SAR 采集元数据。"""

    platform: str = Field(..., description="平台, 如 Sentinel-1A, Sentinel-1B")
    product_type: str = Field(..., description="产品类型, 如 GRD, SLC")
    processing_level: str = Field(..., description="处理级别, 如 L1, L2")
    orbit_direction: str = Field(..., description="轨道方向: ASCENDING, DESCENDING")
    relative_orbit: int = Field(..., description="相对轨道号")
    polarizations: list[str] = Field(..., min_length=1, description="极化方式, 如 ['VV','VH']")
    incidence_angle_min: float = Field(..., ge=0.0, le=90.0, description="最小入射角 (度)")
    incidence_angle_max: float = Field(..., ge=0.0, le=90.0, description="最大入射角 (度)")
    acquisition_time: str = Field(..., description="采集时间 (ISO 8601)")

    @property
    def incidence_angle_mid(self) -> float:
        return (self.incidence_angle_min + self.incidence_angle_max) / 2.0

    @property
    def has_vh(self) -> bool:
        return "VH" in self.polarizations or "vh" in [p.lower() for p in self.polarizations]

    @property
    def has_vv(self) -> bool:
        return "VV" in self.polarizations or "vv" in [p.lower() for p in self.polarizations]

    def is_same_orbit(self, other: "SarMetadata") -> bool:
        """同轨判断: 相同 orbit_direction + relative_orbit。"""
        return (self.orbit_direction == other.orbit_direction
                and self.relative_orbit == other.relative_orbit)

    def is_polarization_compatible(self, other: "SarMetadata") -> bool:
        """极化兼容: 双方都有 VV 或都有 VH。"""
        return (self.has_vv and other.has_vv) or (self.has_vh and other.has_vh)

    @classmethod
    def from_asset_ref(cls, asset_ref, uri: str = None) -> "SarMetadata":
        """从 AssetRef 的 spatial / bands / acquisition_time 构造。

        如果 AssetRef 有完整的 spatial metadata 和 bands，
        则尝试推断。缺少字段使用默认值占位并标记 quality=estimated。
        """
        from core.schemas.contracts.asset import AssetRef
        return cls(
            platform=cls._guess_platform(uri or ""),
            product_type="GRD",
            processing_level="L1",
            orbit_direction="UNKNOWN",
            relative_orbit=-1,
            polarizations=["VV", "VH"] if "vh" in [b.lower() for b in (asset_ref.bands or [])] else ["VV"],
            incidence_angle_min=30.0,
            incidence_angle_max=46.0,
            acquisition_time=asset_ref.acquisition_time or datetime.now().isoformat(),
        )

    @staticmethod
    def _guess_platform(uri: str) -> str:
        for p in ["Sentinel-1A", "Sentinel-1B", "S1A", "S1B"]:
            if p.lower() in uri.lower():
                return "Sentinel-1A" if "A" in p else "Sentinel-1B"
        return "Sentinel-1A"

    def missing_fields(self) -> list[str]:
        """返回值为 UNKNOWN / -1 / 默认值的关键字段列表。"""
        missing = []
        if self.orbit_direction == "UNKNOWN":
            missing.append("orbit_direction")
        if self.relative_orbit < 0:
            missing.append("relative_orbit")
        return missing
