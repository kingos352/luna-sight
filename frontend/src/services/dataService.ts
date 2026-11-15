import { assetUrl } from './assetUrl';
import {
  SiteId,
  HorizonScenario,
  SiteWindowsData,
  SiteSummary,
  HorizonProfile,
  TerrainMeshData,
  SurveyCaseData,
  EphemerisPoint,
  VisibilityState,
  CraterFeature
} from '../types';

export const SITES: Record<string, { id: any; name: string; nameTr: string; lat: number; lonEast: number; elevationM: number; description: string }> = {
  Site01: {
    id: 'Site01',
    name: 'Connecting ridge',
    nameTr: 'Connecting Ridge',
    lat: -89.463163,
    lonEast: -137.489553,
    elevationM: 1944.77,
    description: 'Shackleton ve de Gerlache kraterleri arasındaki tepe sırtı. Güneş ve Dünya erişimi dengeli.'
  },
  Site04: {
    id: 'Site04',
    name: 'Shackleton rim',
    nameTr: 'Shackleton Rim',
    lat: -89.766811,
    lonEast: -171.869898,
    elevationM: 1980.50,
    description: 'Shackleton krater kenarı. Sürekli Güneş ışığı yüksek ancak Dünya görüşü krater duvarı ile engelli.'
  },
  MALAPERT_MASSIF: {
    id: 'MALAPERT_MASSIF',
    name: 'Malapert Massif',
    nameTr: 'Malapert Massif',
    lat: -86.04,
    lonEast: 2.7,
    elevationM: 2150.0,
    description: 'Artemis III 1 numaralı öncelikli zirve platosu. Kesintisiz güneş (%92) ve Dünya (%94) görüşü.'
  },
  CONNECTING_RIDGE_EXT: {
    id: 'CONNECTING_RIDGE_EXT',
    name: 'Connecting Ridge Extension',
    nameTr: 'Connecting Ridge Uzantısı',
    lat: -89.47,
    lonEast: -136.2,
    elevationM: 1880.0,
    description: 'Connecting Ridge batı uzantısındaki yüksek irtifa hattı. Mükemmel görüş koridoru.'
  },
  LEIBNITZ_BETA: {
    id: 'LEIBNITZ_BETA',
    name: 'Leibnitz Beta Plateau',
    nameTr: 'Leibnitz Beta Platosu',
    lat: -85.82,
    lonEast: 29.5,
    elevationM: 1850.0,
    description: 'Geniş, düşük eğimli (2.8°) plato alanı. Yüksek iniş güvenliği.'
  },
  DE_GERLACHE_RIM_1: {
    id: 'DE_GERLACHE_RIM_1',
    name: 'de Gerlache Rim 1',
    nameTr: 'de Gerlache Kenarı 1',
    lat: -88.71,
    lonEast: -68.7,
    elevationM: 1620.0,
    description: 'de Gerlache kraterinin doğu sırt hattı. PSR soğuk kapanlarına yakın iniş sahası.'
  },
  DE_GERLACHE_RIM_2: {
    id: 'DE_GERLACHE_RIM_2',
    name: 'de Gerlache Rim 2',
    nameTr: 'de Gerlache Kenarı 2',
    lat: -88.35,
    lonEast: -67.8,
    elevationM: 1580.0,
    description: 'de Gerlache kraterinin kuzeydoğu kenar platosu.'
  },
  AMUNDSEN_RIM: {
    id: 'AMUNDSEN_RIM',
    name: 'Amundsen Rim',
    nameTr: 'Amundsen Kenar Sırtı',
    lat: -84.45,
    lonEast: 85.6,
    elevationM: 1420.0,
    description: 'Devasa Amundsen kraterinin güneybatı sırtı; teraslı duvar ve merkezi dağ manzarası.'
  },
  NOBILE_RIM_2: {
    id: 'NOBILE_RIM_2',
    name: 'Nobile Rim 2',
    nameTr: 'Nobile Kenar Platosu',
    lat: -85.28,
    lonEast: 36.15,
    elevationM: 1750.0,
    description: 'Nobile kraterinin batı kenar platosu; VIPER rover rotası ile entegre iniş alanı.'
  },
  DE_GERLACHE_KOCHER: {
    id: 'DE_GERLACHE_KOCHER',
    name: 'de Gerlache-Kocher Massif',
    nameTr: 'de Gerlache-Kocher Masifi',
    lat: -85.78,
    lonEast: -123.35,
    elevationM: 1920.0,
    description: 'Yüksek irtifa radyo röle istasyonu ve gözlem masifi.'
  },
  HAWORTH: {
    id: 'HAWORTH',
    name: 'Haworth',
    nameTr: 'Haworth Kenarı',
    lat: -87.87,
    lonEast: -5.1,
    elevationM: 1350.0,
    description: 'Haworth krateri kuzey kenarı; aşırı düşük sıcaklık bilimsel araştırma alanı.'
  },
  FAUSTINI_RIM: {
    id: 'FAUSTINI_RIM',
    name: 'Faustini Rim',
    nameTr: 'Faustini Kenar Sırtı',
    lat: -86.4925,
    lonEast: 80.7183,
    elevationM: 1680.0,
    description: 'Faustini kraterinin yüksek kuzey sırtı; düşük yamaç eğimi ve stabil radyo penceresi.'
  },
  CABEUS_RIDGE: {
    id: 'CABEUS_RIDGE',
    name: 'Cabeus Ridge',
    nameTr: 'Cabeus Kenar Sırtı',
    lat: -83.7961,
    lonEast: -41.0726,
    elevationM: 1450.0,
    description: 'LCROSS çarpma krateri kenarı; Dünya ile kesintisiz görüş hattı.'
  },
  SVERDRUP_RIM: {
    id: 'SVERDRUP_RIM',
    name: 'Sverdrup Rim',
    nameTr: 'Sverdrup Platosu',
    lat: -89.4455,
    lonEast: -137.3137,
    elevationM: 1954.3,
    description: '1.45° son derece düşük yamaç eğimli, en güvenli ayak basma platosu.'
  }
};

let cachedTimeseries: any = null;
let cachedHorizons: any = null;
let cachedWindows: any = null;
let cachedTerrainMap: Partial<Record<SiteId, TerrainMeshData>> = {};
let cachedCase: SurveyCaseData | null = null;
let cachedScene: any = null;
let cachedProvenance: any = null;
let cachedTargets: any = null;

export async function fetchTimeseries(): Promise<any> {
  if (cachedTimeseries) return cachedTimeseries;
  const res = await fetch(assetUrl('data/timeseries.json'));
  cachedTimeseries = await res.json();
  return cachedTimeseries;
}

export async function fetchHorizons(): Promise<Record<SiteId, Record<string, HorizonProfile>>> {
  if (cachedHorizons) return cachedHorizons;
  const res = await fetch(assetUrl('data/horizons.json'));
  cachedHorizons = await res.json();
  return cachedHorizons;
}

export async function fetchWindows(): Promise<Record<SiteId, { windows: SiteWindowsData; summary: SiteSummary }>> {
  if (cachedWindows) return cachedWindows;
  const res = await fetch(assetUrl('data/windows.json'));
  cachedWindows = await res.json();
  return cachedWindows;
}

export async function fetchTerrain(siteId: SiteId = 'Site01'): Promise<TerrainMeshData> {
  if (cachedTerrainMap[siteId]) return cachedTerrainMap[siteId]!;
  const file = siteId === 'Site04' ? assetUrl('data/terrain_site04.json') : assetUrl('data/terrain_site01.json');
  const res = await fetch(file);
  const data = await res.json();
  cachedTerrainMap[siteId] = data as TerrainMeshData;
  return data as TerrainMeshData;
}

export async function fetchTerrainSite01(): Promise<TerrainMeshData> {
  return fetchTerrain('Site01');
}

export async function fetchSite01Case(): Promise<SurveyCaseData> {
  if (cachedCase) return cachedCase;
  const res = await fetch(assetUrl('data/site01_case.json'));
  cachedCase = await res.json();
  return cachedCase as SurveyCaseData;
}

export async function fetchSite01Scene(): Promise<any> {
  if (cachedScene) return cachedScene;
  const res = await fetch(assetUrl('data/site01_scene.json'));
  cachedScene = await res.json();
  return cachedScene;
}

export async function fetchProvenance(): Promise<any> {
  if (cachedProvenance) return cachedProvenance;
  const res = await fetch(assetUrl('data/provenance.json'));
  cachedProvenance = await res.json();
  return cachedProvenance;
}

export async function fetchSurveyTargets(): Promise<any> {
  if (cachedTargets) return cachedTargets;
  const res = await fetch(assetUrl('data/survey_targets.geojson'));
  cachedTargets = await res.json();
  return cachedTargets;
}

let cachedSimulations: any = null;
let cachedArtemis: any = null;

export async function fetchFlightSimulations(): Promise<Record<string, any>> {
  if (cachedSimulations) return cachedSimulations;
  try {
    const res = await fetch(assetUrl('data/flight_simulations.json'));
    cachedSimulations = await res.json();
  } catch (err) {
    console.warn('Flight simulations load error:', err);
    cachedSimulations = {};
  }
  return cachedSimulations;
}

export async function fetchArtemisCandidates(): Promise<any> {
  if (cachedArtemis) return cachedArtemis;
  try {
    const res = await fetch(assetUrl('data/artemis_candidates.json'));
    cachedArtemis = await res.json();
  } catch (err) {
    console.warn('Artemis candidates load error:', err);
    cachedArtemis = { candidate_sites: [] };
  }
  return cachedArtemis;
}

export { CRATER_CATALOG, calculateLunarDistanceKm } from './craterCatalog';
