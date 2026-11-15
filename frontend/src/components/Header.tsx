import React from 'react';
import { useMission } from '../context/MissionContext';
import { SITES } from '../services/dataService';
import { SiteId, HorizonScenario, CameraViewMode } from '../types';
import { Moon, Compass, Eye, ShieldAlert, Sparkles, SlidersHorizontal, Globe, Mountain, Bot } from 'lucide-react';

export const Header: React.FC<{ onOpenAI?: () => void }> = ({ onOpenAI }) => {
  const {
    siteId,
    setSiteId,
    scenario,
    setScenario,
    currentTimestamp,
    cameraMode,
    setCameraMode,
    isCaseActive,
    isVirtualPatchApplied,
    openConnectingRidgeCase,
    closeConnectingRidgeCase,
    minDurationHours,
    setMinDurationHours
  } = useMission();

  return (
    <header className="h-14 border-b border-slate-800 bg-space-900/90 backdrop-blur px-4 flex items-center justify-between z-20 select-none">
      {/* Sol: Logo ve Aday Seçici */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-sky-950/50">
            <Moon className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-wider text-sm text-slate-100">LUNA SIGHT</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-space-800 border border-slate-700 text-sky-400">
                v1.0 • NASA Space Apps
              </span>
            </div>
            <div className="text-[10px] text-slate-400 tracking-tight">
              Ay Güney Kutbu Görev Planlama & Görünürlük Gezgini
            </div>
          </div>
        </div>

        {/* Aday Seçici Butonları */}
        <div className="flex items-center bg-space-950 p-1 rounded-lg border border-slate-800 gap-1">
          {(['Site01', 'Site04'] as SiteId[]).map((id) => {
            const site = SITES[id];
            const isSelected = siteId === id;
            return (
              <button
                key={id}
                onClick={() => {
                  setSiteId(id);
                  if (id === 'Site04' && isCaseActive) {
                    closeConnectingRidgeCase();
                  }
                }}
                className={`px-3 py-1 text-xs rounded-md font-medium transition-all flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-space-800 text-sky-300 border border-sky-600/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-space-900/50'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${isSelected ? 'bg-sky-400 animate-pulse' : 'bg-slate-600'}`} />
                <span>{site.nameTr}</span>
                <span className="text-[10px] opacity-60 font-mono">({id})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Orta: Ufuk Senaryosu ve Kamera Modu */}
      <div className="flex items-center gap-4">
        {/* Ufuk Senaryosu (Arazi Tarama Kapsamı) */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-[11px] text-slate-400 flex items-center gap-1">
            <Compass className="w-3.5 h-3.5 text-slate-500" />
            Tarama Kapsamı:
          </span>
          <div className="flex bg-space-950 p-1 rounded-lg border border-slate-800 gap-1">
            {[
              { id: '0deg', label: '0° Geometrik' },
              { id: '2000m', label: '2 km LOLA' },
              { id: '4000m', label: '4 km LOLA' }
            ].map((scen) => (
              <button
                key={scen.id}
                onClick={() => setScenario(scen.id as HorizonScenario)}
                className={`px-2.5 py-1 text-[11px] rounded font-medium transition-all ${
                  scenario === scen.id
                    ? 'bg-space-800 text-slate-100 border border-slate-600 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {scen.label}
              </button>
            ))}
          </div>
        </div>

        {/* 3B Kamera Modu */}
        <div className="flex items-center bg-space-950 p-1 rounded-lg border border-slate-800 gap-1">
          <button
            onClick={() => setCameraMode('globe')}
            title="3B Ay Küresi"
            className={`px-2 py-1 text-xs rounded font-medium flex items-center gap-1 transition-all ${
              cameraMode === 'globe'
                ? 'bg-space-800 text-sky-400 border border-sky-600/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Küre</span>
          </button>

          <button
            onClick={() => setCameraMode('terrain')}
            title="Serbest Arazi Kamerası"
            className={`px-2 py-1 text-xs rounded font-medium flex items-center gap-1 transition-all ${
              cameraMode === 'terrain'
                ? 'bg-space-800 text-sky-400 border border-sky-600/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Mountain className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Arazi</span>
          </button>

          <button
            onClick={() => setCameraMode('surface_pov')}
            title="Yüzeyden Bakış (Gözlemci POV)"
            className={`px-2 py-1 text-xs rounded font-medium flex items-center gap-1 transition-all ${
              cameraMode === 'surface_pov'
                ? 'bg-space-800 text-sky-400 border border-sky-600/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Yüzeyden</span>
          </button>
        </div>

        {/* Asgari Operasyon Süresi Filtresi */}
        <div className="hidden lg:flex items-center gap-1 text-xs text-slate-400">
          <span className="text-[11px]">Asgari:</span>
          <select
            value={minDurationHours}
            onChange={(e) => setMinDurationHours(Number(e.target.value))}
            className="bg-space-950 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 outline-none focus:border-sky-500"
          >
            <option value={4}>4 Saat</option>
            <option value={8}>8 Saat</option>
            <option value={12}>12 Saat</option>
            <option value={24}>24 Saat</option>
          </select>
        </div>
      </div>

      {/* Sağ: Ayırt Edici Akış: Connecting Ridge Vakası & LunarSight AI & Zaman Rozeti */}
      <div className="flex items-center gap-3">
        {/* LunarSight AI Butonu */}
        <button
          onClick={onOpenAI}
          className="hidden md:flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/40 hover:to-indigo-600/40 border border-purple-500/50 text-purple-200 text-xs font-semibold rounded-md shadow-sm transition-all"
          title="Görüntüye dayalı gerçek AI yüzey analizi"
        >
          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
          <span>LunarSight AI</span>
        </button>

        {/* Connecting Ridge Vaka Butonu */}
        {isCaseActive ? (
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 px-3 py-1 bg-amber-500/15 border border-amber-500/40 text-amber-300 text-xs font-semibold rounded-md animate-pulse">
              <Sparkles className="w-3.5 h-3.5" />
              Connecting Ridge Vakası Aktif
            </span>
            <button
              onClick={closeConnectingRidgeCase}
              className="px-2 py-1 text-xs rounded bg-space-800 hover:bg-space-700 text-slate-300 border border-slate-700"
            >
              Vakayı Kapat
            </button>
          </div>
        ) : (
          <button
            onClick={openConnectingRidgeCase}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-amber-500/20 to-orange-500/20 hover:from-amber-500/30 hover:to-orange-500/30 border border-amber-500/40 text-amber-200 text-xs font-semibold rounded-md shadow-sm transition-all"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            Connecting Ridge Vakasını Aç
          </button>
        )}

        {/* UTC Zaman Göstergesi */}
        <div className="font-mono text-xs px-2.5 py-1 rounded bg-space-950 border border-slate-800 text-slate-300 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>{currentTimestamp.replace('T', ' ').substring(0, 16)} UTC</span>
        </div>
      </div>
    </header>
  );
};
