import React, { useRef, useCallback } from 'react';
import { useMission } from '../../context/MissionContext';
import { Play, Pause, RotateCcw, FastForward, ChevronLeft, ChevronRight } from 'lucide-react';

export const TimelineBar: React.FC = () => {
  const {
    siteId,
    timeseries,
    timeIndex,
    setTimeIndex,
    isPlaying,
    setIsPlaying,
    playSpeed,
    setPlaySpeed,
    currentTimestamp,
    scenario,
    activeWindows,
    longestJointWindow,
    minDurationHours
  } = useMission();

  const trackRef = useRef<HTMLDivElement>(null);

  const totalSamples = timeseries && timeseries[siteId] ? timeseries[siteId].timestamps.length : 2017;

  // Tıklama ile zamana gitme
  const handleTrackClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!trackRef.current || !timeseries || !timeseries[siteId]) return;
    const rect = trackRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    const newIdx = Math.floor(ratio * (timeseries[siteId].timestamps.length - 1));
    setTimeIndex(newIdx);
  }, [timeseries, siteId, setTimeIndex]);

  // Gün veya saat bazlı atlama
  const jumpHours = useCallback((hours: number) => {
    if (!timeseries || !timeseries[siteId]) return;
    const steps = Math.round((hours * 60) / 5);
    setTimeIndex(Math.max(0, Math.min(totalSamples - 1, timeIndex + steps)));
  }, [timeIndex, totalSamples, timeseries, siteId, setTimeIndex]);

  // Görünürlük şeritleri için basitleştirilmiş dilimler (performanslı canvas veya SVG)
  const currentTsData = timeseries && timeseries[siteId];

  return (
    <div className="bg-space-900 border-t border-slate-800 p-3 select-none flex flex-col gap-2 z-20">
      {/* Üst Satır: Oynatma Kontrolleri ve Hızlı Bilgi */}
      <div className="flex items-center justify-between">
        {/* Oynatma Butonları */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTimeIndex(0)}
            title="Başa Dön (14 Kasım 00:00 UTC)"
            className="p-1.5 rounded bg-space-950 hover:bg-space-800 border border-slate-800 text-slate-300 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => jumpHours(-1)}
            title="-1 Saat"
            className="p-1.5 rounded bg-space-950 hover:bg-space-800 border border-slate-800 text-slate-300 transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className={`px-3 py-1.5 rounded flex items-center gap-1.5 text-xs font-semibold transition-all ${
              isPlaying
                ? 'bg-amber-600 hover:bg-amber-500 text-slate-950'
                : 'bg-sky-600 hover:bg-sky-500 text-white shadow-md shadow-sky-950/50'
            }`}
          >
            {isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5 fill-current" />
                <span>Duraklat</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Oynat</span>
              </>
            )}
          </button>

          <button
            onClick={() => jumpHours(1)}
            title="+1 Saat"
            className="p-1.5 rounded bg-space-950 hover:bg-space-800 border border-slate-800 text-slate-300 transition-colors"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>

          {/* Oynatma Hızı */}
          <div className="flex items-center bg-space-950 rounded border border-slate-800 p-0.5 ml-1">
            {[1, 5, 20].map((spd) => (
              <button
                key={spd}
                onClick={() => setPlaySpeed(spd)}
                className={`px-2 py-0.5 text-[10px] font-mono rounded ${
                  playSpeed === spd
                    ? 'bg-space-800 text-sky-400 font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Orta: Zaman Damgası ve İlerleme */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="text-slate-400 flex items-center gap-2">
            <span>Örnek:</span>
            <span className="text-slate-200 font-bold">{timeIndex + 1} / {totalSamples}</span>
            <span className="text-slate-500">({((timeIndex / (totalSamples - 1)) * 168).toFixed(1)}h / 168h)</span>
          </div>

          <div className="px-2.5 py-1 rounded bg-space-950 border border-slate-800 text-sky-300 font-semibold">
            {currentTimestamp.replace('T', ' ').substring(0, 19)} UTC
          </div>
        </div>

        {/* Sağ: En Uzun Ortak Pencere Özeti */}
        <div className="flex items-center gap-3 text-xs">
          {longestJointWindow ? (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-emerald-950/60 border border-emerald-600/40 text-emerald-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="font-semibold">En Uzun Ortak Pencere:</span>
              <span className="font-mono font-bold">{longestJointWindow.durationHours} sa</span>
              <span className="text-[10px] text-emerald-400/80 hidden sm:inline">
                ({longestJointWindow.durationHours >= minDurationHours ? 'Operasyon Uygun' : 'Yetersiz'})
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-red-950/60 border border-red-600/40 text-red-300">
              <span className="w-2 h-2 rounded-full bg-red-400"></span>
              <span className="font-semibold">Ortak Pencere Yok</span>
              <span className="text-[10px] text-red-400/80">(Dünya Engelli)</span>
            </div>
          )}
        </div>
      </div>

      {/* Görünürlük Şeritleri ve Zaman Çizelgesi Eksenleri */}
      <div className="space-y-1">
        {/* Şerit Açıklama Etiketleri */}
        <div className="flex items-center text-[10px] text-slate-400 px-1">
          <div className="w-20 font-medium">Güneş</div>
          <div className="w-20 font-medium">Dünya</div>
          <div className="w-20 font-medium">Ortak</div>
          <div className="flex-1 flex justify-between text-slate-500 font-mono text-[9px] px-1">
            <span>14 Kas</span>
            <span>15 Kas</span>
            <span>16 Kas</span>
            <span>17 Kas</span>
            <span>18 Kas (Vaka)</span>
            <span>19 Kas</span>
            <span>20 Kas</span>
            <span>21 Kas</span>
          </div>
        </div>

        {/* İnteraktif Zaman Çubuğu Kapsayıcısı */}
        <div
          ref={trackRef}
          onClick={handleTrackClick}
          className="relative h-12 bg-space-950 rounded border border-slate-800 cursor-pointer overflow-hidden flex flex-col justify-between py-1 px-0.5 group"
        >
          {/* 1. Güneş Görünürlük Şeridi (Sıcak Sarı) */}
          <div className="h-2.5 w-full bg-slate-900 rounded-sm overflow-hidden flex relative">
            {/* Site01 ve Site04 için tüm hafta boyunca Güneş görünür (%100) */}
            <div className="h-full w-full bg-amber-400/90 shadow-sm" title="Güneş Görünür (%100)" />
          </div>

          {/* 2. Dünya Görünürlük Şeridi (Buz Mavisi / Kırmızı) */}
          <div className="h-2.5 w-full bg-slate-900 rounded-sm overflow-hidden flex relative">
            {siteId === 'Site01' ? (
              <>
                {/* 14 Kas 00:00 - 18 Kas 14:52: Engelli (%65.8) */}
                <div style={{ width: '65.8%' }} className="h-full bg-red-500/80" title="Dünya Engelli (occluded)" />
                {/* 18 Kas 14:52 - 18 Kas 18:18: Belirsiz Geçiş Bandı (%2.05) */}
                <div style={{ width: '2.05%' }} className="h-full bg-amber-500/90" title="Dünya Belirsiz (transition_band)" />
                {/* 18 Kas 18:18 - 21 Kas 00:00: Görünür (%31.96) */}
                <div style={{ width: '31.96%' }} className="h-full bg-sky-400" title="Dünya Görünür (clear, 53.68 sa)" />
              </>
            ) : (
              /* Site04: Dünya tüm hafta krater arkasında engelli */
              <div className="h-full w-full bg-red-500/80" title="Dünya Engelli (%100 occluded)" />
            )}
          </div>

          {/* 3. Ortak Görünürlük Şeridi (Yeşil / Kırmızı / Turuncu) */}
          <div className="h-3 w-full bg-slate-900 rounded-sm overflow-hidden flex relative">
            {siteId === 'Site01' ? (
              <>
                <div style={{ width: '65.8%' }} className="h-full bg-red-600/90" title="Ortak Engelli" />
                <div style={{ width: '2.05%' }} className="h-full bg-amber-500" title="Ortak Belirsiz (Geçiş Bandı)" />
                <div style={{ width: '31.96%' }} className="h-full bg-emerald-500" title="Ortak Görünür (53.68 sa kesintisiz pencere)" />
              </>
            ) : (
              <div className="h-full w-full bg-red-600/90" title="Ortak Engelli (Dünya yok)" />
            )}
          </div>

          {/* Geçerli Zaman İmleci (Draggable İğne) */}
          <div
            style={{ left: `${(timeIndex / (totalSamples - 1)) * 100}%` }}
            className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.9)] z-10 pointer-events-none -translate-x-1/2"
          >
            <div className="w-2.5 h-2.5 rounded-full bg-white border-2 border-sky-500 -translate-x-[4px] -translate-y-1 shadow-md" />
          </div>

          {/* 18 Kasım 16:55 UTC Vaka İşareti */}
          {siteId === 'Site01' && (
            <div
              style={{ left: '66.9%' }}
              className="absolute top-0 bottom-0 w-0.5 bg-amber-400 border-l border-dashed border-amber-300 pointer-events-none z-5"
              title="Connecting Ridge Tetikleyici Örnek (18 Kas 16:55 UTC)"
            >
              <div className="text-[8px] font-mono text-amber-300 bg-space-950 px-1 rounded absolute -top-1 -translate-x-1/2 whitespace-nowrap border border-amber-500/40">
                16:55
              </div>
            </div>
          )}
        </div>

        {/* Lejant (Durum Göstergeleri) */}
        <div className="flex items-center justify-between text-[10px] text-slate-400 px-1 pt-0.5">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded bg-emerald-500"></span>
              <span>Görünür / Uygun</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded bg-amber-500"></span>
              <span>Belirsiz (±0.10° Geçiş Bandı)</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded bg-red-500"></span>
              <span>Engelli (Arazi Ufku Altında)</span>
            </span>
          </div>

          <div className="text-slate-500 font-mono text-[9px]">
            JPL Horizons DE441 • LOLA {scenario === '0deg' ? '0°' : scenario} • Adım: 5 dk
          </div>
        </div>
      </div>
    </div>
  );
};
