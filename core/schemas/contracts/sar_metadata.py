"""
RS-01B-1 / B0 — SarMetadata + per-field MetadataSource

定义：
- MetadataSource: 逐字段的来源枚举
- MetadataConflict: 来源冲突记录
- SarMetadata: 完整 S1 元数据（逐字段 source 追踪 + conflicts）
- SarMetadataResolver: 按优先级逐字段合并，绝不低覆高

优先级（逐字段独立，不允许多来源混合覆盖）：
  A. AssetRef / manifest 显式结构化字段 (priority=0)
  B. GeoTIFF tags (priority=1)
  C. Sidecar JSON (priority=2)
  D. URI / 文件名推断 (priority=3)
  E. UNKNOWN (priority=4)

规则：
- 高优先级来源设置后，低优先级来源不得覆盖该字段
- Tags存在但某字段缺失时，Sidecar继续补该字段
- 冲突值（来源不同且值不同）记录为Conflict，不静默覆盖
- Generic "Sentinel-1" 不自动变成 "Sentinel-1A"
- acquisition_time 不得使用当前时间伪造
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


class MetadataConflict(BaseModel):
    """两个来源对同一字段提供不同值时的冲突记录。"""
    field: str
    higher_priority_value: str
    lower_priority_value: str
    higher_priority_source: MetadataSource
    lower_priority_source: MetadataSource


# ── STRICT 门禁关键字段 ────────────────────────────────────────────
STRICT_FIELDS = frozenset({
    "orbit_direction",
    "relative_orbit",
    "polarizations",
    "acquisition_time",
})


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

    # 冲突记录
    conflicts: list[MetadataConflict] = Field(default_factory=list)

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

    def _get_field_value(self, field: str) -> Any:
        return getattr(self, field, None)

    def _set_field(self, field: str, value: Any, source: MetadataSource) -> None:
        setattr(self, field, value)
        setattr(self, f"source_{field}", source)

    def _try_apply(self, field: str, value: Any, source: MetadataSource) -> bool:
        """尝试应用一个字段值，遵循优先级。返回 True 如果应用成功。

        规则：
        - 新来源优先级 >= 当前来源 → 不覆盖
        - 新来源优先级 < 当前来源，且值不同 → 记录冲突，不覆盖
        - 当前来源为 UNKNOWN → 应用
        """
        current_source = self.get_field_source(field)
        if source.priority < current_source.priority:
            # 新来源优先级更高，应覆盖
            pass  # 继续应用
        elif source.priority == current_source.priority:
            # 同优先级不覆盖
            return False
        else:
            # 新来源优先级更低
            current_value = str(self._get_field_value(field))
            new_value_str = str(value)
            if current_source != MetadataSource.UNKNOWN and current_value != new_value_str:
                # 记录冲突
                self.conflicts.append(MetadataConflict(
                    field=field,
                    higher_priority_value=current_value,
                    lower_priority_value=new_value_str,
                    higher_priority_source=current_source,
                    lower_priority_source=source,
                ))
            return False

        self._set_field(field, value, source)
        return True

    def field_summary(self) -> dict[str, dict]:
        fields = ["platform", "product_type", "processing_level",
                  "orbit_direction", "relative_orbit", "polarizations",
                  "incidence_angle_min", "incidence_angle_max", "acquisition_time"]
        return {f: {"value": str(getattr(self, f, "")),
                    "source": self.get_field_source(f).value,
                    "verified": self.get_field_source(f).is_verified()}
                for f in fields}

    def missing_fields(self) -> list[str]:
        """返回值为 UNKNOWN/空/负的字段（兼容旧代码）。"""
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

    def strict_check(self) -> list[str]:
        """Strict 门禁检查。

        对 STRICT_FIELDS 内的关键字段：
        - 来源为 UNKNOWN → 拒绝
        - 来源为 INFERRED → 拒绝
        - 存在未解决的冲突 → 拒绝

        Warn 模式允许继续，但必须写入 QualityReport。
        """
        errors: list[str] = []
        for field in sorted(STRICT_FIELDS):
            source = self.get_field_source(field)
            if source == MetadataSource.UNKNOWN:
                errors.append(f"strict: {field} 来源为 UNKNOWN，拒绝")
            elif source == MetadataSource.INFERRED:
                errors.append(f"strict: {field} 来源为 INFERRED，拒绝")
        for conflict in self.conflicts:
            if conflict.field in STRICT_FIELDS:
                errors.append(
                    f"strict: {conflict.field} 存在未解决的来源冲突 "
                    f"({conflict.higher_priority_source.value} vs {conflict.lower_priority_source.value})"
                )
        return errors

    def strict_report(self) -> dict:
        """返回包含 strict 检查结果的详细报告。"""
        errors = self.strict_check()
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": [
                f"{f} 来源={self.get_field_source(f).value}"
                for f in sorted(STRICT_FIELDS)
                if self.get_field_source(f) in (MetadataSource.INFERRED, MetadataSource.UNKNOWN)
            ],
            "conflict_count": len(self.conflicts),
            "missing_fields": self.missing_fields(),
            "inferred_fields": self.inferred_fields(),
        }

    @classmethod
    def from_asset_ref(cls, asset_ref, uri: str | None = None) -> "SarMetadata":
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
    # 保持原样——不假设 Generic "Sentinel" 是 S1A
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


# ── 来源优先级常量 ──────────────────────────────────────────────────
_PRIORITY_SOURCES = [
    MetadataSource.ASSET_REF,
    MetadataSource.GEOTIFF_TAGS,
    MetadataSource.SIDECAR,
    MetadataSource.INFERRED,
]


# ── SarMetadataResolver ───────────────────────────────────────

class SarMetadataResolver:
    """按优先级逐字段合并多种来源的 SAR 元数据。

    核心原则：
    1. 读取所有可用来源（AssetRef, Tags, Sidecar）各自独立提取
    2. 按优先级逐字段应用，高优先级来源设置后，低来源不得覆盖
    3. 低来源的值与高来源冲突时记录 Conflict，不静默覆盖
    4. Generic "Sentinel-1" 不自动变成 "Sentinel-1A"
    """

    @staticmethod
    def resolve(asset_ref, uri: str | None = None) -> SarMetadata:
        actual_uri = uri or getattr(asset_ref, "uri", "")
        tags_data = SarMetadataResolver._read_geotiff_tags(actual_uri)
        sidecar_data = _parse_sidecar(actual_uri)

        meta = SarMetadata()

        # Phase A: AssetRef (优先级 0)
        SarMetadataResolver._apply_asset_ref(meta, asset_ref)

        # Phase B: GeoTIFF Tags (优先级 1) — 只在当前来源优先级更低时覆盖
        if tags_data:
            SarMetadataResolver._apply_tags_per_field(meta, tags_data)

        # Phase C: Sidecar (优先级 2) — 只在当前来源更低时覆盖
        if sidecar_data:
            SarMetadataResolver._apply_sidecar_per_field(meta, sidecar_data)

        # Phase D: URI Inferred (优先级 3) — 只在当前 UNKNOWN 时填充
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

    # ── AssetRef（优先级 A）────────────────────────────────────

    @staticmethod
    def _apply_asset_ref(meta: SarMetadata, asset_ref) -> None:
        """应用 AssetRef 来源的字段（优先级最高）。"""
        if asset_ref is None:
            return

        # platform
        plat = getattr(asset_ref, "platform", None) or getattr(asset_ref, "sar_platform", None)
        if plat and str(plat).strip().upper() != "UNKNOWN":
            meta._set_field("platform", _normalize_platform(str(plat)), MetadataSource.ASSET_REF)

        # orbit_direction
        od = getattr(asset_ref, "orbit_direction", None)
        if od and str(od).strip().upper() in ("ASCENDING", "DESCENDING"):
            meta._set_field("orbit_direction", str(od).upper(), MetadataSource.ASSET_REF)

        # relative_orbit
        ro = getattr(asset_ref, "relative_orbit", None)
        if ro is not None and _try_int(ro) >= 0:
            meta._set_field("relative_orbit", _try_int(ro), MetadataSource.ASSET_REF)

        # polarizations from bands
        bands = getattr(asset_ref, "bands", None)
        if bands:
            pols = [b.upper() for b in bands if b.upper() in ("VV", "VH", "HH", "HV")]
            if pols:
                meta._set_field("polarizations", pols, MetadataSource.ASSET_REF)

        # acquisition_time
        acq = getattr(asset_ref, "acquisition_time", None)
        if acq and str(acq).strip():
            meta._set_field("acquisition_time", str(acq).strip(), MetadataSource.ASSET_REF)

        # incidence_angle
        inc_min = getattr(asset_ref, "incidence_angle_min", None)
        if inc_min is not None and _try_float(inc_min) >= 0:
            meta._set_field("incidence_angle_min", _try_float(inc_min), MetadataSource.ASSET_REF)
        inc_max = getattr(asset_ref, "incidence_angle_max", None)
        if inc_max is not None and _try_float(inc_max) >= 0:
            meta._set_field("incidence_angle_max", _try_float(inc_max), MetadataSource.ASSET_REF)

        # product_type / processing_level
        pt = getattr(asset_ref, "product_type", None)
        if pt and str(pt).strip():
            meta._set_field("product_type", str(pt).strip(), MetadataSource.ASSET_REF)
        pl = getattr(asset_ref, "processing_level", None)
        if pl and str(pl).strip():
            meta._set_field("processing_level", str(pl).strip(), MetadataSource.ASSET_REF)

    # ── GeoTIFF Tags（优先级 B）───────────────────────────────

    @staticmethod
    def _try_set_from_tags(meta: SarMetadata, field: str, source_fn) -> None:
        """尝试从 tags 设置一个字段（只在不低于当前优先级时）。"""
        tag_val = source_fn()
        if tag_val is not None:
            meta._try_apply(field, tag_val, MetadataSource.GEOTIFF_TAGS)

    @staticmethod
    def _apply_tags_per_field(meta: SarMetadata, tags: dict) -> None:
        """逐字段应用 GeoTIFF Tags，尊重已有的高优先级来源。"""

        def _tag_platform():
            plat_raw = str(tags.get("platform", "")).upper()
            if plat_raw in ("A", "S1A", "SENTINEL-1A", "SENTINEL 1A"):
                return "Sentinel-1A"
            if plat_raw in ("B", "S1B", "SENTINEL-1B", "SENTINEL 1B"):
                return "Sentinel-1B"
            if "SENTINEL" in plat_raw:
                # Generic "Sentinel-1" → 保持为 "Sentinel-1"，不自动变成 S1A
                raw_val = str(tags.get("platform", "")).strip()
                if raw_val:
                    return raw_val  # 保持原始值
            return None

        def _tag_product_type():
            pt = _from_tags_or_unknown(tags.get("product_type"))
            return pt if pt != "UNKNOWN" else None

        def _tag_processing_level():
            pl = _from_tags_or_unknown(tags.get("processing_level"))
            return pl if pl != "UNKNOWN" else None

        def _tag_orbit_direction():
            od = str(tags.get("orbit_direction", "")).upper()
            return od if od in ("ASCENDING", "DESCENDING") else None

        def _tag_relative_orbit():
            ro = _try_int(tags.get("relative_orbit"))
            return ro if ro >= 0 else None

        def _tag_polarizations():
            pols = _polarizations_from_tags(tags)
            return pols if pols and "UNKNOWN" not in [p.upper() for p in pols] else None

        def _tag_inc_min():
            inc = _try_float(tags.get("incidence_angle_min"))
            return inc if inc >= 0 else None

        def _tag_inc_max():
            inc = _try_float(tags.get("incidence_angle_max"))
            return inc if inc >= 0 else None

        def _tag_acq_time():
            acq = str(tags.get("acquisition_time", "")).strip()
            return acq if acq else None

        SarMetadataResolver._try_set_from_tags(meta, "platform", _tag_platform)
        SarMetadataResolver._try_set_from_tags(meta, "product_type", _tag_product_type)
        SarMetadataResolver._try_set_from_tags(meta, "processing_level", _tag_processing_level)
        SarMetadataResolver._try_set_from_tags(meta, "orbit_direction", _tag_orbit_direction)
        SarMetadataResolver._try_set_from_tags(meta, "relative_orbit", _tag_relative_orbit)
        SarMetadataResolver._try_set_from_tags(meta, "polarizations", _tag_polarizations)
        SarMetadataResolver._try_set_from_tags(meta, "incidence_angle_min", _tag_inc_min)
        SarMetadataResolver._try_set_from_tags(meta, "incidence_angle_max", _tag_inc_max)
        SarMetadataResolver._try_set_from_tags(meta, "acquisition_time", _tag_acq_time)

    # ── Sidecar（优先级 C）─────────────────────────────────────

    @staticmethod
    def _try_set_from_sidecar(meta: SarMetadata, field: str, source_fn) -> None:
        val = source_fn()
        if val is not None:
            meta._try_apply(field, val, MetadataSource.SIDECAR)

    @staticmethod
    def _apply_sidecar_per_field(meta: SarMetadata, sidecar: dict) -> None:
        """逐字段应用 Sidecar，尊重已有的高优先级来源。"""

        def _sc_platform():
            pr = str(sidecar.get("platform", "")).upper()
            if pr in ("A", "S1A", "SENTINEL-1A"):
                return "Sentinel-1A"
            if pr in ("B", "S1B", "SENTINEL-1B"):
                return "Sentinel-1B"
            rv = str(sidecar.get("platform", "")).strip()
            return rv if rv else None

        def _sc_product_type():
            pt = _from_tags_or_unknown(sidecar.get("product_type"))
            return pt if pt != "UNKNOWN" else None

        def _sc_processing_level():
            pl = _from_tags_or_unknown(sidecar.get("processing_level"))
            return pl if pl != "UNKNOWN" else None

        def _sc_orbit_direction():
            od = str(sidecar.get("orbit_direction", "")).upper()
            return od if od in ("ASCENDING", "DESCENDING") else None

        def _sc_relative_orbit():
            ro = _try_int(sidecar.get("relative_orbit"))
            return ro if ro >= 0 else None

        def _sc_polarizations():
            pols_raw = sidecar.get("polarizations", sidecar.get("bands", ""))
            pols = []
            if isinstance(pols_raw, str):
                pols = [p.strip().upper() for p in pols_raw.split(",")]
            elif isinstance(pols_raw, list):
                pols = [p.upper() for p in pols_raw]
            return pols if pols and "UNKNOWN" not in pols else None

        def _sc_inc_min():
            inc = _try_float(sidecar.get("incidence_angle_min"))
            return inc if inc >= 0 else None

        def _sc_inc_max():
            inc = _try_float(sidecar.get("incidence_angle_max"))
            return inc if inc >= 0 else None

        def _sc_acq_time():
            acq = str(sidecar.get("acquisition_time", "")).strip()
            return acq if acq else None

        SarMetadataResolver._try_set_from_sidecar(meta, "platform", _sc_platform)
        SarMetadataResolver._try_set_from_sidecar(meta, "product_type", _sc_product_type)
        SarMetadataResolver._try_set_from_sidecar(meta, "processing_level", _sc_processing_level)
        SarMetadataResolver._try_set_from_sidecar(meta, "orbit_direction", _sc_orbit_direction)
        SarMetadataResolver._try_set_from_sidecar(meta, "relative_orbit", _sc_relative_orbit)
        SarMetadataResolver._try_set_from_sidecar(meta, "polarizations", _sc_polarizations)
        SarMetadataResolver._try_set_from_sidecar(meta, "incidence_angle_min", _sc_inc_min)
        SarMetadataResolver._try_set_from_sidecar(meta, "incidence_angle_max", _sc_inc_max)
        SarMetadataResolver._try_set_from_sidecar(meta, "acquisition_time", _sc_acq_time)

    # ── URI 推断（优先级 D）────────────────────────────────────

    @staticmethod
    def _apply_inferred(meta: SarMetadata, uri: str, asset_ref) -> None:
        """URI 推断——只在当前字段为 UNKNOWN 时填充。"""
        if meta.get_field_source("platform") == MetadataSource.UNKNOWN:
            plat = _guess_platform_from_uri(uri)
            if plat:
                meta._set_field("platform", plat, MetadataSource.INFERRED)

        if meta.get_field_source("polarizations") == MetadataSource.UNKNOWN and asset_ref is not None:
            bands = getattr(asset_ref, "bands", None)
            if bands:
                pols = [b.upper() for b in bands if b.upper() in ("VV", "VH", "HH", "HV")]
                if pols:
                    meta._set_field("polarizations", pols, MetadataSource.INFERRED)

        if meta.get_field_source("product_type") == MetadataSource.UNKNOWN and "GRD" in Path(uri).name.upper():
            meta._set_field("product_type", "GRD", MetadataSource.INFERRED)

        if meta.get_field_source("acquisition_time") == MetadataSource.UNKNOWN:
            acq = _try_extract_date_from_uri(uri)
            if acq:
                meta._set_field("acquisition_time", acq, MetadataSource.INFERRED)

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
