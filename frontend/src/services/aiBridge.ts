import { Streamlit, RenderData } from 'streamlit-component-lib';

export interface Observation {
  feature: string;
  description: string;
  evidence: string;
  certainty: 'observed' | 'inferred' | 'uncertain';
  locationInImage: string | null;
  box: [number, number, number, number] | null;
  point: [number, number] | null;
}

export interface Analysis {
  region: { id: string; imageSource: string };
  aiAnalysis: {
    summary: string; observations: Observation[]; terrainInterpretation: string;
    potentialHazards: string[]; limitations: string[];
  };
  scientificAnalysis: {
    horizon_mean_deg: number | null; horizon_max_deg: number | null;
    joint_visible_fraction: number | null; longest_joint_window_hours: number | null;
    sources: string[];
  };
  metadata: { model: string; timestamp: string; status: string; inferenceExecuted: boolean; notes: string[] };
  conflicts: string[];
}

export interface SurfaceImage {
  dataUrl: string; kind: 'dem' | 'capture' | 'upload'; sourceLabel: string;
  provenance: string; width: number; height: number;
}

export interface BridgeReply {
  id: string; ok: boolean; error?: string; image?: SurfaceImage;
  analysis?: Analysis; answer?: string;
}

let connected = false;
let configuration = { model: '', configured: false };
const waiting = new Map<string, {
  resolve: (value: BridgeReply) => void; reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}>();

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event) => {
  const { args } = (event as CustomEvent<RenderData>).detail;
  connected = true;
  configuration = args.configuration ?? configuration;
  const reply = args.ai_response as BridgeReply | undefined;
  if (reply && waiting.has(reply.id)) {
    const pending = waiting.get(reply.id)!;
    clearTimeout(pending.timer);
    waiting.delete(reply.id);
    if (reply.ok) pending.resolve(reply);
    else pending.reject(new Error(reply.error || 'Analiz tamamlanamadı.'));
  }
  Streamlit.setFrameHeight(760);
});

Streamlit.setComponentReady();
Streamlit.setFrameHeight(760);

export function getAIConfiguration() { return { ...configuration, connected }; }

export function requestAI(payload: Record<string, unknown>, signal?: AbortSignal): Promise<BridgeReply> {
  if (!connected) return Promise.reject(new Error(
    'AI sunucusuna bağlantı yok. Bu görünümü ana LUNA SIGHT uygulamasındaki 3B Ay küresi sekmesinden açın.',
  ));
  if (signal?.aborted) return Promise.reject(new DOMException('İptal edildi', 'AbortError'));
  if (waiting.size) return Promise.reject(new Error('Önceki isteğin tamamlanmasını bekleyin.'));
  const id = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const abandon = () => {
      const pending = waiting.get(id);
      if (!pending) return;
      clearTimeout(pending.timer);
      waiting.delete(id);
      reject(new DOMException('İptal edildi', 'AbortError'));
    };
    const cleanup = () => signal?.removeEventListener('abort', abandon);
    const timer = setTimeout(() => {
      cleanup(); waiting.delete(id);
      reject(new Error('Sunucu yanıtı zaman aşımına uğradı. Yeniden deneyebilirsiniz.'));
    }, 180_000);
    waiting.set(id, {
      resolve: (reply) => { cleanup(); resolve(reply); },
      reject: (error) => { cleanup(); reject(error); }, timer,
    });
    signal?.addEventListener('abort', abandon, { once: true });
    Streamlit.setComponentValue({ ...payload, id });
  });
}
