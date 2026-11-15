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


#: Projenin resmi aday iniş bölgeleri kataloğu (NASA Artemis III Aday İniş Bölgeleri).
CANDIDATE_SITES: dict[str, CandidateSite] = {
    "Site01": CandidateSite(
        site_id="Site01",
        site_name="Connecting ridge",
        latitude_deg=-89.463163,
        longitude_deg_east=-137.489553,
        x_m=-11000.0,
        y_m=-12000.0,
        description="Shackleton ve de Gerlache kraterleri arasındaki bağlantı sırtı.",
    ),
    "Site02": CandidateSite(
        site_id="Site02",
        site_name="Connecting ridge extension",
        latitude_deg=-89.300000,
        longitude_deg_east=-150.000000,
        x_m=-10613.3,
        y_m=-18382.8,
        description="Connecting Ridge uzantısı; elverişli aydınlanma ve PSR yakınlığı.",
    ),
    "Site03": CandidateSite(
        site_id="Site03",
        site_name="de Gerlache rim 1",
        latitude_deg=-88.500000,
        longitude_deg_east=-68.000000,
        x_m=-42175.4,
        y_m=17040.0,
        description="de Gerlache kraterinin kuzeybatı sırtı.",
    ),
    "Site04": CandidateSite(
        site_id="Site04",
        site_name="Shackleton rim",
        latitude_deg=-89.766811,
        longitude_deg_east=-171.869898,
        x_m=-1000.0,
        y_m=-7000.0,
        description="Shackleton kraterinin güney sırtı ve zirve noktası.",
    ),
    "Site05": CandidateSite(
        site_id="Site05",
        site_name="de Gerlache rim 2",
        latitude_deg=-88.710000,
        longitude_deg_east=-64.000000,
        x_m=-35159.7,
        y_m=17148.5,
        description="de Gerlache kraterinin güneydoğu sırtı.",
    ),
    "Site06": CandidateSite(
        site_id="Site06",
        site_name="de Gerlache-Kocher massif",
        latitude_deg=-85.800000,
        longitude_deg_east=-116.300000,
        x_m=-114225.9,
        y_m=-56454.0,
        description="de Gerlache ve Kocher kraterleri arasındaki masif dağ kütlesi.",
    ),
    "Site07": CandidateSite(
        site_id="Site07",
        site_name="Haworth",
        latitude_deg=-87.450000,
        longitude_deg_east=-5.000000,
        x_m=-6740.4,
        y_m=77043.0,
        description="Haworth krateri çevresi ve kalıcı gölgeli bölge (PSR) kenarları.",
    ),
    "Site08": CandidateSite(
        site_id="Site08",
        site_name="Malapert massif",
        latitude_deg=-86.000000,
        longitude_deg_east=2.700000,
        x_m=5716.0,
        y_m=121208.0,
        description="Malapert Dağı sırtı; Dünya ile yüksek görüş hattı ve iletişim avantajı.",
    ),
    "Site09": CandidateSite(
        site_id="Site09",
        site_name="Leibnitz beta plateau",
        latitude_deg=-85.200000,
        longitude_deg_east=33.000000,
        x_m=79319.7,
        y_m=122141.7,
        description="Leibnitz Beta yüksek platosu; geniş iniş alanı ve düz topoğrafya.",
    ),
    "Site11": CandidateSite(
        site_id="Site11",
        site_name="Nobile rim 2",
        latitude_deg=-84.100000,
        longitude_deg_east=59.700000,
        x_m=154604.8,
        y_m=90343.8,
        description="Nobile krateri doğu sırtı alternatifi.",
    ),
    "Site12": CandidateSite(
        site_id="Site12",
        site_name="Amundsen rim",
        latitude_deg=-84.500000,
        longitude_deg_east=85.000000,
        x_m=166271.5,
        y_m=14546.9,
        description="Amundsen krateri yüksek sırtı; antik kabuk materyali erişimi.",
    ),
    "Site13": CandidateSite(
        site_id="Site13",
        site_name="Mons Mouton",
        latitude_deg=-84.600000,
        longitude_deg_east=31.000000,
        x_m=84398.0,
        y_m=140461.8,
        description="Mons Mouton (Faustini Rim A) düz zirveli yüksek dağ platosu.",
    ),
}


def get_candidate_site(site_id: str) -> CandidateSite:
    """Verilen kimliğe ait aday iniş bölgesini döndürür."""
    if site_id not in CANDIDATE_SITES:
        valid_keys = ", ".join(CANDIDATE_SITES.keys())
        raise KeyError(f"Bilinmeyen aday bölge '{site_id}'. Tanımlı bölgeler: {valid_keys}")
    return CANDIDATE_SITES[site_id]
