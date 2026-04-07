"""
Predictive ML model for 6-hour-ahead spoilage risk.

Uses XGBoost with Optuna hyperparameter tuning.
SHAP values provide per-prediction explainability (FDA/GDP audit requirement).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent / "artifacts"


def _compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, float]:
    y_pred = (y_prob >= 0.5).astype(int)
    pr_auc = average_precision_score(y_true, y_prob)
    roc = roc_auc_score(y_true, y_prob)
    f1 = f1_score(y_true, y_pred)

    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    valid = precision >= 0.7
    recall_at_p70 = float(recall[valid].max()) if valid.any() else 0.0

    return {
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc, 4),
        "f1": round(f1, 4),
        "recall_at_precision_70": round(recall_at_p70, 4),
    }


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_optuna_trials: int = 30,
    seed: int = 42,
) -> Tuple[XGBClassifier, Dict[str, float]]:
    """
    Train XGBoost with Optuna hyperparameter search.
    Returns (best_model, val_metrics).
    """
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    scale_pos = int((y_train == 0).sum() / max((y_train == 1).sum(), 1))

    def objective(trial: optuna.Trial) -> float:
        params = {
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            "scale_pos_weight": scale_pos,
            "eval_metric": "aucpr",
            "random_state": seed,
        }
        clf = XGBClassifier(**params)
        clf.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        y_prob = clf.predict_proba(X_val)[:, 1]
        return average_precision_score(y_val, y_prob)

    study = optuna.create_study(direction="maximize", study_name="xgb_spoilage")
    study.optimize(objective, n_trials=n_optuna_trials, show_progress_bar=False)

    best_params = study.best_params
    best_params.update({
        "scale_pos_weight": scale_pos,
        "eval_metric": "aucpr",
        "random_state": seed,
    })
    logger.info("Best Optuna params: %s", best_params)
    logger.info("Best Optuna PR-AUC: %.4f", study.best_value)

    model = XGBClassifier(**best_params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    y_val_prob = model.predict_proba(X_val)[:, 1]
    metrics = _compute_metrics(y_val.values, y_val_prob)
    logger.info("Validation metrics: %s", metrics)

    return model, metrics


def predict(model: XGBClassifier, X: pd.DataFrame) -> np.ndarray:
    """Return spoilage probability for each window."""
    return model.predict_proba(X)[:, 1]


def explain(
    model: XGBClassifier,
    X: pd.DataFrame,
    top_k: int = 5,
) -> List[List[Dict[str, Any]]]:
    """
    Compute SHAP values and return the top-k contributing features
    per row as a list of dicts: [{"feature": ..., "shap_value": ...}, ...].
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    results: List[List[Dict[str, Any]]] = []
    feature_names = list(X.columns)

    for i in range(len(X)):
        row_shap = shap_values[i]
        top_idx = np.argsort(np.abs(row_shap))[-top_k:][::-1]
        top_features = [
            {"feature": feature_names[j], "shap_value": round(float(row_shap[j]), 4)}
            for j in top_idx
        ]
        results.append(top_features)

    return results


def save_model(model: XGBClassifier, path: Optional[Path] = None) -> Path:
    MODEL_DIR.mkdir(exist_ok=True)
    path = path or MODEL_DIR / "xgb_spoilage.joblib"
    joblib.dump(model, path)
    logger.info("Model saved to %s", path)
    return path


def load_model(path: Optional[Path] = None) -> XGBClassifier:
    path = path or MODEL_DIR / "xgb_spoilage.joblib"
    return joblib.load(path)
