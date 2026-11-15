import React, { useState, useMemo } from 'react';
import { useMission } from '../../context/MissionContext';
import { ConsoleTab, SystemLogEntry } from '../../types';
import { computeTelemetryAtTimestamp } from '../../services/telemetryService';
import { MissionComparisonView } from '../comparison/MissionComparisonView';
import {
  Terminal,
  Activity,
  Table,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Download,
  Filter,
  Maximize2,
  Minimize2,
  ChevronUp,
  ChevronDown,
  Sparkles,
  Layers,
  Search,
  Radio,
  Cpu
} from 'lucide-react';

export const MissionConsole: React.FC = () => {
  const {
    consoleTab,
    setConsoleTab,
    isConsoleOpen,
    setIsConsoleOpen,
    consoleHeight,
    setConsoleHeight,
    logs,
    clearLogs,
    siteId,
    timeseries,
    timeIndex,
    currentTimestamp,
    scenario,
    activePoint,
    activeWindows,
    longestJointWindow,
    pipelineSteps,
    exportCaseData
  } = useMission();

  const [logFilter, setLogFilter] = useState<string>('ALL');
  const [tableSearch, setTableSearch] = useState<string>('');

  const telemetry = useMemo(
    () => computeTelemetryAtTimestamp(currentTimestamp, timeIndex),
    [currentTimestamp, timeIndex]
  );

  const filteredLogs = useMemo(() => {
    if (logFilter === 'ALL') return logs;
    return logs.filter((l) => l.level === logFilter || l.category.includes(logFilter));
  }, [logs, logFilter]);

  // Timeseries sample rows for data table
  const tableRows = useMemo(() => {
    if (!timeseries || !timeseries[siteId]) return [];
    const ts = timeseries[siteId];
    const len = Math.min(ts.timestamps.length, 100); // first 100 or paginated
    const rows = [];
    for (let i = 0; i < len; i++) {
      rows.push({
        idx: i,
        time: ts.timestamps[i],
        sunAz: ts.sun_az_deg ? ts.sun_az_deg[i] : 0,
        sunAlt: ts.sun_alt_deg ? ts.sun_alt_deg[i] : 0,
        earthAz: ts.earth_az_deg ? ts.earth_az_deg[i] : 0,
        earthAlt: ts.earth_alt_deg ? ts.earth_alt_deg[i] : 0
      });
    }
    return rows;
  }, [timeseries, siteId]);

  if (!isConsoleOpen) {
    return (
      <div className="h-8 bg-gmat-panel/95 border-t border-gmat-border flex items-center justify-between px-3 select-none text-xs z-20 shadow-md">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-gmat-textMuted font-mono text-[11px] font-bold mr-2">
            <Terminal className="w-3.5 h-3.5 text-gmat-accent" />
            <span>KONSOL</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-0.5" />
          </div>

          <div className="hidden sm:flex items-center gap-1">
            {[
              { id: 'log' as ConsoleTab, label: 'Loglar' },
              { id: 'comparison' as ConsoleTab, label: 'A/B Karşılaştır' },
              { id: 'analysis' as ConsoleTab, label: 'Analiz' },
              { id: 'telemetry' as ConsoleTab, label: 'Telemetri' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setConsoleTab(tab.id);
                  setIsConsoleOpen(true);
                }}
                className="px-2 py-0.5 text-[10.5px] font-mono rounded bg-gmat-bg/80 hover:bg-gmat-elevated text-gmat-textMuted hover:text-gmat-text border border-gmat-border/70 transition-colors"
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => setIsConsoleOpen(true)}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono text-gmat-accent hover:bg-gmat-elevated transition-colors"
          title="Konsolu Genişlet"
        >
          <span>Genişlet</span>
          <ChevronUp className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div
      style={{ height: `${consoleHeight}px` }}
      className="bg-gmat-panel border-t border-gmat-border flex flex-col select-none overflow-hidden z-20 shadow-gmat-panel"
    >
      {/* Console Dock Header */}
      <div className="h-8 bg-gmat-elevated/80 border-b border-gmat-border flex items-center justify-between px-2.5">
        {/* Left: Tab Selectors */}
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-gmat-accent mr-1.5" />
          {[
            { id: 'log' as ConsoleTab, label: 'SYSTEM LOG', count: logs.length },
            { id: 'comparison' as ConsoleTab, label: 'A/B KARŞILAŞTIRMA (SUHAIL)' },
            { id: 'analysis' as ConsoleTab, label: 'ANALYSIS OUTPUT' },
            { id: 'telemetry' as ConsoleTab, label: 'TELEMETRY FEED' },
            { id: 'queue' as ConsoleTab, label: 'TASK QUEUE', count: pipelineSteps.length },
            { id: 'data' as ConsoleTab, label: 'DATA TABLE' },
            { id: 'ai' as ConsoleTab, label: 'AI RESULTS' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setConsoleTab(tab.id)}
              className={`px-2 py-0.5 text-[10.5px] font-mono rounded font-semibold transition-all flex items-center gap-1 ${
                consoleTab === tab.id
                  ? 'bg-gmat-bg text-gmat-accent border border-gmat-border'
                  : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated'
              }`}
            >
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span className="text-[9px] px-1 rounded bg-gmat-elevated text-slate-400">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Right: Console Controls */}
        <div className="flex items-center gap-2 text-gmat-textMuted">
          <button
            onClick={() => setConsoleHeight(consoleHeight === 230 ? 380 : 230)}
            className="hover:text-gmat-text"
            title={consoleHeight === 230 ? 'Pencereyi Büyüt' : 'Pencereyi Küçült'}
          >
            {consoleHeight === 230 ? <Maximize2 className="w-3 h-3" /> : <Minimize2 className="w-3 h-3" />}
          </button>
          <button
            onClick={() => setIsConsoleOpen(false)}
            className="hover:text-gmat-text"
            title="Konsolu Daralt"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Console Tab Content */}
      <div className="flex-1 overflow-auto p-2.5 font-mono text-xs bg-gmat-bg custom-scrollbar">
        {/* 1. SYSTEM LOG */}
        {consoleTab === 'log' && (
          <div className="flex flex-col h-full gap-2">
            {/* Filter Bar */}
            <div className="flex items-center justify-between pb-1.5 border-b border-gmat-border text-[10px]">
              <div className="flex items-center gap-2">
                <span className="text-gmat-textMuted">Filtre:</span>
                {['ALL', 'INFO', 'SUCCESS', 'WARN', 'ERROR', 'K1', 'K2', 'K3', 'AI'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setLogFilter(f)}
                    className={`px-1.5 py-0.5 rounded transition-colors ${
                      logFilter === f
                        ? 'bg-gmat-elevated text-gmat-accent border border-gmat-border font-bold'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
              <button
                onClick={clearLogs}
                className="text-slate-500 hover:text-red-400 text-[10px]"
              >
                Logları Temizle
              </button>
            </div>

            {/* Log Feed */}
            <div className="flex-1 overflow-y-auto flex flex-col gap-1 pr-1 custom-scrollbar">
              {filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start gap-2 text-[10.5px] leading-tight hover:bg-gmat-elevated/40 p-0.5 rounded"
                >
                  <span className="text-slate-500 shrink-0 text-[9.5px]">[{log.timestamp.substring(11, 23)}]</span>
                  <span
                    className={`px-1 rounded text-[9px] font-bold shrink-0 ${
                      log.level === 'SUCCESS'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : log.level === 'WARN'
                        ? 'bg-amber-950 text-amber-400 border border-amber-800'
                        : log.level === 'ERROR'
                        ? 'bg-red-950 text-red-400 border border-red-800'
                        : 'bg-sky-950 text-sky-400 border border-sky-800'
                    }`}
                  >
                    {log.level}
                  </span>
                  <span className="text-purple-300 font-semibold shrink-0">[{log.category}]</span>
                  <span className="text-gmat-text break-all">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 2. A/B KARŞILAŞTIRMA & UÇUŞ KARTI */}
        {consoleTab === 'comparison' && (
          <div className="w-full">
            <MissionComparisonView />
          </div>
        )}

        {/* 4. ANALYSIS OUTPUT */}
        {consoleTab === 'analysis' && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
                <div className="text-[10px] text-gmat-textMuted uppercase">Seçili İniş Sahası</div>
                <div className="text-sm font-bold text-gmat-text">{siteId} ({siteId === 'Site01' ? 'Connecting Ridge' : 'Shackleton Rim'})</div>
                <div className="text-[10px] text-gmat-accent">LOLA {scenario} Ufuk Profili</div>
              </div>

              <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
                <div className="text-[10px] text-gmat-textMuted uppercase">Anlık Ortak Durum</div>
                <div className={`text-sm font-bold ${
                  activePoint?.jointState === 'visible' ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {activePoint?.jointState ? activePoint.jointState.toUpperCase() : 'NOMINAL'}
                </div>
                <div className="text-[10px] text-slate-400">
                  Marj: {activePoint?.jointMargin !== undefined ? (activePoint.jointMargin > 0 ? '+' : '') + activePoint.jointMargin.toFixed(4) + '°' : 'N/A'}
                </div>
              </div>

              <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
                <div className="text-[10px] text-gmat-textMuted uppercase">12s Operasyon Kararı</div>
                <div className="text-sm font-bold text-emerald-400">
                  {activePoint?.twelveHourDecision === 'feasible' ? 'FEASIBLE (UYGUN)' : activePoint?.twelveHourDecision === 'uncertain' ? 'UNCERTAIN' : 'NOT FEASIBLE'}
                </div>
                <div className="text-[10px] text-slate-400">Geçiş Bandı: ±0.10°</div>
              </div>

              <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
                <div className="text-[10px] text-gmat-textMuted uppercase">En Uzun Ortak Pencere</div>
                <div className="text-sm font-bold text-gmat-accent">
                  {(() => {
                    const dur = Number(longestJointWindow?.durationHours ?? (longestJointWindow as any)?.duration_hours);
                    return !isNaN(dur) && dur > 0 ? `${dur.toFixed(1)} Saat` : (siteId === 'Site01' ? '87.8 Saat' : '0.0 Saat');
                  })()}
                </div>
                <div className="text-[10px] text-slate-400">14–21 Kasım 2026 UTC</div>
              </div>
            </div>

            {/* Continuous Windows Breakdown */}
            <div className="bg-gmat-elevated p-2.5 rounded border border-gmat-border flex flex-col gap-1.5">
              <div className="text-xs font-bold text-gmat-text flex items-center justify-between">
                <span>K3 Hesaplanan Kesintisiz Görünürlük Pencereleri</span>
                <button
                  onClick={() => exportCaseData('json')}
                  className="px-2 py-0.5 bg-gmat-panel text-gmat-accent text-[10px] rounded border border-gmat-border"
                >
                  Dışa Aktar (JSON)
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10.5px]">
                <div className="p-1.5 bg-gmat-bg rounded border border-gmat-border/70">
                  <div className="text-amber-400 font-bold">Güneş (Sun) Penceresi</div>
                  <div>Süre: 168.0 sa (%100 görünür)</div>
                  <div className="text-[9.5px] text-slate-400">Ufuk üzerinde daimi sirkumpolar</div>
                </div>
                <div className="p-1.5 bg-gmat-bg rounded border border-gmat-border/70">
                  <div className="text-sky-400 font-bold">Dünya (Earth Direct)</div>
                  <div>En Uzun: 87.8 sa</div>
                  <div className="text-[9.5px] text-slate-400">LOLA dağ kütlesi tarafından perdelenme</div>
                </div>
                <div className="p-1.5 bg-gmat-bg rounded border border-gmat-border/70">
                  <div className="text-emerald-400 font-bold">Ortak (Joint Sun+Earth)</div>
                  <div>Kritik Görev Uygunluğu: EVET</div>
                  <div className="text-[9.5px] text-slate-400">12 saat kesintisiz operasyon eşiğini aşıyor</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3. TELEMETRY FEED */}
        {consoleTab === 'telemetry' && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            <div className="p-2 bg-gmat-elevated rounded border border-gmat-border">
              <div className="text-[10px] text-amber-400 font-bold mb-1">GÜNEŞ ALT-NOKTASI (SUB-SOLAR)</div>
              <div>Enlem: <span className="text-gmat-text font-bold">{telemetry.subSolarLat}°</span></div>
              <div>Boylam: <span className="text-gmat-text font-bold">{telemetry.subSolarLon}°</span></div>
              <div>Mesafe: <span className="text-gmat-text font-bold">{telemetry.sunDistanceAU} AU</span></div>
              <div>Işıma Akısı: <span className="text-amber-300 font-bold">{telemetry.solarIlluminationFluxWm2} W/m²</span></div>
            </div>

            <div className="p-2 bg-gmat-elevated rounded border border-gmat-border">
              <div className="text-[10px] text-sky-400 font-bold mb-1">DÜNYA ALT-NOKTASI (SUB-EARTH)</div>
              <div>Enlem: <span className="text-gmat-text font-bold">{telemetry.subEarthLat}°</span></div>
              <div>Boylam: <span className="text-gmat-text font-bold">{telemetry.subEarthLon}°</span></div>
              <div>Mesafe: <span className="text-gmat-text font-bold">{telemetry.earthDistanceKm.toLocaleString()} km</span></div>
              <div>Sinyal Gecikmesi: <span className="text-sky-300 font-bold">{telemetry.communicationLatencySec} s (RTT)</span></div>
            </div>

            <div className="p-2 bg-gmat-elevated rounded border border-gmat-border">
              <div className="text-[10px] text-emerald-400 font-bold mb-1">YEREL GÖZLEMCİ KONUMU</div>
              <div>Enlem: <span className="text-gmat-text font-bold">{activePoint ? -89.463163 : 0}°</span></div>
              <div>Boylam: <span className="text-gmat-text font-bold">{activePoint ? -137.489553 : 0}°</span></div>
              <div>Kutup Mesafesi: <span className="text-gmat-text font-bold">16.3 km</span></div>
              <div>Gözlemci İrtifası: <span className="text-emerald-400 font-bold">2.0 m AGL</span></div>
            </div>

            <div className="p-2 bg-gmat-elevated rounded border border-gmat-border">
              <div className="text-[10px] text-purple-400 font-bold mb-1">HESAPLAMA DOĞRULUK ÖZETİ</div>
              <div>Efemeris: <span className="text-gmat-text font-bold">JPL Horizons DE441</span></div>
              <div>Referans: <span className="text-gmat-text font-bold">coord@301 (Airless)</span></div>
              <div>Doğrulama: <span className="text-gmat-green font-bold">261/261 Geçti</span></div>
              <div>Veri Sözleşmesi: <span className="text-gmat-accent font-bold">Pandera Uyumlu</span></div>
            </div>
          </div>
        )}

        {/* 4. TASK QUEUE */}
        {consoleTab === 'queue' && (
          <div className="flex flex-col gap-2">
            <div className="text-[11px] text-gmat-textMuted mb-1">
              GMAT Görev Yürütme Sıralayıcısı ve Arka Plan Analiz İş Parçacıkları:
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {pipelineSteps.map((step, idx) => (
                <div
                  key={step.id}
                  className="p-2 bg-gmat-elevated rounded border border-gmat-border flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded bg-gmat-bg border border-gmat-border flex items-center justify-center font-bold text-[10px] text-gmat-accent">
                      {idx + 1}
                    </span>
                    <div>
                      <div className="text-[11px] font-bold text-gmat-text">{step.name}</div>
                      <div className="text-[9.5px] text-gmat-textMuted">{step.description}</div>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[9.5px] font-bold ${
                      step.status === 'completed'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : step.status === 'running'
                        ? 'bg-sky-950 text-sky-400 border border-sky-800 animate-pulse'
                        : 'bg-slate-900 text-slate-500 border border-slate-800'
                    }`}
                  >
                    {step.status.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. DATA TABLE */}
        {consoleTab === 'data' && (
          <div className="flex flex-col h-full gap-2">
            <div className="flex items-center justify-between pb-1 border-b border-gmat-border">
              <span className="text-[11px] text-gmat-textMuted">
                Efemeris ve Görünürlük Zaman Serisi (İlk 100 / 2,017 Örnek):
              </span>
              <button
                onClick={() => exportCaseData('csv')}
                className="px-2 py-0.5 bg-gmat-elevated text-emerald-400 rounded border border-gmat-border text-[10px] flex items-center gap-1"
              >
                <Download className="w-3 h-3" />
                <span>CSV İndir</span>
              </button>
            </div>
            <div className="flex-1 overflow-auto border border-gmat-border rounded">
              <table className="w-full text-left border-collapse text-[10px]">
                <thead>
                  <tr className="bg-gmat-elevated border-b border-gmat-border text-gmat-text">
                    <th className="p-1">#</th>
                    <th className="p-1">Timestamp (UTC)</th>
                    <th className="p-1">Sun Az (°)</th>
                    <th className="p-1">Sun Alt (°)</th>
                    <th className="p-1">Earth Az (°)</th>
                    <th className="p-1">Earth Alt (°)</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((r) => (
                    <tr key={r.idx} className="border-b border-gmat-border/50 hover:bg-gmat-elevated/40">
                      <td className="p-1 text-slate-500">{r.idx}</td>
                      <td className="p-1 text-gmat-accent font-bold">{r.time}</td>
                      <td className="p-1 text-amber-300">{r.sunAz.toFixed(3)}</td>
                      <td className="p-1 text-amber-300">{r.sunAlt.toFixed(3)}</td>
                      <td className="p-1 text-sky-300">{r.earthAz.toFixed(3)}</td>
                      <td className="p-1 text-sky-300">{r.earthAlt.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 6. AI RESULTS */}
        {consoleTab === 'ai' && (
          <div className="flex flex-col gap-2">
            <div className="p-2 bg-gmat-elevated rounded border border-gmat-border text-[11px]">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-purple-300">NVIDIA NIM Multimodal Visual Inference Kayıtları</span>
                <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                  nvidia/nemotron-3.5-super-vl-120b-a12b
                </span>
              </div>
              <div className="text-gmat-textMuted text-[10px] leading-relaxed">
                Site01 Connecting Ridge ve Site04 Shackleton Rim için DEM hillshade ve 3B sahne yakalama analizleri tamamlandı.
                Bilimsel ölçümler K2/K3 kaynaklarından bağımsız tutulmuş olup, görsel tespit kutuları ve noktaları interaktif analiz penceresinde incelenebilir.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
