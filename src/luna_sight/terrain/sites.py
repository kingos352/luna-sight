"""Aday iniş bölgeleri kimlik ve konum kataloğu.

Bu katalog **ölçüm taşımaz**. Yalnızca bölge kimliği ve konumu burada
durur: `site_id`, `site_name`, enlem, doğu-pozitif boylam ve kutup
stereografik `x_m`/`y_m`.

Yükseklik, eğim, pürüzlülük, güneşlenme yüzdesi, Dünya görüş yüzdesi ve
uygunluk puanı alanları varsayılan olarak `None`'dır ve **doğrulanmış bir
ürüne bağlanmadan doldurulmaz**. Bu alanlara elle sayı yazmak, ölçülmüş
bir değermiş gibi görünen ama hiçbir hesaptan gelmeyen bir iddia üretir;
`0.0` yazmak da aynı iddianın başka kılığıdır. Bu yüzden tip
`float | None` ve varsayılan `None`.

Ölçülmüş değerlerin tek kaynağı `outputs/` altındaki ürünlerdir:

- `outputs/k2/<site>_summary.json`  — LRO/LOLA 5 m/piksel DEM'den ufuk
  profili, kapsam oranı ve kalite bayrağı (`source_id: pgda-lola-5mpp`)
- `outputs/k3/<site>_summary.json`  — görünürlük durumları, pencereler,
  ortak görünürlük oranı

Bölgesel DEM karosu yalnızca `Site01` ve `Site04` için mevcut
(`data/cache/lola/<site>_final_adj_5mpp_surf.tif`). Kalan bölgeler
konum bağlamıdır: haritada yer gösterirler, ölçüm sağlamazlar.

Konum tutarlılığı: `x_m`/`y_m`, kutup stereografik izdüşümünde
`latitude_deg`/`longitude_deg_east` değerinden türetilir
(`luna_sight.terrain.polar.lonlat_to_xy`). Katalog ilk hâlinde 14
bölgenin 11'inde bu ikisi birbiriyle çelişiyordu; sapma `CABEUS_RIDGE`
için 202 km'ye çıkıyordu. Enlem/boylam atıf verilebilir nicelik olduğu
için türetilmiş `x_m`/`y_m` yeniden hesaplandı. `tests/test_terrain_sites.py`
bu tutarlılığı tüm bölgeler için ±50 m toleransla denetler.

Kimlik uyarısı: bu liste NASA'nın Artemis III resmi aday bölge listesi
**değildir**. Gerçek yer adları (Shackleton, Sverdrup, Haworth, Cabeus…)
literatürden alınmıştır; o adların bu depoda doğrulanmış bir ölçümü
olduğu anlamına gelmez.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateSite:
    """Aday iniş bölgesinin kimliği ve konumu.

    Ölçüm alanları `None` kalır; değer yalnızca doğrulanmış bir üründen
    gelir. Modül açıklamasına bakın.
    """

    site_id: str
    site_name: str
    latitude_deg: float
    longitude_deg_east: float
    x_m: float
    y_m: float
    elevation_m: float | None = None
    slope_deg: float | None = None
    roughness_tri_m: float | None = None
    solar_pct: float | None = None
    dte_pct: float | None = None
    suitability_score: float | None = None
    operational_role: str = ""
    description: str = ""

    @property
    def has_measurements(self) -> bool:
        """Bu bölge için katalogda bağlanmış bir ölçüm var mı."""
        return any(
            value is not None
            for value in (
                self.elevation_m,
                self.slope_deg,
                self.roughness_tri_m,
                self.solar_pct,
                self.dte_pct,
                self.suitability_score,
            )
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg_east": self.longitude_deg_east,
            "x_m": self.x_m,
            "y_m": self.y_m,
            "elevation_m": self.elevation_m,
            "slope_deg": self.slope_deg,
            "roughness_tri_m": self.roughness_tri_m,
            "solar_pct": self.solar_pct,
            "dte_pct": self.dte_pct,
            "suitability_score": self.suitability_score,
            "operational_role": self.operational_role,
            "description": self.description,
        }


#: Bölgesel 5 m/piksel LOLA DEM karosu bulunan bölgeler.
SITES_WITH_REGIONAL_DEM: tuple[str, ...] = ("Site01", "Site04")


#: Projenin resmi aday iniş bölgeleri kataloğu (NASA Artemis III; ölçüm içermez).
CANDIDATE_SITES: dict[str, CandidateSite] = {
    "Site01": CandidateSite(
        site_id="Site01",
        site_name="Connecting ridge",
        latitude_deg=-89.463163,
        longitude_deg_east=-137.489553,
        x_m=-11000.0,
        y_m=-12000.0,
        operational_role="Artemis III Mürettebatlı İniş & Geceleme Öncesi Solar İstasyon",
        description=(
            "Shackleton ve de Gerlache kraterleri arasındaki tepe sırtı. Güneş ve Dünya "
            "erişimi dengeli."
        ),
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
        operational_role="Kalıcı Gölge (PSR) Keşif & Solar Zirve Konuşlandırma",
        description=(
            "Shackleton krater kenarı. Sürekli Güneş ışığı yüksek ancak Dünya görüşü krater "
            "duvarı ile engelli."
        ),
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
        raise KeyError(f"Bilinmeyen bölge kimliği: {site_id}")
    return CANDIDATE_SITES[site_id]


def list_candidate_sites() -> list[CandidateSite]:
    """Tüm aday bölgeleri döndürür."""
    return list(CANDIDATE_SITES.values())
