import React from 'react';
import { useMission } from '../../context/MissionContext';
import { Sun, Globe, Activity } from 'lucide-react';

export const ElevationMarginChart: React.FC = () => {
  const { activePoint, isCaseActive, isVirtualPatchApplied, siteId } = useMission();

  // Değerler
  const {
    sunAz,
    sunAlt,
    sunHorizon,
    sunMargin,
    sunState,
    earthAz,
    earthAlt,
    earthHorizon,
    earthMargin,
    earthState,
    jointMargin,
    jointState
  } = activePoint;

  // Grafik Açı Ölçeği: -6° ile +6° arası
  // SVG Genişlik: 280, Yükseklik: 140
  const width = 280;
  const height = 130;
  const minVal = -6.0;
  const maxVal = 6.0;
  const scaleY = (val: number) => {
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    return height - ((clamped - minVal) / (maxVal - minVal)) * height;
  };

  const zeroY = scaleY(0);
  const bandTopY = scaleY(0.10);
  const bandBottomY = scaleY(-0.10);

  // Vaka durumunda özel büyütülmüş görünüm (Zoom on ±0.20° transition band)
  const isZoomCase = isCaseActive && siteId === 'Site01';

  // Zoom ölçeği: 0.0° ile +1.20° arası (Dünya ve Ufuk detayı)
  const zoomMin = 0.8;
  const zoomMax = 1.2;
  const scaleZoomY = (val: number) => {
    const clamped = Math.max(zoomMin, Math.min(zoomMax, val));
    return height - ((clamped - zoomMin) / (zoomMax - zoomMin)) * height;
  };

  return (
    <div className="bg-space-950 rounded-lg border border-slate-800 p-3 select-none flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-sky-400" />
          Açı & Marj Grafiği
        </span>
        <span className="text-[10px] font-mono text-slate-400">
          {isZoomCase ? 'Büyütülmüş Eşik Modu' : 'Ölçek: [−6°, +6°]'}
        </span>
      </div>

      {/* SVG Bar / Karşılaştırma Grafiği */}
      <div className="relative bg-space-900 rounded border border-slate-800/80 p-2">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-32 overflow-visible">
          {/* Arka plan ızgarası */}
          <line x1="0" y1={zeroY} x2={width} y2={zeroY} stroke="#334155" strokeDasharray="3 3" />
          <text x="5" y={zeroY - 3} fill="#64748b" fontSize="9" fontFamily="monospace">0.0° Geometrik Ufuk</text>

          {/* ±0.10° Modelleme Geçiş Bandı */}
          <rect
            x="0"
            y={bandTopY}
            width={width}
            height={Math.max(1, bandBottomY - bandTopY)}
            fill="#f59e0b"
            fillOpacity="0.12"
          />
          <line x1="0" y1={bandTopY} x2={width} y2={bandTopY} stroke="#f59e0b" strokeOpacity="0.4" strokeDasharray="2 2" />
          <text x={width - 65} y={bandTopY - 2} fill="#f59e0b" fontSize="8" fontFamily="monospace">+0.10° Eşik</text>

          {/* Sütun 1: Güneş Açıları */}
          <g transform="translate(45, 0)">
            {/* Ufuk Seviyesi Çizgisi */}
            <line
              x1="-25"
              y1={scaleY(sunHorizon)}
              x2="25"
              y2={scaleY(sunHorizon)}
              stroke="#94a3b8"
              strokeWidth="2"
            />
            {/* Yükseklik Çubuğu */}
            <circle cx="0" cy={scaleY(sunAlt)} r="4.5" fill="#fbbf24" stroke="#d97706" strokeWidth="1.5" />
            <text x="0" y={height - 5} fill="#fbbf24" fontSize="10" fontWeight="bold" textAnchor="middle">
              Güneş
            </text>
            <text x="0" y={scaleY(sunAlt) - 7} fill="#fbbf24" fontSize="9" fontFamily="monospace" textAnchor="middle">
              {sunAlt > 0 ? `+${sunAlt.toFixed(2)}°` : `${sunAlt.toFixed(2)}°`}
            </text>
          </g>

          {/* Sütun 2: Dünya Açıları */}
          <g transform="translate(140, 0)">
            {/* Ufuk Seviyesi */}
            <line
              x1="-25"
              y1={scaleY(earthHorizon)}
              x2="25"
              y2={scaleY(earthHorizon)}
              stroke="#94a3b8"
              strokeWidth="2"
            />
            {/* Yükseklik Noktası */}
            <circle cx="0" cy={scaleY(earthAlt)} r="4.5" fill="#38bdf8" stroke="#0284c7" strokeWidth="1.5" />
            <text x="0" y={height - 5} fill="#38bdf8" fontSize="10" fontWeight="bold" textAnchor="middle">
              Dünya
            </text>
            <text x="0" y={scaleY(earthAlt) - 7} fill="#38bdf8" fontSize="9" fontFamily="monospace" textAnchor="middle">
              {earthAlt > 0 ? `+${earthAlt.toFixed(2)}°` : `${earthAlt.toFixed(2)}°`}
            </text>
          </g>

          {/* Sütun 3: Açısal Marj (Yükseklik − Ufuk) */}
          <g transform="translate(230, 0)">
            {/* Marj Barı */}
            <rect
              x="-12"
              y={earthMargin >= 0 ? scaleY(earthMargin) : zeroY}
              width="24"
              height={Math.abs(scaleY(earthMargin) - zeroY)}
              fill={earthState === 'visible' ? '#22c55e' : earthState === 'blocked' ? '#ef4444' : '#f59e0b'}
              rx="2"
            />
            <text x="0" y={height - 5} fill="#94a3b8" fontSize="10" fontWeight="bold" textAnchor="middle">
              Dünya Marjı
            </text>
            <text
              x="0"
              y={scaleY(earthMargin) + (earthMargin >= 0 ? -6 : 14)}
              fill={earthState === 'visible' ? '#4ade80' : earthState === 'blocked' ? '#f87171' : '#fbbf24'}
              fontSize="9"
              fontFamily="monospace"
              fontWeight="bold"
              textAnchor="middle"
            >
              {earthMargin > 0 ? `+${earthMargin.toFixed(3)}°` : `${earthMargin.toFixed(3)}°`}
            </text>
          </g>
        </svg>
      </div>

      {/* Sayısal Detaylar Tablosu */}
      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
        <div className="bg-space-900 p-2 rounded border border-slate-800">
          <div className="text-amber-400 font-bold mb-1 flex items-center gap-1">
            <Sun className="w-3 h-3" /> Güneş Geometrisi
          </div>
          <div className="text-slate-400">Azimut: <span className="text-slate-200">{sunAz.toFixed(2)}°</span></div>
          <div className="text-slate-400">Yükseklik: <span className="text-slate-200">+{sunAlt.toFixed(3)}°</span></div>
          <div className="text-slate-400">Arazi Ufku: <span className="text-slate-200">{sunHorizon.toFixed(3)}°</span></div>
          <div className="text-slate-400">Marj (Alt−Ufuk): <span className="text-emerald-400 font-bold">+{sunMargin.toFixed(3)}°</span></div>
          <div className="mt-1 text-[10px] font-sans font-semibold text-emerald-400">Durum: Görünür (Visible)</div>
        </div>

        <div className="bg-space-900 p-2 rounded border border-slate-800">
          <div className="text-sky-400 font-bold mb-1 flex items-center gap-1">
            <Globe className="w-3 h-3" /> Dünya Geometrisi
          </div>
          <div className="text-slate-400">Azimut: <span className="text-slate-200">{earthAz.toFixed(2)}°</span></div>
          <div className="text-slate-400">Yükseklik: <span className="text-slate-200">{earthAlt > 0 ? `+${earthAlt.toFixed(3)}°` : `${earthAlt.toFixed(3)}°`}</span></div>
          <div className="text-slate-400">Arazi Ufku: <span className="text-slate-200">+{earthHorizon.toFixed(3)}°</span></div>
          <div className="text-slate-400">Marj: <span className={`font-bold ${earthMargin > 0.10 ? 'text-emerald-400' : earthMargin < -0.10 ? 'text-red-400' : 'text-amber-400'}`}>
            {earthMargin > 0 ? `+${earthMargin.toFixed(4)}°` : `${earthMargin.toFixed(4)}°`}
          </span></div>
          <div className="mt-1 text-[10px] font-sans font-semibold">
            Durum: <span className={earthState === 'visible' ? 'text-emerald-400' : earthState === 'blocked' ? 'text-red-400' : 'text-amber-400'}>
              {earthState === 'visible' ? 'Görünür' : earthState === 'blocked' ? 'Engelli' : 'Belirsiz (Geçiş Bandı)'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
