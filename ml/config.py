import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    train_path: Path = Path("data/train")
    val_path: Path = Path("data/val")
    test_path: Path = Path("data/test")
    batch_size: int = Field(default=32, ge=1)
    num_workers: int = Field(default=2, ge=0)


class ModelConfig(BaseModel):
    backbone: str = "resnet18"
    num_classes: int = 2
    pretrained: bool = True
    dropout: float = Field(default=0.3, ge=0.0, le=1.0)


class TrainingConfig(BaseModel):
    learning_rate: float = Field(default=1e-4, gt=0)
    max_epochs: int = Field(default=50, ge=1)
    early_stop_patience: int = Field(default=10, ge=1)
    gradient_clip_val: float = Field(default=1.0, gt=0)
    seed: int = 42


class OptimizerConfig(BaseModel):
    name: Literal["adam", "sgd", "adamw"] = "adamw"
    weight_decay: float = Field(default=1e-4, ge=0)


class LoggingConfig(BaseModel):
    log_dir: Path = Path("logs")
    log_every_n_steps: int = Field(default=10, ge=1)
    save_top_k: int = Field(default=3, ge=1)
    metrics_log: Path = Path("logs/metrics.json")


class TrainConfig(BaseModel):
    data: DataConfig = DataConfig()
    model: ModelConfig = ModelConfig()
    training: TrainingConfig = TrainingConfig()
    optimizer: OptimizerConfig = OptimizerConfig()
    logging: LoggingConfig = LoggingConfig()

    def validate_paths(self) -> list[str]:
        warnings: list[str] = []
        if not self.data.train_path.exists():
            warnings.append(f"Train path {self.data.train_path} does not exist")
        if not self.data.val_path.exists():
            warnings.append(f"Val path {self.data.val_path} does not exist")
        return warnings

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent, exclude_none=True)

    @classmethod
    def from_json(cls, path: str | Path) -> "TrainConfig":
        p = Path(path)
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        return cls.model_validate(data)

    @classmethod
    def smoke_defaults(cls) -> "TrainConfig":
        return cls(
            training=TrainingConfig(
                max_epochs=2,
                seed=42,
            ),
            data=DataConfig(
                batch_size=4,
                num_workers=0,
            ),
        )
