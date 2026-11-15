import React, { useState } from 'react';
import { useMission } from '../../context/MissionContext';
import {
  Download,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Sun,
  Globe,
  Mountain,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Zap,
  Activity,
  Layers,
  FileText
} from 'lucide-react';

interface SiteCardProps {
  siteId: 'Site01' | 'Site04';
  title: string;
  name: string;
  coordinates: string;
  sunHours: number;
  earthHours: number;
  jointHours: number;
  longestEarthWindow: number;
  longestJointWindow: number;
  longestBlackout: number;
  optimalLanding: string;
  horizonMean: number;
  horizonMax: number;
  horizonMaxAz: number;
  sunDelta?: number;
  earthDelta?: number;
  jointDelta?: number;
  jointLongestDelta?: number;
  blackoutDelta?: number;
}

export const MissionComparisonView: React.FC = () => {
  const { suhailParams, downloadFlightBriefingCard } = useMission();
  const [openObstacleA, setOpenObstacleA] = useState(true);
  const [openObstacleB, setOpenObstacleB] = useState(true);

  // Dynamic calculations according to SUHAIL constraints
  const minSunReq = suhailParams.minSunReq;
  const maxBlackoutTol = suhailParams.maxBlackoutTol;

  // Site 01 Metrics (from real K2/K3 run)
  const s01SunHours = 169.0;
  const s01EarthHours = 54.0;
  const s01JointHours = 54.0;
  const s01LongestEarth = 54.0;
  const s01LongestJoint = 54.0;
  const s01LongestBlackout = 111.0;

  // Site 04 Metrics (from real K2/K3 run)
  const s04SunHours = 169.0;
  const s04EarthHours = 0.0;
  const s04JointHours = 0.0;
  const s04LongestEarth = 0.0;
  const s04LongestJoint = 0.0;
  const s04LongestBlackout = 169.0;

  // Evaluation criteria
  const s01SunPass = (s01SunHours / 169.0) * 100 >= minSunReq;
  const s01BlackoutPass = s01LongestBlackout <= maxBlackoutTol;
  const s01Pass = s01SunPass && s01BlackoutPass;

  const s04SunPass = (s04SunHours / 169.0) * 100 >= minSunReq;
  const s04BlackoutPass = s04LongestBlackout <= maxBlackoutTol;
  const s04Pass = s04SunPass && s04BlackoutPass;

  return (
    <div className="w-full flex flex-col gap-3 p-1 select-none font-sans">
      {/* 1. Comparison Headline Verdict Band */}
      <div className="p-3 rounded-lg bg-gmat-elevated border border-gmat-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-gmat-panel">
        <div>
          <span className="text-[10px] font-mono tracking-wider text-gmat-accent font-bold uppercase">
            Karşılaştırma Sonucu
          </span>
          <p className="text-xs text-gmat-text font-medium mt-0.5">
            Doğrudan Dünya bağlantısı yalnızca <strong className="text-gmat-accent">Site01: Connecting Ridge</strong> bölgesinde var:{' '}
            <strong className="text-gmat-green">54.0 saat</strong> ortak görünürlük.{' '}
            <span className="text-gmat-textMuted">Site04 Shackleton Rim bu pencerede hiç vermiyor.</span>
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] self-end sm:self-auto">
          <div className="px-2 py-1 rounded bg-gmat-bg border border-gmat-border">
            <span className="text-gmat-textMuted text-[10px]">Site01 Ortak: </span>
            <span className="text-gmat-green font-bold">54.0 sa</span>
          </div>
          <div className="px-2 py-1 rounded bg-gmat-bg border border-gmat-border">
            <span className="text-gmat-textMuted text-[10px]">Site04 Ortak: </span>
            <span className="text-gmat-red font-bold">0.0 sa</span>
          </div>
        </div>
      </div>

      {/* 2. Side-by-Side Comparative Columns (Site01 vs Site04 - Image 3) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* ================= COLUMN A: SITE 01 ================= */}
        <div className="bg-gmat-panel p-3 rounded-xl border border-gmat-border flex flex-col gap-2.5 shadow-md">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono font-bold text-gmat-accent px-1.5 py-0.2 rounded bg-gmat-bg border border-gmat-border">
                  Bölge A
                </span>
                <span className="text-sm font-bold text-gmat-text">Connecting Ridge (Site01)</span>
              </div>
              <div className="text-[10px] text-gmat-textMuted font-mono mt-0.5">
                Koordinat: Enlem -89.4632°, Boylam -137.4896° D · K2/LOLA ufuk profili
              </div>
            </div>
          </div>

          {/* SUHAIL Status Banner */}
          {s01Pass ? (
            <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/50 text-emerald-300 text-xs font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>GÖREV İÇİN UYGUN (PASS) · Güneş %100 · Kesinti {s01LongestBlackout} sa ≤ {maxBlackoutTol} sa</span>
            </div>
          ) : (
            <div className="p-2 rounded bg-red-950/40 border border-red-500/50 text-red-300 text-xs font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
              <span>GÖREV RİSKLİ (FAIL) · Kriter İhlali: Kesinti {s01LongestBlackout.toFixed(1)} sa &gt; {maxBlackoutTol} sa</span>
            </div>
          )}

          {/* 6 Metric Cards Grid */}
          <div className="grid grid-cols-2 gap-2 font-mono">
            {/* Card 1: Güneş Görünürlük */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Güneş görünürlük süresi</div>
              <div className="text-base font-bold text-amber-300">{s01SunHours.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-slate-500">↑ +0.0 sa</div>
            </div>

            {/* Card 2: Dünya Doğrudan Görüş */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Dünya doğrudan görüş penceresi</div>
              <div className="text-base font-bold text-sky-300">{s01EarthHours.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-gmat-green font-bold">↑ +54.0 sa</div>
            </div>

            {/* Card 3: Ortak Görünürlük */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Ortak görünürlük</div>
              <div className="text-base font-bold text-gmat-green">{s01JointHours.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-gmat-green font-bold">↑ +54.0 sa</div>
            </div>

            {/* Card 4: En Uzun Dünya Penceresi */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">En uzun Dünya penceresi</div>
              <div className="text-base font-bold text-sky-300">{s01LongestEarth.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-slate-500">Kesintisiz DTE</div>
            </div>

            {/* Card 5: En Uzun Kesintisiz İletişim */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">En Uzun Kesintisiz İletişim (Güneş+D...)</div>
              <div className="text-base font-bold text-gmat-green">{s01LongestJoint.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-gmat-green font-bold">↑ +54.0 sa</div>
            </div>

            {/* Card 6: Maksimum İletişimsizlik */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Maksimum İletişimsizlik</div>
              <div className="text-base font-bold text-red-400">{s01LongestBlackout.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-emerald-400 font-bold">↓ -58.0 sa</div>
            </div>
          </div>

          {/* Tactical Landing Recommendation */}
          <div className="p-2.5 rounded bg-sky-950/30 border border-sky-500/40 text-xs">
            <div className="font-semibold text-sky-200 flex items-center gap-1.5">
              <span>🚀 Taktik İniş Önerisi:</span>
              <span className="font-mono font-bold text-gmat-accent">18 Nov 2026 19:00 UTC</span>
            </div>
            <div className="text-[10px] text-sky-300/80 italic mt-0.5">
              (En uzun pencere: 54.0 sa kesintisiz güç ve iletişim)
            </div>
          </div>

          {/* Download Flight Briefing Card */}
          <button
            onClick={() => downloadFlightBriefingCard('Site01')}
            className="w-full py-1.5 px-3 bg-gmat-elevated hover:bg-gmat-border border border-gmat-border rounded text-xs font-semibold text-gmat-text flex items-center justify-center gap-1.5 transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-gmat-accent" />
            <span>Site01 Uçuş Kartını İndir (.md)</span>
          </button>

          {/* Topographic Obstruction Summary Accordion */}
          <div className="rounded border border-gmat-border bg-gmat-bg overflow-hidden">
            <button
              onClick={() => setOpenObstacleA(!openObstacleA)}
              className="w-full p-2 flex items-center justify-between text-[11px] font-semibold text-gmat-text hover:bg-gmat-elevated/40"
            >
              <span>Topoğrafik engel özeti</span>
              {openObstacleA ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
            </button>
            {openObstacleA && (
              <div className="p-2.5 border-t border-gmat-border/70 text-[10.5px] font-mono text-gmat-textMuted flex flex-col gap-1">
                <div>• Ortalama ufuk yüksekliği: <strong className="text-gmat-text">-2.0°</strong></div>
                <div>• En yüksek engel: <strong className="text-gmat-text">0.2° (Güneş azimutu 181°)</strong></div>
                <div>• Güneş geometrik olarak ufkun üzerindeyken topoğrafya tarafından kesilen süre: <strong className="text-gmat-green">%0</strong></div>
              </div>
            )}
          </div>
        </div>

        {/* ================= COLUMN B: SITE 04 ================= */}
        <div className="bg-gmat-panel p-3 rounded-xl border border-gmat-border flex flex-col gap-2.5 shadow-md">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono font-bold text-slate-400 px-1.5 py-0.2 rounded bg-gmat-bg border border-gmat-border">
                  Bölge B
                </span>
                <span className="text-sm font-bold text-gmat-text">Shackleton Rim (Site04)</span>
              </div>
              <div className="text-[10px] text-gmat-textMuted font-mono mt-0.5">
                Koordinat: Enlem -89.7668°, Boylam -171.8699° D · K2/LOLA ufuk profili
              </div>
            </div>
          </div>

          {/* SUHAIL Status Banner */}
          {s04Pass ? (
            <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/50 text-emerald-300 text-xs font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>GÖREV İÇİN UYGUN (PASS) · Güneş %100</span>
            </div>
          ) : (
            <div className="p-2 rounded bg-red-950/40 border border-red-500/50 text-red-300 text-xs font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
              <span>GÖREV RİSKLİ (FAIL) · Kriter İhlali: Kesinti {s04LongestBlackout.toFixed(1)} sa &gt; {maxBlackoutTol} sa</span>
            </div>
          )}

          {/* 6 Metric Cards Grid */}
          <div className="grid grid-cols-2 gap-2 font-mono">
            {/* Card 1: Güneş Görünürlük */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Güneş görünürlük süresi</div>
              <div className="text-base font-bold text-amber-300">{s04SunHours.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-slate-500">↑ +0.0 sa</div>
            </div>

            {/* Card 2: Dünya Doğrudan Görüş */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Dünya doğrudan görüş penceresi</div>
              <div className="text-base font-bold text-slate-400">{s04EarthHours.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-red-400 font-bold">↓ -54.0 sa</div>
            </div>

            {/* Card 3: Ortak Görünürlük */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Ortak görünürlük</div>
              <div className="text-base font-bold text-slate-400">{s04JointHours.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-red-400 font-bold">↓ -54.0 sa</div>
            </div>

            {/* Card 4: En Uzun Dünya Penceresi */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">En uzun Dünya penceresi</div>
              <div className="text-base font-bold text-slate-400">{s04LongestEarth.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-red-400">0.0 sa (Engelli)</div>
            </div>

            {/* Card 5: En Uzun Kesintisiz İletişim */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">En Uzun Kesintisiz İletişim (Güneş+D...)</div>
              <div className="text-base font-bold text-slate-400">{s04LongestJoint.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-red-400 font-bold">↓ -54.0 sa</div>
            </div>

            {/* Card 6: Maksimum İletişimsizlik */}
            <div className="bg-gmat-elevated p-2 rounded border border-gmat-border">
              <div className="text-[9.5px] text-gmat-textMuted">Maksimum İletişimsizlik</div>
              <div className="text-base font-bold text-red-400">{s04LongestBlackout.toFixed(1)} sa</div>
              <div className="text-[9.5px] text-red-400 font-bold">↑ +58.0 sa</div>
            </div>
          </div>

          {/* Tactical Landing Recommendation */}
          <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-xs">
            <div className="font-semibold text-slate-400 flex items-center gap-1.5">
              <span>🚀 Taktik İniş Önerisi:</span>
              <span className="font-mono text-red-400 font-bold">Pencere bulunamadı</span>
            </div>
            <div className="text-[10px] text-slate-500 italic mt-0.5">
              (En uzun pencere: 0.0 sa kesintisiz güç ve iletişim)
            </div>
          </div>

          {/* Download Flight Briefing Card */}
          <button
            onClick={() => downloadFlightBriefingCard('Site04')}
            className="w-full py-1.5 px-3 bg-gmat-elevated hover:bg-gmat-border border border-gmat-border rounded text-xs font-semibold text-gmat-text flex items-center justify-center gap-1.5 transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-gmat-accent" />
            <span>Site04 Uçuş Kartını İndir (.md)</span>
          </button>

          {/* Topographic Obstruction Summary Accordion */}
          <div className="rounded border border-gmat-border bg-gmat-bg overflow-hidden">
            <button
              onClick={() => setOpenObstacleB(!openObstacleB)}
              className="w-full p-2 flex items-center justify-between text-[11px] font-semibold text-gmat-text hover:bg-gmat-elevated/40"
            >
              <span>Topoğrafik engel özeti</span>
              {openObstacleB ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
            </button>
            {openObstacleB && (
              <div className="p-2.5 border-t border-gmat-border/70 text-[10.5px] font-mono text-gmat-textMuted flex flex-col gap-1">
                <div>• Ortalama ufuk yüksekliği: <strong className="text-gmat-text">-27.5°</strong></div>
                <div>• En yüksek engel: <strong className="text-gmat-text">-19.0° (Güneş azimutu 213°)</strong></div>
                <div>• Güneş geometrik olarak ufkun üzerindeyken topoğrafya tarafından kesilen süre: <strong className="text-gmat-green">%0</strong></div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
