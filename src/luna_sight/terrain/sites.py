"""Aday iniş bölgeleri koordinat ve referans kataloğu (K2).

Bu katalog, LUNA SIGHT projesindeki tüm modüller (K1 Horizons sorguları,
K3 görünürlük motoru, K4 kullanıcı arayüzü) için resmi ve doğrulanmış
aday iniş noktalarını sağlar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateSite:
    """K2 tarafından doğrulanan resmi aday iniş noktası."""

    site_id: str
    site_name: str
    latitude_deg: float
    longitude_deg_east: float
    x_m: float
    y_m: float
    description: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg_east": self.longitude_deg_east,
            "x_m": self.x_m,
            "y_m": self.y_m,
            "description": self.description,
        }


#: Projenin resmi aday iniş bölgeleri kataloğu.
CANDIDATE_SITES: dict[str, CandidateSite] = {
    "Site01": CandidateSite(
        site_id="Site01",
        site_name="Connecting ridge",
        latitude_deg=-89.463163,
        longitude_deg_east=222.510447,
        x_m=-11000.0,
        y_m=-12000.0,
        description="Shackleton ve de Gerlache kraterleri arasındaki bağlantı sırtı.",
    ),
    "Site04": CandidateSite(
        site_id="Site04",
        site_name="Shackleton rim",
        latitude_deg=-89.766811,
        longitude_deg_east=188.130102,
        x_m=-1000.0,
        y_m=-7000.0,
        description="Shackleton kraterinin güney sırtı ve zirve noktası.",
    ),
}


def get_candidate_site(site_id: str) -> CandidateSite:
    """Verilen kimliğe ait aday iniş bölgesini döndürür."""
    if site_id not in CANDIDATE_SITES:
        valid_keys = ", ".join(CANDIDATE_SITES.keys())
        raise KeyError(f"Bilinmeyen aday bölge '{site_id}'. Tanımlı bölgeler: {valid_keys}")
    return CANDIDATE_SITES[site_id]
