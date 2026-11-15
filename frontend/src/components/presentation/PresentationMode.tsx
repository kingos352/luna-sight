import React, { useState, useEffect } from 'react';
import { useMission } from '../../context/MissionContext';
import {
  Presentation,
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  X,
  CheckCircle,
  Sparkles,
  Mountain,
  Radio,
  Sun,
  ShieldAlert,
  Globe,
  Award
} from 'lucide-react';

interface TourStep {
  title: string;
  subtitle: string;
  description: string;
  badge: string;
  targetSite?: 'Site01' | 'Site04';
  cameraMode?: 'globe' | 'terrain';
  layerMode?: 'wac' | 'topo';
}

const TOUR_STEPS: TourStep[] = [
  {
    title: '1. Misyon Tanıtımı & Ay Güney Kutbu',
    subtitle: 'Artemis Aday İniş Bölgeleri İncelemesi',
    description: 'Ay’ın güney kutbu, su buzu içeren kalıcı gölgeli kraterler (PSR) ve yüksek dağ zirvelerinde uzun süreli güneş ışığı potansiyeli sunar. LUNA SIGHT, NASA JPL Horizons efemerisi ve LOLA 5m/px DEM verileriyle görünürlük ve iniş fizibilitesini analiz eder.',
    badge: 'NASA SPACE APPS 2026',
    cameraMode: 'globe',
    layerMode: 'wac'
  },
  {
    title: '2. Connecting Ridge (Site 01) Odaklanması',
    subtitle: 'Shackleton ve de Gerlache Arasındaki Tepe Sırtı',
    description: 'Enlem: -89.46°, Boylam: -137.49° D. Connecting Ridge, hem sürekli güneş enerjisi erişimi hem de Dünya ile doğrudan haberleşme (Direct-to-Earth) açısından en dengeli aday bölgedir.',
    badge: 'ADAY BÖLGE SİTE 01',
    targetSite: 'Site01',
    cameraMode: 'globe',
    layerMode: 'topo'
  },
  {
    title: '3. LOLA 5m/px Yüksek Çözünürlüklü 3B Arazi Modeli',
    subtitle: 'Topografik Yüzey ve Eğim Analizi',
    description: 'LRO Laser Altimeter 5 metre/piksel çözünürlüğündeki dijital yükseklik modeli (DEM), 4000 metre yarıçapında yerel tepe ve krater kenarlarının gerçek profilini çıkarır.',
    badge: 'K2 TERRAIN ENGINE',
    targetSite: 'Site01',
    cameraMode: 'terrain'
  },
  {
    title: '4. K3 Bilimsel Görünürlük Motoru',
    subtitle: '3 Durumlu Analiz (Visible, Blocked, Uncertain) & ±0.10° Geçiş Bandı',
    description: 'Klasik ikili (True/False) mantık yerine, bilimsel belirsizlikleri modelleyen ±0.10° geçiş bandı uygulanmıştır. 14–21 Kasım 2026 UTC simülasyonunda 2,017 zaman adımı titizlikle test edilmiştir.',
    badge: 'K3 VISIBILITY ENGINE',
    targetSite: 'Site01',
    cameraMode: 'terrain'
  },
  {
    title: '5. Shackleton Rim (Site 04) Karşılaştırması',
    subtitle: 'Yüksek Güneş, Engelli Dünya Hattı',
    description: 'Shackleton krater kenarı (%100 Güneş ışığı) almasına karşın, kraterin dik dağ duvarları Dünya görüş hattını bloke eder. Bu nedenle tek başına otonom görevler için risklidir.',
    badge: 'KARŞILAŞTIRMA SİTE 04',
    targetSite: 'Site04',
    cameraMode: 'globe',
    layerMode: 'topo'
  },
  {
    title: '6. LunarSight AI Görsel Yüzey Yorumlaması',
    subtitle: 'NVIDIA Multimodal VLM Entegrasyonu',
    description: 'NVIDIA Nemotron 3.5 VLM modeli, DEM hillshade ve 3B sahne görselleri üzerinde krater kenarları, dik eğimler ve engel bölgelerini tespit eder. Bilimsel ölçümler K2/K3 motorunda korunurken, AI görsel karar desteği sağlar.',
    badge: 'NVIDIA NIM VLM',
    targetSite: 'Site01',
    cameraMode: 'globe',
    layerMode: 'wac'
  },
  {
    title: '7. Bilimsel Görev Karar Karnesi',
    subtitle: '12 Saatlik Kesintisiz Ortak Operasyon Kararı',
    description: 'Connecting Ridge (Site01), 87.8 saatlik kesintisiz ortak görünürlük (Güneş + Dünya) penceresiyle Artemis rover ve iniş araçları için kritik eşiği karşılayarak operasyonel açıdan en elverişli saha olarak doğrulanmıştır.',
    badge: 'BİLİMSEL KARAR: UYGUN',
    targetSite: 'Site01',
    cameraMode: 'terrain'
  }
];

export const PresentationMode: React.FC = () => {
  const {
    isPresentationMode,
    setIsPresentationMode,
    setSiteId,
    setCameraMode,
    setLayerMode
  } = useMission();

  const [stepIndex, setStepIndex] = useState<number>(0);
  const [autoPlay, setAutoPlay] = useState<boolean>(false);

  const step = TOUR_STEPS[stepIndex];

  // Apply step scene state
  useEffect(() => {
    if (!isPresentationMode) return;
    if (step.targetSite) setSiteId(step.targetSite);
    if (step.cameraMode) setCameraMode(step.cameraMode);
    if (step.layerMode) setLayerMode(step.layerMode);
  }, [stepIndex, isPresentationMode, step, setSiteId, setCameraMode, setLayerMode]);

  // Autoplay timer
  useEffect(() => {
    if (!autoPlay || !isPresentationMode) return;
    const timer = setInterval(() => {
      setStepIndex((prev) => (prev < TOUR_STEPS.length - 1 ? prev + 1 : 0));
    }, 12000);
    return () => clearInterval(timer);
  }, [autoPlay, isPresentationMode]);

  if (!isPresentationMode) return null;

  return (
    <div className="fixed inset-0 z-50 pointer-events-none flex flex-col justify-between p-6 select-none">
      {/* Top Overlay Banner */}
      <div className="pointer-events-auto flex items-center justify-between bg-gmat-panel/90 backdrop-blur-md border border-gmat-border p-3.5 rounded-xl shadow-2xl max-w-4xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-emerald-500 to-sky-600 flex items-center justify-center shadow-gmat-green">
            <Presentation className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-gmat-text">LUNA SIGHT — Mission Presentation Mode</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-700 font-bold">
                {step.badge}
              </span>
            </div>
            <div className="text-[11px] text-gmat-textMuted font-mono">
              Adım {stepIndex + 1} / {TOUR_STEPS.length} · Hakem ve Jüri Değerlendirme Turu
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoPlay(!autoPlay)}
            className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-all ${
              autoPlay ? 'bg-amber-600 text-white' : 'bg-gmat-elevated text-gmat-text hover:bg-gmat-border'
            }`}
          >
            {autoPlay ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{autoPlay ? 'Durdur' : 'Otomatik Oynat'}</span>
          </button>
          <button
            onClick={() => setIsPresentationMode(false)}
            className="p-1.5 rounded bg-gmat-elevated hover:bg-red-950 text-gmat-textMuted hover:text-red-400 transition-colors"
            title="Sunum Modundan Çık"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Bottom Narrative Card */}
      <div className="pointer-events-auto max-w-3xl mx-auto w-full bg-gmat-panel/95 backdrop-blur-md border border-gmat-border p-4 rounded-xl shadow-2xl flex flex-col gap-2.5">
        <div className="flex items-center justify-between border-b border-gmat-border/70 pb-2">
          <div>
            <h2 className="text-base font-bold text-gmat-text">{step.title}</h2>
            <div className="text-xs text-gmat-accent font-mono">{step.subtitle}</div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setStepIndex((prev) => Math.max(0, prev - 1))}
              disabled={stepIndex === 0}
              className="p-1.5 rounded bg-gmat-elevated text-gmat-text disabled:opacity-30 hover:bg-gmat-border transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono text-gmat-textMuted px-2">
              {stepIndex + 1} / {TOUR_STEPS.length}
            </span>
            <button
              onClick={() => setStepIndex((prev) => Math.min(TOUR_STEPS.length - 1, prev + 1))}
              disabled={stepIndex === TOUR_STEPS.length - 1}
              className="p-1.5 rounded bg-gmat-elevated text-gmat-text disabled:opacity-30 hover:bg-gmat-border transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        <p className="text-xs text-gmat-text leading-relaxed">
          {step.description}
        </p>

        {/* Step indicators */}
        <div className="flex items-center gap-1 pt-1 justify-center">
          {TOUR_STEPS.map((_, i) => (
            <div
              key={i}
              onClick={() => setStepIndex(i)}
              className={`h-1.5 rounded-full transition-all cursor-pointer ${
                i === stepIndex ? 'w-6 bg-gmat-accent' : 'w-2 bg-slate-700 hover:bg-slate-500'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
