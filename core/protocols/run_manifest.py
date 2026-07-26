"""RunManifest — Agent B hook protocol for candidate delivery notification.

G0.3-A: Config point for Agent B. Agent B implements RunManifestHook to
receive the manifest after each SAR pipeline run.

Usage:
    from core.protocols.run_manifest import SimpleRunManifest, RunManifestHook

    def my_hook(m: RunManifest):
        print(f"Run {m.run_id} complete: {m.total_candidates} candidates")

    tool = SarTemporalChangeTool(registry)
    tool.agent_b_hook = my_hook  # Set hook
    result = tool.run(task, spec, ctx)
    # hook called automatically on success
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class RunManifest(BaseModel):
    """Minimal manifest delivered to Agent B after a SAR pipeline run."""
    model_config = dict(frozen=True)

    run_id: str = Field(..., description="运行 ID")
    scene_index: int = Field(..., description="当前场景序号")
    total_candidates: int = Field(..., ge=0, description="候选总数")
    candidate_ids: list[str] = Field(default_factory=list, description="候选 ID 列表")
    candidate_track_ids: list[str] = Field(default_factory=list, description="跟踪 ID 列表")
    envelope_ref: str | None = Field(None, description="CandidateDeliveryEnvelope 引用路径")


class SimpleRunManifest(RunManifest):
    """Simple RunManifest implementation for in-process use."""

    @classmethod
    def from_envelope(cls, envelope) -> SimpleRunManifest:
        """Build manifest from a CandidateDeliveryEnvelope."""
        from core.schemas.contracts.candidate_envelope import CandidateDeliveryEnvelope
        return cls(
            run_id=envelope.run_id,
            scene_index=envelope.scene_index,
            total_candidates=envelope.total_candidates,
            candidate_ids=[c.candidate_id for c in envelope.candidates],
            candidate_track_ids=[c.candidate_track_id for c in envelope.candidates],
        )


class RunManifestHook(Protocol):
    """Protocol for Agent B's manifest hook.

    Agent B implements this to receive run manifests after each
    SAR pipeline execution. GeoAgent calls hook(manifest) at the
    end of each successful candidate delivery.
    """

    def __call__(self, manifest: RunManifest) -> None:
        """Process a run manifest."""
        ...
