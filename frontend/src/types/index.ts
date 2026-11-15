// LUNA SIGHT - Veri Tipleri & Sözleşmesi

export type SiteId =
  | 'Site01'
  | 'Site04'
  | 'MALAPERT_MASSIF'
  | 'CONNECTING_RIDGE_EXT'
  | 'LEIBNITZ_BETA'
  | 'DE_GERLACHE_RIM_1'
  | 'DE_GERLACHE_RIM_2'
  | 'AMUNDSEN_RIM'
  | 'NOBILE_RIM_2'
  | 'DE_GERLACHE_KOCHER'
  | 'HAWORTH'
  | 'FAUSTINI_RIM'
  | 'CABEUS_RIDGE'
  | 'SVERDRUP_RIM';

export type HorizonScenario = '0deg' | '2000m' | '4000m';

export type VisibilityState = 'visible' | 'blocked' | 'uncertain';

export type CameraViewMode = 'globe' | 'terrain' | 'surface_pov';

export type MapLayerMode = 'wac' | 'topo';

// NASA GMAT Workstation Layout Presets
export type WorkspacePreset = 'exploration' | 'scientific' | 'ai' | 'presentation';

// Mission Console Tabs
export type ConsoleTab = 'log' | 'analysis' | 'comparison' | 'simulation' | 'telemetry' | 'queue' | 'data' | 'ai';

// Inspector Tabs
export type InspectorTab = 'telemetry' | 'comparison' | 'simulation' | 'terrain' | 'crater' | 'ai';

// Camera Presets
export type CameraPreset =
  | 'south_pole'
  | 'site01'
  | 'site04'
  | 'equatorial'
  | 'surface_pov'
  | 'free'
  | 'shoemaker'
  | 'malapert'
  | 'amundsen';

// SUHAIL Mission Parameters (Image 2)
export interface SuhailParameters {
  sourceMode: 'real' | 'synthetic';
  missionDays: number;
  samplingInterval: '1h' | '5m';
  startUtc: string;
  minSunReq: number;
  maxBlackoutTol: number;
}

// Lunar South Pole Feature Type & Hierarchy
export type FeatureType = 'crater' | 'plain' | 'ridge' | 'plateau' | 'peak' | 'site';
export type FeatureTier = 1 | 2 | 3; // 1: Major Landmark, 2: Regional, 3: Local Sector

// Lunar South Pole Feature Catalog Entry
export interface CraterFeature {
  id: string;
  name: string;
  type?: FeatureType;
  tier?: FeatureTier;
  sector?: string;
  lat: number;
  lonEast: number;
  diameterKm?: number;
  depthM?: number;
  rimHeightM?: number;
  elevationM?: number;
  hazardRisk: 'Low' | 'Moderate' | 'High' | 'Severe';
  permanentlyShadowed: boolean;
  scientificInterest: string;
}

// Distance Measurement Tool
export interface MeasurementPoint {
  lat: number;
  lonEast: number;
  elevationM?: number;
}

export interface MeasurementState {
  active: boolean;
  pointA: MeasurementPoint | null;
  pointB: MeasurementPoint | null;
  distanceKm: number | null;
}

// System Log Entry
export interface SystemLogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'TELEMETRY' | 'SUCCESS';
  category: 'K1-EPHEMERIS' | 'K2-TERRAIN' | 'K3-VISIBILITY' | 'AI-VLM' | 'SYSTEM' | 'PIPELINE';
  message: string;
}

// Analysis Pipeline Step
export type PipelineStepId = 'dataset' | 'roi' | 'terrain' | 'visibility' | 'ai' | 'report';

export interface PipelineStep {
  id: PipelineStepId;
  name: string;
  description: string;
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number;
  detail?: string;
  outputSummary?: string;
  durationMs?: number;
}

export interface SiteInfo {
  id: SiteId;
  name: string;
  nameTr: string;
  lat: number;
  lonEast: number;
  elevationM: number;
  description: string;
}

export interface EphemerisPoint {
  timestampUtc: string;
  sunAzDeg: number;
  sunAltDeg: number;
  earthAzDeg: number;
  earthAltDeg: number;
  terrainHorizonSunDeg: number;
  terrainHorizonEarthDeg: number;
  sunMarginDeg: number;
  earthMarginDeg: number;
  jointMarginDeg: number;
  sunState: VisibilityState;
  earthState: VisibilityState;
  jointState: VisibilityState;
  qualityFlag: string;
}

export interface WindowInterval {
  body: 'sun' | 'earth' | 'joint';
  state: VisibilityState;
  startUtc: string;
  endUtc: string;
  durationHours: number;
  startRefined?: boolean;
  endRefined?: boolean;
  reason?: string;
}

export interface SiteWindowsData {
  sun: WindowInterval[];
  earth: WindowInterval[];
  joint: WindowInterval[];
}

export interface SiteSummary {
  site_id: SiteId;
  coordinate: {
    latitude_deg: number;
    longitude_deg_east: number;
  };
  bodies: {
    sun: {
      window_count: number;
      total_hours: number;
      state_hours: { visible: number; blocked: number; uncertain: number };
      visible_fraction: number;
      longest_visible_hours: number | null;
      longest_visible_start_utc: string | null;
    };
    earth: {
      window_count: number;
      total_hours: number;
      state_hours: { visible: number; blocked: number; uncertain: number };
      visible_fraction: number;
      longest_visible_hours: number | null;
      longest_visible_start_utc: string | null;
    };
    joint: {
      window_count: number;
      total_hours: number;
      state_hours: { visible: number; blocked: number; uncertain: number };
      visible_fraction: number;
      longest_visible_hours: number | null;
      longest_visible_start_utc: string | null;
    };
  };
}

export interface HorizonProfile {
  azimuth_deg: number[];
  horizon_deg: number[];
  occluder_distance_m: number[];
}

export interface TerrainMeshData {
  bounds: {
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    width_m: number;
    height_m: number;
  };
  grid_size: [number, number];
  resolution_m: number;
  observer_pos: {
    x_m: number;
    y_m: number;
    z_ground_m: number;
    z_eye_m: number;
  };
  patch_corners_m: Array<{ x_m: number; y_m: number }>;
  patch_center_m: { x_m: number; y_m: number };
  patch_dimensions_m: [number, number];
  rays?: {
    ray_130?: {
      azimuth_deg: number;
      weight: number;
      occluder_dist_m: number;
      occluder_coords: { x_m: number; y_m: number; z_m: number };
    };
    ray_131?: {
      azimuth_deg: number;
      weight: number;
      occluder_dist_m: number;
      occluder_coords: { x_m: number; y_m: number; z_m: number };
    };
    earth_ray?: {
      azimuth_deg: number;
      altitude_deg: number;
    };
  };
  elevations_surf: number[][];
  elevations_err_clone1?: number[][];
  provenance?: {
    source: string;
    surf_sha256: string;
    err1_sha256: string;
  };
}

export interface SurveyCaseData {
  site_id: SiteId;
  site_name: string;
  operation_window: {
    start_utc: string;
    end_utc: string;
    duration_hours: number;
    sample_step_minutes: number;
    total_samples: number;
  };
  trigger_sample: {
    timestamp_utc: string;
    description: string;
  };
  modeling_parameters: {
    transition_band_deg: number;
    transition_band_type: string;
    observer_height_m: number;
    scan_radius_m: number;
  };
  models: {
    Site01_nominal: ModelSampleResult;
    Site01_clone1: ModelSampleResult;
    Site01_clone2: ModelSampleResult;
  };
}

export interface ModelSampleResult {
  earth: {
    azimuth_deg: number;
    altitude_deg: number;
    terrain_horizon_deg: number;
    margin_deg: number;
    sample_status: VisibilityState;
    occluder_dist_m?: number;
    occluder_coords?: { x_m: number; y_m: number; z_m: number };
  };
  sun: {
    azimuth_deg: number;
    altitude_deg: number;
    terrain_horizon_deg: number;
    margin_deg: number;
    sample_status: VisibilityState;
  };
  joint_sample_status: VisibilityState;
  twelve_hour_operation_decision: 'feasible' | 'uncertain' | 'not_feasible';
}

// GMAT Workstation Extensions
export type GmatInspectorTab = 'terrain' | 'visibility' | 'craters' | 'ai';

export interface ResourceNode {
  id: string;
  label: string;
  category: 'LUNAR DATA' | 'ANALYSIS MODULES' | 'MISSION RESOURCES' | 'OUTPUT';
  type: 'dataset' | 'module' | 'site' | 'crater' | 'layer' | 'output';
  active: boolean;
  visible: boolean;
  badge?: string;
  badgeColor?: 'sky' | 'green' | 'amber' | 'purple' | 'slate';
  metadata?: Record<string, string | number>;
}

// Flight Physics & Simulation Models (Eray'ın Çalışması Entegrasyonu)
export interface FlightSimulationData {
  site_id: string;
  site_name: string;
  coordinates: {
    latitude_deg: number;
    longitude_deg_east: number;
    elevation_m: number;
  };
  suitability_score: number;
  operational_role: string;
  landing_simulation: {
    status: string;
    status_label_tr: string;
    duration_s: number;
    landing_error_m: number;
    touchdown_vz_ms: number;
    touchdown_vxy_ms: number;
    tilt_deg: number;
    fuel_remaining_kg: number;
    fuel_remaining_pct: number;
    overall_score: number;
    trajectory_sample: Array<{
      t: number;
      alt_m: number;
      vz_ms: number;
      vxy_ms: number;
      fuel_kg: number;
      thrust_n: number;
      pitch_deg: number;
    }>;
  };
  boulder_hazard: {
    slope_deg: number;
    crater_dist_m: number;
    footprint_area_m2: number;
    critical_diameter_m: number;
    gamma: number;
    expected_hazardous_boulders: number;
    collision_probability: number;
    bhi_score: number;
    hazard_class: string;
    risk_level: string;
  };
  gateway_relay: {
    coverage_pct: number;
    total_visible_hours: number;
    longest_pass_hours: number;
    gateway_orbit: string;
  };
  penumbra_power: {
    visible_disk_percent: number;
    effective_flux_wm2: number;
    generated_power_watts: number;
    eclipse_state: string;
  };
  knife_edge_diffraction: {
    diffraction_loss_db: number;
    emergency_margin_db: number;
    link_status: string;
  };
}
