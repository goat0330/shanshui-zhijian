"""
Dataset Registry — formalizes data sources with license tracking and checkout.

Usage:
    registry = DatasetRegistry()
    for ds in registry.list_available():
        print(ds.dataset_id, ds.license_type)
    entry = registry.get("sentinel2_l2a")
"""

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
    def from_dict(cls, d: dict) -> "DatasetEntry":
        extra = {k: v for k, v in d.items() if k not in cls.__dataclass_fields__}
        return cls(
            dataset_id=d["dataset_id"],
            name=d.get("name", ""),
            source_type=d.get("source_type", ""),
            source_uri=d.get("source_uri", ""),
            bands=d.get("bands", []),
            resolution_m=d.get("resolution_m", 10),
            temporal=d.get("temporal", False),
            license=d.get("license", ""),
            citation=d.get("citation", ""),
            restrictions=d.get("restrictions", ""),
            gee_collection=d.get("gee_collection", False),
            requires_download=d.get("requires_download", False),
            band_aliases=d.get("band_aliases"),
            local_path=d.get("local_path"),
            extra=extra,
        )


class DatasetRegistry:
    def __init__(self, registry_path: Path = _REGISTRY_PATH):
        self._path = Path(registry_path)
        self._datasets: dict[str, DatasetEntry] = {}
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        for entry in raw.get("datasets", []):
            ds = DatasetEntry.from_dict(entry)
            self._datasets[ds.dataset_id] = ds

    def list_available(self) -> list[DatasetEntry]:
        return list(self._datasets.values())

    def list_source_types(self, source_type: str) -> list[DatasetEntry]:
        return [d for d in self._datasets.values() if d.source_type == source_type]

    def get(self, dataset_id: str) -> DatasetEntry | None:
        return self._datasets.get(dataset_id)

    def get_by_source_uri(self, uri: str) -> list[DatasetEntry]:
        return [d for d in self._datasets.values() if d.source_uri == uri]

    def locate_local(self, dataset_id: str, root: Path = Path("data")) -> Path | None:
        entry = self.get(dataset_id)
        if entry is None:
            return None
        candidates = [
            root / entry.source_uri,
            root / "chongqing_demo" / "raw" / f"{dataset_id.replace('chongqing_demo_', '')}.tif",
            root / entry.dataset_id.replace("chongqing_demo_", "") / "raw" / f"{dataset_id}.tif",
        ]
        for c in candidates:
            expanded = Path(str(c).replace("chongqing_demo_", ""))
            if expanded.exists():
                return expanded
            if Path(c).exists():
                return Path(c)
        return None

    def verify_license(self, dataset_id: str) -> dict:
        entry = self.get(dataset_id)
        if entry is None:
            return {"ok": False, "reason": "unknown dataset"}
        ok = bool(entry.license) and "restricted" not in entry.license.lower()
        return {
            "ok": ok,
            "dataset_id": dataset_id,
            "license": entry.license,
            "citation": entry.citation,
            "restrictions": entry.restrictions,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {"datasets": [d.__dict__ for d in self._datasets.values()]},
            indent=indent,
            ensure_ascii=False,
        )
