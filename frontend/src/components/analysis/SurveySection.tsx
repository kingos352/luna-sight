import React from 'react';
import { useMission } from '../../context/MissionContext';
import { Download, Sparkles, AlertCircle, CheckCircle2, HelpCircle, Layers, MapPin } from 'lucide-react';

export const SurveySection: React.FC = () => {
  const {
    isCaseActive,
    isVirtualPatchApplied,
    toggleVirtualPatch,
    openConnectingRidgeCase,
    exportCaseData,
    sceneData,
    caseData
  } = useMission();

  const patch = sceneData?.proposed_survey_patch;

  return (
    <div className="bg-space-950 rounded-lg border border-slate-800 p-3 select-none flex flex-col gap-3">
      {/* Başlık ve Durum */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-bold text-slate-100">
            Ölçüm Planla — Ayırt Edici Akış
          </span>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
          isCaseActive ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-space-900 text-slate-400 border border-slate-800'
        }`}>
          {isCaseActive ? 'Vaka Açık' : 'Hazır'}
        </span>
      </div>

      {!isCaseActive ? (
        <div className="bg-space-900/60 rounded p-3 border border-slate-800/80 text-xs text-slate-300 flex flex-col gap-2">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Connecting Ridge sahasında 18–19 Kasım 2026 UTC 12 saatlik operasyonel penceresinde,
            yerel topoğrafik belirsizliğin karar sınıfını nasıl değiştirdiğini kanıtlayan doğrulanmış vaka.
          </p>
          <button
            onClick={openConnectingRidgeCase}
            className="w-full py-2 px-3 rounded bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-slate-950 font-bold text-xs shadow-md transition-all flex items-center justify-center gap-2"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Connecting Ridge Vakasını Aç
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Vaka Özet Kartı */}
          <div className="bg-space-900 p-2.5 rounded border border-slate-800 text-[11px] font-mono space-y-1">
            <div className="flex justify-between text-slate-400 border-b border-slate-800/80 pb-1 mb-1">
              <span>Operasyon Penceresi:</span>
              <span className="text-slate-200 font-bold">18 Kas 16:55 → 19 Kas 04:55 UTC (12 sa)</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Tetikleyici An:</span>
              <span className="text-amber-300 font-bold">18 Kasım 2026 16:55 UTC</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Dünya Azimut / İrtifa:</span>
              <span className="text-slate-200">130.730898° / +1.074733°</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Modelleme Bandı Eşiği:</span>
              <span className="text-slate-200">±0.100000° (Geçiş Eşiği)</span>
            </div>
          </div>

          {/* Sanal Ölçüm Uygulama Anahtarı (Clone 1 Yaması) */}
          <div className="bg-space-900 p-2.5 rounded border border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-slate-200">Sanal Ölçümü Uygula</div>
              <div className="text-[10px] text-slate-400 font-mono">
                {isVirtualPatchApplied ? 'Clone 1 Yaması Devrede (Kot Sabit)' : 'Nominal Deney Yüzeyi'}
              </div>
            </div>
            <button
              onClick={toggleVirtualPatch}
              className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${
                isVirtualPatchApplied
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-950/40'
                  : 'bg-space-800 text-slate-300 hover:bg-space-700 border border-slate-700'
              }`}
            >
              {isVirtualPatchApplied ? 'Aktif (Clone 1)' : 'Pasif (Nominal)'}
            </button>
          </div>

          {/* Sonuç Kartı: Uygun -> Belirsiz Karşılaştırması */}
          <div className={`p-3 rounded-lg border transition-all ${
            isVirtualPatchApplied
              ? 'bg-amber-950/30 border-amber-500/50 text-amber-200'
              : 'bg-emerald-950/30 border-emerald-500/50 text-emerald-200'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold flex items-center gap-1.5">
                {isVirtualPatchApplied ? (
                  <HelpCircle className="w-4 h-4 text-amber-400" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                )}
                12 Saatlik Görev Kararı:
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider font-mono ${
                isVirtualPatchApplied
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              }`}>
                {isVirtualPatchApplied ? 'Belirsiz (Uncertain)' : 'Uygun (Feasible)'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div>
                <span className="text-slate-400">Arazi Ufku: </span>
                <span className="font-bold text-slate-100">
                  {isVirtualPatchApplied ? '+1.036964°' : '+0.970511°'}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Açı Payı (Marj): </span>
                <span className={`font-bold ${isVirtualPatchApplied ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {isVirtualPatchApplied ? '+0.037769°' : '+0.104222°'}
                </span>
              </div>
            </div>

            <div className="mt-2 text-[10px] text-slate-300 leading-normal border-t border-slate-800/60 pt-1.5">
              {isVirtualPatchApplied
                ? 'Clone 1 mikro-rölyef yaması ufku +0.066° yükseltti. Açı payı +0.10° altına düştüğü için 12 saatlik pencere Uygun durumundan Belirsiz durumuna geçti.'
                : 'Nominal arazide açı payı (+0.104°) geçiş eşiğinin (+0.10°) üzerinde kaldığı için tüm pencere kesintisiz Uygun kabul edilmektedir.'}
            </div>
          </div>

          {/* Önerilen Ölçüm Alanı Bilgisi (400x400 m) */}
          <div className="bg-space-900 p-2.5 rounded border border-slate-800 text-[11px] font-mono space-y-1">
            <div className="text-xs font-bold text-slate-200 flex items-center gap-1 font-sans">
              <MapPin className="w-3 h-3 text-sky-400" />
              Önerilen Ek Ölçüm Alanı ({patch?.name || 'Target_MethodA_CriticalRidge'})
            </div>
            <div className="text-slate-400">Boyut: <span className="text-slate-200">400 × 400 m (160 000 m²)</span></div>
            <div className="text-slate-400">Merkez (X, Y): <span className="text-slate-200">-11 009.61 m, -11 915.54 m</span></div>
            <div className="text-slate-400">Merkez (Lat, Lon): <span className="text-slate-200">-89.464998°, -137.262991° D</span></div>
            <div className="text-slate-400">Datum / Çerçeve: <span className="text-slate-200">MOON_ME (JPL DE421)</span></div>
          </div>

          {/* Dışa Aktarma Butonları */}
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => exportCaseData('json')}
              className="flex-1 py-1.5 px-2 bg-space-900 hover:bg-space-800 border border-slate-700 text-slate-200 text-xs font-medium rounded flex items-center justify-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-sky-400" />
              <span>Vaka JSON İndir</span>
            </button>
            <button
              onClick={() => exportCaseData('csv')}
              className="flex-1 py-1.5 px-2 bg-space-900 hover:bg-space-800 border border-slate-700 text-slate-200 text-xs font-medium rounded flex items-center justify-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-emerald-400" />
              <span>Vaka CSV İndir</span>
            </button>
          </div>

          {/* Bilimsel Sınırlar Uyarısı */}
          <div className="bg-space-950 p-2 rounded border border-slate-800/80 text-[10px] text-slate-400 leading-relaxed flex items-start gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-300">Araştırma İddiası & Sınırlar:</strong> Bu vaka, yerel arazi yamasının karar sınıfını etkileyebildiğini gösteren idealize edilmiş bir deneydir. Kesin haberleşme kaybı veya genel yöntem üstünlüğü iddiası taşımaz.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
