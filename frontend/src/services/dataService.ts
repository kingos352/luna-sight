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
  VisibilityState
} from '../types';

export const SITES: Record<SiteId, { id: SiteId; name: string; nameTr: string; lat: number; lonEast: number; elevationM: number; description: string }> = {
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
