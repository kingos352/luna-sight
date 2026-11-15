"""
tests/test_ml_engine.py
=======================
Saf NumPy Tabanlı Makine Öğrenimi (ML) Motoru Birim ve Doğrulama Testleri.
"""

import tempfile
from pathlib import Path
import pytest
import numpy as np

from backend.ml_engine import (
    PureNumpyScaler,
    PureNumpyRidgeRegressor,
    PureNumpySoftmaxClassifier,
    MLEngine,
    compute_regression_metrics,
    compute_classification_metrics,
    FEATURE_NAMES,
    CLASSES,
)


def test_pure_numpy_scaler():
    """Ölçeklendirici fit ve transform testi."""
    X = np.array([[10.0, 100.0], [20.0, 200.0], [30.0, 300.0]])
    scaler = PureNumpyScaler()
    X_scaled = scaler.fit_transform(X)

    # Ortalama 0, varyans 1 olmalı
    assert np.allclose(np.mean(X_scaled, axis=0), [0.0, 0.0], atol=1e-7)
    assert np.allclose(np.std(X_scaled, axis=0), [1.0, 1.0], atol=1e-7)

    # Serileştirme ve geri yükleme
    s_dict = scaler.to_dict()
    scaler2 = PureNumpyScaler().from_dict(s_dict)
    X2_scaled = scaler2.transform(X)
    assert np.allclose(X_scaled, X2_scaled)


def test_pure_numpy_ridge_regression():
    """Kapalı form Ridge Regresyonu ve metrikler testi."""
    # Sentetik doğrusal veri: y = 2*x1 - 3*x2 + 5
    rng = np.random.default_rng(42)
    X = rng.normal(size=(100, 2))
    y = 2.0 * X[:, 0] - 3.0 * X[:, 1] + 5.0 + rng.normal(0.0, 0.1, size=100)

    reg = PureNumpyRidgeRegressor(alpha=0.1)
    reg.fit(X, y)
    y_pred = reg.predict(X).ravel()

    metrics = compute_regression_metrics(y, y_pred)
    assert metrics["r2"] > 0.95
    assert metrics["rmse"] < 0.2

    # Ağırlıkların doğruluğu
    assert abs(reg.weights_[0, 0] - 2.0) < 0.15
    assert abs(reg.weights_[1, 0] - (-3.0)) < 0.15


def test_pure_numpy_softmax_classifier():
    """Çok sınıflı Softmax sınıflandırıcı testi."""
    rng = np.random.default_rng(42)
    # 3 ayrık küme üret
    X0 = rng.normal(loc=[-3.0, -3.0], scale=0.5, size=(40, 2))
    X1 = rng.normal(loc=[0.0, 3.0], scale=0.5, size=(40, 2))
    X2 = rng.normal(loc=[3.0, -3.0], scale=0.5, size=(40, 2))

    X = np.vstack([X0, X1, X2])
    y = np.array(["SAFE"] * 40 + ["HARD"] * 40 + ["CRASH"] * 40)

    clf = PureNumpySoftmaxClassifier(learning_rate=0.1, epochs=300)
    clf.fit(X, y)

    probs = clf.predict_proba(X)
    assert probs.shape == (120, 3)
    # Olasılık toplamları 1.0 olmalı
    assert np.allclose(np.sum(probs, axis=1), 1.0)

    preds = clf.predict(X)
    metrics = compute_classification_metrics(y, preds)
    assert metrics["accuracy"] >= 0.90
    assert metrics["f1_macro"] >= 0.90


def test_ml_engine_lifecycle_and_risk_assessment():
    """Tüm MLEngine döngüsü: eğitim, özellik önemi ve risk kestirimi testi."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        model_file = Path(f.name)

    try:
        engine = MLEngine(model_file=model_file)
        # Zorunlu tohumlama ile eğit
        train_res = engine.train(force_seed=True, min_samples=30)
        assert train_res["status"] == "success"
        assert engine.is_trained is True
        assert model_file.exists()

        status = engine.get_status()
        assert status["is_trained"] is True
        assert len(status["feature_importance"]) == 8
        assert "slope_deg" in status["feature_importance"]

        # Risk Değerlendirmesi: Güvenli Koşullar
        safe_telemetry = {
            "initial_alt_m": 3200.0,
            "initial_vh_ms": 60.0,
            "initial_vv_ms": -26.0,
            "slope_deg": 2.5,
            "roughness_tri_m": 0.20,
            "solar_illum_pct": 95.0,
            "dte_vis_pct": 95.0,
            "total_mass_kg": 5000.0,
        }
        res_safe = engine.predict_risk(safe_telemetry)
        assert res_safe["predicted_score"] >= 75.0
        assert res_safe["risk_level"] in ["LOW", "MODERATE"]
        assert "guidance_margins" in res_safe
        assert "advisory_text_tr" in res_safe

        # Risk Değerlendirmesi: Tehlikeli Koşullar (Yüksek Eğim ve Pürüzlülük)
        danger_telemetry = {
            "initial_alt_m": 3500.0,
            "initial_vh_ms": 78.0,
            "initial_vv_ms": -45.0,
            "slope_deg": 18.5,
            "roughness_tri_m": 1.6,
            "solar_illum_pct": 10.0,
            "dte_vis_pct": 20.0,
            "total_mass_kg": 5000.0,
        }
        res_danger = engine.predict_risk(danger_telemetry)
        assert res_danger["predicted_score"] < res_safe["predicted_score"]
        assert res_danger["risk_level"] in ["HIGH", "CRITICAL"]

        # Modeli baştan yükleme testi
        engine_loaded = MLEngine(model_file=model_file)
        assert engine_loaded.is_trained is True
        assert engine_loaded.training_sample_count == engine.training_sample_count

        # Sayısal Kararlılık ve NaN/Inf Giriş Testi
        nan_telemetry = {
            "initial_alt_m": float("nan"),
            "initial_vh_ms": 60.0,
            "initial_vv_ms": -25.0,
            "slope_deg": 3.0,
            "roughness_tri_m": 0.2,
            "solar_illum_pct": 90.0,
            "dte_vis_pct": 90.0,
            "total_mass_kg": 5000.0,
        }
        res_nan = engine.predict_risk(nan_telemetry)
        assert res_nan["risk_level"] == "CRITICAL"
        assert res_nan["predicted_score"] == 0.0
        assert "NaN/Inf" in res_nan["risk_status_tr"]
    finally:
        if model_file.exists():
            try:
                model_file.unlink()
            except Exception:
                pass
