import React, { useState, useMemo } from 'react';
import { useMission } from '../../context/MissionContext';
import { SITES } from '../../services/dataService';
import { CRATER_CATALOG } from '../../services/craterCatalog';
import { SiteId, CraterFeature } from '../../types';
import { MissionParametersView } from '../parameters/MissionParametersView';
import {
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  Globe,
  Mountain,
  Eye,
  EyeOff,
  Radio,
  Sun,
  ShieldAlert,
  Sparkles,
  FileText,
  Download,
  Layers,
  MapPin,
  CheckCircle2,
  AlertCircle,
  Clock,
  Compass,
  SlidersHorizontal,
  Scale,
  Rocket
} from 'lucide-react';

interface TreeSectionProps {
  title: string;
  count?: number;
  isOpenDefault?: boolean;
  children: React.ReactNode;
}

const TreeSection: React.FC<TreeSectionProps> = ({ title, count, isOpenDefault = true, children }) => {
  const [open, setOpen] = useState(isOpenDefault);
  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-2 py-1 text-[11px] font-mono font-bold text-gmat-textMuted hover:text-gmat-text bg-gmat-elevated/40 hover:bg-gmat-elevated rounded transition-colors"
      >
        <div className="flex items-center gap-1.5">
          {open ? <ChevronDown className="w-3 h-3 text-gmat-accent" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
          <span>{title}</span>
        </div>
        {count !== undefined && (
          <span className="text-[9.5px] px-1 rounded bg-gmat-bg border border-gmat-border text-gmat-textDim">
            {count}
          </span>
        )}
      </button>
      {open && <div className="mt-1 pl-2 flex flex-col gap-0.5">{children}</div>}
    </div>
  );
};

export const ResourceExplorer: React.FC<{ onOpenAI?: () => void; onClose?: () => void }> = ({ onOpenAI, onClose }) => {
  const {
    siteId,
    setSiteId,
    scenario,
    setScenario,
    layerMode,
    setLayerMode,
    displacementEnabled,
    setDisplacementEnabled,
    cameraMode,
    setCameraMode,
    selectedCrater,
    setSelectedCrater,
    setCameraPreset,
    isCaseActive,
    openConnectingRidgeCase,
    closeConnectingRidgeCase,
    isVirtualPatchApplied,
    toggleVirtualPatch,
    exportCaseData,
    setIsPipelineModalOpen,
    setIsComparisonModalOpen,
    setConsoleTab,
    setIsConsoleOpen
  } = useMission();

  const [sidebarTab, setSidebarTab] = useState<'resources' | 'parameters'>('resources');
  const [catalogFilter, setCatalogFilter] = useState<'all' | 'crater' | 'plain'>('all');
  const [catalogSearch, setCatalogSearch] = useState<string>('');

  const filteredFeatures = useMemo(() => {
    return CRATER_CATALOG.filter((f) => {
      if (catalogFilter === 'crater' && f.type !== 'crater') return false;
      if (catalogFilter === 'plain' && f.type !== 'plain' && f.type !== 'plateau') return false;
      if (catalogSearch && !f.name.toLowerCase().includes(catalogSearch.toLowerCase())) return false;
      return true;
    });
  }, [catalogFilter, catalogSearch]);

  return (
    <aside className={`${sidebarTab === 'parameters' ? 'w-76 md:w-80' : 'w-64'} h-full bg-gmat-panel border-r border-gmat-border flex flex-col select-none overflow-hidden shadow-gmat-panel transition-all duration-150`}>
      {/* Sidebar Header with Switcher */}
      <div className="h-9 px-2.5 border-b border-gmat-border flex items-center justify-between bg-gmat-elevated/60">
        <div className="flex items-center gap-1 bg-gmat-bg p-0.5 rounded border border-gmat-border">
          <button
            onClick={() => setSidebarTab('resources')}
            className={`px-2 py-0.5 text-[10.5px] font-mono rounded font-semibold transition-all flex items-center gap-1 ${
              sidebarTab === 'resources'
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-border shadow-xs'
                : 'text-gmat-textMuted hover:text-gmat-text'
            }`}
          >
            <Layers className="w-3 h-3" />
            <span>Kaynaklar</span>
          </button>
          <button
            onClick={() => setSidebarTab('parameters')}
            className={`px-2 py-0.5 text-[10.5px] font-mono rounded font-semibold transition-all flex items-center gap-1 ${
              sidebarTab === 'parameters'
                ? 'bg-gmat-elevated text-sky-400 border border-gmat-border shadow-xs'
                : 'text-gmat-textMuted hover:text-gmat-text'
            }`}
          >
            <SlidersHorizontal className="w-3 h-3 text-sky-400" />
            <span>Parametreler</span>
          </button>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[9.5px] font-mono text-gmat-textDim">SUHAIL</span>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-gmat-bg text-gmat-textMuted hover:text-gmat-text transition-colors"
              title="Paneli Kapat"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Sidebar Content */}
      {sidebarTab === 'parameters' ? (
        <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
          <MissionParametersView />
        </div>
      ) : (
        /* Hierarchical Resource Tree */
        <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
        {/* 1. LUNAR DATA */}
        <TreeSection title="LUNAR DATA" count={5}>
          {/* LOLA DEM */}
          <div
            onClick={() => {
              setCameraMode('terrain');
              setCameraPreset('site01');
            }}
            className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
              cameraMode === 'terrain'
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/30'
                : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
            }`}
          >
            <div className="flex items-center gap-1.5 truncate">
              <Mountain className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="truncate">LOLA 5m/px DEM</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg border border-gmat-border text-emerald-400">
              5m/px
            </span>
          </div>

          {/* Surface Imagery (WAC 4K) */}
          <div
            onClick={() => {
              setCameraMode('globe');
              setLayerMode('wac');
            }}
            className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
              cameraMode === 'globe' && layerMode === 'wac'
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/30'
                : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
            }`}
          >
            <div className="flex items-center gap-1.5 truncate">
              <Globe className="w-3.5 h-3.5 text-sky-400 shrink-0" />
              <span className="truncate">LRO WAC 4K Mosaic</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg border border-gmat-border text-sky-400">
              4K
            </span>
          </div>

          {/* QuickMap Colorized Topo */}
          <div
            onClick={() => {
              setCameraMode('globe');
              setLayerMode('topo');
            }}
            className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
              cameraMode === 'globe' && layerMode === 'topo'
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/30'
                : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
            }`}
          >
            <div className="flex items-center gap-1.5 truncate">
              <Compass className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="truncate">QuickMap Topo Layer</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg border border-gmat-border text-amber-400">
              LOLA
            </span>
          </div>

          {/* 3D Displacement Relief Toggle */}
          <div
            onClick={() => setDisplacementEnabled(!displacementEnabled)}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              {displacementEnabled ? (
                <Eye className="w-3.5 h-3.5 text-gmat-green shrink-0" />
              ) : (
                <EyeOff className="w-3.5 h-3.5 text-slate-500 shrink-0" />
              )}
              <span className="truncate">3D Yüzey Kabartması</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-slate-400">
              {displacementEnabled ? 'ON' : 'OFF'}
            </span>
          </div>

          {/* South Pole Craters & Plains Catalog */}
          <div className="mt-1 pl-1.5 border-l border-gmat-border/70 flex flex-col gap-1">
            <div className="flex items-center justify-between px-1">
              <span className="text-[9.5px] font-mono text-gmat-textDim uppercase font-bold">
                Kutup Özellikleri ({filteredFeatures.length})
              </span>
              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => setCatalogFilter('all')}
                  className={`px-1 py-0.2 rounded text-[8.5px] font-mono ${catalogFilter === 'all' ? 'text-white bg-gmat-border font-bold' : 'text-slate-500'}`}
                >
                  Tümü
                </button>
                <button
                  onClick={() => setCatalogFilter('crater')}
                  className={`px-1 py-0.2 rounded text-[8.5px] font-mono ${catalogFilter === 'crater' ? 'text-amber-300 bg-amber-950 font-bold' : 'text-slate-500'}`}
                >
                  Krater
                </button>
                <button
                  onClick={() => setCatalogFilter('plain')}
                  className={`px-1 py-0.2 rounded text-[8.5px] font-mono ${catalogFilter === 'plain' ? 'text-emerald-300 bg-emerald-950 font-bold' : 'text-slate-500'}`}
                >
                  Düzlük
                </button>
              </div>
            </div>

            {/* Quick Filter Search */}
            <input
              type="text"
              placeholder="Krater veya düzlük ara..."
              value={catalogSearch}
              onChange={(e) => setCatalogSearch(e.target.value)}
              className="w-full bg-gmat-bg border border-gmat-border rounded px-1.5 py-0.5 text-[10px] text-gmat-text placeholder-slate-600 font-mono outline-none focus:border-gmat-accent"
            />

            {/* Scrollable Feature List */}
            <div className="max-h-48 overflow-y-auto custom-scrollbar flex flex-col gap-0.5 pr-0.5">
              {filteredFeatures.map((crater: CraterFeature) => {
                const isSelected = selectedCrater?.id === crater.id;
                const isPlain = crater.type === 'plain' || crater.type === 'plateau';
                const isPeak = crater.type === 'peak' || crater.type === 'ridge';

                return (
                  <div
                    key={crater.id}
                    onClick={() => {
                      setSelectedCrater(crater);
                      setCameraMode('globe');
                    }}
                    className={`flex items-center justify-between px-1.5 py-0.5 rounded text-[10.5px] cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-gmat-elevated text-gmat-accent font-semibold border border-gmat-border'
                        : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/40'
                    }`}
                  >
                    <div className="flex items-center gap-1 truncate">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{
                          backgroundColor: isPlain ? '#22c55e' : isPeak ? '#38bdf8' : '#f59e0b'
                        }}
                      />
                      <span className="truncate">{crater.name}</span>
                    </div>
                    {crater.diameterKm && (
                      <span className="text-[9px] font-mono text-slate-500 shrink-0 ml-1">
                        {crater.diameterKm}km
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </TreeSection>

        {/* 2. ANALYSIS MODULES */}
        <TreeSection title="ANALYSIS MODULES" count={6}>
          {/* Mission Parameters & SUHAIL Constraints */}
          <div
            onClick={() => setSidebarTab('parameters')}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-sky-300 hover:bg-sky-950/40 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <SlidersHorizontal className="w-3.5 h-3.5 text-sky-400 shrink-0" />
              <span className="truncate">Görev Parametreleri & SUHAIL</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-sky-400 font-bold">2. Adım</span>
          </div>

          {/* Topographic Horizon (K2) */}
          <div
            onClick={() => setIsPipelineModalOpen(true)}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <Mountain className="w-3.5 h-3.5 text-sky-400 shrink-0" />
              <span className="truncate">K2 Ufuk Profili</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-sky-400">{scenario}</span>
          </div>

          {/* Visibility Engine (K3) */}
          <div
            onClick={() => setIsPipelineModalOpen(true)}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <Radio className="w-3.5 h-3.5 text-gmat-green shrink-0" />
              <span className="truncate">K3 Görünürlük Motoru</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-gmat-green">±0.10°</span>
          </div>

          {/* Solar Illumination */}
          <div className="flex items-center justify-between px-2 py-1 rounded text-xs text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors cursor-pointer">
            <div className="flex items-center gap-1.5 truncate">
              <Sun className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="truncate">Güneş Işıklanma Analizi</span>
            </div>
            <span className="text-[9px] font-mono text-amber-400 font-bold">14–21 Kas</span>
          </div>

          {/* Slope & Hazard Assessment */}
          <div
            onClick={() => {
              if (siteId === 'Site01') {
                if (isCaseActive) closeConnectingRidgeCase();
                else openConnectingRidgeCase();
              }
            }}
            className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
              isCaseActive
                ? 'bg-amber-950/40 text-gmat-amber border border-amber-600/40'
                : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
            }`}
          >
            <div className="flex items-center gap-1.5 truncate">
              <ShieldAlert className="w-3.5 h-3.5 text-gmat-amber shrink-0" />
              <span className="truncate">Tehlike & Eğim Değerlendirme</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-gmat-amber">
              {isCaseActive ? 'AKTİF' : '15° EŞİK'}
            </span>
          </div>

          {/* LunarSight AI Multimodal */}
          <div
            onClick={onOpenAI}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-purple-300 hover:text-purple-100 hover:bg-purple-950/40 border border-purple-500/20 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <Sparkles className="w-3.5 h-3.5 text-purple-400 shrink-0" />
              <span className="truncate">LunarSight AI (VLM)</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-purple-900/40 text-purple-300">
              Nemotron
            </span>
          </div>
        </TreeSection>

        {/* 3. MISSION RESOURCES */}
        <TreeSection title="MISSION RESOURCES" count={4}>
          {/* Site01 Connecting Ridge */}
          <div
            onClick={() => {
              setSiteId('Site01');
              setCameraPreset('site01');
            }}
            className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
              siteId === 'Site01'
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/30 font-semibold'
                : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
            }`}
          >
            <div className="flex items-center gap-1.5 truncate">
              <MapPin className="w-3.5 h-3.5 text-gmat-accent shrink-0" />
              <span className="truncate">Connecting Ridge (Site01)</span>
            </div>
            <span className="text-[9px] font-mono text-slate-400">-89.46°</span>
          </div>

          {/* Site04 Shackleton Rim */}
          <div
            onClick={() => {
              setSiteId('Site04');
              setCameraPreset('site04');
            }}
            className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
              siteId === 'Site04'
                ? 'bg-gmat-elevated text-gmat-accent border border-gmat-accent/30 font-semibold'
                : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
            }`}
          >
            <div className="flex items-center gap-1.5 truncate">
              <MapPin className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="truncate">Shackleton Rim (Site04)</span>
            </div>
            <span className="text-[9px] font-mono text-slate-400">-89.77°</span>
          </div>

          {/* Connecting Ridge Virtual Patch */}
          {siteId === 'Site01' && (
            <div
              onClick={toggleVirtualPatch}
              className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                isVirtualPatchApplied
                  ? 'bg-purple-950/40 text-purple-300 border border-purple-500/40'
                  : 'text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50'
              }`}
            >
              <div className="flex items-center gap-1.5 truncate">
                <Compass className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                <span className="truncate">Target_MethodA Yama</span>
              </div>
              <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-purple-300">
                {isVirtualPatchApplied ? 'KLON-1' : 'NOMİNAL'}
              </span>
            </div>
          )}

          {/* Observer Height */}
          <div className="flex items-center justify-between px-2 py-1 rounded text-xs text-gmat-textDim">
            <div className="flex items-center gap-1.5 truncate">
              <Eye className="w-3.5 h-3.5 text-slate-500 shrink-0" />
              <span className="truncate">Gözlemci İrtifası</span>
            </div>
            <span className="text-[9.5px] font-mono text-slate-400 font-bold">h = 2.0 m</span>
          </div>
        </TreeSection>

        {/* 4. OUTPUTS & REPORTS */}
        <TreeSection title="OUTPUT" count={4}>
          <div
            onClick={() => exportCaseData('json')}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <Download className="w-3.5 h-3.5 text-gmat-accent shrink-0" />
              <span className="truncate">Görünürlük Raporu (JSON)</span>
            </div>
            <span className="text-[9px] font-mono text-slate-500">JSON</span>
          </div>

          <div
            onClick={() => exportCaseData('csv')}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <Download className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="truncate">Kanonik Sözleşme (CSV)</span>
            </div>
            <span className="text-[9px] font-mono text-slate-500">CSV</span>
          </div>

          <div
            onClick={() => setIsComparisonModalOpen(true)}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-emerald-300 hover:bg-emerald-950/40 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <Scale className="w-3.5 h-3.5 text-gmat-green shrink-0" />
              <span className="truncate">A/B Karşılaştırma & Uçuş Kartları</span>
            </div>
            <span className="text-[9px] font-mono px-1 rounded bg-gmat-bg text-gmat-green font-bold">SUHAIL</span>
          </div>

          <div
            onClick={() => setIsPipelineModalOpen(true)}
            className="flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-elevated/50 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              <FileText className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="truncate">Görev Karar Karnesi</span>
            </div>
            <span className="text-[9px] font-mono text-amber-400 font-bold">K3</span>
          </div>
        </TreeSection>
      </div>
      )}
    </aside>
  );
};
