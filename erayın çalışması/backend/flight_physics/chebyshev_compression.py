"""
backend/flight_physics/chebyshev_compression.py
===============================================
Chebyshev Polinomu Uçuş ve Yörünge Açısı Sıkıştırma Modülü.

Gereksinim:
- fit_chebyshev_series(timestamps, angles, degree=8) -> list[float]
- evaluate_chebyshev(coeffs, t_normalized) -> float (O(1) sürede anlık açı, hata < 0.005°)

Chebyshev polinom serileri T_n(x), özellikle uzay aviyonik sistemlerinde (JPL ephemeris DE405/DE421 formatı)
yörüngesel açıları (Güneş azimut/yükselme, Dünya görüş açıları, iniş yönelim açıları)
minimum Runge salınımı ve minimax yaklaşım hatası ile sıkıştırmak için kullanılır.
"""

from __future__ import annotations
from typing import Sequence, Union, Tuple, Dict, Any
import numpy as np


def normalize_timestamps(
    timestamps: Sequence[float],
    t_min: float | None = None,
    t_max: float | None = None,
) -> Tuple[np.ndarray, float, float]:
    """
    Zaman damgalarını Chebyshev polinom tanım aralığı olan [-1.0, +1.0] aralığına normalize eder.

    Dönüş:
        (t_norm, t_min, t_max)
    """
    ts = np.asarray(timestamps, dtype=np.float64)
    if len(ts) == 0:
        raise ValueError("Zaman damgası dizisi boş olamaz.")

    actual_min = float(np.min(ts)) if t_min is None else float(t_min)
    actual_max = float(np.max(ts)) if t_max is None else float(t_max)

    if actual_max <= actual_min:
        # Tek nokta veya sıfır zaman aralığı
        return np.zeros_like(ts), actual_min, actual_max

    t_norm = 2.0 * (ts - actual_min) / (actual_max - actual_min) - 1.0
    return np.clip(t_norm, -1.0, 1.0), actual_min, actual_max


def fit_chebyshev_series(
    timestamps: Sequence[float],
    angles: Sequence[float],
    degree: int = 8,
) -> list[float]:
    """
    Verilen zaman damgaları ve açı serisini belirtilen derecede Chebyshev polinomuna uydurur.

    Parametreler:
        timestamps: Zaman serisi (saniye, saat veya normalize edilmiş değerler)
        angles: Yörüngesel veya yönelim açıları (derece)
        degree: Polinom derecesi (varsayılan: 8)

    Dönüş:
        list[float]: Chebyshev katsayıları [c0, c1, ..., c_degree]
    """
    ts = np.asarray(timestamps, dtype=np.float64)
    ang = np.asarray(angles, dtype=np.float64)

    if len(ts) != len(ang):
        raise ValueError(f"Zaman damgası uzunluğu ({len(ts)}) ile açı uzunluğu ({len(ang)}) eşleşmiyor.")
    if len(ts) <= degree:
        degree = max(1, len(ts) - 1)

    # Eğer timestamps zaten [-1, 1] aralığında değilse normalize et
    if np.min(ts) < -1.0001 or np.max(ts) > 1.0001 or (np.min(ts) >= 0.0 and np.max(ts) > 1.0):
        t_norm, _, _ = normalize_timestamps(ts)
    else:
        t_norm = np.clip(ts, -1.0, 1.0)

    # Chebyshev fit (np.polynomial.chebyshev.chebfit)
    coeffs = np.polynomial.chebyshev.chebfit(t_norm, ang, deg=degree)
    return [float(c) for c in coeffs]


def evaluate_chebyshev(coeffs: Sequence[float], t_normalized: float) -> float:
    """
    Clenshaw algoritması ile O(1) sabit sürede normalize zaman damgasında (t in [-1, 1])
    Chebyshev polinomunu hesaplar. Orijinal seriye göre hata < 0.005°.

    Parametreler:
        coeffs: Chebyshev katsayıları dizisi [c0, c1, ..., c_n]
        t_normalized: [-1.0, 1.0] aralığında normalleştirilmiş zaman

    Dönüş:
        float: Hesaplanmış açı değeri (derece)
    """
    if len(coeffs) == 0:
        return 0.0

    # Sınır kırpma
    x = float(np.clip(t_normalized, -1.0, 1.0))

    # Clenshaw algoritması (Numerik kararlılık ve O(1) hız)
    # b_{k} = 2*x*b_{k+1} - b_{k+2} + c_k
    # Sonuç: c0 + x*b1 - b2
    c = np.asarray(coeffs, dtype=np.float64)
    n = len(c) - 1

    b1 = 0.0
    b2 = 0.0
    two_x = 2.0 * x

    for k in range(n, 0, -1):
        b0 = two_x * b1 - b2 + c[k]
        b2 = b1
        b1 = b0

    result = x * b1 - b2 + c[0]
    return float(result)


class ChebyshevTrajectoryCompressor:
    """
    Uçuş açısı ve efemeris serilerini Chebyshev katsayıları olarak saklayan ve
    yüksek verimle dekompresyon sağlayan aviyonik sıkıştırıcı sınıfı.
    """

    def __init__(self, degree: int = 8):
        self.degree = degree
        self.coeffs: list[float] = []
        self.t_min: float = 0.0
        self.t_max: float = 1.0
        self.max_residual_deg: float = 0.0

    def compress(
        self,
        timestamps: Sequence[float],
        angles: Sequence[float],
    ) -> Dict[str, Any]:
        """Seriyi sıkıştırır ve katsayılar ile sıkıştırma metriklerini döner."""
        ts = np.asarray(timestamps, dtype=np.float64)
        ang = np.asarray(angles, dtype=np.float64)

        t_norm, self.t_min, self.t_max = normalize_timestamps(ts)
        self.coeffs = fit_chebyshev_series(t_norm, ang, degree=self.degree)

        # Hata analizi
        reconstructed = np.array([evaluate_chebyshev(self.coeffs, tn) for tn in t_norm])
        residuals = np.abs(ang - reconstructed)
        self.max_residual_deg = float(np.max(residuals)) if len(residuals) > 0 else 0.0
        mean_residual_deg = float(np.mean(residuals)) if len(residuals) > 0 else 0.0

        original_bytes = len(ang) * 8
        compressed_bytes = len(self.coeffs) * 8 + 16  # coeffs + t_min/t_max
        compression_ratio = original_bytes / max(compressed_bytes, 1)

        return {
            "degree": self.degree,
            "coeffs": self.coeffs,
            "t_min": self.t_min,
            "t_max": self.t_max,
            "max_residual_deg": self.max_residual_deg,
            "mean_residual_deg": mean_residual_deg,
            "compression_ratio": compression_ratio,
            "accuracy_passed": bool(self.max_residual_deg < 0.005),
        }

    def decompress(self, t: float) -> float:
        """Herhangi bir t zamanında anlık açıyı O(1) sürede döner."""
        if self.t_max <= self.t_min:
            t_norm = 0.0
        else:
            t_norm = 2.0 * (t - self.t_min) / (self.t_max - self.t_min) - 1.0
        return evaluate_chebyshev(self.coeffs, t_norm)
