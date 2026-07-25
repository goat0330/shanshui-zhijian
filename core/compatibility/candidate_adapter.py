"""CandidateCompatibilityAdapter — v0.2/v0.3 adapter."""
from core.schemas.contracts.candidate import DetectionCandidate
class CandidateCompatibilityAdapter:
    SUPPORTED={"rs-contract.v0.2","rs-contract.v0.3"}
    @staticmethod
    def normalize(d):
        v=d.get("schema_version","")
        if v in CandidateCompatibilityAdapter.SUPPORTED:return d
        raise ValueError(f"Unsupported version: {v}")
    @staticmethod
    def to_detection_candidate(d):return DetectionCandidate(**CandidateCompatibilityAdapter.normalize(d).get("candidate",d))
    @staticmethod
    def get_fixture_assets(d):return CandidateCompatibilityAdapter.normalize(d).get("assets",[])
    @staticmethod
    def get_modalities(d):
        n=CandidateCompatibilityAdapter.normalize(d)
        return dict(modalities_expected=n.get("modalities_expected",[]),modalities_present=n.get("modalities_present",[]),modalities_missing=n.get("modalities_missing",[]),missing_context_notes=n.get("missing_context_notes"))
