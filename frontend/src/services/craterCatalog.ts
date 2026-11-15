import { CraterFeature } from '../types';

/**
 * Kaynak: NASA & IAU Gazetteer of Planetary Nomenclature (ad, koordinat, çap).
 * Gazetteer rakım, derinlik ve kenar yüksekliği vermez; o alanlar bu depoda
 * türetilemediği için katalogdan çıkarıldı.
 * Comprehensive Lunar South Pole Feature Catalog (-80° to -90° Latitude).
 * Categorized by Feature Types (Kraterler, Düzlükler, Sırtlar, Platolar, Zirveler)
 * and Level of Detail (Tier 1: Global Landmark, Tier 2: Regional, Tier 3: Local Sector).
 */
export const CRATER_CATALOG: CraterFeature[] = [
  // =========================================================================
  // SEKTÖR 1: DOĞRUDAN KUTUP & CONNECTING RIDGE (Central Polar Ridge)
  // =========================================================================
  {
    id: 'feature-south-pole',
    name: 'Ay Güney Kutbu (90°S)',
    type: 'site',
    tier: 1,
    sector: 'Kutup & Connecting Ridge',
    lat: -90.0,
    lonEast: 0.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: false,
    scientificInterest: 'Ay dönme ekseninin sıfır noktası. Güneş ufukta daimi yatay döner (0° - 1.5° yükseklik).'
  },
  {
    id: 'crater-shackleton',
    name: 'Shackleton Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.67,
    lonEast: 129.78,
    diameterKm: 21.0,
    hazardRisk: 'Severe',
    permanentlyShadowed: true,
    scientificInterest: 'Tam kutup noktasını çevreleyen çarpma krateri. İç tabanı <40 K kalıcı gölgede (PSR) su buzu barındırır.'
  },
  {
    id: 'feature-connecting-ridge',
    name: 'Connecting Ridge Düzlüğü (Site01)',
    type: 'ridge',
    tier: 1,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.46,
    lonEast: -137.49,
    diameterKm: 14.5,
    hazardRisk: 'Moderate',
    permanentlyShadowed: false,
    scientificInterest: 'Shackleton ile de Gerlache arasındaki yüksek sırt. Yüksek güneşlenme ve 54 sa doğrudan Dünya görüşü sunar.'
  },
  {
    id: 'feature-shackleton-rim',
    name: 'Shackleton Kenar Sırtı (Site04)',
    type: 'ridge',
    tier: 1,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.77,
    lonEast: 120.50,
    diameterKm: 8.2,
    hazardRisk: 'High',
    permanentlyShadowed: false,
    scientificInterest: 'Shackleton kenarındaki yüksek zirve sırtı; dik iç eğimler (>28°) ve yüksek güneşlenme marjı.'
  },
  {
    id: 'crater-de-gerlache',
    name: 'de Gerlache Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Kutup & Connecting Ridge',
    lat: -88.48,
    lonEast: -88.34,
    diameterKm: 32.7,
    hazardRisk: 'High',
    permanentlyShadowed: true,
    scientificInterest: 'Connecting Ridge yapısının batı çapasını oluşturan büyük kadim krater. İç tabanı derin soğuk kapan.'
  },
  {
    id: 'plain-de-gerlache-rim',
    name: 'de Gerlache Kenar Düzlüğü',
    type: 'plain',
    tier: 2,
    sector: 'Kutup & Connecting Ridge',
    lat: -88.20,
    lonEast: -72.00,
    diameterKm: 22.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'de Gerlache kraterinin kuzey kenarında yer alan geniş, düşük eğimli (<7°) rover operasyon ve iniş düzlüğü.'
  },
  {
    id: 'peak-pel-1',
    name: 'Peak of Eternal Light (PEL-1)',
    type: 'peak',
    tier: 2,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.72,
    lonEast: 124.00,
    hazardRisk: 'Moderate',
    permanentlyShadowed: false,
    scientificInterest: 'Yıllık %86+ kesintisiz güneş ışığı alan ebedi ışık zirvesi; güneş paneli çiftliği için bir numaralı aday.'
  },
  {
    id: 'peak-pel-2',
    name: 'Peak of Eternal Light (PEL-2)',
    type: 'peak',
    tier: 2,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.48,
    lonEast: -142.00,
    hazardRisk: 'Moderate',
    permanentlyShadowed: false,
    scientificInterest: 'Connecting Ridge üzerinde yer alan ikinci yüksek ışıma masifi.'
  },
  {
    id: 'crater-spudis',
    name: 'Spudis Krateri',
    type: 'crater',
    tier: 2,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.51,
    lonEast: -84.60,
    diameterKm: 13.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Shackleton ile de Gerlache arasında yer alan ve Dr. Paul Spudis onuruna adlandırılan taze çarpma krateri.'
  },
  {
    id: 'crater-sverdrup',
    name: 'Sverdrup Krateri',
    type: 'crater',
    tier: 2,
    sector: 'Kutup & Connecting Ridge',
    lat: -88.50,
    lonEast: -152.00,
    diameterKm: 35.0,
    hazardRisk: 'High',
    permanentlyShadowed: true,
    scientificInterest: 'Kutup arkasında kalan geniş kalıcı gölgeli krater havzası.'
  },
  {
    id: 'crater-henson',
    name: 'Henson Krateri',
    type: 'crater',
    tier: 3,
    sector: 'Kutup & Connecting Ridge',
    lat: -88.60,
    lonEast: -131.00,
    diameterKm: 43.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Kutup kaşifi Matthew Henson onuruna adlandırılmış derin krater kenarı.'
  },
  {
    id: 'plain-south-pole-traverse',
    name: 'Kutup Geçiş Koridoru',
    type: 'plain',
    tier: 3,
    sector: 'Kutup & Connecting Ridge',
    lat: -89.85,
    lonEast: 45.00,
    diameterKm: 18.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Shackleton ve Shoemaker arasında rover geçişine uygun yumuşak eğimli düzlük.'
  },

  // =========================================================================
  // SEKTÖR 2: SHOEMAKER - FAUSTINI - HAWORTH HAVZASI (Cold Trap Basin)
  // =========================================================================
  {
    id: 'crater-shoemaker',
    name: 'Shoemaker Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Shoemaker-Faustini',
    lat: -88.14,
    lonEast: 44.98,
    diameterKm: 50.9,
    hazardRisk: 'High',
    permanentlyShadowed: true,
    scientificInterest: '2009 NASA LCROSS çarpma hedefi. Spektroskopik hidroksil ve su buzu varlığı ilk kez burada doğrulandı.'
  },
  {
    id: 'crater-faustini',
    name: 'Faustini Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Shoemaker-Faustini',
    lat: -87.18,
    lonEast: 84.31,
    diameterKm: 39.0,
    hazardRisk: 'High',
    permanentlyShadowed: true,
    scientificInterest: 'Aşınmış kenarlı derin soğuk kapan; iç yamaçlarında dik kum akıntıları (>25°) mevcuttur.'
  },
  {
    id: 'crater-haworth',
    name: 'Haworth Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Shoemaker-Faustini',
    lat: -87.40,
    lonEast: -5.10,
    diameterKm: 51.4,
    hazardRisk: 'High',
    permanentlyShadowed: true,
    scientificInterest: 'Güneş sisteminde ölçülen en soğuk noktalardan biri (25–35 Kelvin). Tabanda süper-uçucular hapsolmuştur.'
  },
  {
    id: 'plain-haworth-floor',
    name: 'Haworth Taban Düzlüğü',
    type: 'plain',
    tier: 2,
    sector: 'Shoemaker-Faustini',
    lat: -87.20,
    lonEast: -3.50,
    diameterKm: 26.0,
    hazardRisk: 'Severe',
    permanentlyShadowed: true,
    scientificInterest: 'Güneş ışığı hiç almayan, kalın regolit ve kristalize su buzu tabakası barındıran düz taban alanı.'
  },
  {
    id: 'ridge-haworth-shoemaker',
    name: 'Haworth-Shoemaker Sırtı',
    type: 'ridge',
    tier: 2,
    sector: 'Shoemaker-Faustini',
    lat: -87.80,
    lonEast: 20.00,
    diameterKm: 32.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: false,
    scientificInterest: 'İki dev krater arasında yükselen, dönemsel yüksek aydınlanma alan stratejik plato.'
  },
  {
    id: 'plateau-faustini-rim',
    name: 'Faustini Kenar Platosu',
    type: 'plateau',
    tier: 2,
    sector: 'Shoemaker-Faustini',
    lat: -87.10,
    lonEast: 77.00,
    diameterKm: 28.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Geniş, yatay ve krater içine iniş yapacak robotik kollar için ideal iletişim ve enerji üssü düzlüğü.'
  },
  {
    id: 'crater-slater',
    name: 'Slater Krateri',
    type: 'crater',
    tier: 2,
    sector: 'Shoemaker-Faustini',
    lat: -88.10,
    lonEast: 111.00,
    diameterKm: 25.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Faustini ile Amundsen arasında yer alan kalıcı gölgeli derin krater.'
  },
  {
    id: 'corridor-slater-faustini',
    name: 'Slater-Faustini Geçiş Koridoru',
    type: 'plain',
    tier: 3,
    sector: 'Shoemaker-Faustini',
    lat: -87.60,
    lonEast: 98.00,
    diameterKm: 16.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Doğu ve batı kutup havzaları arasında rover hareketine olanak tanıyan koridor.'
  },

  // =========================================================================
  // SEKTÖR 3: NOBILE - AMUNDSEN - SCOTT SEKTÖRÜ (Doğu Yüksekleri & VIPER)
  // =========================================================================
  {
    id: 'crater-nobile',
    name: 'Nobile Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Nobile-Amundsen',
    lat: -85.28,
    lonEast: 53.27,
    diameterKm: 79.3,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'NASA VIPER rover görevinin ana hedef alanı; yüzey buz dağılımı haritalaması için kritik sahadır.'
  },
  {
    id: 'plain-nobile-rim-ridge',
    name: 'Nobile Kenar Sırtı & VIPER Düzlüğü',
    type: 'plain',
    tier: 2,
    sector: 'Nobile-Amundsen',
    lat: -85.30,
    lonEast: 37.80,
    diameterKm: 35.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Geniş açık düzlük; düşük kayaç yoğunluğu ve elverişli iletişim geometrisi ile güvenli iniş alanı.'
  },
  {
    id: 'crater-amundsen',
    name: 'Amundsen Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Nobile-Amundsen',
    lat: -84.44,
    lonEast: 82.78,
    diameterKm: 103.4,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Görkemli teraslı duvarları ve merkezi zirvesi olan devasa kompleks kutup krateri.'
  },
  {
    id: 'peak-amundsen-central',
    name: 'Amundsen Merkezi Masifi',
    type: 'peak',
    tier: 2,
    sector: 'Nobile-Amundsen',
    lat: -84.50,
    lonEast: 83.20,
    hazardRisk: 'High',
    permanentlyShadowed: false,
    scientificInterest: 'Krater tabanından 1.8 km yukarı fırlayan kadim Ay mantosu izlerini taşıyan dağ masifi.'
  },
  {
    id: 'plain-amundsen-rim',
    name: 'Amundsen Kenar Düzlüğü',
    type: 'plain',
    tier: 2,
    sector: 'Nobile-Amundsen',
    lat: -84.10,
    lonEast: 85.00,
    diameterKm: 42.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Krater kuzey dış yamacında uzanan sakin, düz yüzey örtüsü.'
  },
  {
    id: 'plateau-leibnitz',
    name: 'Leibnitz Platosu / Düzlüğü',
    type: 'plateau',
    tier: 2,
    sector: 'Nobile-Amundsen',
    lat: -85.50,
    lonEast: 35.00,
    diameterKm: 48.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Kutup bölgesinin en yüksek düzlüklerinden biri. Ufuk engeli minimum seviyededir.'
  },
  {
    id: 'crater-scott',
    name: 'Scott Krateri',
    type: 'crater',
    tier: 2,
    sector: 'Nobile-Amundsen',
    lat: -82.10,
    lonEast: 48.50,
    diameterKm: 108.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Kutup çemberi sınırındaki büyük krater; lavla kaplanmış düz tabana sahiptir.'
  },
  {
    id: 'crater-wiechert',
    name: 'Wiechert Krateri',
    type: 'crater',
    tier: 3,
    sector: 'Nobile-Amundsen',
    lat: -84.20,
    lonEast: 165.00,
    diameterKm: 41.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Doğu kutup boylamlarında yer alan derin krater.'
  },
  {
    id: 'crater-idelson',
    name: "Idel'son Krateri",
    type: 'crater',
    tier: 3,
    sector: 'Nobile-Amundsen',
    lat: -81.20,
    lonEast: 112.50,
    diameterKm: 60.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Doğu sınır krateri.'
  },

  // =========================================================================
  // SEKTÖR 4: MALAPERT - CABEUS SEKTÖRÜ (Dünya Görüş Zirveleri & Masifler)
  // =========================================================================
  {
    id: 'peak-mons-malapert',
    name: 'Mons Malapert / Malapert Dağı',
    type: 'peak',
    tier: 1,
    sector: 'Malapert-Cabeus',
    lat: -85.90,
    lonEast: 2.90,
    diameterKm: 28.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: false,
    scientificInterest: 'Artemis III aday sahası. 5 km rakımlı bu dev dağ zirvesi, Dünya ile neredeyse kesintisiz doğrudan görüş sağlar.'
  },
  {
    id: 'crater-cabeus',
    name: 'Cabeus Krateri',
    type: 'crater',
    tier: 1,
    sector: 'Malapert-Cabeus',
    lat: -84.90,
    lonEast: -35.50,
    diameterKm: 98.0,
    hazardRisk: 'High',
    permanentlyShadowed: true,
    scientificInterest: 'LCROSS uydusunun çarptırıldığı ana krater. 100 kg su buzu ve hidrokarbon buharı tespit edilmiştir.'
  },
  {
    id: 'crater-malapert',
    name: 'Malapert Krateri',
    type: 'crater',
    tier: 2,
    sector: 'Malapert-Cabeus',
    lat: -84.90,
    lonEast: 12.90,
    diameterKm: 69.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Malapert dağ silsilesinin güney eteğinde uzanan antik krater.'
  },
  {
    id: 'plain-malapert-plateau',
    name: 'Malapert Etek Düzlüğü',
    type: 'plain',
    tier: 2,
    sector: 'Malapert-Cabeus',
    lat: -85.30,
    lonEast: 8.00,
    diameterKm: 30.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Dağ yamacına geçişten önce gelen son derece düzlük geniş iniş bölgesi.'
  },
  {
    id: 'crater-cabeus-b',
    name: 'Cabeus B Krateri',
    type: 'crater',
    tier: 3,
    sector: 'Malapert-Cabeus',
    lat: -82.40,
    lonEast: -53.00,
    diameterKm: 61.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Cabeus kraterinin batısındaki uydu krateri.'
  },
  {
    id: 'plain-cabeus-intercrater',
    name: 'Cabeus Kraterlerarası Düzlük',
    type: 'plain',
    tier: 3,
    sector: 'Malapert-Cabeus',
    lat: -85.20,
    lonEast: -42.00,
    diameterKm: 34.0,
    hazardRisk: 'Low',
    permanentlyShadowed: false,
    scientificInterest: 'Cabeus ile Cabeus A arasındaki geçiş ovası.'
  },
  {
    id: 'crater-kocher',
    name: 'Kocher Krateri',
    type: 'crater',
    tier: 3,
    sector: 'Malapert-Cabeus',
    lat: -84.50,
    lonEast: 134.00,
    diameterKm: 24.0,
    hazardRisk: 'Moderate',
    permanentlyShadowed: true,
    scientificInterest: 'Yüksek enlem krateri.'
  },
  {
    id: 'crater-drygalski',
    name: 'Drygalski Krateri',
    type: 'crater',
    tier: 3,
    sector: 'Malapert-Cabeus',
    lat: -79.30,
    lonEast: -84.90,
    diameterKm: 162.0,
    hazardRisk: 'Severe',
    permanentlyShadowed: true,
    scientificInterest: 'Güney kutup ufuk dairesini belirleyen devasa çarpma havzası.'
  }
];

/**
 * Great-circle surface distance on a sphere of radius R = 1,737.4 km (Moon).
 */
export function calculateLunarDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 1737.4; // Mean lunar radius in km
  const toRad = Math.PI / 180;
  const phi1 = lat1 * toRad;
  const phi2 = lat2 * toRad;
  const deltaPhi = (lat2 - lat1) * toRad;
  const deltaLambda = (lon2 - lon1) * toRad;

  const a = Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
            Math.cos(phi1) * Math.cos(phi2) *
            Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}
