import React, { Suspense } from 'react';
import * as THREE from 'three';
import { Canvas } from '@react-three/fiber';
import { Stars } from '@react-three/drei';
import { LunarGlobe } from './LunarGlobe';
import { TerrainMesh } from './TerrainMesh';
import { CameraControls } from './CameraControls';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { useMission } from '../../context/MissionContext';
import {
  Globe,
  Mountain,
  Eye,
  Compass,
  Ruler,
  Layers,
  ChevronDown,
  Sun
} from 'lucide-react';
import { CameraPreset } from '../../types';

export const LunarViewer: React.FC = () => {
  const {
    siteId,
    setSiteId,
    cameraMode,
    setCameraMode,
    layerMode,
    setLayerMode,
    displacementEnabled,
    setDisplacementEnabled,
    illuminationMode,
    setIlluminationMode,
    setCameraPreset,
    measurement,
    resetMeasurement,
    activePoint,
    labelDisplayMode,
    setLabelDisplayMode,
    featureFilterType,
    setFeatureFilterType,
    selectedSector,
    setSelectedSector
  } = useMission();

  return (
    <div className="relative w-full h-full bg-space-950 overflow-hidden select-none">
      <ErrorBoundary fallbackTitle="3B Ay Sahnesi Yüklenemedi (WebGL Fallback)">
        <div id="luna-sight-webgl-container" className="w-full h-full">
          <Canvas
            shadows={false}
            dpr={[1, 1.5]}
            camera={{ fov: 45, near: 0.5, far: 35000, position: [0, -9, 8] }}
            gl={{
              antialias: true,
              alpha: false,
              preserveDrawingBuffer: true,
              powerPreference: 'high-performance',
              toneMapping: THREE.NeutralToneMapping,
              toneMappingExposure: 1.05
            }}
            className="w-full h-full"
          >
            <color attach="background" args={['#040609']} />

            {/* NASA Moon Trek / Bilimsel Aydınlatma Sistemi */}
            {illuminationMode === 'moontrek' ? (
              <>
                {/* NASA Moon Trek Dengeli Küresel Aydınlatma (Gözü Yormayan Pürüzsüz Harita Modu) */}
                <ambientLight intensity={0.78} color="#f8fafc" />
                <directionalLight
                  position={[20, 25, 30]}
                  intensity={0.8}
                  color="#fffef5"
                />
                <directionalLight
                  position={[-25, -15, -20]}
                  intensity={0.35}
                  color="#cbd5e1"
                />
              </>
            ) : (
              <>
                {/* Gerçekçi Derin Uzay Güneş Simülasyonu */}
                <ambientLight intensity={0.25} color="#64748b" />
                <directionalLight
                  position={[45, 12, -25]}
                  intensity={1.6}
                  color="#fffbf0"
                />
                <directionalLight position={[-30, -5, 25]} intensity={0.25} color="#38bdf8" />
              </>
            )}

            {/* Uzak Yıldız Kümesi */}
            <Stars radius={120} depth={60} count={3500} factor={4} saturation={0} fade speed={0.4} />

            <Suspense fallback={null}>
              {cameraMode === 'globe' ? (
                <LunarGlobe />
              ) : (
                <TerrainMesh />
              )}
              <CameraControls />
            </Suspense>
          </Canvas>
        </div>
      </ErrorBoundary>

      {/* 1. Sol Üst: Minimalist ve Ferah Telemetri Rozeti */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gmat-panel/80 backdrop-blur-md border border-gmat-border/70 text-xs shadow-xl">
        <div className="flex items-center gap-1.5 font-bold text-gmat-text">
          <span className="w-2 h-2 rounded-full bg-gmat-accent animate-pulse" />
          <span>{siteId === 'Site01' ? 'Connecting Ridge (Site01)' : 'Shackleton Rim (Site04)'}</span>
        </div>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-[11px] text-amber-300">
          Güneş: {activePoint?.sunAlt !== undefined ? activePoint.sunAlt.toFixed(1) : '+1.5'}°
        </span>
        <span className="font-mono text-[11px] text-sky-300">
          Dünya: {activePoint?.earthAlt !== undefined ? activePoint.earthAlt.toFixed(1) : '-5.0'}°
        </span>
        <span className="font-mono text-[11px] text-slate-400">89.46°S</span>
      </div>

      {/* 2. Sağ Üst: Tekilleştirilmiş Zarif Cam Görünüm Kontrol Çubuğu (Spacious Unified Glass HUD) */}
      <div className="absolute top-3 right-3 z-10 hidden sm:flex items-center gap-2 p-1.5 rounded-xl bg-gmat-panel/85 backdrop-blur-md border border-gmat-border/70 text-xs shadow-2xl">
        {cameraMode === 'globe' ? (
          <>
            {/* Kutup Sektörü Seçici */}
            <div className="flex items-center bg-gmat-bg/80 rounded-lg border border-gmat-border px-2 py-1 gap-1.5">
              <Compass className="w-3.5 h-3.5 text-gmat-accent shrink-0" />
              <select
                value={selectedSector}
                onChange={(e) => {
                  const sec = e.target.value;
                  setSelectedSector(sec);
                  if (sec === 'all') setCameraPreset('south_pole');
                  else if (sec === 'Kutup & Connecting Ridge') setCameraPreset('site01');
                  else if (sec === 'Shoemaker-Faustini') setCameraPreset('shoemaker');
                  else if (sec === 'Malapert-Cabeus') setCameraPreset('malapert');
                  else if (sec === 'Nobile-Amundsen') setCameraPreset('amundsen');
                }}
                className="bg-transparent text-[11px] text-gmat-text font-mono outline-none cursor-pointer pr-1"
              >
                <option value="all">Sektör: Tüm Kutup</option>
                <option value="Kutup & Connecting Ridge">Kutup & Connecting Ridge</option>
                <option value="Shoemaker-Faustini">Shoemaker - Faustini</option>
                <option value="Malapert-Cabeus">Mons Malapert & Cabeus</option>
                <option value="Nobile-Amundsen">Nobile & Amundsen</option>
              </select>
            </div>

            {/* Doku Seçici */}
            <div className="flex items-center bg-gmat-bg/80 rounded-lg border border-gmat-border p-0.5">
              <button
                onClick={() => setLayerMode('wac')}
                className={`px-2 py-0.5 rounded text-[10.5px] font-medium transition-colors ${
                  layerMode === 'wac'
                    ? 'bg-gmat-elevated text-gmat-accent font-semibold shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Doğal WAC
              </button>
              <button
                onClick={() => setLayerMode('topo')}
                className={`px-2 py-0.5 rounded text-[10.5px] font-medium transition-colors ${
                  layerMode === 'topo'
                    ? 'bg-gmat-elevated text-emerald-300 font-semibold shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                QuickMap Topo
              </button>
            </div>

            {/* 3B Kabartma */}
            <button
              onClick={() => setDisplacementEnabled(!displacementEnabled)}
              className={`px-2 py-1 rounded-lg text-[10.5px] font-mono border transition-colors ${
                displacementEnabled
                  ? 'bg-sky-950/70 text-sky-300 border-sky-600/50 font-semibold'
                  : 'bg-gmat-bg/80 text-slate-500 border-gmat-border hover:text-slate-300'
              }`}
              title="3B yükseklik kabartmasını açıp kapatır"
            >
              3B: {displacementEnabled ? 'AÇIK' : 'KAPALI'}
            </button>

            {/* Aydınlatma: Moon Trek vs Güneş */}
            <button
              onClick={() => setIlluminationMode(illuminationMode === 'moontrek' ? 'solar' : 'moontrek')}
              title={illuminationMode === 'moontrek' ? 'NASA Moon Trek Dengeli Aydınlatma (Gözü Yormayan)' : 'Güneş Simülasyonu'}
              className={`px-2 py-1 rounded-lg text-[10.5px] font-mono border transition-colors flex items-center gap-1 ${
                illuminationMode === 'moontrek'
                  ? 'bg-amber-950/60 text-amber-300 border-amber-600/50 font-semibold'
                  : 'bg-gmat-bg/80 text-slate-400 border-gmat-border hover:text-slate-200'
              }`}
            >
              <Sun className="w-3 h-3 text-amber-400" />
              <span>{illuminationMode === 'moontrek' ? 'Moon Trek' : 'Güneş'}</span>
            </button>

            {/* Etiketler (LOD Filter) */}
            <div className="flex items-center bg-gmat-bg/80 rounded-lg border border-gmat-border px-2 py-1 gap-1.5">
              <Layers className="w-3.5 h-3.5 text-gmat-accent shrink-0" />
              <select
                value={labelDisplayMode}
                onChange={(e) => setLabelDisplayMode(e.target.value as any)}
                className="bg-transparent text-[11px] text-gmat-text font-mono outline-none cursor-pointer pr-1"
              >
                <option value="lod">Etiket: Kademeli (LOD)</option>
                <option value="all">Etiket: Tümü</option>
                <option value="off">Etiket: Gizle</option>
              </select>
            </div>

            {/* 3B Araziye Geç */}
            <button
              onClick={() => setCameraMode('terrain')}
              className="px-2.5 py-1 rounded-lg bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 border border-emerald-500/40 text-[10.5px] font-mono font-semibold transition-colors"
            >
              3B Arazi
            </button>
          </>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-mono text-xs">5m LOLA Arazisi:</span>
            <div className="flex items-center bg-gmat-bg/80 rounded-lg border border-gmat-border p-0.5">
              <button
                onClick={() => setSiteId('Site01')}
                className={`px-2 py-0.5 rounded text-[10.5px] font-mono ${
                  siteId === 'Site01'
                    ? 'bg-emerald-900/70 text-emerald-300 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Site01
              </button>
              <button
                onClick={() => setSiteId('Site04')}
                className={`px-2 py-0.5 rounded text-[10.5px] font-mono ${
                  siteId === 'Site04'
                    ? 'bg-emerald-900/70 text-emerald-300 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Site04
              </button>
            </div>
            <button
              onClick={() => setCameraMode('globe')}
              className="px-2.5 py-1 rounded-lg bg-sky-950/80 hover:bg-sky-900 text-sky-300 border border-sky-500/40 text-[10.5px] font-mono font-semibold transition-colors"
            >
              Küreye Dön
            </button>
          </div>
        )}
      </div>

      {/* Mesafe Ölçüm Bildirimi (Aktif Olduğunda Üstte Zarif Kayan Bildirim) */}
      {measurement.active && (
        <div className="absolute top-16 left-3 z-10 flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-950/90 border border-amber-500/50 text-[11px] font-mono text-amber-200 shadow-2xl backdrop-blur-md">
          <Ruler className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span>Mesafe Aracı:</span>
          {measurement.distanceKm !== null ? (
            <span className="font-bold text-amber-300">{measurement.distanceKm} km (Büyük Daire)</span>
          ) : (
            <span className="text-amber-400/80">Küre üzerinde 2 noktaya tıklayın</span>
          )}
          <button
            onClick={resetMeasurement}
            className="ml-2 px-1.5 py-0.5 rounded bg-black/40 hover:bg-black/60 text-[10px] text-amber-300 hover:text-white transition-colors"
          >
            Kapat
          </button>
        </div>
      )}
    </div>
  );
};
