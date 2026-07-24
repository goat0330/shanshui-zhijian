"""
RS-01B-1 — SarQualityValidator

SAR 双时相输入质量计算与校验。
不改变变化检测算法，只做输入门禁。
"""

import numpy as np
from dataclasses import dataclass
from typing import Any

from core.schemas.contracts.perception import QualityReport
from core.schemas.contracts.sar_metadata import SarMetadata
from core.schemas.contracts.validation_policy import (
    SarValidationPolicy, PolicyMode,
    MissingOrbitMetadata, MissingRequiredBand,
)


@dataclass
class ValidationResult:
    """校验结果：通过/拒绝/警告。"""
    passed: bool
    quality: QualityReport
    rejection_reason: str | None = None

    @property
    def rejected(self) -> bool:
        return not self.passed


def compute_input_quality(
    arr_t1: np.ndarray,    # (bands, H, W)
    arr_t2: np.ndarray,    # (bands, H, W)
    bands_t1: list[str],
    bands_t2: list[str],
    nodata: float = -9999.0,
) -> dict[str, float]:
    """计算双时相输入质量指标。

    Returns:
        dict with: valid_pixel_ratio, nodata_ratio, finite_pixel_ratio,
                   spatial_overlap_ratio, constant_pixel_ratio,
                   vv_dynamic_range, vh_dynamic_range
    """
    # 只比较共有的波段
    common = [b for b in bands_t1 if b in bands_t2]
    if not common:
        return {
            "valid_pixel_ratio": 0.0, "nodata_ratio": 1.0,
            "finite_pixel_ratio": 0.0, "spatial_overlap_ratio": 1.0,
            "constant_pixel_ratio": 1.0,
        }

    idx_t1 = [bands_t1.index(b) for b in common]
    idx_t2 = [bands_t2.index(b) for b in common]

    data_t1 = arr_t1[idx_t1].reshape(len(common), -1)  # (bands, N)
    data_t2 = arr_t2[idx_t2].reshape(len(common), -1)

    # 有效像元 (非 nodata)
    valid_t1 = ~np.isclose(data_t1, nodata, atol=1e-3)
    valid_t2 = ~np.isclose(data_t2, nodata, atol=1e-3)
    valid_both = valid_t1 & valid_t2
    valid_pixel_ratio = float(np.mean(valid_both))

    nodata_ratio = 1.0 - float(np.mean(valid_t1 & valid_t2))

    # 有限值比
    finite_t1 = np.isfinite(data_t1) & ~np.isclose(data_t1, nodata, atol=1e-3)
    finite_t2 = np.isfinite(data_t2) & ~np.isclose(data_t2, nodata, atol=1e-3)
    finite_pixel_ratio = float(np.mean(finite_t1 & finite_t2))

    # 空间重叠: 两个时相都有效的区域
    spatial_overlap_ratio = valid_pixel_ratio  # trivial: same grid

    # 常量像素: 所有波段标准差为 0
    valid_mask = valid_both.all(axis=0)
    if valid_mask.sum() > 0:
        valid_data = data_t1[:, valid_mask]
        band_stds = np.std(valid_data, axis=1)
        is_constant = band_stds < 1e-6
        constant_pixel_ratio = float(np.mean(is_constant)) if len(is_constant) > 0 else 0.0
    else:
        constant_pixel_ratio = 1.0

    # VV/VH 动态范围
    vv_range = None
    vh_range = None
    vv_valid = valid_both[0]  # first band is VV
    if vv_valid.sum() > 0:
        vv_vals = data_t1[0, vv_valid]
        vv_range = (float(np.min(vv_vals)), float(np.max(vv_vals)))
    if "vh" in [b.lower() for b in common]:
        vh_idx = [i for i, b in enumerate(common) if b.lower() == "vh"][0]
        vh_valid = valid_both[vh_idx]
        if vh_valid.sum() > 0:
            vh_vals = data_t1[vh_idx, vh_valid]
            vh_range = (float(np.min(vh_vals)), float(np.max(vh_vals)))

    return {
        "valid_pixel_ratio": valid_pixel_ratio,
        "nodata_ratio": nodata_ratio,
        "finite_pixel_ratio": finite_pixel_ratio,
        "spatial_overlap_ratio": spatial_overlap_ratio,
        "constant_pixel_ratio": constant_pixel_ratio,
        "vv_dynamic_range": vv_range,
        "vh_dynamic_range": vh_range,
    }


def validate_sar_input(
    meta_before: SarMetadata,
    meta_after: SarMetadata,
    bands_before: list[str],
    bands_after: list[str],
    quality_metrics: dict[str, Any],
    policy: SarValidationPolicy,
    width_t1: int, height_t1: int,
    width_t2: int, height_t2: int,
) -> ValidationResult:
    """校验 SAR 双时相输入。

    Args:
        meta_before, meta_after: SAR 元数据
        bands_before, bands_after: 实际波段名
        quality_metrics: compute_input_quality 的输出
        policy: 验证策略
        width_t1, height_t1: T1 尺寸
        width_t2, height_t2: T2 尺寸

    Returns:
        ValidationResult
    """
    # trust 模式直接放行
    if policy.mode == PolicyMode.TRUST:
        qr = QualityReport(valid_pixel_ratio=1.0)
        return ValidationResult(passed=True, quality=qr)

    reasons: list[str] = []
    warnings: list[str] = []
    reject = False
    rejection_reason = None

    orbit_match = meta_before.is_same_orbit(meta_after)
    pol_compat = meta_before.is_polarization_compatible(meta_after)
    res_compat = (width_t1, height_t1) == (width_t2, height_t2)

    # --- 轨道 ---
    missing_meta = meta_before.missing_fields() or meta_after.missing_fields()
    if missing_meta:
        if policy.missing_orbit_metadata == MissingOrbitMetadata.REJECT:
            reasons.append(f"缺失轨道元数据: {missing_meta}")
            reject = True
            rejection_reason = f"missing_metadata: {missing_meta}"
        elif policy.missing_orbit_metadata == MissingOrbitMetadata.WARN:
            warnings.append(f"缺失轨道元数据 (warn): {missing_meta}")
        else:
            warnings.append(f"缺失轨道元数据 (ignored): {missing_meta}")

    if not reject and policy.orbit_direction_policy.value == "same" and meta_before.orbit_direction != "UNKNOWN":
        if meta_before.orbit_direction != meta_after.orbit_direction:
            reasons.append(f"轨道方向不一致: {meta_before.orbit_direction} vs {meta_after.orbit_direction}")
            reject = True
            rejection_reason = rejection_reason or "orbit_direction_mismatch"

    if not reject and policy.orbit_policy.value == "same" and meta_before.relative_orbit > 0:
        if meta_before.relative_orbit != meta_after.relative_orbit:
            reasons.append(f"相对轨道不一致: {meta_before.relative_orbit} vs {meta_after.relative_orbit}")
            reject = True
            rejection_reason = rejection_reason or "orbit_mismatch"

    # --- 极化 ---
    missing_pols = [p for p in policy.required_polarizations
                    if not any(p.lower() in b.lower() for b in bands_before + bands_after)]
    if missing_pols:
        if policy.missing_required_band == MissingRequiredBand.REJECT:
            reasons.append(f"缺失必需极化: {missing_pols}")
            reject = True
            rejection_reason = rejection_reason or f"missing_polarization: {missing_pols}"
        else:
            warnings.append(f"缺失必需极化 (warn): {missing_pols}")

    # --- 空间重叠 ---
    if quality_metrics.get("valid_pixel_ratio", 0.0) < policy.minimum_valid_pixel_ratio:
        reasons.append(f"有效像元比不足: {quality_metrics['valid_pixel_ratio']:.3f} < {policy.minimum_valid_pixel_ratio}")
        reject = True
        rejection_reason = rejection_reason or "low_valid_pixel_ratio"

    if quality_metrics.get("spatial_overlap_ratio", 0.0) < policy.minimum_spatial_overlap_ratio:
        reasons.append(f"空间重叠比不足: {quality_metrics['spatial_overlap_ratio']:.3f} < {policy.minimum_spatial_overlap_ratio}")
        reject = True
        rejection_reason = rejection_reason or "low_spatial_overlap"

    # --- 分辨率 ---
    if not res_compat:
        warnings.append(f"分辨率不兼容: T1=({width_t1},{height_t1}), T2=({width_t2},{height_t2})")

    # --- 决定 ---
    if reject and policy.rejects_on():
        qr = QualityReport(
            valid_pixel_ratio=quality_metrics.get("valid_pixel_ratio", 0.0),
            nodata_ratio=quality_metrics.get("nodata_ratio", 0.0),
            finite_pixel_ratio=quality_metrics.get("finite_pixel_ratio", 0.0),
            spatial_overlap_ratio=quality_metrics.get("spatial_overlap_ratio", 0.0),
            constant_pixel_ratio=quality_metrics.get("constant_pixel_ratio", 0.0),
            vv_dynamic_range=quality_metrics.get("vv_dynamic_range"),
            vh_dynamic_range=quality_metrics.get("vh_dynamic_range"),
            orbit_match=orbit_match,
            polarization_compatible=pol_compat,
            resolution_compatible=res_compat,
            rejection_reason=rejection_reason,
            recommendations=warnings,
            reasons=reasons,
        )
        return ValidationResult(passed=False, quality=qr, rejection_reason=rejection_reason)

    # warn 模式: 不拒绝但记录
    if not reject and policy.mode == PolicyMode.WARN and warnings:
        reasons = warnings[:]  # 降级为原因
    else:
        reasons = reasons or warnings

    qr = QualityReport(
        valid_pixel_ratio=quality_metrics.get("valid_pixel_ratio", 0.0),
        nodata_ratio=quality_metrics.get("nodata_ratio", 0.0),
        finite_pixel_ratio=quality_metrics.get("finite_pixel_ratio", 0.0),
        spatial_overlap_ratio=quality_metrics.get("spatial_overlap_ratio", 0.0),
        constant_pixel_ratio=quality_metrics.get("constant_pixel_ratio", 0.0),
        vv_dynamic_range=quality_metrics.get("vv_dynamic_range"),
        vh_dynamic_range=quality_metrics.get("vh_dynamic_range"),
        orbit_match=orbit_match,
        polarization_compatible=pol_compat,
        resolution_compatible=res_compat,
        rejection_reason=None,
        recommendations=warnings,
        reasons=reasons,
    )
    return ValidationResult(passed=True, quality=qr)
