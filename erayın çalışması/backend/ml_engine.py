"""
backend/ml_engine.py
====================
Saf NumPy Tabanlı, %100 Yerel Ay İniş Makine Öğrenimi (ML) Motoru.
Sıfır dış bağımlılıkla (Scikit-Learn gerekmeden) çalışır; varsa Scikit-Learn adaptörü sunar.

Modeller:
1. Çoklu Regresyon (Ridge Regression / Normal Equations):
   - İniş Sağlık Skoru (0-100) ve Harcanan İtici Yakıt (kg) Tahmini
   - R² ve RMSE Performans Metrikleri
2. Çok Sınıflı Lojistik Softmax Sınıflandırıcı:
   - İniş Sonucu Olasılıkları (SAFE / HARD / CRASH)
   - Doğruluk (Accuracy) ve F1 Skoru (Macro / Weighted)
3. Özellik Önem Düzeyleri (Feature Importance):
   - Parametrelerin (eğim, düşey hız, TRI vb.) iniş başarısına oransal etkisi
4. Ön Uçuş Risk Tahmincisi (Pre-Flight Risk Assessor):
   - Başlangıç telemetrisine göre risk seviyesi ve güdüm marjı tavsiyesi
5. Model Serileştirme & Otomatik Eğitim (data/ml_model.json)
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from backend.config import DATA_DIR

M_TOTAL_INITIAL_KG: float = 5000.0
from backend.landing_db import get_dataset_for_ml, get_stats, seed_initial_trials

DEFAULT_MODEL_PATH = DATA_DIR / "ml_model.json"

FEATURE_NAMES = [
    "initial_alt_m",
    "initial_vh_ms",
    "initial_vv_ms",
    "slope_deg",
    "roughness_tri_m",
    "solar_illum_pct",
    "dte_vis_pct",
    "total_mass_kg",
]

FEATURE_LABELS_TR = {
    "initial_alt_m": "Başlangıç İrtifası (m)",
    "initial_vh_ms": "Başlangıç Yatay Hızı (m/s)",
    "initial_vv_ms": "Başlangıç Düşey Hızı (m/s)",
    "slope_deg": "Yüzey Eğimi (°)",
    "roughness_tri_m": "Yüzey Pürüzlülüğü TRI (m)",
    "solar_illum_pct": "Güneşlenme Oranı (%)",
    "dte_vis_pct": "Dünya Görüş Hattı DTE (%)",
    "total_mass_kg": "Uzay Aracı Toplam Kütlesi (kg)",
}

CLASSES = ["SAFE", "HARD", "CRASH"]


# =============================================================================
# YEREL STANDART ÖLÇEKLENDİRİCİ (StandardScaler)
# =============================================================================
class PureNumpyScaler:
    """Veri matrisini ortalama=0 ve standart sapma=1 olacak şekilde ölçekler."""

    def __init__(self) -> None:
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> PureNumpyScaler:
        X = np.asarray(X, dtype=np.float64)
        self.mean_ = np.mean(X, axis=0)
        self.std_ = np.std(X, axis=0)
        # Sıfıra bölünmeyi engelle
        self.std_ = np.where(self.std_ < 1e-8, 1.0, self.std_)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            raise ValueError("Scaler henüz eğitilmedi (fit edilmedi).")
        X = np.asarray(X, dtype=np.float64)
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": self.mean_.tolist() if self.mean_ is not None else None,
            "std": self.std_.tolist() if self.std_ is not None else None,
        }

    def from_dict(self, data: Dict[str, Any]) -> PureNumpyScaler:
        if data.get("mean") is not None:
            self.mean_ = np.array(data["mean"], dtype=np.float64)
        if data.get("std") is not None:
            self.std_ = np.array(data["std"], dtype=np.float64)
        return self


# =============================================================================
# SAF NUMPY ÇOKLU REGRESYON MODELİ (Ridge Regression / L2 Regularization)
# =============================================================================
class PureNumpyRidgeRegressor:
    """
    Kapalı form Normal Denklemler ile L2 düzenlileştirmeli Çoklu Regresyon.
    w = (X^T X + lambda * I)^(-1) X^T Y
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = float(alpha)
        self.weights_: Optional[np.ndarray] = None  # (n_features, n_targets)
        self.bias_: Optional[np.ndarray] = None  # (n_targets,)

    def fit(self, X: np.ndarray, Y: np.ndarray) -> PureNumpyRidgeRegressor:
        X = np.asarray(X, dtype=np.float64)
        Y = np.asarray(Y, dtype=np.float64)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)

        n_samples, n_features = X.shape

        # Veriyi merkezileştirerek bias'ı analitik hesapla
        mean_x = np.mean(X, axis=0)
        mean_y = np.mean(Y, axis=0)

        X_centered = X - mean_x
        Y_centered = Y - mean_y

        # L2 Düzenlileştirme: (X^T X + alpha * I)
        A = X_centered.T @ X_centered + self.alpha * np.eye(n_features)
        b = X_centered.T @ Y_centered

        # Kararlı doğrusal denklem çözümü (pseudo-inverse fallback)
        try:
            self.weights_ = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            self.weights_ = np.linalg.pinv(A) @ b

        self.bias_ = mean_y - mean_x @ self.weights_
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.weights_ is None or self.bias_ is None:
            raise ValueError("Regresyon modeli henüz eğitilmedi.")
        X = np.asarray(X, dtype=np.float64)
        preds = X @ self.weights_ + self.bias_
        return preds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha": self.alpha,
            "weights": self.weights_.tolist() if self.weights_ is not None else None,
            "bias": self.bias_.tolist() if self.bias_ is not None else None,
        }

    def from_dict(self, data: Dict[str, Any]) -> PureNumpyRidgeRegressor:
        self.alpha = float(data.get("alpha", 1.0))
        if data.get("weights") is not None:
            self.weights_ = np.array(data["weights"], dtype=np.float64)
        if data.get("bias") is not None:
            self.bias_ = np.array(data["bias"], dtype=np.float64)
        return self


# =============================================================================
# SAF NUMPY ÇOK SINIFLI SOFTMAX LOJİSTİK SINIFLANDIRICI
# =============================================================================
class PureNumpySoftmaxClassifier:
    """
    Mini-Batch Gradient Descent ve Çapraz Entropi Kaybı ile Softmax Sınıflandırıcı.
    K sınıflı olasılık dağılımı: P(y=k|x) = exp(z_k) / sum(exp(z))
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        epochs: int = 400,
        l2_reg: float = 0.01,
        batch_size: int = 32,
    ) -> None:
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.l2_reg = l2_reg
        self.batch_size = batch_size
        self.classes_ = list(CLASSES)
        self.W_: Optional[np.ndarray] = None  # (n_features, n_classes)
        self.b_: Optional[np.ndarray] = None  # (n_classes,)

    def _softmax(self, Z: np.ndarray) -> np.ndarray:
        # Sayısal taşmayı önlemek için max Z çıkarılır
        exp_Z = np.exp(Z - np.max(Z, axis=1, keepdims=True))
        return exp_Z / np.sum(exp_Z, axis=1, keepdims=True)

    def fit(self, X: np.ndarray, y: np.ndarray) -> PureNumpySoftmaxClassifier:
        X = np.asarray(X, dtype=np.float64)
        n_samples, n_features = X.shape
        n_classes = len(self.classes_)

        # One-hot kodlama
        class_to_idx = {c: i for i, c in enumerate(self.classes_)}
        Y_onehot = np.zeros((n_samples, n_classes), dtype=np.float64)
        for i, label in enumerate(y):
            idx = class_to_idx.get(str(label), 0)
            Y_onehot[i, idx] = 1.0

        # Xavier / Glorot Ağırlık İlklendirme
        rng = np.random.default_rng(42)
        scale = math.sqrt(2.0 / (n_features + n_classes))
        self.W_ = rng.normal(0.0, scale, size=(n_features, n_classes))
        self.b_ = np.zeros((n_classes,), dtype=np.float64)

        # Gradient Descent Optimizasyonu (Momentum ile)
        v_W = np.zeros_like(self.W_)
        v_b = np.zeros_like(self.b_)
        beta = 0.9

        for epoch in range(self.epochs):
            indices = np.arange(n_samples)
            rng.shuffle(indices)

            for start in range(0, n_samples, self.batch_size):
                end = min(start + self.batch_size, n_samples)
                b_idx = indices[start:end]

                X_b = X[b_idx]
                Y_b = Y_onehot[b_idx]
                m = len(b_idx)

                # İleri Yayılım
                Z = X_b @ self.W_ + self.b_
                P = self._softmax(Z)

                # Gradyanlar: dL/dZ = P - Y
                dZ = P - Y_b
                dW = (X_b.T @ dZ) / m + self.l2_reg * self.W_
                db = np.sum(dZ, axis=0) / m

                # Momentum Güncellemesi
                v_W = beta * v_W + (1 - beta) * dW
                v_b = beta * v_b + (1 - beta) * db

                self.W_ -= self.learning_rate * v_W
                self.b_ -= self.learning_rate * v_b

        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.W_ is None or self.b_ is None:
            raise ValueError("Sınıflandırıcı henüz eğitilmedi.")
        X = np.asarray(X, dtype=np.float64)
        Z = X @ self.W_ + self.b_
        return self._softmax(Z)

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        indices = np.argmax(proba, axis=1)
        return np.array([self.classes_[i] for i in indices])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classes": self.classes_,
            "W": self.W_.tolist() if self.W_ is not None else None,
            "b": self.b_.tolist() if self.b_ is not None else None,
        }

    def from_dict(self, data: Dict[str, Any]) -> PureNumpySoftmaxClassifier:
        self.classes_ = data.get("classes", list(CLASSES))
        if data.get("W") is not None:
            self.W_ = np.array(data["W"], dtype=np.float64)
        if data.get("b") is not None:
            self.b_ = np.array(data["b"], dtype=np.float64)
        return self


# =============================================================================
# METRİK DEĞERLENDİRİCİ (R², RMSE, Accuracy, F1-Score)
# =============================================================================
def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """R² ve RMSE metriklerini hesaplar."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    mse = np.mean((y_true - y_pred) ** 2)
    rmse = math.sqrt(float(mse))

    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    ss_res = np.sum((y_true - y_pred) ** 2)

    if ss_tot < 1e-8:
        r2 = 1.0 if ss_res < 1e-8 else 0.0
    else:
        r2 = float(1.0 - (ss_res / ss_tot))

    return {
        "rmse": round(rmse, 3),
        "r2": round(max(-1.0, min(1.0, r2)), 4),
    }


def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Doğruluk (Accuracy) ve F1 Skorlarını (Macro ve Weighted) hesaplar."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    n = len(y_true)
    if n == 0:
        return {"accuracy": 0.0, "f1_macro": 0.0, "f1_weighted": 0.0}

    accuracy = float(np.mean(y_true == y_pred))

    # Sınıf bazlı Precision, Recall, F1
    f1_list = []
    weights = []

    for cls in CLASSES:
        tp = np.sum((y_true == cls) & (y_pred == cls))
        fp = np.sum((y_true != cls) & (y_pred == cls))
        fn = np.sum((y_true == cls) & (y_pred != cls))
        count = np.sum(y_true == cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        f1_list.append(f1)
        weights.append(count)

    f1_macro = float(np.mean(f1_list))
    total_samples = sum(weights)
    f1_weighted = float(sum(f1 * w for f1, w in zip(f1_list, weights)) / total_samples) if total_samples > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
    }


# =============================================================================
# ANA MAKİNE ÖĞRENİMİ MOTORU (MLEngine)
# =============================================================================
class MLEngine:
    """
    Ay İniş Görevi Otonom Makine Öğrenimi Motoru.
    Girdi telemetrilerini işler, modelleri yönetir, risk ve güdüm marjı üretir.
    """

    def __init__(self, model_file: Optional[Union[str, Path]] = None) -> None:
        self.model_file = Path(model_file) if model_file else DEFAULT_MODEL_PATH
        self.scaler = PureNumpyScaler()
        self.regressor = PureNumpyRidgeRegressor(alpha=1.5)
        self.classifier = PureNumpySoftmaxClassifier(learning_rate=0.06, epochs=450, l2_reg=0.01)

        self.feature_names = list(FEATURE_NAMES)
        self.feature_importance: Dict[str, float] = {}
        self.metrics: Dict[str, Any] = {}
        self.is_trained: bool = False
        self.last_trained_at: Optional[str] = None
        self.training_sample_count: int = 0

        # Varsa kayıtlı modeli yükle
        self.load_model()

    def train(self, force_seed: bool = False, min_samples: int = 15) -> Dict[str, Any]:
        """
        Veritabanındaki verilerle regresyon ve sınıflandırma modellerini eğitir.
        Gerektiğinde veritabanına otomatik tohumlama yapar.
        """
        stats = get_stats()
        if stats["total_trials"] < min_samples or force_seed:
            seed_initial_trials(count=max(50, min_samples - stats["total_trials"]))

        X, y_reg, y_cls, feature_names = get_dataset_for_ml()
        n_samples = len(X)
        if n_samples < 5:
            raise ValueError(f"Eğitim için yetersiz veri ({n_samples} kayıt). Asgari 5 kayıt gereklidir.")

        self.feature_names = feature_names

        # 1. Özellikleri Standartlaştır
        X_scaled = self.scaler.fit_transform(X)

        # 2. Regresyon Eğitimi (total_score, fuel_consumed_kg)
        self.regressor.fit(X_scaled, y_reg)
        y_reg_pred = self.regressor.predict(X_scaled)

        # Metrikler
        score_metrics = compute_regression_metrics(y_reg[:, 0], y_reg_pred[:, 0])
        fuel_metrics = compute_regression_metrics(y_reg[:, 1], y_reg_pred[:, 1])

        # 3. Sınıflandırıcı Eğitimi (SAFE, HARD, CRASH)
        self.classifier.fit(X_scaled, y_cls)
        y_cls_pred = self.classifier.predict(X_scaled)
        cls_metrics = compute_classification_metrics(y_cls, y_cls_pred)

        # 4. Özellik Önem Düzeyleri Hesabı
        self._compute_feature_importance()

        self.metrics = {
            "score_regression": score_metrics,
            "fuel_regression": fuel_metrics,
            "classification": cls_metrics,
            "overall_accuracy_pct": round(cls_metrics["accuracy"] * 100.0, 1),
            "overall_r2": score_metrics["r2"],
        }

        self.is_trained = True
        self.training_sample_count = n_samples
        self.last_trained_at = datetime.now(timezone.utc).isoformat()

        # Modeli diske kaydet
        self.save_model()

        return {
            "status": "success",
            "training_samples": n_samples,
            "metrics": self.metrics,
            "feature_importance": self.feature_importance,
            "trained_at": self.last_trained_at,
        }

    def _compute_feature_importance(self) -> None:
        """
        Ölçeklendirilmiş regresyon katsayıları ve sınıflandırıcı ağırlıkları üzerinden
        normalleştirilmiş özellik önem yüzdeleri (%0-100) çıkarır.
        """
        if self.regressor.weights_ is None or self.classifier.W_ is None:
            return

        # Regresyon ağırlık büyüklükleri (sağlık skoru ve yakıt tüketimi)
        w_score = np.abs(self.regressor.weights_[:, 0])
        # Sınıflandırıcı ağırlık büyüklükleri
        w_cls = np.mean(np.abs(self.classifier.W_), axis=1)

        combined_weights = (w_score * 0.6) + (w_cls * 0.4)
        total_w = np.sum(combined_weights)

        if total_w < 1e-8:
            norm_importance = np.ones(len(self.feature_names)) / len(self.feature_names)
        else:
            norm_importance = (combined_weights / total_w) * 100.0

        self.feature_importance = {}
        for name, imp in zip(self.feature_names, norm_importance):
            self.feature_importance[name] = round(float(imp), 2)

        # En önemliden aza doğru sırala
        self.feature_importance = dict(
            sorted(self.feature_importance.items(), key=lambda kv: kv[1], reverse=True)
        )

    def predict_risk(self, telemetry: Union[Dict[str, float], List[float], np.ndarray]) -> Dict[str, Any]:
        """
        Ön Uçuş Risk Tahmincisi (Pre-Flight Risk Assessor).
        Verilen başlangıç koşulları ve arazi telemetrisi için başarı olasılığı,
        beklenen iniş skoru ve tavsiye edilen güdüm marjını döner.
        """
        if not self.is_trained:
            self.auto_train()

        # Telemetri vektörünü oluştur
        if isinstance(telemetry, dict):
            vector = [
                float(telemetry.get("initial_alt_m", 3200.0)),
                float(telemetry.get("initial_vh_ms", 62.0)),
                float(telemetry.get("initial_vv_ms", -28.0)),
                float(telemetry.get("slope_deg", 4.0)),
                float(telemetry.get("roughness_tri_m", 0.3)),
                float(telemetry.get("solar_illum_pct", 80.0)),
                float(telemetry.get("dte_vis_pct", 85.0)),
                float(telemetry.get("total_mass_kg", M_TOTAL_INITIAL_KG)),
            ]
        elif isinstance(telemetry, (list, tuple, np.ndarray)):
            vector = list(telemetry)
            if len(vector) < 8:
                vector.extend([M_TOTAL_INITIAL_KG] * (8 - len(vector)))
            vector = vector[:8]
        else:
            raise ValueError("Geçersiz telemetri veri tipi.")

        # Sayısal Kararlılık ve Sensör Hata Koruması (NaN / Inf)
        if any(math.isnan(v) or math.isinf(v) for v in vector):
            return {
                "predicted_score": 0.0,
                "predicted_fuel_consumed_kg": 2800.0,
                "predicted_fuel_remaining_pct": 0.0,
                "probabilities": {"SAFE": 0.0, "HARD": 0.0, "CRASH": 1.0},
                "most_likely_outcome": "CRASH",
                "risk_level": "CRITICAL",
                "risk_color": "#ef4444",
                "risk_status_tr": "KRİTİK HATA (Geçersiz Sensör Verisi: NaN/Inf Algılandı)",
                "guidance_margins": {
                    "recommended_throttle_band": "İptal (Abort) / Güvenli Mod",
                    "recommended_max_touchdown_vz_ms": "N/A",
                    "abort_gate_altitude_m": "ACİL İPTAL",
                },
                "advisory_text_tr": (
                    "Telemetri girdisinde geçersiz (NaN veya Sonsuz) değer tespit edildi. "
                    "Otonom güdüm güvenlik protokolü gereği acil iptal (abort) moduna geçilmelidir."
                ),
                "input_telemetry": {
                    name: (0.0 if math.isnan(val) or math.isinf(val) else round(val, 2))
                    for name, val in zip(self.feature_names, vector)
                },
            }

        X_in = np.array([vector], dtype=np.float64)
        X_scaled = self.scaler.transform(X_in)

        # Regresyon Tahmini: [total_score, fuel_consumed_kg]
        reg_preds = self.regressor.predict(X_scaled)[0]
        pred_score = float(np.clip(reg_preds[0], 0.0, 100.0))
        pred_fuel_cons = float(np.clip(reg_preds[1], 1500.0, 2800.0))
        pred_fuel_rem_pct = float(np.clip(((2800.0 - pred_fuel_cons) / 2800.0) * 100.0, 0.0, 100.0))

        # Sınıflandırma Tahmini: Olasılık Dağılımı
        probs = self.classifier.predict_proba(X_scaled)[0]
        prob_dict = {
            "SAFE": round(float(probs[0]), 3),
            "HARD": round(float(probs[1]), 3),
            "CRASH": round(float(probs[2]), 3),
        }
        most_likely_outcome = self.classifier.classes_[int(np.argmax(probs))]

        # Risk Seviyesi Belirleme
        p_safe = prob_dict["SAFE"]
        p_crash = prob_dict["CRASH"]

        if p_crash > 0.35 or p_safe < 0.40 or pred_score < 50.0:
            risk_level = "CRITICAL"
            risk_color = "#ef4444"
            status_text = "KRİTİK RİSK (İniş Önerilmez - Yönlendirme Gerekli)"
        elif p_crash > 0.15 or p_safe < 0.70 or pred_score < 75.0:
            risk_level = "HIGH"
            risk_color = "#f97316"
            status_text = "YÜKSEK RİSK (Kritik Eğim / Yakıt Marjı Sınırda)"
        elif p_safe < 0.88 or pred_score < 88.0:
            risk_level = "MODERATE"
            risk_color = "#f59e0b"
            status_text = "ORTA RİSK (Nominal İniş Şartları Sağlanabilir)"
        else:
            risk_level = "LOW"
            risk_color = "#10b981"
            status_text = "DÜŞÜK RİSK (Apollo E-Guidance İdeal İniş Profili)"

        # Güdüm ve İtki Marjı Tavsiyeleri
        slope_input = vector[3]
        init_vv_input = abs(vector[2])

        recommended_throttle_margin = "65% - 85% Kısma Bandı"
        if slope_input > 8.0:
            recommended_touchdown_vz = "< 0.8 m/s (Hassas Düşey Kısma)"
            guidance_advice = (
                "Yüzey eğimi Artemis sınırlarını zorluyor (> 8°). "
                "Devrilme (tip-over) riskini engellemek için terminal kapıda yatay hız sıfırlanmalı, "
                "düşey temas hızı 1.0 m/s altına indirilmelidir."
            )
        elif init_vv_input > 30.0:
            recommended_touchdown_vz = "< 1.2 m/s"
            guidance_advice = (
                "Başlangıç alçalma hızı yüksek. E-Guidance ateşleme zamanını (t_go) 5-8 sn erkene alarak "
                "ana itki fazında aşırı yakıt sarfiyatını sınırlayınız."
            )
        else:
            recommended_touchdown_vz = "<= 1.5 m/s (NASA Artemis Standardı)"
            guidance_advice = (
                "Telemetri ve topoğrafik parametreler nominal. "
                "Standart Gravity Turn + 5. derece Apollo polinom profili ile güvenli temas öngörülmektedir."
            )

        return {
            "predicted_score": round(pred_score, 1),
            "predicted_fuel_consumed_kg": round(pred_fuel_cons, 1),
            "predicted_fuel_remaining_pct": round(pred_fuel_rem_pct, 1),
            "probabilities": prob_dict,
            "most_likely_outcome": most_likely_outcome,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "risk_status_tr": status_text,
            "guidance_margins": {
                "recommended_throttle_band": recommended_throttle_margin,
                "recommended_max_touchdown_vz_ms": recommended_touchdown_vz,
                "abort_gate_altitude_m": "35.0 m (Görsel Güdüm Kilidi)",
            },
            "advisory_text_tr": guidance_advice,
            "input_telemetry": {
                name: round(val, 2) for name, val in zip(self.feature_names, vector)
            },
        }

    def auto_train(self, min_samples: int = 15) -> bool:
        """Veritabanında yeterli kayıt varsa modeli eğitir."""
        stats = get_stats()
        if stats["total_trials"] < min_samples:
            seed_initial_trials(count=min_samples)
        try:
            self.train(force_seed=False, min_samples=min_samples)
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """ML Motoru durumunu, doğruluk metriklerini ve özellik önemini döner."""
        if not self.is_trained:
            self.auto_train()

        return {
            "is_trained": self.is_trained,
            "last_trained_at": self.last_trained_at,
            "training_samples": self.training_sample_count,
            "metrics": self.metrics,
            "feature_importance": self.feature_importance,
            "feature_labels_tr": FEATURE_LABELS_TR,
            "features_used": self.feature_names,
            "classes": CLASSES,
            "mode": "100% Pure NumPy Engine (Zero Dependency)",
        }

    def save_model(self, path: Optional[Union[str, Path]] = None) -> None:
        """Model ağırlıklarını ve parametrelerini JSON dosyasına kaydeder."""
        save_path = Path(path) if path else self.model_file
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0.0",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "training_samples": self.training_sample_count,
            "metrics": self.metrics,
            "feature_names": self.feature_names,
            "feature_importance": self.feature_importance,
            "scaler": self.scaler.to_dict(),
            "regressor": self.regressor.to_dict(),
            "classifier": self.classifier.to_dict(),
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_model(self, path: Optional[Union[str, Path]] = None) -> bool:
        """Kayıtlı modeli JSON dosyasından geri yükler."""
        load_path = Path(path) if path else self.model_file
        if not load_path.exists():
            return False

        try:
            with open(load_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.feature_names = data.get("feature_names", list(FEATURE_NAMES))
            self.feature_importance = data.get("feature_importance", {})
            self.metrics = data.get("metrics", {})
            self.training_sample_count = data.get("training_samples", 0)
            self.last_trained_at = data.get("saved_at")

            if "scaler" in data:
                self.scaler.from_dict(data["scaler"])
            if "regressor" in data:
                self.regressor.from_dict(data["regressor"])
            if "classifier" in data:
                self.classifier.from_dict(data["classifier"])

            self.is_trained = True
            return True
        except Exception:
            return False


# Küresel tekil ML Motoru örneği
ml_engine = MLEngine()
