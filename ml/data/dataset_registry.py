"""Dataset registry with explicit licence-review and local-file semantics."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REGISTRY_PATH = Path(__file__).parent / "dataset_registry.json"


@dataclass
class DatasetEntry:
    dataset_id: str
    name: str
    source_type: str
    source_uri: str
    bands: list[str]
    resolution_m: int
    temporal: bool = False
    license: str = ""
    citation: str = ""
    restrictions: str = ""
    gee_collection: bool = False
    requires_download: bool = False
    band_aliases: list[str] | None = None
    local_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "DatasetEntry":
        known = set(cls.__dataclass_fields__)
        return cls(
            dataset_id=data["dataset_id"],
            name=data.get("name", ""),
            source_type=data.get("source_type", ""),
            source_uri=data.get("source_uri", ""),
            bands=data.get("bands", []),
            resolution_m=data.get("resolution_m", 10),
            temporal=data.get("temporal", False),
            license=data.get("license", ""),
            citation=data.get("citation", ""),
            restrictions=data.get("restrictions", ""),
            gee_collection=data.get("gee_collection", False),
            requires_download=data.get("requires_download", False),
            band_aliases=data.get("band_aliases"),
            local_path=data.get("local_path"),
            extra={key: value for key, value in data.items() if key not in known},
        )

    @property
    def role(self) -> str:
        return str(self.extra.get("role", ""))


class DatasetRegistry:
    def __init__(self, registry_path: Path = _REGISTRY_PATH):
        self._path = Path(registry_path)
        self._datasets: dict[str, DatasetEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        for item in raw.get("datasets", []):
            entry = DatasetEntry.from_dict(item)
            self._datasets[entry.dataset_id] = entry

    def list_available(self) -> list[DatasetEntry]:
        return list(self._datasets.values())

    def list_source_types(self, source_type: str) -> list[DatasetEntry]:
        return [entry for entry in self._datasets.values() if entry.source_type == source_type]

    def get(self, dataset_id: str) -> DatasetEntry | None:
        return self._datasets.get(dataset_id)

    def get_by_source_uri(self, uri: str) -> list[DatasetEntry]:
        return [entry for entry in self._datasets.values() if entry.source_uri == uri]

    def locate_local(self, dataset_id: str, root: Path = Path("data")) -> Path | None:
        entry = self.get(dataset_id)
        if entry is None:
            return None
        candidates: list[Path] = []
        if entry.local_path:
            candidates.append(Path(entry.local_path))
        source = Path(entry.source_uri)
        candidates.append(source)
        if not source.is_absolute() and (not source.parts or source.parts[0] != root.name):
            candidates.append(root / source)
        candidates.extend([
            root / "chongqing_demo" / "raw" / f"{dataset_id.replace('chongqing_demo_', '')}.tif",
            root / dataset_id.replace("chongqing_demo_", "") / "raw" / f"{dataset_id}.tif",
        ])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def verify_license(self, dataset_id: str) -> dict:
        entry = self.get(dataset_id)
        if entry is None:
            return {"ok": False, "reason": "unknown dataset"}
        licence = entry.license.strip()
        combined = f"{licence} {entry.restrictions}".lower()
        review_markers = (
            "license_review_required",
            "licence_review_required",
            "restricted",
            "cc-by-nc",
            "cc by-nc",
            "non-commercial",
            "noncommercial",
        )
        requires_review = any(marker in combined for marker in review_markers)
        redistribution_ok = not requires_review and "project_internal" not in combined
        return {
            "ok": bool(licence) and not requires_review,
            "requires_review": requires_review,
            "redistribution_ok": redistribution_ok,
            "dataset_id": dataset_id,
            "license": licence,
            "citation": entry.citation,
            "restrictions": entry.restrictions,
            "role": entry.role,
        }

    def to_json(self, indent: int = 2) -> str:
        datasets = []
        for entry in self._datasets.values():
            item = {
                "dataset_id": entry.dataset_id,
                "name": entry.name,
                "source_type": entry.source_type,
                "source_uri": entry.source_uri,
                "bands": entry.bands,
                "resolution_m": entry.resolution_m,
                "temporal": entry.temporal,
                "license": entry.license,
                "citation": entry.citation,
                "restrictions": entry.restrictions,
                "gee_collection": entry.gee_collection,
                "requires_download": entry.requires_download,
            }
            if entry.band_aliases is not None:
                item["band_aliases"] = entry.band_aliases
            if entry.local_path is not None:
                item["local_path"] = entry.local_path
            item.update(entry.extra)
            datasets.append(item)
        return json.dumps({"datasets": datasets}, indent=indent, ensure_ascii=False)
