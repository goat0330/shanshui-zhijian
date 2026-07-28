import hashlib
import json
from pathlib import Path
from typing import Any


class ArtifactMetadata:
    def __init__(
        self,
        artifact_id: str,
        file_path: str | Path,
        artifact_type: str = "model",
        sha256: str = "",
        size_bytes: int = 0,
        extra: dict | None = None,
    ):
        self.artifact_id = artifact_id
        self.file_path = Path(file_path)
        self.artifact_type = artifact_type
        self.sha256 = sha256 or self._compute_sha256(self.file_path)
        self.size_bytes = size_bytes or self.file_path.stat().st_size if self.file_path.exists() else 0
        self.extra = extra or {}
        self.created_at = ""

    def _compute_sha256(self, path: Path) -> str:
        if not path.exists():
            return ""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "file_path": str(self.file_path),
            "artifact_type": self.artifact_type,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "extra": self.extra,
        }

    def save_metadata(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return p

    @classmethod
    def from_file(cls, path: str | Path) -> "ArtifactMetadata":
        p = Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        return cls(**raw)


class ModelCheckpoint:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.exists() else 0

    def sha256(self) -> str:
        if not self.exists():
            return ""
        sha = hashlib.sha256()
        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()


def save_checkpoint(state: dict, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    import torch
    torch.save(state, str(p))
    return p


def load_checkpoint(path: str | Path, map_location: str = "cpu", weights_only: bool = False) -> dict:
    import torch
    return torch.load(str(path), map_location=map_location, weights_only=weights_only)


def find_latest_checkpoint(checkpoint_dir: str | Path, pattern: str = "*.pt") -> Path | None:
    d = Path(checkpoint_dir)
    if not d.exists():
        return None
    files = sorted(d.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None
