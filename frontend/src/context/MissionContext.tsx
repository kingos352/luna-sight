import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import {
  SiteId,
  HorizonScenario,
  CameraViewMode,
  VisibilityState,
  WindowInterval,
  SiteSummary,
  HorizonProfile,
  TerrainMeshData,
  SurveyCaseData
} from '../types';
import {
  fetchTimeseries,
  fetchHorizons,
  fetchWindows,
  fetchTerrain,
  fetchTerrainSite01,
  fetchSite01Case,
  fetchSite01Scene,
  fetchProvenance,
  fetchSurveyTargets
} from '../services/dataService';
import {
  interpolateHorizon,
  classifyBodyVisibility,
  classifyJointVisibility,
  extractWindowsFromSeries
} from '../services/visibilityCalculator';

interface MissionContextType {
  siteId: SiteId;
  setSiteId: (site: SiteId) => void;
  scenario: HorizonScenario;
  setScenario: (scen: HorizonScenario) => void;
  timeIndex: number;
  setTimeIndex: (idx: number) => void;
  currentTimestamp: string;
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  playSpeed: number;
  setPlaySpeed: (spd: number) => void;
  minDurationHours: number;
  setMinDurationHours: (hrs: number) => void;
  cameraMode: CameraViewMode;
  setCameraMode: (mode: CameraViewMode) => void;
  layerMode: 'wac' | 'topo';
  setLayerMode: (mode: 'wac' | 'topo') => void;
  displacementEnabled: boolean;
  setDisplacementEnabled: (enabled: boolean) => void;
  isCaseActive: boolean;
  isVirtualPatchApplied: boolean;
  openConnectingRidgeCase: () => void;
  closeConnectingRidgeCase: () => void;
  toggleVirtualPatch: () => void;
  
  // Data
  loading: boolean;
  error: string | null;
  timeseries: any;
  horizons: Record<SiteId, Record<string, HorizonProfile>> | null;
  windowsData: any;
  terrainData: TerrainMeshData | null;
  caseData: SurveyCaseData | null;
  sceneData: any;
  provenanceData: any;
  
  // Active computed sample values
  activePoint: {
    timestamp: string;
    sunAz: number;
    sunAlt: number;
    sunHorizon: number;
    sunMargin: number;
    sunState: VisibilityState;
    earthAz: number;
    earthAlt: number;
    earthHorizon: number;
    earthMargin: number;
    earthState: VisibilityState;
    jointMargin: number;
    jointState: VisibilityState;
    twelveHourDecision: 'feasible' | 'uncertain' | 'not_feasible';
  };
  
  // Dynamic Windows
  activeWindows: WindowInterval[];
  longestJointWindow: WindowInterval | null;
  exportCaseData: (format: 'json' | 'csv') => void;
}

const MissionContext = createContext<MissionContextType | undefined>(undefined);

export const MissionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [siteId, setSiteId] = useState<SiteId>('Site01');
  const [scenario, setScenario] = useState<HorizonScenario>('4000m');
  const [timeIndex, setTimeIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playSpeed, setPlaySpeed] = useState<number>(1);
  const [minDurationHours, setMinDurationHours] = useState<number>(12.0);
  const [cameraMode, setCameraMode] = useState<CameraViewMode>('globe');
  const [layerMode, setLayerMode] = useState<'wac' | 'topo'>('wac');
  const [displacementEnabled, setDisplacementEnabled] = useState<boolean>(true);
  const [isCaseActive, setIsCaseActive] = useState<boolean>(false);
  const [isVirtualPatchApplied, setIsVirtualPatchApplied] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [timeseries, setTimeseries] = useState<any>(null);
  const [horizons, setHorizons] = useState<Record<SiteId, Record<string, HorizonProfile>> | null>(null);
  const [windowsData, setWindowsData] = useState<any>(null);
  const [terrainData, setTerrainData] = useState<TerrainMeshData | null>(null);
  const [caseData, setCaseData] = useState<SurveyCaseData | null>(null);
  const [sceneData, setSceneData] = useState<any>(null);
  const [provenanceData, setProvenanceData] = useState<any>(null);

  // Initial Data Load
  useEffect(() => {
    async function loadAll() {
      try {
        setLoading(true);
        const [ts, hor, win, terr, cCase, cScene, prov] = await Promise.all([
          fetchTimeseries(),
          fetchHorizons(),
          fetchWindows(),
          fetchTerrainSite01(),
          fetchSite01Case(),
          fetchSite01Scene(),
          fetchProvenance()
        ]);
        setTimeseries(ts);
        setHorizons(hor);
        setWindowsData(win);
        setTerrainData(terr);
        setCaseData(cCase);
        setSceneData(cScene);
        setProvenanceData(prov);
        setLoading(false);
      } catch (err: any) {
        console.error('Veri yükleme hatası:', err);
        setError(err.message || 'Veri yüklenemedi');
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  // Update terrain mesh when site changes
  useEffect(() => {
    let isMounted = true;
    fetchTerrain(siteId)
      .then((terr) => {
        if (isMounted) setTerrainData(terr);
      })
      .catch((err) => console.error('Arazi verisi yüklenemedi:', siteId, err));
    return () => {
      isMounted = false;
    };
  }, [siteId]);

  // Time playback interval
  useEffect(() => {
    if (!isPlaying || !timeseries || !timeseries[siteId]) return;
    const intervalMs = Math.max(50, Math.floor(400 / playSpeed));
    const timer = setInterval(() => {
      setTimeIndex((prev) => {
        const maxIdx = timeseries[siteId].timestamps.length - 1;
        if (prev >= maxIdx) {
          setIsPlaying(false);
          return maxIdx;
        }
        return prev + 1;
      });
    }, intervalMs);
    return () => clearInterval(timer);
  }, [isPlaying, playSpeed, timeseries, siteId]);

  const currentTimestamp = useMemo(() => {
    if (!timeseries || !timeseries[siteId]) return '2026-11-14T00:00:00Z';
    return timeseries[siteId].timestamps[timeIndex] || '2026-11-14T00:00:00Z';
  }, [timeseries, siteId, timeIndex]);

  // Compute active point values dynamically based on scenario or case override
  const activePoint = useMemo(() => {
    if (!timeseries || !timeseries[siteId]) {
      return {
        timestamp: currentTimestamp,
        sunAz: 0,
        sunAlt: 0,
        sunHorizon: 0,
        sunMargin: 0,
        sunState: 'uncertain' as VisibilityState,
        earthAz: 0,
        earthAlt: 0,
        earthHorizon: 0,
        earthMargin: 0,
        earthState: 'uncertain' as VisibilityState,
        jointMargin: 0,
        jointState: 'uncertain' as VisibilityState,
        twelveHourDecision: 'uncertain' as const
      };
    }

    const ts = timeseries[siteId];
    const sAz = ts.sun_az[timeIndex];
    const sAlt = ts.sun_alt[timeIndex];
    const eAz = ts.earth_az[timeIndex];
    const eAlt = ts.earth_alt[timeIndex];

    // If Connecting Ridge Case is active and at 2026-11-18T16:55:00Z
    if (isCaseActive && siteId === 'Site01') {
      if (isVirtualPatchApplied) {
        // Condition B: Patch only, observer ground elevation fixed at 1944.7671m
        // Earth horizon = +1.036964°, margin = +0.037769° -> uncertain
        // 12-hour decision = uncertain
        return {
          timestamp: currentTimestamp,
          sunAz: 206.822286,
          sunAlt: 1.069834,
          sunHorizon: -0.796403,
          sunMargin: 1.866237,
          sunState: 'visible' as VisibilityState,
          earthAz: 130.730898,
          earthAlt: 1.074733,
          earthHorizon: 1.036964,
          earthMargin: 0.037769,
          earthState: 'uncertain' as VisibilityState,
          jointMargin: 0.037769,
          jointState: 'uncertain' as VisibilityState,
          twelveHourDecision: 'uncertain' as const
        };
      } else {
        // Condition A: Nominal baseline
        // Earth horizon = +0.970511°, margin = +0.104222° -> visible
        // 12-hour decision = feasible
        return {
          timestamp: currentTimestamp,
          sunAz: 206.822286,
          sunAlt: 1.069834,
          sunHorizon: -0.796403,
          sunMargin: 1.866237,
          sunState: 'visible' as VisibilityState,
          earthAz: 130.730898,
          earthAlt: 1.074733,
          earthHorizon: 0.970511,
          earthMargin: 0.104222,
          earthState: 'visible' as VisibilityState,
          jointMargin: 0.104222,
          jointState: 'visible' as VisibilityState,
          twelveHourDecision: 'feasible' as const
        };
      }
    }

    // Normal time series computation
    let sHor = 0;
    let eHor = 0;

    if (scenario === '0deg') {
      sHor = 0.0;
      eHor = 0.0;
    } else if (scenario === '2000m') {
      sHor = ts.sun_horizon_2km[timeIndex];
      eHor = ts.earth_horizon_2km[timeIndex];
    } else {
      // 4000m
      sHor = ts.sun_horizon_4km[timeIndex];
      eHor = ts.earth_horizon_4km[timeIndex];
    }

    const sunClass = classifyBodyVisibility(sAlt, sHor, 0.10);
    const earthClass = classifyBodyVisibility(eAlt, eHor, 0.10);
    const jointState = classifyJointVisibility(sunClass.state, earthClass.state);
    const jointMargin = Math.min(sunClass.marginDeg, earthClass.marginDeg);

    const decision: 'feasible' | 'uncertain' | 'not_feasible' =
      jointState === 'visible' ? 'feasible' : jointState === 'blocked' ? 'not_feasible' : 'uncertain';

    return {
      timestamp: currentTimestamp,
      sunAz: sAz,
      sunAlt: sAlt,
      sunHorizon: sHor,
      sunMargin: sunClass.marginDeg,
      sunState: sunClass.state,
      earthAz: eAz,
      earthAlt: eAlt,
      earthHorizon: eHor,
      earthMargin: earthClass.marginDeg,
      earthState: earthClass.state,
      jointMargin: jointMargin,
      jointState: jointState,
      twelveHourDecision: decision
    };
  }, [timeseries, siteId, timeIndex, scenario, isCaseActive, isVirtualPatchApplied, currentTimestamp]);

  // Compute active continuous windows for the chosen scenario
  const activeWindows = useMemo(() => {
    if (!timeseries || !timeseries[siteId]) return [];
    
    // For 4000m nominal and no case active, use the verified K3 windows
    if (scenario === '4000m' && windowsData && windowsData[siteId] && !isCaseActive) {
      return windowsData[siteId].windows.joint || [];
    }

    const ts = timeseries[siteId];
    const timestamps = ts.timestamps;
    const states: VisibilityState[] = [];

    for (let i = 0; i < timestamps.length; i++) {
      const sAlt = ts.sun_alt[i];
      const eAlt = ts.earth_alt[i];
      let sHor = 0;
      let eHor = 0;
      if (scenario === '0deg') {
        sHor = 0;
        eHor = 0;
      } else if (scenario === '2000m') {
        sHor = ts.sun_horizon_2km[i];
        eHor = ts.earth_horizon_2km[i];
      } else {
        sHor = ts.sun_horizon_4km[i];
        eHor = ts.earth_horizon_4km[i];
      }
      const sClass = classifyBodyVisibility(sAlt, sHor, 0.10);
      const eClass = classifyBodyVisibility(eAlt, eHor, 0.10);
      states.push(classifyJointVisibility(sClass.state, eClass.state));
    }

    return extractWindowsFromSeries(timestamps, states, 'visible', 5);
  }, [timeseries, siteId, scenario, windowsData, isCaseActive]);

  const longestJointWindow = useMemo(() => {
    if (!activeWindows || activeWindows.length === 0) return null;
    let longest = activeWindows[0];
    for (const w of activeWindows) {
      if (w.durationHours > longest.durationHours) {
        longest = w;
      }
    }
    return longest;
  }, [activeWindows]);

  // Case actions
  const openConnectingRidgeCase = useCallback(() => {
    setSiteId('Site01');
    setIsCaseActive(true);
    setIsVirtualPatchApplied(false);
    setScenario('4000m');
    setCameraMode('surface_pov');
    setIsPlaying(false);

    // 2026-11-18T16:55:00Z index:
    if (timeseries && timeseries['Site01']) {
      const targetTs = '2026-11-18T16:55:00+00:00';
      const idx = timeseries['Site01'].timestamps.findIndex((t: string) => t.startsWith('2026-11-18T16:55'));
      if (idx !== -1) {
        setTimeIndex(idx);
      }
    }
  }, [timeseries]);

  const closeConnectingRidgeCase = useCallback(() => {
    setIsCaseActive(false);
    setIsVirtualPatchApplied(false);
  }, []);

  const toggleVirtualPatch = useCallback(() => {
    setIsVirtualPatchApplied((prev) => !prev);
  }, []);

  // Export Case Data
  const exportCaseData = useCallback((format: 'json' | 'csv') => {
    const triggerUtc = '2026-11-18T16:55:00Z';
    const opStartUtc = '2026-11-18T16:55:00Z';
    const opEndUtc = '2026-11-19T04:55:00Z';
    const currentModel = isVirtualPatchApplied ? 'Site01_clone1_patch_only' : 'Site01_nominal';
    const currentMargin = isVirtualPatchApplied ? 0.037769 : 0.104222;
    const currentHorizon = isVirtualPatchApplied ? 1.036964 : 0.970511;
    const currentDecision = isVirtualPatchApplied ? 'uncertain' : 'feasible';

    const metadata = {
      project: "LUNA SIGHT - Lunar Landing Site Navigator",
      site_id: "Site01",
      site_name: "Connecting ridge",
      target_body: "Moon",
      coordinate_frame: "MOON_ME (JPL DE421)",
      projection: "South Polar Stereographic",
      datum_radius_m: 1737400.0,
      longitude_convention: "East positive (-180 to +180 deg)",
      units: {
        projected_coordinates: "meters",
        geographic_coordinates: "degrees",
        angles: "degrees",
        elevation: "meters"
      },
      warning: "Lunar body-fixed coordinates. DO NOT reproject onto Earth WGS84 datum.",
      operation_window: {
        start_utc: opStartUtc,
        end_utc: opEndUtc,
        duration_hours: 12.0
      },
      trigger_sample_utc: triggerUtc,
      active_scenario: {
        model_id: currentModel,
        virtual_patch_applied: isVirtualPatchApplied,
        earth_altitude_deg: 1.074733,
        earth_azimuth_deg: 130.730898,
        terrain_horizon_deg: currentHorizon,
        angular_margin_deg: currentMargin,
        sample_status: isVirtualPatchApplied ? "uncertain" : "visible",
        twelve_hour_decision: currentDecision,
        transition_band_threshold_deg: 0.10
      },
      proposed_survey_patch: sceneData?.proposed_survey_patch || {
        name: "Target_MethodA_CriticalRidge",
        dimensions_m: [400, 400],
        center_projected_m: { x_m: -11009.61, y_m: -11915.54 }
      },
      provenance: provenanceData?.data_products || []
    };

    if (format === 'json') {
      const blob = new Blob([JSON.stringify(metadata, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `luna_sight_site01_survey_case_${isVirtualPatchApplied ? 'clone1' : 'nominal'}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      // CSV format
      const csvRows = [
        ['parameter', 'value', 'unit', 'description'],
        ['site_id', 'Site01', 'string', 'Connecting Ridge'],
        ['coordinate_frame', 'MOON_ME (DE421)', 'string', 'Lunar body-fixed'],
        ['projection', 'South Polar Stereographic', 'string', 'True scale at pole'],
        ['datum_radius', '1737400.0', 'meters', 'Moon radius datum'],
        ['observer_x', '-11000.0', 'meters', 'Projected Easting'],
        ['observer_y', '-12000.0', 'meters', 'Projected Northing'],
        ['observer_lat', '-89.463163', 'degrees', 'Lunar Latitude'],
        ['observer_lon_east', '-137.489553', 'degrees', 'East positive Longitude'],
        ['operation_start_utc', opStartUtc, 'ISO8601', 'Window Start'],
        ['operation_end_utc', opEndUtc, 'ISO8601', 'Window End'],
        ['trigger_utc', triggerUtc, 'ISO8601', 'Trigger UTC Sample'],
        ['model_id', currentModel, 'string', 'Terrain model evaluated'],
        ['virtual_patch_applied', isVirtualPatchApplied ? 'true' : 'false', 'boolean', 'Clone 1 patch status'],
        ['earth_altitude_deg', '1.074733', 'degrees', 'Horizons DE441 apparent'],
        ['earth_azimuth_deg', '130.730898', 'degrees', 'Degrees clockwise from True North'],
        ['terrain_horizon_deg', currentHorizon.toFixed(6), 'degrees', 'LOLA derived horizon'],
        ['angular_margin_deg', currentMargin.toFixed(6), 'degrees', 'Altitude minus Horizon'],
        ['transition_band_threshold_deg', '0.100000', 'degrees', 'Modeling band setting'],
        ['sample_status', isVirtualPatchApplied ? 'uncertain' : 'visible', 'enum', 'Sample visibility state'],
        ['twelve_hour_operation_decision', currentDecision, 'enum', 'Window operational feasibility'],
        ['patch_name', 'Target_MethodA_CriticalRidge', 'string', '400x400m survey target'],
        ['patch_center_x_m', '-11009.61', 'meters', 'Easting'],
        ['patch_center_y_m', '-11915.54', 'meters', 'Northing'],
        ['patch_center_lat_deg', '-89.464998', 'degrees', 'Latitude'],
        ['patch_center_lon_deg_east', '-137.262991', 'degrees', 'Longitude East positive']
      ];
      const csvContent = csvRows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `luna_sight_site01_survey_case_${isVirtualPatchApplied ? 'clone1' : 'nominal'}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [isVirtualPatchApplied, sceneData, provenanceData]);

  return (
    <MissionContext.Provider
      value={{
        siteId,
        setSiteId,
        scenario,
        setScenario,
        timeIndex,
        setTimeIndex,
        currentTimestamp,
        isPlaying,
        setIsPlaying,
        playSpeed,
        setPlaySpeed,
        minDurationHours,
        setMinDurationHours,
        cameraMode,
        setCameraMode,
        layerMode,
        setLayerMode,
        displacementEnabled,
        setDisplacementEnabled,
        isCaseActive,
        isVirtualPatchApplied,
        openConnectingRidgeCase,
        closeConnectingRidgeCase,
        toggleVirtualPatch,
        loading,
        error,
        timeseries,
        horizons,
        windowsData,
        terrainData,
        caseData,
        sceneData,
        provenanceData,
        activePoint,
        activeWindows,
        longestJointWindow,
        exportCaseData
      }}
    >
      {children}
    </MissionContext.Provider>
  );
};

export const useMission = () => {
  const context = useContext(MissionContext);
  if (!context) {
    throw new Error('useMission must be used within a MissionProvider');
  }
  return context;
};
