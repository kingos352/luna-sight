/**
 * Telemetry computations for solar and terrestrial vectors at the lunar South Pole.
 */

export interface TelemetryData {
  timestampUtc: string;
  subSolarLat: number;
  subSolarLon: number;
  subEarthLat: number;
  subEarthLon: number;
  sunDistanceAU: number;
  earthDistanceKm: number;
  solarIlluminationFluxWm2: number;
  communicationLatencySec: number;
}

export function computeTelemetryAtTimestamp(timestampUtc: string, timeIndex: number): TelemetryData {
  // Approximate analytical lunar librations and solar sub-point for Nov 14-21, 2026 UTC
  const sampleFraction = timeIndex / 2016; // 7 days of 5-min intervals
  
  // Sub-solar latitude varies between -1.5° and -1.6° due to lunar obliquity (1.54°)
  const subSolarLat = -1.54 + 0.08 * Math.sin(sampleFraction * Math.PI * 2);
  // Lunar synodic day is ~29.53 Earth days; over 7 days longitude progresses ~85.3°
  const subSolarLon = ((142.5 - sampleFraction * 85.3 + 360) % 360) - 180;

  // Sub-Earth point reflects lunar optical and physical libration
  const subEarthLat = 6.42 + 0.35 * Math.sin(sampleFraction * Math.PI * 2 + 0.4);
  const subEarthLon = -4.18 + 0.28 * Math.cos(sampleFraction * Math.PI * 2 + 0.2);

  // Distances
  const sunDistanceAU = 0.9882 + 0.0003 * Math.sin(sampleFraction * Math.PI * 2);
  const earthDistanceKm = 384400 + 4200 * Math.cos(sampleFraction * Math.PI * 2);

  // Solar constant at 1 AU is ~1361 W/m² -> scaled by (1/rAU)²
  const solarIlluminationFluxWm2 = Math.round(1361 / (sunDistanceAU * sunDistanceAU));

  // Speed of light round-trip direct-to-earth latency
  const c = 299792.458; // km/s
  const communicationLatencySec = Number(((earthDistanceKm / c) * 2).toFixed(3));

  return {
    timestampUtc,
    subSolarLat: Number(subSolarLat.toFixed(3)),
    subSolarLon: Number(subSolarLon.toFixed(3)),
    subEarthLat: Number(subEarthLat.toFixed(3)),
    subEarthLon: Number(subEarthLon.toFixed(3)),
    sunDistanceAU: Number(sunDistanceAU.toFixed(4)),
    earthDistanceKm: Math.round(earthDistanceKm),
    solarIlluminationFluxWm2,
    communicationLatencySec
  };
}
