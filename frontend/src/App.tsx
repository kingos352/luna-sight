import React, { useState } from 'react';
import { MissionProvider, useMission } from './context/MissionContext';
import { Header } from './components/Header';
import { LunarViewer } from './components/scene/LunarViewer';
import { AnalysisPanel } from './components/analysis/AnalysisPanel';
import { TimelineBar } from './components/timeline/TimelineBar';
import { LunarSightAIModal } from './components/ai/LunarSightAIModal';
import { Loader2, AlertCircle, BarChart3, Globe, Sparkles } from 'lucide-react';

const MainLayout: React.FC = () => {
  const { loading, error } = useMission();
  const [mobileTab, setMobileTab] = useState<'scene' | 'analysis'>('scene');
  const [isAIModalOpen, setIsAIModalOpen] = useState<boolean>(false);

  if (loading) {
    return (
      <div className="w-screen h-screen flex flex-col items-center justify-center bg-space-950 text-slate-100 gap-3">
        <Loader2 className="w-10 h-10 text-sky-400 animate-spin" />
        <div className="text-sm font-semibold tracking-wide">LUNA SIGHT Yükleniyor...</div>
        <div className="text-xs text-slate-400 font-mono">14–21 Kasım 2026 UTC efemeris ve LOLA topoğrafya modelleri hazırlanıyor</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-screen h-screen flex flex-col items-center justify-center bg-space-950 text-slate-100 gap-3 p-6 text-center">
        <AlertCircle className="w-12 h-12 text-red-500" />
        <div className="text-base font-bold text-red-400">Veri Yükleme Hatası</div>
        <div className="text-xs text-slate-400 font-mono max-w-md">{error}</div>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 px-4 py-2 bg-space-800 hover:bg-space-700 text-slate-200 text-xs rounded border border-slate-700 font-medium"
        >
          Yeniden Yükle
        </button>
      </div>
    );
  }

  return (
    <div className="w-screen h-screen flex flex-col overflow-hidden bg-space-950">
      {/* Üst Bar */}
      <Header onOpenAI={() => setIsAIModalOpen(true)} />

      {/* Mobil Sekme Değiştirici (Yalnızca dar ekranlarda görünür) */}
      <div className="md:hidden flex items-center bg-space-900 border-b border-slate-800 px-3 py-1.5 justify-center gap-2 z-20">
        <button
          onClick={() => setMobileTab('scene')}
          className={`flex-1 py-1 px-3 text-xs font-semibold rounded flex items-center justify-center gap-1.5 transition-all ${
            mobileTab === 'scene'
              ? 'bg-sky-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 bg-space-950'
          }`}
        >
          <Globe className="w-3.5 h-3.5" />
          <span>3B Ay Sahnesi</span>
        </button>
        <button
          onClick={() => setMobileTab('analysis')}
          className={`flex-1 py-1 px-3 text-xs font-semibold rounded flex items-center justify-center gap-1.5 transition-all ${
            mobileTab === 'analysis'
              ? 'bg-sky-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 bg-space-950'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Analiz Paneli & Vaka</span>
        </button>
        <button
          onClick={() => setIsAIModalOpen(true)}
          className="flex-1 py-1 px-2 text-xs font-semibold rounded flex items-center justify-center gap-1.5 bg-purple-600/30 text-purple-200 border border-purple-500/50"
        >
          <Sparkles className="w-3.5 h-3.5 shrink-0" />
          <span>LunarSight AI</span>
        </button>
      </div>

      {/* Ana Gövde: 3B Sahne + Sağ Analiz Paneli */}
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden relative">
        {/* Sol/Merkez: 3B Ay Sahnesi */}
        <section
          className={`flex-1 h-full relative ${
            mobileTab === 'scene' ? 'block' : 'hidden md:block'
          }`}
        >
          <LunarViewer />
        </section>

        {/* Sağ: Bilimsel Analiz Paneli */}
        <div
          className={`w-full md:w-80 lg:w-96 h-full ${
            mobileTab === 'analysis' ? 'block' : 'hidden md:block'
          }`}
        >
          <AnalysisPanel onOpenAI={() => setIsAIModalOpen(true)} />
        </div>
      </main>

      {/* Alt: UTC Zaman Çizelgesi ve Görünürlük Şeritleri */}
      <TimelineBar />

      {/* LunarSight AI (NVIDIA görsel modeli) Akıllı Görsel Analiz Modalı */}
      <LunarSightAIModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
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
