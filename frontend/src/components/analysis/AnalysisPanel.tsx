import React from 'react';
import { useMission } from '../../context/MissionContext';
import { SITES } from '../../services/dataService';
import { ElevationMarginChart } from './ElevationMarginChart';
import { SurveySection } from './SurveySection';
import { ShieldCheck, Moon, Compass, Radio, CheckCircle, XCircle, AlertTriangle, Sparkles } from 'lucide-react';

export const AnalysisPanel: React.FC<{ onOpenAI?: () => void }> = ({ onOpenAI }) => {
  const { siteId, activePoint, scenario, longestJointWindow, minDurationHours } = useMission();
  const site = SITES[siteId];

  const { jointState, jointMargin, twelveHourDecision } = activePoint;

  return (
    <aside className="w-full h-full bg-space-900 border-l border-slate-800 flex flex-col overflow-y-auto select-none p-3 gap-3 z-10 custom-scrollbar">
      {/* 1. Seçili Aday Kartı */}
      <div className="bg-space-950 p-3 rounded-lg border border-slate-800">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <Moon className="w-4 h-4 text-sky-400" />
            <h2 className="text-sm font-bold text-slate-100">{site.nameTr}</h2>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-space-900 border border-slate-800 text-sky-400 font-bold">
            {site.id}
          </span>
        </div>

        <p className="text-[11px] text-slate-400 leading-normal mb-2">
          {site.description}
        </p>

        <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono bg-space-900/60 p-2 rounded border border-slate-800/80 mb-2">
          <div>Enlem: <span className="text-slate-200">{site.lat}°</span></div>
          <div>Boylam (D): <span className="text-slate-200">{site.lonEast}°</span></div>
          <div>Tarama: <span className="text-sky-300 font-bold">{scenario}</span></div>
        </div>

        {/* LunarSight AI Hızlı Analiz Butonu */}
        <button
          onClick={onOpenAI}
          className="w-full py-1.5 px-2 bg-gradient-to-r from-purple-600/20 to-indigo-600/20 hover:from-purple-600/30 hover:to-indigo-600/30 border border-purple-500/40 rounded text-purple-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
          <span>LunarSight AI ile Sahneyi İncele</span>
        </button>
      </div>

      {/* 2. Operasyonel Görünürlük Durum Kartı (Anlık ve 12s Karar) */}
      <div className="bg-space-950 p-3 rounded-lg border border-slate-800 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-sky-400" />
            Anlık Ortak Durum
          </span>
          <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold flex items-center gap-1 uppercase ${
            jointState === 'visible'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : jointState === 'blocked'
              ? 'bg-red-500/20 text-red-300 border border-red-500/40'
              : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
          }`}>
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

        <div className="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2 font-mono">
          <span>Kritik Açı Marjı:</span>
          <span className={`font-bold ${jointMargin > 0.10 ? 'text-emerald-400' : jointMargin < -0.10 ? 'text-red-400' : 'text-amber-400'}`}>
            {jointMargin > 0 ? `+${jointMargin.toFixed(4)}°` : `${jointMargin.toFixed(4)}°`}
          </span>
        </div>

        {/* 12 Saatlik Operasyon Kararı Rozeti */}
        <div className="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2 font-mono">
          <span>12s Operasyon Kararı:</span>
          <span className={`font-bold ${
            twelveHourDecision === 'feasible'
              ? 'text-emerald-400'
              : twelveHourDecision === 'not_feasible'
              ? 'text-red-400'
              : 'text-amber-400'
          }`}>
            {twelveHourDecision === 'feasible' ? 'Uygun (Feasible)' : twelveHourDecision === 'not_feasible' ? 'Engelli (Not Feasible)' : 'Belirsiz (Uncertain)'}
          </span>
        </div>
      </div>

      {/* 3. Açı ve Marj Grafiği */}
      <ElevationMarginChart />

      {/* 4. Ölçüm Planla (Connecting Ridge Vakası & Sanal Ölçüm) */}
      <SurveySection />

      {/* 5. Provenance & Doğrulama Meta Verisi */}
      <div className="bg-space-950 p-2.5 rounded-lg border border-slate-800 text-[10px] text-slate-400 font-mono space-y-1">
        <div className="flex items-center gap-1 text-slate-300 font-semibold mb-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Veri Kökeni & Doğrulama</span>
        </div>
        <div>Efemeris: JPL Horizons DE441 (Airless, coord@301)</div>
        <div>DEM: Barker et al. 2021 LOLA 5mpp (GSFC PGDA)</div>
        <div>Koordinat Çerçevesi: MOON_ME (JPL DE421)</div>
        <div>Modelleme Ayarı: ±0.10° Geçiş Bandı</div>
      </div>
    </aside>
  );
};
