// LUNA SIGHT - Veri Tipleri & Sözleşmesi

export type SiteId = 'Site01' | 'Site04';

export type HorizonScenario = '0deg' | '2000m' | '4000m';

export type VisibilityState = 'visible' | 'blocked' | 'uncertain';

export type CameraViewMode = 'globe' | 'terrain' | 'surface_pov';

export type MapLayerMode = 'wac' | 'topo';

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
