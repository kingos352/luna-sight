import React, { useState } from 'react';
import { useMission } from '../../context/MissionContext';
import { SITES } from '../../services/dataService';
import { ElevationMarginChart } from '../analysis/ElevationMarginChart';
import { SurveySection } from '../analysis/SurveySection';
import { MissionComparisonView } from '../comparison/MissionComparisonView';
import {
  Compass,
  Mountain,
  Radio,
  Sun,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Info,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Layers,
  MapPin,
  ChevronRight,
  Maximize2
} from 'lucide-react';

type InspectorTab = 'telemetry' | 'terrain' | 'crater' | 'comparison' | 'ai';

export const ScientificInspector: React.FC<{ onOpenAI?: () => void; onClose?: () => void }> = ({ onOpenAI, onClose }) => {
  const {
    siteId,
    activePoint,
    scenario,
    longestJointWindow,
    minDurationHours,
    selectedCrater,
    setSelectedCrater,
    aiConfig
  } = useMission();

  const [activeTab, setActiveTab] = useState<InspectorTab>('telemetry');

  // Küreden veya gezginden bir krater/düzlük seçildiğinde otomatik müfettiş sekmesine geç
  React.useEffect(() => {
    if (selectedCrater) {
      setActiveTab('crater');
    }
  }, [selectedCrater]);

  const site = SITES[siteId];
  const { jointState, jointMargin, twelveHourDecision, sunAlt, sunAz, earthAlt, earthAz, sunHorizon, earthHorizon } = activePoint;

  return (
    <aside className="w-84 lg:w-96 h-full bg-gmat-panel border-l border-gmat-border flex flex-col select-none overflow-hidden shadow-gmat-panel">
      {/* Inspector Header & Tabs */}
      <div className="h-9 border-b border-gmat-border flex items-center justify-between px-2.5 bg-gmat-elevated/60">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-gmat-text">
          <Info className="w-3.5 h-3.5 text-gmat-accent" />
          <span>Scientific Inspector</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="flex items-center bg-gmat-bg p-0.5 rounded border border-gmat-border gap-0.5">
            {[
              { id: 'telemetry' as InspectorTab, label: 'Telemetri' },
              { id: 'terrain' as InspectorTab, label: 'Arazi' },
              { id: 'crater' as InspectorTab, label: 'Krater' },
              { id: 'comparison' as InspectorTab, label: 'Karşılaştır' },
              { id: 'ai' as InspectorTab, label: 'AI' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-1.5 py-0.5 text-[10.5px] font-mono rounded transition-all ${
                  activeTab === tab.id
                    ? 'bg-gmat-elevated text-gmat-accent border border-gmat-border font-bold'
                    : 'text-gmat-textMuted hover:text-gmat-text'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-gmat-bg text-gmat-textMuted hover:text-gmat-text transition-colors"
              title="Paneli Kapat"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Inspector Body Content */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3 custom-scrollbar">
        {/* TAB 1: TELEMETRY & VISIBILITY */}
        {activeTab === 'telemetry' && (
          <>
            {/* Site & Operational Status Card */}
            <div className="bg-gmat-bg p-3 rounded-lg border border-gmat-border">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-gmat-accent" />
                  <span className="text-sm font-bold text-gmat-text">{site.nameTr}</span>
                </div>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gmat-elevated border border-gmat-border text-gmat-accent font-bold">
                  {site.id}
                </span>
              </div>
              <div className="text-[11px] text-gmat-textMuted mb-2">
                {site.description}
              </div>

              {/* Coordinates Grid */}
              <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono bg-gmat-elevated/70 p-2 rounded border border-gmat-border mb-2.5">
                <div>Enlem: <span className="text-gmat-text font-bold">{site.lat}°</span></div>
                <div>Boylam (D): <span className="text-gmat-text font-bold">{site.lonEast}°</span></div>
                <div>Tarama Kapsamı: <span className="text-gmat-accent font-bold">{scenario}</span></div>
              </div>

              {/* Instant Joint State Badge */}
              <div className="flex items-center justify-between p-2 rounded bg-gmat-elevated border border-gmat-border">
                <span className="text-xs font-semibold text-gmat-text flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-gmat-accent" />
                  Ortak Görünürlük
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold flex items-center gap-1 uppercase ${
                    jointState === 'visible'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-gmat-green'
                      : jointState === 'blocked'
                      ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  }`}
                >
                  {jointState === 'visible' ? (
                    <>
                      <CheckCircle className="w-3 h-3 text-emerald-400" />
                      Görünür
                    </>
                  ) : jointState === 'blocked' ? (
                    <>
                      <XCircle className="w-3 h-3 text-red-400" />
                      Engelli
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="w-3 h-3 text-amber-400" />
                      Belirsiz
                    </>
                  )}
                </span>
              </div>
            </div>

            {/* Sun & Earth Vector Readout */}
            <div className="bg-gmat-bg p-3 rounded-lg border border-gmat-border flex flex-col gap-2">
              <span className="text-xs font-semibold text-gmat-text flex items-center gap-1.5">
                <Sun className="w-3.5 h-3.5 text-amber-400" />
                Gök Cisimleri Konum Vektörleri
              </span>

              {/* Sun Vectors */}
              <div className="p-2 rounded bg-gmat-elevated/60 border border-gmat-border/70 text-[10.5px] font-mono">
                <div className="flex justify-between text-amber-300 font-bold mb-1">
                  <span>Güneş (Sun)</span>
                  <span>Az: {sunAz.toFixed(2)}° | Alt: {sunAlt.toFixed(2)}°</span>
                </div>
                <div className="flex justify-between text-gmat-textMuted text-[10px]">
                  <span>Ufuk Yüksekliği:</span>
                  <span className="text-slate-300">{sunHorizon.toFixed(2)}°</span>
                </div>
                <div className="flex justify-between text-gmat-textMuted text-[10px]">
                  <span>Açısal Marj:</span>
                  <span className={sunAlt - sunHorizon > 0 ? 'text-gmat-green font-bold' : 'text-gmat-red font-bold'}>
                    {(sunAlt - sunHorizon > 0 ? '+' : '') + (sunAlt - sunHorizon).toFixed(3)}°
                  </span>
                </div>
              </div>

              {/* Earth Vectors */}
              <div className="p-2 rounded bg-gmat-elevated/60 border border-gmat-border/70 text-[10.5px] font-mono">
                <div className="flex justify-between text-sky-300 font-bold mb-1">
                  <span>Dünya (Earth)</span>
                  <span>Az: {earthAz.toFixed(2)}° | Alt: {earthAlt.toFixed(2)}°</span>
                </div>
                <div className="flex justify-between text-gmat-textMuted text-[10px]">
                  <span>Ufuk Yüksekliği:</span>
                  <span className="text-slate-300">{earthHorizon.toFixed(2)}°</span>
                </div>
                <div className="flex justify-between text-gmat-textMuted text-[10px]">
                  <span>Açısal Marj:</span>
                  <span className={earthAlt - earthHorizon > 0 ? 'text-gmat-green font-bold' : 'text-gmat-red font-bold'}>
                    {(earthAlt - earthHorizon > 0 ? '+' : '') + (earthAlt - earthHorizon).toFixed(3)}°
                  </span>
                </div>
              </div>
            </div>

            {/* Interactive Horizon Profile Graph */}
            <ElevationMarginChart />
          </>
        )}

        {/* TAB 2: TERRAIN & VIRTUAL PATCH */}
        {activeTab === 'terrain' && (
          <>
            <div className="bg-gmat-bg p-3 rounded-lg border border-gmat-border flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gmat-text flex items-center gap-1.5">
                  <Mountain className="w-3.5 h-3.5 text-emerald-400" />
                  LOLA Topoğrafya Spesifikasyonu
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gmat-elevated text-emerald-400">
                  LOLA LDEM
                </span>
              </div>
              <div className="text-[11px] text-gmat-textMuted">
                NASA Lunar Reconnaissance Orbiter (LRO) Laser Altimeter 5 metre/piksel polar stereografik ızgarası.
              </div>
              <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono bg-gmat-elevated p-2 rounded border border-gmat-border">
                <div>Izgara Boyutu: <span className="text-gmat-text">801 × 801 px</span></div>
                <div>Örnekleme: <span className="text-gmat-text">5.00 m/px</span></div>
                <div>Altimetre Kapsamı: <span className="text-gmat-text">8% - 11% (LDEC)</span></div>
                <div>Gözlemci Yüksekliği: <span className="text-gmat-text">2.0 m</span></div>
              </div>
            </div>

            {/* Survey Section */}
            <SurveySection />
          </>
        )}

        {/* TAB 3: CRATER & PLAIN CATALOG & HAZARDS */}
        {activeTab === 'crater' && (
          <div className="bg-gmat-bg p-3 rounded-lg border border-gmat-border flex flex-col gap-2.5">
            <span className="text-xs font-semibold text-gmat-text flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-gmat-amber" />
              <span>Güney Kutbu Özellik İncelemesi</span>
            </span>

            {selectedCrater ? (
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between p-2 rounded bg-gmat-elevated border border-gmat-border">
                  <div>
                    <div className="text-sm font-bold text-gmat-text">{selectedCrater.name}</div>
                    <div className="text-[9.5px] font-mono text-sky-400">
                      {selectedCrater.sector || 'Güney Kutup Sektörü'}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                      selectedCrater.hazardRisk === 'Severe'
                        ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                        : selectedCrater.hazardRisk === 'High'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    }`}>
                      {selectedCrater.hazardRisk} Risk
                    </span>
                    <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg border border-gmat-border text-gmat-textDim uppercase">
                      {selectedCrater.type === 'plain'
                        ? 'DÜZLÜK'
                        : selectedCrater.type === 'plateau'
                        ? 'PLATO'
                        : selectedCrater.type === 'peak'
                        ? 'ZİRVE'
                        : selectedCrater.type === 'ridge'
                        ? 'SIRT'
                        : selectedCrater.type === 'site'
                        ? 'KUTUP NOKTASI'
                        : 'KRATER'}
                    </span>
                  </div>
                </div>

                <div className="text-[11px] text-gmat-textMuted leading-relaxed">
                  {selectedCrater.scientificInterest}
                </div>

                <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono bg-gmat-elevated p-2 rounded border border-gmat-border">
                  {selectedCrater.diameterKm !== undefined && (
                    <div>{selectedCrater.type === 'plain' || selectedCrater.type === 'plateau' ? 'Genişlik:' : 'Çap:'} <span className="text-gmat-text font-bold">{selectedCrater.diameterKm} km</span></div>
                  )}
                  <div>Kalıcı Gölge (PSR): <span className={selectedCrater.permanentlyShadowed ? 'text-amber-400 font-bold' : 'text-slate-400 font-bold'}>{selectedCrater.permanentlyShadowed ? 'EVET' : 'HAYIR'}</span></div>
                  <div>Enlem: <span className="text-gmat-text">{selectedCrater.lat}°</span></div>
                  <div>Boylam (D): <span className="text-gmat-text">{selectedCrater.lonEast}°</span></div>
                  <div>Önem Kademesi: <span className="text-gmat-accent font-bold">LOD {selectedCrater.tier || 1}</span></div>
                </div>

                <button
                  onClick={() => setSelectedCrater(null)}
                  className="mt-1 py-1 px-2 text-xs text-gmat-textMuted hover:text-gmat-text bg-gmat-elevated hover:bg-gmat-elevated/80 rounded border border-gmat-border transition-colors"
                >
                  Seçimi Temizle
                </button>
              </div>
            ) : (
              <div className="p-4 text-center text-xs text-gmat-textMuted bg-gmat-elevated/40 rounded border border-dashed border-gmat-border">
                3B Ay küresi üzerindeki herhangi bir krater veya düzlük etiketine tıklayarak bilimsel özelliklerini inceleyin.
              </div>
            )}
          </div>
        )}

        {/* TAB 4: A/B COMPARISON & FLIGHT BRIEFING */}
        {activeTab === 'comparison' && (
          <div className="w-full">
            <MissionComparisonView />
          </div>
        )}

        {/* TAB 5: LUNARSIGHT AI */}
        {activeTab === 'ai' && (
          <div className="bg-gmat-bg p-3 rounded-lg border border-gmat-border flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gmat-text flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                LunarSight AI Asistanı
              </span>
              <span className="text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-500/30">
                NIM VLM
              </span>
            </div>

            <div className="text-[11px] text-gmat-textMuted leading-normal">
              NVIDIA NIM çok modlu görsel yapay zeka modeli (`nvidia/nemotron-3.5-super-vl-120b-a12b`), LOLA DEM hillshade ve 3B sahne yakalamaları üzerinde jeolojik görsel analiz yapar.
            </div>

            <div className="p-2 rounded bg-gmat-elevated border border-gmat-border font-mono text-[10px] flex flex-col gap-1">
              <div className="flex justify-between">
                <span className="text-gmat-textMuted">Aktif Model:</span>
                <span className="text-purple-300 truncate max-w-[180px]">nemotron-3.5-super-vl-120b</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gmat-textMuted">Çıkarım Durumu:</span>
                <span className="text-emerald-400 font-bold">READY (ONLINE)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gmat-textMuted">Giriş Kaynağı:</span>
                <span className="text-slate-300">LOLA 5m/px DEM Hillshade</span>
              </div>
            </div>

            <button
              onClick={onOpenAI}
              className="py-2 px-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition-all"
            >
              <Sparkles className="w-4 h-4 text-purple-200" />
              <span>LunarSight AI Analiz Panelini Aç</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};
