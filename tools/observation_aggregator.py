"""
RS-03 — ObservationAggregator（最小实现）

将 list[Observation] 聚合为 DetectionCandidate。

填补 CONTRACT_GAPS.md 中的缺口 1（聚合引擎缺失）。
"""

import statistics
from typing import Any

from core.schemas.contracts.perception import Observation
from core.schemas.contracts.candidate import (
    DetectionCandidate,
    CandidateQualitySummary,
)


class ObservationAggregator:
    """将 list[Observation] 聚合为 DetectionCandidate（最小实现）。"""

    VERSION = "rc-02-v1"

    @staticmethod
    def _majority_vote(values: list[str]) -> str:
        """多数决。若平局则返回第一个出现的值。"""
        if not values:
            return "unknown"
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        max_count = max(counts.values())
        # 平局时返回第一个达到 max_count 的值
        for v in values:
            if counts[v] == max_count:
                return v
        return values[0]

    @staticmethod
    def _compute_temporal_extent(
        observations: list[Observation],
    ) -> dict[str, str]:
        """计算 temporal_extent：取所有观测 temporal 的 start 最小值和 end 最大值。

        若 Observations 没有 temporal 字段，返回 {"start": "unknown", "end": "unknown"}。
        """
        starts: list[str] = []
        ends: list[str] = []
        for obs in observations:
            t = obs.temporal or {}
            if "start" in t and isinstance(t["start"], str):
                starts.append(t["start"])
            if "end" in t and isinstance(t["end"], str):
                ends.append(t["end"])
        return {
            "start": min(starts) if starts else "unknown",
            "end": max(ends) if ends else "unknown",
        }

    @staticmethod
    def _compute_quality_summary(
        observations: list[Observation],
    ) -> CandidateQualitySummary | None:
        """从 Observations 计算质量摘要。"""
        if not observations:
            return None
        scores = [o.score for o in observations if o.score is not None]
        if not scores:
            return None
        mean_score = sum(scores) / len(scores)
        score_std: float | None = None
        if len(scores) >= 2:
            try:
                score_std = statistics.stdev(scores)
            except statistics.StatisticsError:
                pass
        return CandidateQualitySummary(
            mean_score=mean_score,
            n_observations=len(observations),
            area_consistency=None,
            score_std=score_std,
        )

    @staticmethod
    def _compute_coordinate_space(
        observations: list[Observation],
    ) -> str | None:
        """多数决 coordinate_space。"""
        spaces = [o.coordinate_space for o in observations if o.coordinate_space]
        if not spaces:
            return None
        return ObservationAggregator._majority_vote(spaces)

    @staticmethod
    def _pick_geometry(
        observations: list[Observation],
    ) -> dict[str, Any] | None:
        """选取非空的第一个 geometry。"""
        for obs in observations:
            if obs.geometry:
                return obs.geometry
        return None

    def aggregate(
        self,
        observations: list[Observation],
        candidate_type: str | None = None,
    ) -> DetectionCandidate:
        """将 list[Observation] 聚合为 DetectionCandidate。

        Args:
            observations: 待聚合的 Observation 列表
            candidate_type: 可选的 candidate_type，若为 None 则多数决

        Returns:
            DetectionCandidate 实例
        """
        if not observations:
            raise ValueError("至少需要 1 个 Observation 才能聚合")

        # candidate_id = f"cand-{obs[0].observation_id}"
        candidate_id = f"cand-{observations[0].observation_id}"

        # observation_refs
        observation_refs = [o.observation_id for o in observations]

        # temporal_extent
        temporal_extent = self._compute_temporal_extent(observations)

        # score = min of all scores
        scores = [o.score for o in observations if o.score is not None]
        score = min(scores) if scores else 0.0

        # candidate_type
        if candidate_type is None:
            candidate_type = self._majority_vote(
                [o.label for o in observations]
            )

        # quality_summary
        quality_summary = self._compute_quality_summary(observations)

        # coordinate_space
        coordinate_space = self._compute_coordinate_space(observations)

        # geometry
        geometry = self._pick_geometry(observations)

        return DetectionCandidate(
            candidate_id=candidate_id,
            observation_refs=observation_refs,
            temporal_extent=temporal_extent,
            candidate_type=candidate_type,
            score=score,
            rule_version=self.VERSION,
            geometry=geometry,
            quality_summary=quality_summary,
            coordinate_space=coordinate_space,
            evidence_refs=[],
        )
