"""K2 ufuk profilinin azimut → yükseklik araması.

K3 motoru, K1'den gelen azimut/yükseklik serisindeki her örnek için o
azimuta karşılık gelen topoğrafik ufku bu modülden alır. Profil 0–360°
arasında dairesel olduğu için 359° ile 1° arasındaki geçiş enterpolasyonla
kapatılır.

Profilde eksik (``NaN``) bir bölge varsa, o bölgeye düşen sorgular ``None``
döner; motor bunu ``uncertain`` olarak raporlar.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np


class HorizonProfileLookup:
    """Azimut bazlı ufuk profili (derece) üzerinde dairesel arama."""

    def __init__(self, azimuth_deg, horizon_deg) -> None:
        az = np.asarray(azimuth_deg, dtype=float).ravel()
        el = np.asarray(horizon_deg, dtype=float).ravel()
        if az.shape != el.shape:
            raise ValueError("azimuth_deg ve horizon_deg aynı uzunlukta olmalı.")
        if az.size < 2:
            raise ValueError("Profil en az iki nokta içermeli.")

        order = np.argsort(az, kind="stable")
        az, el = az[order], el[order]
        if np.any(np.diff(az) <= 0.0):
            raise ValueError("azimuth_deg tekrar eden değer içermemeli.")
        if np.isfinite(el).sum() < 2:
            raise ValueError("Profilde en az iki geçerli ufuk değeri olmalı.")
        if az.min() < 0.0 or az.max() >= 360.0 + 1e-9:
            raise ValueError("azimuth_deg [0, 360) aralığında olmalı.")

        self._az = az
        self._el = el
        # Dairesel arama için diziyi her iki yönde birer tur genişlet.
        self._az_ext = np.concatenate([az - 360.0, az, az + 360.0])
        self._el_ext = np.concatenate([el, el, el])

    # ------------------------------------------------------------------ kurulum
    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        azimuth_column: str = "azimuth_deg",
        horizon_column: str = "horizon_deg",
    ) -> "HorizonProfileLookup":
        """K2 çıktısındaki profil CSV'sini yükler."""
        azimuths: list[float] = []
        horizons: list[float] = []
        with Path(path).open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or azimuth_column not in reader.fieldnames:
                raise ValueError(f"{path}: {azimuth_column} sütunu yok.")
            if horizon_column not in reader.fieldnames:
                raise ValueError(f"{path}: {horizon_column} sütunu yok.")
            for row in reader:
                azimuths.append(float(row[azimuth_column]))
                raw = row[horizon_column]
                horizons.append(float(raw) if raw not in ("", None) else math.nan)
        return cls(azimuths, horizons)

    # ------------------------------------------------------------------ sorgu
    def elevation_at(self, azimuth_deg: float) -> float | None:
        """Tek bir azimut için ufuk yüksekliği; veri yoksa ``None``."""
        value = float(np.interp(float(azimuth_deg) % 360.0, self._az_ext, self._el_ext))
        return None if math.isnan(value) else value

    def elevations_at(self, azimuths) -> np.ndarray:
        """Vektörel sorgu; bilinmeyen azimutlar ``NaN`` döner."""
        az = np.asarray(azimuths, dtype=float) % 360.0
        return np.interp(az, self._az_ext, self._el_ext)

    @property
    def azimuths(self) -> np.ndarray:
        return self._az.copy()

    @property
    def horizons(self) -> np.ndarray:
        return self._el.copy()

    @property
    def valid_fraction(self) -> float:
        return float(np.isfinite(self._el).mean())

    def summary(self) -> dict[str, float]:
        finite = self._el[np.isfinite(self._el)]
        return {
            "points": int(self._az.size),
            "valid_points": int(finite.size),
            "valid_fraction": round(self.valid_fraction, 4),
            "horizon_min_deg": round(float(finite.min()), 4),
            "horizon_max_deg": round(float(finite.max()), 4),
        }
