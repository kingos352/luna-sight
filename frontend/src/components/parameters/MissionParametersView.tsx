import React from 'react';
import { useMission } from '../../context/MissionContext';
import {
  Sliders,
  Calendar,
  Clock,
  Database,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  ChevronDown
} from 'lucide-react';

export const MissionParametersView: React.FC = () => {
  const { suhailParams, updateSuhailParams, addLog } = useMission();

  return (
    <div className="w-full bg-gmat-bg/95 p-3 rounded-xl border border-gmat-border flex flex-col gap-3 font-sans select-none text-xs shadow-md">
      {/* 1. Header & Step Badge */}
      <div className="flex items-center justify-between pb-1.5 border-b border-gmat-border">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-sky-950/80 border border-sky-500/50 text-gmat-accent font-mono text-[11px] font-bold">
            2 · Görev Parametreleri
          </span>
        </div>
        <span className="text-[10px] font-mono text-gmat-textDim">SUHAIL STANDARDI</span>
      </div>

      {/* 2. Data Source Selector */}
      <div className="flex flex-col gap-1">
        <label className="text-[11px] font-semibold text-gmat-text flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-gmat-accent" />
            Veri Kaynağı
          </span>
          <span className="text-[10px] text-slate-500 font-mono">outputs/k3/</span>
        </label>
        <select
          value={suhailParams.sourceMode}
          onChange={(e) => updateSuhailParams({ sourceMode: e.target.value as 'real' | 'synthetic' })}
          className="w-full bg-gmat-elevated border border-gmat-border rounded px-2.5 py-1.5 text-xs text-gmat-text font-mono focus:border-gmat-accent outline-none"
        >
          <option value="real">Gerçek Ekip Çıktısı (K2/K3)</option>
          <option value="synthetic">Sentetik Analitik Doğrulama (Mock)</option>
        </select>
        <div className="text-[9.5px] text-gmat-textDim font-mono">
          Kaynak: <span className="text-gmat-accent">outputs/k3/&lt;Site&gt;_visibility.csv</span>
        </div>
      </div>

      {/* 3. Mission Duration (Days) */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-semibold text-gmat-text flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            Görev süresi (gün)
          </label>
          <span className="font-mono text-xs font-bold text-gmat-accent">{suhailParams.missionDays} Gün</span>
        </div>
        <input
          type="range"
          min="1"
          max="14"
          step="1"
          value={suhailParams.missionDays}
          onChange={(e) => updateSuhailParams({ missionDays: Number(e.target.value) })}
          className="w-full accent-sky-400 h-1.5 bg-gmat-elevated rounded cursor-pointer"
        />
        <div className="flex justify-between text-[9px] text-slate-500 font-mono">
          <span>1 gün</span>
          <span>7 gün (Nominal)</span>
          <span>14 gün</span>
        </div>
      </div>

      {/* 4. Sampling Interval */}
      <div className="flex flex-col gap-1">
        <label className="text-[11px] font-semibold text-gmat-text flex items-center gap-1.5">
          <Sliders className="w-3.5 h-3.5 text-emerald-400" />
          Zaman örnekleme aralığı
        </label>
        <select
          value={suhailParams.samplingInterval}
          onChange={(e) => updateSuhailParams({ samplingInterval: e.target.value as '1h' | '5m' })}
          className="w-full bg-gmat-elevated border border-gmat-border rounded px-2.5 py-1.5 text-xs text-gmat-text font-mono focus:border-gmat-accent outline-none"
        >
          <option value="1h">1 saat (Hızlı Operasyonel)</option>
          <option value="5m">5 dakika (Bilimsel Yüksek Hassasiyet)</option>
        </select>
      </div>

      {/* 5. Mission Start UTC */}
      <div className="flex flex-col gap-1">
        <label className="text-[11px] font-semibold text-gmat-text flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5 text-purple-400" />
          Görev başlangıcı (UTC)
        </label>
        <div className="w-full bg-gmat-elevated border border-gmat-border rounded px-2.5 py-1.5 text-xs text-gmat-accent font-mono flex items-center justify-between">
          <span>2026/11/14, 00:00 UTC</span>
          <Calendar className="w-3.5 h-3.5 text-gmat-textMuted" />
        </div>
      </div>

      {/* 6. Window Summary Note */}
      <div className="p-2 rounded bg-gmat-elevated/70 border border-gmat-border text-[10px] text-gmat-textMuted flex flex-col gap-0.5 font-mono">
        <div>• Pencere: {suhailParams.missionDays} gün × 1 saat = {suhailParams.missionDays * 24} adım</div>
        <div>• Gerçek çıktı aralığı: 2026-11-14 00:00 → 2026-11-21 00:00 UTC</div>
        <div className="text-slate-500 text-[9px] mt-0.5">
          Pencere dışı seçimlerde başlangıç verinin ilk anına çekilir; veri sonu aşılırsa grafik kırpılır.
        </div>
      </div>

      <div className="h-px bg-gmat-border my-0.5" />

      {/* 7. SUHAIL Constraints Section */}
      <div className="flex flex-col gap-2.5">
        <div className="text-xs font-bold text-gmat-text flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-gmat-accent" />
          <span>Görev kısıtları (SUHAIL)</span>
        </div>

        {/* Min Sun Requirement */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gmat-textMuted">Min. Güneş İhtiyacı (%)</span>
            <span className="font-mono text-xs font-bold text-amber-300">%{suhailParams.minSunReq}</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={suhailParams.minSunReq}
            onChange={(e) => updateSuhailParams({ minSunReq: Number(e.target.value) })}
            className="w-full accent-amber-400 h-1.5 bg-gmat-elevated rounded cursor-pointer"
          />
          <div className="flex justify-between text-[9px] text-slate-500 font-mono">
            <span>%0</span>
            <span>%70 (Kritik Eşik)</span>
            <span>%100</span>
          </div>
        </div>

        {/* Max Blackout Tolerance */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gmat-textMuted">Maks. Telsiz Kesintisi Toleransı (saat)</span>
            <span className="font-mono text-xs font-bold text-sky-300">{suhailParams.maxBlackoutTol} sa</span>
          </div>
          <input
            type="range"
            min="0"
            max="72"
            step="4"
            value={suhailParams.maxBlackoutTol}
            onChange={(e) => updateSuhailParams({ maxBlackoutTol: Number(e.target.value) })}
            className="w-full accent-sky-400 h-1.5 bg-gmat-elevated rounded cursor-pointer"
          />
          <div className="flex justify-between text-[9px] text-slate-500 font-mono">
            <span>0 sa</span>
            <span>24 sa (Maks. Limit)</span>
            <span>72 sa</span>
          </div>
        </div>
      </div>
    </div>
  );
};
