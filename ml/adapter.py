from pathlib import Path
from typing import Any, Protocol


class ModelAdapter(Protocol):
    def train(self, X: Any, y: Any) -> None:
        ...

    def predict(self, X: Any) -> Any:
        ...

    def predict_proba(self, X: Any) -> Any:
        ...

    def evaluate(self, X: Any, y: Any) -> dict:
        ...

    def save(self, path: str | Path) -> None:
        ...

    @classmethod
    def load(cls, path: str | Path) -> Any:
        ...
