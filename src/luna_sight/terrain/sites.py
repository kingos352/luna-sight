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
SITES_WITH_REGIONAL_DEM: tuple[str, ...] = ('Site01', 'Site04')


#: Aday bölge kataloğu. Ölçüm içermez; modül açıklamasına bakın.
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
    "MALAPERT_MASSIF": CandidateSite(
        site_id="MALAPERT_MASSIF",
        site_name="Malapert Massif",
        latitude_deg=-86.04,
        longitude_deg_east=2.7,
        x_m=5658.8,
        y_m=119994.9,
        operational_role="Artemis III Birincil İnsanlı İniş & Kalıcı Artemis Base Camp Ana Konumu",
        description=(
            "Ay güney kutbunun simgesi olan devasa dağ kütlesi. Zirve platosu sürekli güneş "
            "ve kesintisiz Dünya görüşü sunar."
        ),
    ),
    "CONNECTING_RIDGE_EXT": CandidateSite(
        site_id="CONNECTING_RIDGE_EXT",
        site_name="Connecting Ridge Extension",
        latitude_deg=-89.47,
        longitude_deg_east=-136.2,
        x_m=-11123.8,
        y_m=-11599.8,
        operational_role=(
            "Artemis III Mürettebatlı İniş & Geceleme Öncesi Solar İstasyon Konuşlandırma"
        ),
        description=(
            "Connecting Ridge sırtının batı uzantısındaki yüksek irtifa hattı. Shackleton ile "
            "de Gerlache kraterleri arasındaki geçit."
        ),
    ),
    "LEIBNITZ_BETA": CandidateSite(
        site_id="LEIBNITZ_BETA",
        site_name="Leibnitz Beta Plateau",
        latitude_deg=-85.82,
        longitude_deg_east=29.5,
        x_m=62443.2,
        y_m=110367.9,
        operational_role="Alternatif Artemis III İniş Platosu & Genişletilmiş Yüzey Keşif Üssü",
        description=(
            "Geniş ve son derece düşük eğimli plato alanı. Yüksek iniş güvenliği ve geniş "
            "hareket serbestisi sağlar."
        ),
    ),
    "DE_GERLACHE_RIM_1": CandidateSite(
        site_id="DE_GERLACHE_RIM_1",
        site_name="de Gerlache Rim 1",
        latitude_deg=-88.71,
        longitude_deg_east=-68.7,
        x_m=-36446.6,
        y_m=14209.9,
        operational_role="Bilimsel Keşif ve Kalıcı Gölge Bölgesi (PSR) Örnekleme Noktası",
        description=(
            "de Gerlache kraterinin doğu sırt hattı. Krater içine doğrudan robotik kol veya "
            "rover sortisi imkanı."
        ),
    ),
    "DE_GERLACHE_RIM_2": CandidateSite(
        site_id="DE_GERLACHE_RIM_2",
        site_name="de Gerlache Rim 2",
        latitude_deg=-88.35,
        longitude_deg_east=-67.8,
        x_m=-46327.8,
        y_m=18906.0,
        operational_role="Yedek İniş Bölgesi & Çift Görevli İletişim İstasyonu",
        description="de Gerlache kraterinin kuzeydoğu kenar platosu.",
    ),
    "AMUNDSEN_RIM": CandidateSite(
        site_id="AMUNDSEN_RIM",
        site_name="Amundsen Rim",
        latitude_deg=-84.45,
        longitude_deg_east=85.6,
        x_m=167929.9,
        y_m=12921.5,
        operational_role="Derin Krater Kenar Keşfi & Magmatik Malzeme İncelemesi",
        description=(
            "Devasa Amundsen kraterinin güneybatı sırtı. Teraslı duvar yapısı ve merkezi dağ "
            "kütlesi manzarası."
        ),
    ),
    "NOBILE_RIM_2": CandidateSite(
        site_id="NOBILE_RIM_2",
        site_name="Nobile Rim 2",
        latitude_deg=-85.28,
        longitude_deg_east=36.15,
        x_m=84478.1,
        y_m=115636.3,
        operational_role="Uçucu Madde Haritalama & Robotik-İnsanlı İş Birliği Üssü",
        description=(
            "Nobile kraterinin batı kenar platosu. VIPER keşif rotasıyla doğrudan entegrasyon "
            "potansiyeli."
        ),
    ),
    "DE_GERLACHE_KOCHER": CandidateSite(
        site_id="DE_GERLACHE_KOCHER",
        site_name="de Gerlache-Kocher Massif",
        latitude_deg=-85.78,
        longitude_deg_east=-123.35,
        x_m=-106940.7,
        y_m=-70380.6,
        operational_role="Yüksek İrtifa Radyo Röle İstasyonu & Uzun Dönemli Gözlem Noktası",
        description="de Gerlache ile Kocher arasındaki yüksek dağlık masif.",
    ),
    "HAWORTH": CandidateSite(
        site_id="HAWORTH",
        site_name="Haworth",
        latitude_deg=-87.87,
        longitude_deg_east=-5.1,
        x_m=-5742.2,
        y_m=64340.4,
        operational_role="Aşırı Düşük Sıcaklık Bilimsel İstasyonu (Kriyojenik Tuzaklar)",
        description=(
            "Haworth krateri kuzey kenarı. Güneş sisteminin en soğuk noktalarına sınır teşkil "
            "eder."
        ),
    ),
    "FAUSTINI_RIM": CandidateSite(
        site_id="FAUSTINI_RIM",
        site_name="Faustini Rim",
        latitude_deg=-86.4925,
        longitude_deg_east=80.7183,
        x_m=104999.4,
        y_m=17159.9,
        operational_role="Su Buzu Teyit Üssü & Kalıcı İletişim İstasyonu",
        description=(
            "Faustini kraterinin yüksek kuzey sırtı; düşük yamaç eğimi ve stabil radyo "
            "penceresi."
        ),
    ),
    "CABEUS_RIDGE": CandidateSite(
        site_id="CABEUS_RIDGE",
        site_name="Cabeus Ridge",
        latitude_deg=-83.7961,
        longitude_deg_east=-41.0726,
        x_m=-123720.5,
        y_m=141960.5,
        operational_role="LCROSS İmpakt Doğrulama Sahası & Volatil Madde Keşfi",
        description=(
            "Cabeus kraterini kuşatan yüksek sırt; Dünya ile sürekli doğrudan görüş hattına "
            "sahiptir."
        ),
    ),
    "SVERDRUP_RIM": CandidateSite(
        site_id="SVERDRUP_RIM",
        site_name="Sverdrup Rim",
        latitude_deg=-89.4455,
        longitude_deg_east=-137.3137,
        x_m=-11400.0,
        y_m=-12360.0,
        operational_role="Alternatif İnsanlı & Otonom Güvenli İniş Limanı",
        description="Sverdrup kraterinin yüksek sırt platosu; düşük eğimli aday ayak basma alanı.",
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
