import React, { useState } from 'react';
import { MissionProvider, useMission } from './context/MissionContext';
import { MissionToolbar } from './components/toolbar/MissionToolbar';
import { ResourceExplorer } from './components/explorer/ResourceExplorer';
import { LunarViewer } from './components/scene/LunarViewer';
import { ScientificInspector } from './components/inspector/ScientificInspector';
import { TimelineBar } from './components/timeline/TimelineBar';
import { MissionConsole } from './components/console/MissionConsole';
import { LunarAnalysisPipeline } from './components/pipeline/LunarAnalysisPipeline';
import { PresentationMode } from './components/presentation/PresentationMode';
import { LunarSightAIModal } from './components/ai/LunarSightAIModal';
import { ComparisonModal } from './components/comparison/ComparisonModal';
import { ParametersModal } from './components/parameters/ParametersModal';
import { Loader2, AlertCircle, BarChart3, Globe, Sparkles, Layers, SlidersHorizontal, Terminal, ChevronLeft, ChevronRight } from 'lucide-react';

const MainLayout: React.FC = () => {
  const {
    loading,
    error,
    workspacePreset,
    isPresentationMode,
    isLeftSidebarOpen,
    setIsLeftSidebarOpen,
    isRightSidebarOpen,
    setIsRightSidebarOpen,
    isComparisonModalOpen,
    setIsComparisonModalOpen,
    isParametersDrawerOpen,
    setIsParametersDrawerOpen
  } = useMission();

  const [mobileTab, setMobileTab] = useState<'explorer' | 'scene' | 'inspector' | 'console'>('scene');
  const [isAIModalOpen, setIsAIModalOpen] = useState<boolean>(false);

  if (loading) {
    return (
      <div className="w-screen h-screen flex flex-col items-center justify-center bg-gmat-bg text-gmat-text gap-3.5 select-none">
        <div className="relative">
          <div className="w-14 h-14 rounded-full border-2 border-gmat-border border-t-gmat-accent animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="w-2 h-2 rounded-full bg-gmat-accent animate-ping" />
          </div>
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="text-sm font-bold tracking-wider text-gmat-text font-sans">
            LUNA SIGHT <span className="text-gmat-accent font-mono text-xs">GMAT WORKSTATION</span>
          </div>
          <div className="text-xs text-gmat-textMuted font-mono">
            JPL Horizons DE441 efemeris & LOLA 5m/px sayısal yükseklik modelleri yükleniyor...
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-screen h-screen flex flex-col items-center justify-center bg-gmat-bg text-gmat-text gap-3 p-6 text-center select-none">
        <AlertCircle className="w-12 h-12 text-gmat-red" />
        <div className="text-base font-bold text-red-400 font-sans">Veri ve Telemetri Yükleme Hatası</div>
        <div className="text-xs text-gmat-textMuted font-mono max-w-md">{error}</div>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 px-4 py-2 bg-gmat-elevated hover:bg-gmat-border text-gmat-text text-xs rounded border border-gmat-border font-medium transition-colors"
        >
          Yeniden Bağlan
        </button>
      </div>
    );
  }

  // 1. Presentation Mode (Full-screen cinematic view with interactive guide)
  if (isPresentationMode || workspacePreset === 'presentation') {
    return (
      <div className="w-screen h-screen flex flex-col overflow-hidden bg-gmat-bg relative select-none">
        <main className="flex-1 w-full h-full relative">
          <LunarViewer />
          <PresentationMode />
        </main>
      </div>
    );
  }

  // 2. Full Multi-Panel NASA GMAT Workstation Layout
  return (
    <div className="w-screen h-screen flex flex-col overflow-hidden bg-gmat-bg font-sans">
      {/* Top Mission Toolbar */}
      <MissionToolbar onOpenAI={() => setIsAIModalOpen(true)} />

      {/* Mobile Tab Switcher (Visible only on small viewports) */}
      <div className="md:hidden flex items-center bg-gmat-panel border-b border-gmat-border px-2 py-1 justify-center gap-1 z-20">
        <button
          onClick={() => setMobileTab('explorer')}
          className={`flex-1 py-1 px-2 text-[11px] font-semibold rounded flex items-center justify-center gap-1 ${
            mobileTab === 'explorer' ? 'bg-gmat-accent text-slate-950 font-bold' : 'text-gmat-textMuted bg-gmat-bg'
          }`}
        >
          <Layers className="w-3 h-3" />
          <span>Explorer</span>
        </button>
        <button
          onClick={() => setMobileTab('scene')}
          className={`flex-1 py-1 px-2 text-[11px] font-semibold rounded flex items-center justify-center gap-1 ${
            mobileTab === 'scene' ? 'bg-gmat-accent text-slate-950 font-bold' : 'text-gmat-textMuted bg-gmat-bg'
          }`}
        >
          <Globe className="w-3 h-3" />
          <span>3B Ay</span>
        </button>
        <button
          onClick={() => setMobileTab('inspector')}
          className={`flex-1 py-1 px-2 text-[11px] font-semibold rounded flex items-center justify-center gap-1 ${
            mobileTab === 'inspector' ? 'bg-gmat-accent text-slate-950 font-bold' : 'text-gmat-textMuted bg-gmat-bg'
          }`}
        >
          <SlidersHorizontal className="w-3 h-3" />
          <span>Inspector</span>
        </button>
        <button
          onClick={() => setIsAIModalOpen(true)}
          className="py-1 px-2 text-[11px] font-semibold rounded flex items-center justify-center gap-1 bg-purple-600/30 text-purple-200 border border-purple-500/50"
        >
          <Sparkles className="w-3 h-3" />
          <span>AI</span>
        </button>
      </div>

      {/* Center Workstation: Left Explorer + 3D Moon Workspace + Right Inspector */}
      <main className="flex-1 w-full min-w-0 flex flex-col md:flex-row overflow-hidden relative">
        {/* Left Sidebar: GMAT Lunar Resource Explorer */}
        {isLeftSidebarOpen && (
          <div className={`h-full shrink-0 ${mobileTab === 'explorer' ? 'block w-full' : 'hidden md:block'} z-10 animate-in slide-in-from-left duration-150`}>
            <ResourceExplorer onOpenAI={() => setIsAIModalOpen(true)} onClose={() => setIsLeftSidebarOpen(false)} />
          </div>
        )}

        {/* Center Workspace: High-Resolution 3D Lunar Digital Twin */}
        <section
          className={`flex-1 min-w-0 h-full relative overflow-hidden ${
            mobileTab === 'scene' ? 'block' : 'hidden md:block'
          }`}
        >
          {/* Subtle Floating Left Sidebar Open Button when collapsed */}
          {!isLeftSidebarOpen && (
            <button
              onClick={() => setIsLeftSidebarOpen(true)}
              className="absolute top-1/2 left-2 -translate-y-1/2 z-20 px-1 py-3 rounded-r-md bg-gmat-panel/90 hover:bg-gmat-elevated border border-l-0 border-gmat-border text-gmat-accent shadow-xl flex flex-col items-center gap-1 group transition-all"
              title="Kaynaklar & Parametreler Panelini Aç"
            >
              <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              <span className="text-[9px] font-mono [writing-mode:vertical-lr] text-gmat-textMuted tracking-wider uppercase font-semibold">
                Kaynaklar
              </span>
            </button>
          )}

          <LunarViewer />

          {/* Subtle Floating Right Inspector Open Button when collapsed */}
          {!isRightSidebarOpen && (
            <button
              onClick={() => setIsRightSidebarOpen(true)}
              className="absolute top-1/2 right-2 -translate-y-1/2 z-20 px-1 py-3 rounded-l-md bg-gmat-panel/90 hover:bg-gmat-elevated border border-r-0 border-gmat-border text-gmat-accent shadow-xl flex flex-col items-center gap-1 group transition-all"
              title="Bilimsel Müfettiş Panelini Aç"
            >
              <ChevronLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
              <span className="text-[9px] font-mono [writing-mode:vertical-lr] text-gmat-textMuted tracking-wider uppercase font-semibold">
                Müfettiş
              </span>
            </button>
          )}
        </section>

        {/* Right Sidebar: Scientific Contextual Inspector */}
        {isRightSidebarOpen && (
          <div className={`h-full shrink-0 ${mobileTab === 'inspector' ? 'block w-full' : 'hidden md:block'} z-10 animate-in slide-in-from-right duration-150`}>
            <ScientificInspector onOpenAI={() => setIsAIModalOpen(true)} onClose={() => setIsRightSidebarOpen(false)} />
          </div>
        )}
      </main>

      {/* Bottom Timeline Bar: UTC Ephemeris Timeline & Step Controller */}
      <TimelineBar />

      {/* Bottom Dock: Collapsible NASA GMAT Mission Console */}
      <MissionConsole />

      {/* Interactive Modals */}
      <LunarAnalysisPipeline />

      <LunarSightAIModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
      />

      <ComparisonModal
        isOpen={isComparisonModalOpen}
        onClose={() => setIsComparisonModalOpen(false)}
      />

      <ParametersModal
        isOpen={isParametersDrawerOpen}
        onClose={() => setIsParametersDrawerOpen(false)}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <MissionProvider>
      <MainLayout />
    </MissionProvider>
  );
};

export default App;
