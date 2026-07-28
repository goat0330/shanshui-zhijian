import numpy as np


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return 0.0
    return float(np.mean(y_true == y_pred))


def precision(y_true: np.ndarray, y_pred: np.ndarray, pos_label: int = 1) -> float:
    tp = np.sum((y_pred == pos_label) & (y_true == pos_label))
    fp = np.sum((y_pred == pos_label) & (y_true != pos_label))
    if tp + fp == 0:
        return 0.0
    return float(tp / (tp + fp))


def recall(y_true: np.ndarray, y_pred: np.ndarray, pos_label: int = 1) -> float:
    tp = np.sum((y_pred == pos_label) & (y_true == pos_label))
    fn = np.sum((y_pred != pos_label) & (y_true == pos_label))
    if tp + fn == 0:
        return 0.0
    return float(tp / (tp + fn))


def f1_score(y_true: np.ndarray, y_pred: np.ndarray, pos_label: int = 1) -> float:
    p = precision(y_true, y_pred, pos_label)
    r = recall(y_true, y_pred, pos_label)
    if p + r == 0:
        return 0.0
    return float(2 * p * r / (p + r))


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int = 2) -> np.ndarray:
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1
    return cm


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return 0.0
    return float(np.mean((y_true - y_pred) ** 2))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return 0.0
    return float(np.mean(np.abs(y_true - y_pred)))


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return 0.0
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return 1.0
    return float(1 - ss_res / ss_tot)


def classification_report(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    classes = sorted(set(int(x) for x in np.unique(np.concatenate([y_true, y_pred]))))
    report: dict = {"accuracy": accuracy(y_true, y_pred)}
    for c in classes:
        report[f"class_{c}_precision"] = precision(y_true, y_pred, c)
        report[f"class_{c}_recall"] = recall(y_true, y_pred, c)
        report[f"class_{c}_f1"] = f1_score(y_true, y_pred, c)
    return report
