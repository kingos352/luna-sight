import React, { Suspense } from 'react';
import * as THREE from 'three';
import { Canvas } from '@react-three/fiber';
import { Stars } from '@react-three/drei';
import { LunarGlobe } from './LunarGlobe';
import { TerrainMesh } from './TerrainMesh';
import { CameraControls } from './CameraControls';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { useMission } from '../../context/MissionContext';
import { Globe, Mountain, Eye, Sparkles } from 'lucide-react';

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
    isCaseActive,
    isVirtualPatchApplied,
    toggleVirtualPatch
  } = useMission();

  return (
    <div className="relative w-full h-full bg-space-950 overflow-hidden select-none">
      <ErrorBoundary fallbackTitle="3B Ay Sahnesi Yüklenemedi (WebGL Fallback)">
        <div id="luna-sight-webgl-container" className="w-full h-full">
          <Canvas
            shadows
            dpr={[1, 2]}
            camera={{ fov: 45, near: 0.1, far: 2000, position: [0, -9, 8] }}
            gl={{
              antialias: true,
              alpha: false,
              preserveDrawingBuffer: true,
              powerPreference: 'high-performance',
              toneMapping: THREE.ACESFilmicToneMapping,
              toneMappingExposure: 1.2
            }}
            className="w-full h-full"
          >
          <color attach="background" args={['#040609']} />

          {/* Derin Uzay Işıklandırması: Yüksek Kontrastlı Doğrudan Güneş Işığı */}
          <ambientLight intensity={0.06} />

          {/* Güneş (Doğrudan Yüksek Yoğunluklu Paralel Işık) */}
          <directionalLight
            position={[45, 12, -25]}
            intensity={2.8}
            color="#fffbf0"
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-bias={-0.0001}
          />

          {/* Dünya Parlaması (Earthshine - Buz Mavisi Hafif Dolgu) */}
          <directionalLight position={[-30, -5, 25]} intensity={0.25} color="#38bdf8" />

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

      {/* 3B Sahne Üzeri Zarif, Minimal Bilgi Rozeti */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-space-950/80 backdrop-blur border border-slate-800/80 text-[11px] text-slate-300 shadow-md">
          {cameraMode === 'globe' ? (
            <>
              <Globe className="w-3.5 h-3.5 text-sky-400" />
              <span>Ay Küresi ({layerMode === 'wac' ? 'NASA Moon Trek 4K WAC' : 'QuickMap LOLA Topoğrafya'})</span>
            </>
          ) : cameraMode === 'terrain' ? (
            <>
              <Mountain className="w-3.5 h-3.5 text-emerald-400" />
              <span>{siteId === 'Site01' ? 'Connecting Ridge (Site01)' : 'Shackleton Rim (Site04)'} LOLA 5m Arazisi</span>
            </>
          ) : (
            <>
              <Eye className="w-3.5 h-3.5 text-amber-400" />
              <span>Yüzey Gözlemci Bakışı (h = 2.0 m)</span>
            </>
          )}
        </div>

        {cameraMode === 'terrain' && (
          <button
            onClick={() => setCameraMode('globe')}
            className="px-2.5 py-1 rounded-md bg-sky-950/80 hover:bg-sky-900 border border-sky-500/50 text-[11px] text-sky-200 shadow-md flex items-center gap-1 transition-all"
          >
            <Globe className="w-3.5 h-3.5" />
            <span>Küreye Dön</span>
          </button>
        )}
      </div>

      {/* Sağ Üst: Doku & Topoğrafya Katman Seçici */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 p-1 rounded-lg bg-space-950/90 backdrop-blur border border-slate-800/90 text-xs shadow-lg">
        {cameraMode === 'globe' ? (
          <>
            <button
              onClick={() => setLayerMode('wac')}
              className={`px-2.5 py-1 rounded-md font-medium text-[11px] flex items-center gap-1 transition-all ${
                layerMode === 'wac'
                  ? 'bg-space-800 text-sky-300 border border-sky-500/50 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>🌕 Doğal WAC</span>
            </button>

            <button
              onClick={() => setLayerMode('topo')}
              className={`px-2.5 py-1 rounded-md font-medium text-[11px] flex items-center gap-1 transition-all ${
                layerMode === 'topo'
                  ? 'bg-space-800 text-emerald-300 border border-emerald-500/50 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>🌈 QuickMap Topo</span>
            </button>

            <div className="w-[1px] h-4 bg-slate-800 mx-0.5" />

            <button
              onClick={() => setDisplacementEnabled(!displacementEnabled)}
              title="Küre üzerindeki fiziksel 3B yükseklik kabartmasını açıp kapatır"
              className={`px-2 py-1 rounded-md font-mono text-[10px] transition-all ${
                displacementEnabled
                  ? 'bg-amber-950/70 text-amber-300 border border-amber-500/50'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              <span>3B Kabartma: {displacementEnabled ? 'AÇIK' : 'KAPALI'}</span>
            </button>
          </>
        ) : (
          <div className="flex items-center gap-1 text-[11px] px-2 py-1 text-slate-300">
            <span>Arazi:</span>
            <button
              onClick={() => setSiteId('Site01')}
              className={`px-2 py-0.5 rounded text-[10px] font-mono ${siteId === 'Site01' ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-500/50' : 'text-slate-400'}`}
            >
              Site01
            </button>
            <button
              onClick={() => setSiteId('Site04')}
              className={`px-2 py-0.5 rounded text-[10px] font-mono ${siteId === 'Site04' ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-500/50' : 'text-slate-400'}`}
            >
              Site04
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
