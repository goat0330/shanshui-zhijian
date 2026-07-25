"""
RS-01B-1 / B0 — SarMetadata + per-field MetadataSource

定义：
- MetadataSource: 逐字段的来源枚举
- SarMetadata: 完整 S1 元数据（逐字段 source 追踪）
- SarMetadataResolver: 按优先级（A→B→C→D→UNKNOWN）逐字段合并

优先级（逐字段合并，禁止一个来源覆盖所有字段）：
  A. AssetRef / manifest 显式结构化字段
  B. GeoTIFF tags
  C. Sidecar JSON
  D. URI / 文件名推断
  E. UNKNOWN（显式缺省标记）
"""

import enum
from datetime import datetime
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class MetadataSource(str, enum.Enum):
    """元数据来源优先级。"""
    ASSET_REF = "asset_ref"
    GEOTIFF_TAGS = "geotiff_tags"
    SIDECAR = "sidecar"
    INFERRED = "inferred"
    UNKNOWN = "unknown"

    @property
    def priority(self) -> int:
        return {"asset_ref": 0, "geotiff_tags": 1, "sidecar": 2, "inferred": 3, "unknown": 4}[self.value]

    def is_trusted(self) -> bool:
        return self in (MetadataSource.ASSET_REF, MetadataSource.GEOTIFF_TAGS)

    def is_verified(self) -> bool:
        return self in (MetadataSource.ASSET_REF, MetadataSource.GEOTIFF_TAGS, MetadataSource.SIDECAR)


class SarMetadata(BaseModel):
    """Sentinel-1 SAR 采集元数据，每个字段记录来源。"""

    platform: str = "UNKNOWN"
    product_type: str = "UNKNOWN"
    processing_level: str = "UNKNOWN"
    orbit_direction: str = "UNKNOWN"
    relative_orbit: int = -1
    polarizations: list[str] = ["UNKNOWN"]
    incidence_angle_min: float = -1.0
    incidence_angle_max: float = -1.0
    acquisition_time: str = ""

    # 逐字段来源
    source_platform: MetadataSource = MetadataSource.UNKNOWN
    source_product_type: MetadataSource = MetadataSource.UNKNOWN
    source_processing_level: MetadataSource = MetadataSource.UNKNOWN
    source_orbit_direction: MetadataSource = MetadataSource.UNKNOWN
    source_relative_orbit: MetadataSource = MetadataSource.UNKNOWN
    source_polarizations: MetadataSource = MetadataSource.UNKNOWN
    source_incidence_angle_min: MetadataSource = MetadataSource.UNKNOWN
    source_incidence_angle_max: MetadataSource = MetadataSource.UNKNOWN
    source_acquisition_time: MetadataSource = MetadataSource.UNKNOWN

    # 向后兼容
    source: str = "unknown"

    @property
    def incidence_angle_mid(self) -> float:
        if self.incidence_angle_min >= 0 and self.incidence_angle_max >= 0:
            return (self.incidence_angle_min + self.incidence_angle_max) / 2.0
        return -1.0

    @property
    def has_vh(self) -> bool:
        return "VH" in [p.upper() for p in self.polarizations]

    @property
    def has_vv(self) -> bool:
        return "VV" in [p.upper() for p in self.polarizations]

    def is_same_orbit(self, other: "SarMetadata") -> bool:
        return (self.orbit_direction == other.orbit_direction
                and self.relative_orbit == other.relative_orbit
                and self.relative_orbit >= 0)

    def is_polarization_compatible(self, other: "SarMetadata") -> bool:
        return (self.has_vv and other.has_vv) or (self.has_vh and other.has_vh)

    def get_field_source(self, field: str) -> MetadataSource:
        src_attr = f"source_{field}"
        if hasattr(self, src_attr):
            return getattr(self, src_attr)
        return MetadataSource.UNKNOWN

    def field_summary(self) -> dict[str, dict]:
        fields = ["platform", "product_type", "processing_level",
                  "orbit_direction", "relative_orbit", "polarizations",
                  "incidence_angle_min", "incidence_angle_max", "acquisition_time"]
        return {f: {"value": str(getattr(self, f, "")),
                    "source": self.get_field_source(f).value,
                    "verified": self.get_field_source(f).is_verified()}
                for f in fields}

    def missing_fields(self) -> list[str]:
        missing = []
        if self.orbit_direction == "UNKNOWN":
            missing.append("orbit_direction")
        if self.relative_orbit < 0:
            missing.append("relative_orbit")
        if not self.acquisition_time:
            missing.append("acquisition_time")
        if "UNKNOWN" in [p.upper() for p in self.polarizations]:
            missing.append("polarizations")
        return missing

    def inferred_fields(self) -> list[str]:
        return [f for f in ["platform", "product_type", "processing_level",
                            "orbit_direction", "relative_orbit", "polarizations",
                            "incidence_angle_min", "incidence_angle_max", "acquisition_time"]
                if self.get_field_source(f) == MetadataSource.INFERRED]

    def unknown_fields(self) -> list[str]:
        return [f for f in ["platform", "product_type", "processing_level",
                            "orbit_direction", "relative_orbit", "polarizations",
                            "incidence_angle_min", "incidence_angle_max", "acquisition_time"]
                if self.get_field_source(f) == MetadataSource.UNKNOWN]

    @classmethod
    def from_asset_ref(cls, asset_ref, uri: str = None) -> "SarMetadata":
        return SarMetadataResolver.resolve(asset_ref, uri)


# ── 辅助函数 ────────────────────────────────────────────────

def _polarizations_from_tags(tags: dict) -> list[str] | None:
    raw = tags.get("polarizations")
    if raw:
        return [p.strip().upper() for p in str(raw).split(",")]
    return None


def _parse_sidecar(uri: str) -> dict | None:
    if not uri:
        return None
    p = Path(uri)
    for sp in [p.with_suffix(p.suffix + ".meta.json"), p.parent / f"{p.stem}.meta.json"]:
        if sp.exists():
            import json
            with open(str(sp)) as f:
                return json.load(f)
    return None


def _guess_platform_from_uri(uri: str) -> str | None:
    uri_lower = uri.lower()
    if "s1a" in uri_lower or "sentinel-1a" in uri_lower:
        return "Sentinel-1A"
    if "s1b" in uri_lower or "sentinel-1b" in uri_lower:
        return "Sentinel-1B"
    return None


def _try_int(val, default=-1) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _try_float(val, default=-1.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _normalize_platform(raw: str) -> str:
    ru = raw.upper()
    if ru in ("A", "S1A", "SENTINEL-1A", "SENTINEL 1A"):
        return "Sentinel-1A"
    if ru in ("B", "S1B", "SENTINEL-1B", "SENTINEL 1B"):
        return "Sentinel-1B"
    return raw


def _try_extract_date_from_uri(uri: str) -> str | None:
    import re
    m = re.search(r'(\d{4})(\d{2})(\d{2})', Path(uri).stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00Z"
    return None


def _from_tags_or_unknown(val, default="UNKNOWN") -> str:
    if val and str(val).strip():
        return str(val).strip()
    return default


# ── SarMetadataResolver ───────────────────────────────────────

class SarMetadataResolver:
    """按优先级逐字段合并多种来源的 SAR 元数据。"""

    @staticmethod
    def resolve(asset_ref, uri: str = None) -> SarMetadata:
        actual_uri = uri or getattr(asset_ref, "uri", "")
        tags_data = SarMetadataResolver._read_geotiff_tags(actual_uri)
        sidecar_data = _parse_sidecar(actual_uri) if tags_data is None else None

        meta = SarMetadata()

        # Step A: AssetRef fields
        SarMetadataResolver._apply_asset_ref(meta, asset_ref)

        if tags_data:
            # Step B: GeoTIFF tags (overrides A)
            SarMetadataResolver._apply_tags(meta, tags_data)
        elif sidecar_data:
            # Step C: Sidecar (overrides A)
            SarMetadataResolver._apply_sidecar(meta, sidecar_data)
        else:
            # Step D: Inferred from URI
            SarMetadataResolver._apply_inferred(meta, actual_uri, asset_ref)

        meta.source = SarMetadataResolver._compute_overall_source(meta)
        return meta

    @staticmethod
    def _read_geotiff_tags(uri: str) -> dict | None:
        if not uri or not Path(uri).exists():
            return None
        try:
            import rasterio
            with rasterio.open(uri) as src:
                return dict(src.tags())
        except Exception:
            return None

    @staticmethod
    def _apply_asset_ref(meta: SarMetadata, asset_ref) -> None:
        if asset_ref is None:
            return

        # platform
        plat = getattr(asset_ref, "platform", None) or getattr(asset_ref, "sar_platform", None)
        if plat and str(plat).strip().upper() != "UNKNOWN":
            meta.platform = _normalize_platform(str(plat))
            meta.source_platform = MetadataSource.ASSET_REF

        # orbit_direction
        od = getattr(asset_ref, "orbit_direction", None)
        if od and str(od).strip().upper() in ("ASCENDING", "DESCENDING"):
            meta.orbit_direction = str(od).upper()
            meta.source_orbit_direction = MetadataSource.ASSET_REF

        # relative_orbit
        ro = getattr(asset_ref, "relative_orbit", None)
        if ro is not None and _try_int(ro) >= 0:
            meta.relative_orbit = _try_int(ro)
            meta.source_relative_orbit = MetadataSource.ASSET_REF

        # polarizations from bands
        bands = getattr(asset_ref, "bands", None)
        if bands and len(bands) > 0:
            pols = [b.upper() for b in bands if b.upper() in ("VV", "VH", "HH", "HV")]
            if pols:
                meta.polarizations = pols
                meta.source_polarizations = MetadataSource.ASSET_REF

        # acquisition_time
        acq = getattr(asset_ref, "acquisition_time", None)
        if acq and str(acq).strip():
            meta.acquisition_time = str(acq).strip()
            meta.source_acquisition_time = MetadataSource.ASSET_REF

        # incidence_angle
        inc_min = getattr(asset_ref, "incidence_angle_min", None)
        if inc_min is not None and _try_float(inc_min) >= 0:
            meta.incidence_angle_min = _try_float(inc_min)
            meta.source_incidence_angle_min = MetadataSource.ASSET_REF
        inc_max = getattr(asset_ref, "incidence_angle_max", None)
        if inc_max is not None and _try_float(inc_max) >= 0:
            meta.incidence_angle_max = _try_float(inc_max)
            meta.source_incidence_angle_max = MetadataSource.ASSET_REF

        # product_type / processing_level
        pt = getattr(asset_ref, "product_type", None)
        if pt and str(pt).strip():
            meta.product_type = str(pt).strip()
            meta.source_product_type = MetadataSource.ASSET_REF
        pl = getattr(asset_ref, "processing_level", None)
        if pl and str(pl).strip():
            meta.processing_level = str(pl).strip()
            meta.source_processing_level = MetadataSource.ASSET_REF

    @staticmethod
    def _apply_tags(meta: SarMetadata, tags: dict) -> None:
        # platform
        plat_raw = str(tags.get("platform", "")).upper()
        if plat_raw in ("A", "S1A", "SENTINEL-1A", "SENTINEL 1A"):
            meta.platform = "Sentinel-1A"; meta.source_platform = MetadataSource.GEOTIFF_TAGS
        elif plat_raw in ("B", "S1B", "SENTINEL-1B", "SENTINEL 1B"):
            meta.platform = "Sentinel-1B"; meta.source_platform = MetadataSource.GEOTIFF_TAGS
        elif "SENTINEL" in plat_raw:
            meta.platform = "Sentinel-1A"; meta.source_platform = MetadataSource.GEOTIFF_TAGS

        # product_type
        pt = _from_tags_or_unknown(tags.get("product_type"))
        if pt != "UNKNOWN":
            meta.product_type = pt; meta.source_product_type = MetadataSource.GEOTIFF_TAGS

        pl = _from_tags_or_unknown(tags.get("processing_level"))
        if pl != "UNKNOWN":
            meta.processing_level = pl; meta.source_processing_level = MetadataSource.GEOTIFF_TAGS

        od = str(tags.get("orbit_direction", "")).upper()
        if od in ("ASCENDING", "DESCENDING"):
            meta.orbit_direction = od; meta.source_orbit_direction = MetadataSource.GEOTIFF_TAGS

        ro = _try_int(tags.get("relative_orbit"))
        if ro >= 0:
            meta.relative_orbit = ro; meta.source_relative_orbit = MetadataSource.GEOTIFF_TAGS

        pols = _polarizations_from_tags(tags)
        if pols and "UNKNOWN" not in [p.upper() for p in pols]:
            meta.polarizations = pols; meta.source_polarizations = MetadataSource.GEOTIFF_TAGS

        inc_min = _try_float(tags.get("incidence_angle_min"))
        if inc_min >= 0:
            meta.incidence_angle_min = inc_min; meta.source_incidence_angle_min = MetadataSource.GEOTIFF_TAGS
        inc_max = _try_float(tags.get("incidence_angle_max"))
        if inc_max >= 0:
            meta.incidence_angle_max = inc_max; meta.source_incidence_angle_max = MetadataSource.GEOTIFF_TAGS

        acq = str(tags.get("acquisition_time", "")).strip()
        if acq:
            meta.acquisition_time = acq; meta.source_acquisition_time = MetadataSource.GEOTIFF_TAGS

    @staticmethod
    def _apply_sidecar(meta: SarMetadata, sidecar: dict) -> None:
        plat_raw = str(sidecar.get("platform", "")).upper()
        if plat_raw in ("A", "S1A", "SENTINEL-1A"):
            meta.platform = "Sentinel-1A"; meta.source_platform = MetadataSource.SIDECAR
        elif plat_raw in ("B", "S1B", "SENTINEL-1B"):
            meta.platform = "Sentinel-1B"; meta.source_platform = MetadataSource.SIDECAR

        pt = _from_tags_or_unknown(sidecar.get("product_type"))
        if pt != "UNKNOWN":
            meta.product_type = pt; meta.source_product_type = MetadataSource.SIDECAR
        pl = _from_tags_or_unknown(sidecar.get("processing_level"))
        if pl != "UNKNOWN":
            meta.processing_level = pl; meta.source_processing_level = MetadataSource.SIDECAR

        od = str(sidecar.get("orbit_direction", "")).upper()
        if od in ("ASCENDING", "DESCENDING"):
            meta.orbit_direction = od; meta.source_orbit_direction = MetadataSource.SIDECAR
        ro = _try_int(sidecar.get("relative_orbit"))
        if ro >= 0:
            meta.relative_orbit = ro; meta.source_relative_orbit = MetadataSource.SIDECAR

        pols_raw = sidecar.get("polarizations", sidecar.get("bands", ""))
        pols = []
        if isinstance(pols_raw, str):
            pols = [p.strip().upper() for p in pols_raw.split(",")]
        elif isinstance(pols_raw, list):
            pols = [p.upper() for p in pols_raw]
        if pols and "UNKNOWN" not in pols:
            meta.polarizations = pols; meta.source_polarizations = MetadataSource.SIDECAR

        inc_min = _try_float(sidecar.get("incidence_angle_min"))
        if inc_min >= 0:
            meta.incidence_angle_min = inc_min; meta.source_incidence_angle_min = MetadataSource.SIDECAR
        inc_max = _try_float(sidecar.get("incidence_angle_max"))
        if inc_max >= 0:
            meta.incidence_angle_max = inc_max; meta.source_incidence_angle_max = MetadataSource.SIDECAR

        acq = str(sidecar.get("acquisition_time", "")).strip()
        if acq:
            meta.acquisition_time = acq; meta.source_acquisition_time = MetadataSource.SIDECAR

    @staticmethod
    def _apply_inferred(meta: SarMetadata, uri: str, asset_ref) -> None:
        if meta.source_platform == MetadataSource.UNKNOWN:
            plat = _guess_platform_from_uri(uri)
            if plat:
                meta.platform = plat; meta.source_platform = MetadataSource.INFERRED

        if meta.source_polarizations == MetadataSource.UNKNOWN and asset_ref is not None:
            bands = getattr(asset_ref, "bands", None)
            if bands and len(bands) > 0:
                pols = [b.upper() for b in bands if b.upper() in ("VV", "VH", "HH", "HV")]
                if pols:
                    meta.polarizations = pols; meta.source_polarizations = MetadataSource.INFERRED

        if meta.source_product_type == MetadataSource.UNKNOWN and "GRD" in Path(uri).name.upper():
            meta.product_type = "GRD"; meta.source_product_type = MetadataSource.INFERRED

        if meta.source_acquisition_time == MetadataSource.UNKNOWN:
            acq = _try_extract_date_from_uri(uri)
            if acq:
                meta.acquisition_time = acq; meta.source_acquisition_time = MetadataSource.INFERRED

    @staticmethod
    def _compute_overall_source(meta: SarMetadata) -> str:
        sources = set()
        for f in ["platform", "product_type", "processing_level",
                  "orbit_direction", "relative_orbit", "polarizations",
                  "incidence_angle_min", "incidence_angle_max", "acquisition_time"]:
            s = meta.get_field_source(f)
            if s != MetadataSource.UNKNOWN:
                sources.add(s.value)
        if MetadataSource.ASSET_REF.value in sources:
            return "asset_ref"
        if MetadataSource.GEOTIFF_TAGS.value in sources:
            return "geotiff_tags"
        if MetadataSource.SIDECAR.value in sources:
            return "sidecar"
        if MetadataSource.INFERRED.value in sources:
            return "inferred"
        return "unknown"
