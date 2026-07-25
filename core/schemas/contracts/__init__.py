"""
RS-00 / RS-01A — 契约枚举与导出
"""

from enum import Enum


class Modality(str, Enum):
    SAR = "sar"
    OPTICAL = "optical"
    DEM = "dem"
    VECTOR = "vector"
    MASK = "mask"
    VIDEO = "video"
    METADATA = "metadata"
    UNKNOWN = "unknown"


class AssetRole(str, Enum):
    BEFORE = "before"
    AFTER = "after"
    HISTORY = "history"
    CURRENT = "current"
    AUXILIARY = "auxiliary"
    PRIOR = "prior"
    MASK = "mask"
    LABEL = "label"
    SPATIAL_METADATA = "spatial_metadata"
    OPTICAL_SUPPORT = "optical_support"


class SpatialReliability(str, Enum):
    GEOREFERENCED = "georeferenced"
    PIXEL_ONLY = "pixel_only"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class TaskType(str, Enum):
    TEMPORAL_CHANGE_DETECTION = "temporal_change_detection"
    WATER_EXTRACTION = "water_extraction"
    OBJECT_DETECTION = "object_detection"
    CLASSIFICATION = "classification"
    ANOMALY_SCORING = "anomaly_scoring"


class ExecutionStatus(str, Enum):
    SUCCEEDED_WITH_OBSERVATIONS = "succeeded_with_observations"
    SUCCEEDED_EMPTY = "succeeded_empty"
    NO_DATA = "no_data"
    INVALID_INPUT = "invalid_input"
    FAILED = "failed"


class ScoreType(str, Enum):
    MODEL_PROBABILITY = "model_probability"
    RULE_BASED = "rule_based"
    ENSEMBLE = "ensemble"


class ObservationType(str, Enum):
    SAR_BACKSCATTER_CHANGE = "sar_backscatter_change"
    OPTICAL_WATER_INDEX = "optical_water_index"
    OPTICAL_WATER_INDEX_SUPPORT = "optical_water_index_support"
    WATER_EXTENT = "water_extent"
    CHANGE_POLYGON = "change_polygon"
    OBJECT_DETECTION = "object_detection"
    ANOMALY_SCORE = "anomaly_score"


# G0.3-A exports — imported directly from candidate module to avoid name clash
# with ScoreType above (MODEL_PROBABILITY / RULE_BASED / ENSEMBLE).
# Candidate's ScoreType (WITHIN_RUN_RANKING) is available via:
#   from core.schemas.contracts.candidate import ScoreType
# CandidateDeliveryEnvelope is available via:
#   from core.schemas.contracts.candidate_envelope import CandidateDeliveryEnvelope
