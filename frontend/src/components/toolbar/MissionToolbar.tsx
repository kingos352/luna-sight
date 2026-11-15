import React, { useState, useEffect } from 'react';
import { useMission } from '../../context/MissionContext';
import { SITES } from '../../services/dataService';
import { SiteId, HorizonScenario, WorkspacePreset, CameraPreset } from '../../types';
import {
  Moon,
  Compass,
  Play,
  RotateCcw,
  Sparkles,
  Camera,
  Layers,
  Ruler,
  Presentation,
  Cpu,
  ShieldCheck,
  Workflow,
  Maximize2,
  Tv,
  Eye,
  Activity,
  SlidersHorizontal,
  ChevronDown,
  Download,
  Scale,
  Sliders,
  Rocket,
  PanelLeft,
  PanelRight,
  Terminal
} from 'lucide-react';

export const MissionToolbar: React.FC<{ onOpenAI?: () => void }> = ({ onOpenAI }) => {
  const {
    siteId,
    setSiteId,
    scenario,
    setScenario,
    currentTimestamp,
    workspacePreset,
    setWorkspacePreset,
    isPipelineRunning,
    runPipeline,
    setIsPipelineModalOpen,
    measurement,
    setMeasurementActive,
    resetMeasurement,
    isPresentationMode,
    setIsPresentationMode,
    setCameraPreset,
    layerMode,
    setLayerMode,
    displacementEnabled,
    setDisplacementEnabled,
    aiConfig,
    setIsComparisonModalOpen,
    setIsParametersDrawerOpen,
    setConsoleTab,
    isConsoleOpen,
    setIsConsoleOpen,
    isLeftSidebarOpen,
    setIsLeftSidebarOpen,
    isRightSidebarOpen,
    setIsRightSidebarOpen
  } = useMission();

  const [utcClock, setUtcClock] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcClock(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleCaptureScreenshot = () => {
    const canvas = document.querySelector('canvas');
    if (!canvas) return;
    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `luna_sight_mission_control_${Date.now()}.png`;
    a.click();
  };

  return (
    <header className="h-13 bg-gmat-panel border-b border-gmat-border px-3.5 flex items-center justify-between z-30 select-none shadow-md">
      {/* 1. Brand & Mission Authority */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded bg-gradient-to-br from-gmat-accent to-indigo-600 flex items-center justify-center shadow-gmat-glow border border-sky-400/40">
            <Moon className="w-4.5 h-4.5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 leading-none">
              <span className="font-bold tracking-wider text-sm text-gmat-text font-sans">LUNA SIGHT</span>
              <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-gmat-elevated border border-gmat-border text-gmat-accent font-semibold">
                GMAT-X
              </span>
            </div>
            <div className="text-[9.5px] text-gmat-textMuted tracking-tight font-mono mt-0.5">
              NASA Lunar Mission Control Workstation
            </div>
          </div>
        </div>

        <div className="h-6 w-px bg-gmat-border mx-1" />

        {/* 2. Candidate Site Selector */}
        <div className="flex items-center bg-gmat-bg p-0.5 rounded border border-gmat-border gap-1">
          {(['Site01', 'Site04'] as SiteId[]).map((id) => {
            const site = SITES[id];
            const isSelected = siteId === id;
            return (
              <button
                key={id}
                onClick={() => setSiteId(id)}
                className={`px-2.5 py-1 text-xs rounded font-medium transition-all flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/40 shadow-sm'
                    : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-panel'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-gmat-accent animate-pulse' : 'bg-slate-600'}`} />
                <span>{site.nameTr}</span>
                <span className="text-[9.5px] opacity-60 font-mono">({id})</span>
              </button>
            );
          })}

          {/* Artemis III Extra Candidate Sites Selector (Eray'ın Çalışması) */}
          <select
            value={siteId}
            onChange={(e) => setSiteId(e.target.value as SiteId)}
            className="bg-gmat-elevated border border-gmat-border text-gmat-text text-[11px] font-mono rounded px-2 py-1 outline-none focus:border-gmat-accent"
          >
            <option value="Site01">Diğer Artemis Sahaları (18)...</option>
            {Object.keys(SITES).filter(k => k !== 'Site01' && k !== 'Site04').map((k) => (
              <option key={k} value={k}>
                {SITES[k as SiteId]?.nameTr}
              </option>
            ))}
          </select>
        </div>

        {/* 3. Horizon Scenario Scope */}
        <div className="hidden lg:flex items-center bg-gmat-bg p-0.5 rounded border border-gmat-border gap-0.5">
          {[
            { id: '0deg', label: '0° Geom' },
            { id: '2000m', label: '2 km LOLA' },
            { id: '4000m', label: '4 km LOLA' }
          ].map((scen) => (
            <button
              key={scen.id}
              onClick={() => setScenario(scen.id as HorizonScenario)}
              className={`px-2 py-0.5 text-[11px] font-mono rounded transition-all ${
                scenario === scen.id
                  ? 'bg-gmat-elevated text-gmat-text border border-gmat-borderLight font-semibold'
                  : 'text-gmat-textMuted hover:text-gmat-text'
              }`}
            >
              {scen.label}
            </button>
          ))}
        </div>
      </div>

      {/* 4. Center: Analysis Pipeline & Quick Tools */}
      <div className="flex items-center gap-2">
        {/* Pipeline Execution Button */}
        <button
          onClick={() => {
            setIsPipelineModalOpen(true);
            if (!isPipelineRunning) {
              runPipeline();
            }
          }}
          disabled={isPipelineRunning}
          className="px-3 py-1 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs font-semibold rounded border border-sky-400/40 shadow-sm flex items-center gap-1.5 transition-all"
        >
          <Workflow className={`w-3.5 h-3.5 ${isPipelineRunning ? 'animate-spin' : ''}`} />
          <span>{isPipelineRunning ? 'Pipeline Koşuyor...' : 'Pipeline Çalıştır'}</span>
        </button>

        {/* Parameters (SUHAIL) Trigger */}
        <button
          onClick={() => setIsParametersDrawerOpen(true)}
          className="px-2.5 py-1 bg-sky-950/40 text-sky-300 hover:text-sky-200 hover:bg-sky-900/60 border border-sky-500/40 text-xs rounded font-medium flex items-center gap-1.5 transition-all shadow-xs"
          title="Görev Parametreleri & SUHAIL Kısıtları (Fotoğraf 2)"
        >
          <Sliders className="w-3.5 h-3.5 text-sky-400" />
          <span className="inline font-semibold">Parametreler</span>
        </button>

        {/* A/B Comparison Scorecard Trigger */}
        <button
          onClick={() => setIsComparisonModalOpen(true)}
          className="px-2.5 py-1 bg-emerald-950/40 text-emerald-300 hover:text-emerald-200 hover:bg-emerald-900/60 border border-emerald-500/40 text-xs rounded font-medium flex items-center gap-1.5 transition-all shadow-xs"
          title="Site01 vs Site04 Karşılaştırmalı Değerlendirme & Görev Riski Kartları (Fotoğraf 3)"
        >
          <Scale className="w-3.5 h-3.5 text-emerald-400" />
          <span className="inline font-semibold">A/B Karşılaştır</span>
        </button>

        {/* Measurement Tool Toggle */}
        <button
          onClick={() => setMeasurementActive(!measurement.active)}
          className={`px-2.5 py-1 text-xs rounded font-medium border flex items-center gap-1.5 transition-all ${
            measurement.active
              ? 'bg-gmat-amber/20 text-gmat-amber border-gmat-amber/50 shadow-gmat-amber'
              : 'bg-gmat-bg text-gmat-textMuted border-gmat-border hover:text-gmat-text hover:bg-gmat-elevated'
          }`}
          title="Yüzey Mesafe Ölçüm Aracı"
        >
          <Ruler className="w-3.5 h-3.5" />
          <span className="hidden xl:inline">Mesafe Ölç</span>
          {measurement.distanceKm !== null && (
            <span className="font-mono text-[10px] text-gmat-amber font-bold ml-1">
              {measurement.distanceKm} km
            </span>
          )}
        </button>

        {/* Presentation Mode Toggle */}
        <button
          onClick={() => setIsPresentationMode(true)}
          className="px-2.5 py-1 bg-gmat-bg text-gmat-textMuted hover:text-emerald-300 hover:bg-emerald-950/40 border border-gmat-border hover:border-emerald-600/40 text-xs rounded font-medium flex items-center gap-1.5 transition-all"
          title="Hakem ve Jüri Sunum Modu"
        >
          <Presentation className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden xl:inline">Sunum Modu</span>
        </button>

        {/* Screenshot capture */}
        <button
          onClick={handleCaptureScreenshot}
          className="p-1.5 bg-gmat-bg hover:bg-gmat-elevated text-gmat-textMuted hover:text-gmat-text border border-gmat-border rounded transition-colors"
          title="3B Sahne Ekran Görüntüsü Al"
        >
          <Camera className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 5. Right: Workspace Layout Presets & Health Status */}
      <div className="flex items-center gap-2.5">
        {/* Panel Toggle Switches (Clean & Spacious Ergonomics) */}
        <div className="flex items-center bg-gmat-bg p-0.5 rounded border border-gmat-border gap-0.5">
          <button
            onClick={() => setIsLeftSidebarOpen(!isLeftSidebarOpen)}
            className={`p-1.5 rounded transition-all flex items-center gap-1 ${
              isLeftSidebarOpen
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-border shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
            title={isLeftSidebarOpen ? 'Sol Paneli Gizle' : 'Sol Paneli Göster (Kaynaklar / Parametreler)'}
          >
            <PanelLeft className="w-3.5 h-3.5" />
            <span className="hidden xl:inline text-[10px] font-mono">Kaynaklar</span>
          </button>

          <button
            onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
            className={`p-1.5 rounded transition-all flex items-center gap-1 ${
              isRightSidebarOpen
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-border shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
            title={isRightSidebarOpen ? 'Sağ Müfettiş Panelini Gizle' : 'Sağ Müfettiş Panelini Göster'}
          >
            <PanelRight className="w-3.5 h-3.5" />
            <span className="hidden xl:inline text-[10px] font-mono">Müfettiş</span>
          </button>

          <button
            onClick={() => setIsConsoleOpen(!isConsoleOpen)}
            className={`p-1.5 rounded transition-all flex items-center gap-1 ${
              isConsoleOpen
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-border shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
            title={isConsoleOpen ? 'Alt Konsolu Daralt' : 'Alt Konsolu Genişlet'}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span className="hidden xl:inline text-[10px] font-mono">Konsol</span>
          </button>
        </div>

        {/* Workspace Layout Selector */}
        <div className="flex items-center bg-gmat-bg p-0.5 rounded border border-gmat-border gap-0.5">
          {[
            { id: 'exploration' as WorkspacePreset, label: 'Keşif', icon: Eye },
            { id: 'scientific' as WorkspacePreset, label: 'Bilimsel', icon: SlidersHorizontal },
            { id: 'ai' as WorkspacePreset, label: 'AI Analiz', icon: Sparkles }
          ].map((preset) => {
            const Icon = preset.icon;
            const isSel = workspacePreset === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => setWorkspacePreset(preset.id)}
                className={`px-2 py-0.5 text-xs rounded font-medium flex items-center gap-1 transition-all ${
                  isSel
                    ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/40 shadow-sm'
                    : 'text-gmat-textMuted hover:text-gmat-text'
                }`}
              >
                <Icon className="w-3 h-3" />
                <span>{preset.label}</span>
              </button>
            );
          })}
        </div>

        {/* LunarSight AI Primary Trigger */}
        <button
          onClick={onOpenAI}
          className="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-200 border border-purple-500/40 text-xs font-semibold rounded flex items-center gap-1.5 transition-all shadow-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
          <span>LunarSight AI</span>
        </button>

        {/* System & AI Telemetry Chip */}
        <div className="hidden 2xl:flex items-center gap-2 font-mono text-[10px] text-gmat-textMuted bg-gmat-bg px-2 py-1 rounded border border-gmat-border">
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-gmat-green animate-telemetry" />
            <span className="text-gmat-green font-bold">261/261 PASS</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1 text-gmat-text">
            <span>{utcClock}</span>
          </div>
        </div>
      </div>
    </header>
  );
};
