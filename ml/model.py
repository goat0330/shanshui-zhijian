from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score


class BaselineModel:
    def __init__(self, n_estimators: int = 100, max_depth: int = 10, random_state: int = 42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self.model: RandomForestClassifier | None = None
        self.feature_names: list[str] | None = None

    def train(self, X, y):
        self.feature_names = list(X.columns) if hasattr(X, "columns") else None
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=self.random_state,
            class_weight="balanced",
            n_jobs=-1,
        )
        self.model.fit(X, y)

    def predict(self, X):
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        return self.model.predict(X)

    def predict_proba(self, X):
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        return self.model.predict_proba(X)

    def evaluate(self, X, y) -> dict:
        y_pred = self.predict(X)
        y_prob = self.predict_proba(X)[:, 1]
        return {
            "accuracy": accuracy_score(y, y_pred),
            "precision": precision_score(y, y_pred, zero_division=0),
            "recall": recall_score(y, y_pred, zero_division=0),
            "f1_score": f1_score(y, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y, y_prob) if len(set(y)) > 1 else 0.0,
            "n_samples": len(y),
        }

    def save(self, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model": self.model,
            "feature_names": self.feature_names,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "random_state": self.random_state,
        }, p)

    @classmethod
    def load(cls, path: str | Path):
        data = joblib.load(Path(path))
        instance = cls(
            n_estimators=data.get("n_estimators", 100),
            max_depth=data.get("max_depth", 10),
            random_state=data.get("random_state", 42),
        )
        instance.model = data["model"]
        instance.feature_names = data.get("feature_names")
        return instance

    def get_params(self) -> dict:
        return {
            "model_type": "RandomForest",
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "random_state": self.random_state,
        }
