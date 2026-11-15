import { HorizonProfile, VisibilityState, WindowInterval } from '../types';

/**
 * 359° - 0° sınırını doğru saran dairesel doğrusal ufuk enterpolasyonu.
 * Azimut gerçek kuzeyden (0°) saat yönünde doğuya (90°) doğru artar.
 */
export function interpolateHorizon(profile: HorizonProfile, azimuthDeg: number): number {
  if (!profile || !profile.horizon_deg || profile.horizon_deg.length === 0) {
    return 0.0;
  }
  // [0, 360) aralığına normalize et
  let az = azimuthDeg % 360.0;
  if (az < 0) az += 360.0;

  const len = profile.horizon_deg.length;
  const i0 = Math.floor(az) % len;
  const i1 = (i0 + 1) % len;
  const weight = az - Math.floor(az);

  const h0 = profile.horizon_deg[i0];
  const h1 = profile.horizon_deg[i1];

  return (1.0 - weight) * h0 + weight * h1;
}

/**
 * Tek cisim görünürlük sınıflandırması.
 * Bilimsel kural:
 * Varsayılan ±0,10° bant bir modelleme ayarıdır.
 * marj > +0,10° ise visible
 * marj < -0,10° ise blocked
 * aksi halde (|marj| <= 0,10°) uncertain
 */
export function classifyBodyVisibility(
  altitudeDeg: number,
  horizonDeg: number,
  transitionBandDeg: number = 0.10
): { marginDeg: number; state: VisibilityState } {
  const marginDeg = altitudeDeg - horizonDeg;
  if (marginDeg > transitionBandDeg) {
    return { marginDeg, state: 'visible' };
  } else if (marginDeg < -transitionBandDeg) {
    return { marginDeg, state: 'blocked' };
  } else {
    return { marginDeg, state: 'uncertain' };
  }
}

/**
 * Ortak görünürlük sınıflandırması.
 * Bilimsel kural:
 * İki cisim de visible ise -> visible
 * Cisimlerden biri kesin blocked ise -> blocked
 * Kalan tüm durumlarda -> uncertain
 */
export function classifyJointVisibility(
  sunState: VisibilityState,
  earthState: VisibilityState
): VisibilityState {
  if (sunState === 'visible' && earthState === 'visible') {
    return 'visible';
  }
  if (sunState === 'blocked' || earthState === 'blocked') {
    return 'blocked';
  }
  return 'uncertain';
}

/**
 * Zaman serisi noktalarından kesintisiz pencereleri türetir.
 * Eksik zaman adımları ve belirsiz örnekler pencereyi böler.
 */
export function extractWindowsFromSeries(
  timestamps: string[],
  states: VisibilityState[],
  targetState: VisibilityState = 'visible',
  sampleStepMinutes: number = 5
): WindowInterval[] {
  const windows: WindowInterval[] = [];
  let inWindow = false;
  let startIdx = 0;

  for (let i = 0; i < states.length; i++) {
    const isTarget = states[i] === targetState;

    if (isTarget && !inWindow) {
      inWindow = true;
      startIdx = i;
    } else if (!isTarget && inWindow) {
      inWindow = false;
      const count = i - startIdx;
      const durationHours = (count * sampleStepMinutes) / 60.0;
      windows.push({
        body: 'joint',
        state: targetState,
        startUtc: timestamps[startIdx],
        endUtc: timestamps[i - 1],
        durationHours: Number(durationHours.toFixed(2)),
        reason: targetState === 'visible' ? 'clear' : 'occluded'
      });
    }
  }

  if (inWindow) {
    const count = states.length - startIdx;
    const durationHours = (count * sampleStepMinutes) / 60.0;
    windows.push({
      body: 'joint',
      state: targetState,
      startUtc: timestamps[startIdx],
      endUtc: timestamps[states.length - 1],
      durationHours: Number(durationHours.toFixed(2)),
      reason: targetState === 'visible' ? 'clear' : 'occluded'
    });
  }

  return windows;
}
