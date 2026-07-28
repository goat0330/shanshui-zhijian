"""
RS-00 契约 — AssetRef + SpatialMetadata

AssetRef 只描述资产固有属性，不携带任务角色。
角色由 TaskAssetBinding 表达。
"""

from typing import Any
from pydantic import BaseModel, Field, field_validator
from . import Modality, SpatialReliability


class SpatialMetadata(BaseModel):
    """资产的空间元数据"""
    reliability: SpatialReliability
    crs: str | None = Field(None, description="CRS，如 EPSG:4326")
    transform: list[float] | None = Field(None, description="仿射变换 [a, b, c, d, e, f]", min_length=6, max_length=6)
    bounds: list[float] | None = Field(None, description="外包框 [xmin, ymin, xmax, ymax]", min_length=4, max_length=4)
    width: int | None = Field(None, ge=0)
    height: int | None = Field(None, ge=0)

    @field_validator("crs")
    @classmethod
    def crs_must_be_epsg(cls, v: str | None) -> str | None:
        if v and not v.upper().startswith("EPSG:"):
            raise ValueError(f"CRS 必须使用 EPSG: 格式，收到: {v}")
        return v.upper() if v else v


class AssetRef(BaseModel):
    """输入资产的轻量引用。不携带任务角色（角色在 TaskAssetBinding 中）。"""
    asset_id: str = Field(..., min_length=1, description="资产稳定 ID")
    uri: str = Field(..., min_length=1, description="文件路径或 URL")
    media_type: str = Field(..., description="媒体类型，如 image/tiff; application=geotiff")
    modality: Modality
    spatial: SpatialMetadata | None = None
    bands: list[str] | None = Field(None, description="波段名称列表")
    acquisition_time: str | None = Field(None, description="RFC 3339 采集时间")
    checksum: str | None = Field(None, description="SHA-256")
