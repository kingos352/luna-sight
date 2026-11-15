import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, Camera, Upload, Download, X, AlertTriangle, Loader2, Mountain } from 'lucide-react';
import { useMission } from '../../context/MissionContext';
import { Analysis, SurfaceImage, requestAI, getAIConfiguration } from '../../services/aiBridge';

const certainty = { observed: 'Görselde seçiliyor', inferred: 'Yorum', uncertain: 'Belirsiz' };
const colors = ['#38bdf8', '#f59e0b', '#a78bfa', '#34d399'];
type Tab = 'caption' | 'detect' | 'point' | 'query';

export const LunarSightAIModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const { siteId, currentTimestamp, scenario, isCaseActive, isVirtualPatchApplied, setIsPlaying } = useMission();
  const [activeTab, setActiveTab] = useState<Tab>('caption');
  const [image, setImage] = useState<SurfaceImage | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [focus, setFocus] = useState('Belirgin sırtlar, krater kenarları ve çöküntüler');
  const [question, setQuestion] = useState('Bu görüntü hangi arazi özelliklerini gösteriyor, neleri söyleyemeyiz?');
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const config = getAIConfiguration();
  const scene = { timestamp: currentTimestamp, scenario, caseActive: isCaseActive, virtualPatch: isVirtualPatchApplied };

  const newRequest = () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    return { token: ++revision.current, signal: abortRef.current.signal };
  };
  const clearResults = () => { setAnalysis(null); setMessages([]); setError(''); setNotice(''); };

  async function prepare(kind: 'dem' | 'capture' | 'upload', dataUrl?: string, filename?: string) {
    const { token, signal } = newRequest();
    setBusy(true); setImage(null); clearResults();
    try {
      const reply = await requestAI({ action: 'prepare', site_id: siteId, kind, data_url: dataUrl, filename, scene }, signal);
      if (token !== revision.current) return;
      if (!reply.image) throw new Error('Sunucu görüntü döndürmedi.');
      setImage(reply.image);
    } catch (e) {
      if (token === revision.current && (e as Error).name !== 'AbortError') setError((e as Error).message);
    } finally { if (token === revision.current) setBusy(false); }
  }

  useEffect(() => {
    if (!isOpen) { abortRef.current?.abort(); revision.current++; setBusy(false); return; }
    previousFocus.current = document.activeElement as HTMLElement;
    setIsPlaying(false);
    void prepare('dem');
    requestAnimationFrame(() => dialogRef.current?.focus());
    return () => { abortRef.current?.abort(); revision.current++; previousFocus.current?.focus(); };
  }, [isOpen, siteId]);

  useEffect(() => {
    if (!isOpen) return;
    const keydown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose(); }
      if (e.key === 'Tab') {
        const elements = dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [tabindex="0"]');
        if (!elements?.length) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', keydown);
    return () => document.removeEventListener('keydown', keydown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!image || !canvasRef.current) return;
    let canceled = false;
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');
    if (!context) return;
    const preview = new Image();
    preview.onload = () => {
      if (canceled) return;
      canvas.width = preview.width; canvas.height = preview.height;
      context.drawImage(preview, 0, 0);
      analysis?.aiAnalysis.observations.forEach((observation, i) => {
        context.strokeStyle = colors[i % colors.length];
        context.fillStyle = colors[i % colors.length];
        context.lineWidth = 2;
        context.font = `${Math.max(13, Math.round(canvas.width / 55))}px sans-serif`;
        if (activeTab === 'detect' && observation.box) {
          const [x0, y0, x1, y1] = observation.box;
          context.strokeRect(x0 * canvas.width, y0 * canvas.height, (x1 - x0) * canvas.width, (y1 - y0) * canvas.height);
          context.fillText(String(i + 1), x0 * canvas.width + 4, Math.max(18, y0 * canvas.height - 5));
        }
        if (activeTab === 'point' && observation.point) {
          const [x, y] = observation.point;
          context.beginPath(); context.arc(x * canvas.width, y * canvas.height, 6, 0, Math.PI * 2); context.stroke();
          context.fillText(String(i + 1), x * canvas.width + 10, y * canvas.height - 5);
        }
      });
    };
    preview.onerror = () => { if (!canceled) setError('Görüntü önizlemesi okunamadı. Yeniden hazırlayın.'); };
    preview.src = image.dataUrl;
    return () => { canceled = true; };
  }, [image, analysis, activeTab]);

  async function capture() {
    const canvas = document.querySelector<HTMLCanvasElement>('#luna-sight-webgl-container canvas');
    if (!canvas || !canvas.width || !canvas.height) { setError('3B sahne henüz hazır değil. LOLA DEM seçeneğini kullanabilirsiniz.'); return; }
    try {
      const small = document.createElement('canvas');
      const ratio = Math.min(1, 1024 / Math.max(canvas.width, canvas.height));
      small.width = Math.max(32, Math.round(canvas.width * ratio)); small.height = Math.max(32, Math.round(canvas.height * ratio));
      const context = small.getContext('2d');
      if (!context) throw new Error('Görüntü yakalanamadı.');
      context.drawImage(canvas, 0, 0, small.width, small.height);
      await prepare('capture', small.toDataURL('image/jpeg', 0.9));
    } catch { setError('3B sahne yakalanamadı. DEM görüntüsünü kullanabilir veya dosya yükleyebilirsiniz.'); }
  }

  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 4 * 1024 * 1024) {
      setError('PNG, JPEG veya WEBP seçin; dosya en fazla 4 MB olmalı.'); return;
    }
    const reader = new FileReader();
    reader.onerror = () => setError('Dosya okunamadı.');
    reader.onload = () => void prepare('upload', String(reader.result), file.name);
    reader.readAsDataURL(file);
  }

  async function run() {
    if (!image || busy) return;
    const { token, signal } = newRequest();
    setBusy(true); setError(''); setNotice('');
    try {
      const payload = { site_id: siteId, kind: image.kind, data_url: image.kind === 'dem' ? undefined : image.dataUrl, scene };
      const reply = await requestAI(activeTab === 'query'
        ? { ...payload, action: 'ask', question }
        : { ...payload, action: 'analyze', mode: activeTab, focus: activeTab === 'caption' ? '' : focus }, signal);
      if (token !== revision.current) return;
      if (activeTab === 'query') {
        if (!reply.answer) throw new Error('Model cevap döndürmedi.');
        setMessages(previous => [...previous, { role: 'Siz', text: question }, { role: 'LunarSight AI', text: reply.answer! }]);
      } else {
        if (!reply.analysis) throw new Error('Model analiz döndürmedi.');
        setAnalysis(reply.analysis);
        const observations = reply.analysis.aiAnalysis.observations;
        if (activeTab === 'detect' && !observations.some(item => item.box)) setNotice('Model bu görüntüde bir kutu konumu vermedi. Gözlemler aşağıda.');
        if (activeTab === 'point' && !observations.some(item => item.point)) setNotice('Model bu görüntüde bir nokta konumu vermedi. Gözlemler aşağıda.');
        if (reply.analysis.metadata.status === 'partial') setNotice('Model yanıtı kısmi. Sonucu aşağıdaki sınırlarla birlikte değerlendirin.');
      }
    } catch (e) { if (token === revision.current && (e as Error).name !== 'AbortError') setError((e as Error).message); }
    finally { if (token === revision.current) setBusy(false); }
  }

  function downloadJSON() {
    if (!analysis) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(analysis, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = `lunarsight_${siteId}_analysis.json`; link.click(); URL.revokeObjectURL(url);
  }
  function downloadImage() {
    if (!canvasRef.current) return;
    const link = document.createElement('a'); link.href = canvasRef.current.toDataURL('image/png'); link.download = `lunarsight_${siteId}_${activeTab}.png`; link.click();
  }

  if (!isOpen) return null;
  const result = analysis?.aiAnalysis;
  const button = 'px-2.5 py-1.5 text-xs rounded bg-space-900 hover:bg-space-800 border border-slate-700 text-slate-200 flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed';
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 backdrop-blur-md p-3 md:p-4">
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="lunar-ai-title" tabIndex={-1} className="w-full max-w-5xl bg-space-900 border border-slate-800 rounded-xl shadow-2xl flex flex-col h-[92vh] overflow-hidden outline-none">
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-slate-800 bg-space-950">
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles className="w-5 h-5 text-purple-400 shrink-0" />
            <div><h2 id="lunar-ai-title" className="font-bold text-sm text-slate-100">LunarSight AI</h2><p className="text-[10px] text-slate-400">{siteId} · Görüntüye dayalı yüzey yorumu</p></div>
          </div>
          <button onClick={onClose} aria-label="LunarSight AI penceresini kapat" className={button}><X className="w-5 h-5" /></button>
        </div>
        <div className="flex flex-wrap gap-2 px-4 py-2 border-b border-slate-800">
          <button disabled={busy} onClick={() => void prepare('dem')} className={button}><Mountain className="w-3.5 h-3.5 text-sky-400" />LOLA DEM</button>
          <button disabled={busy} onClick={() => void capture()} className={button}><Camera className="w-3.5 h-3.5 text-sky-400" />3B Sahneyi Yakala</button>
          <button disabled={busy} onClick={() => fileRef.current?.click()} className={button}><Upload className="w-3.5 h-3.5 text-emerald-400" />Görsel Yükle</button>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label="Analiz görüntüsü yükle" onChange={upload} />
        </div>
        <div className="flex-1 flex flex-col md:flex-row overflow-y-auto md:overflow-hidden min-h-0">
          <div className="flex-1 min-w-0 bg-space-950 p-4 flex flex-col gap-3 items-center justify-center border-b md:border-b-0 md:border-r border-slate-800">
            {image ? <><canvas ref={canvasRef} aria-label={`${siteId} analiz görüntüsü`} className="max-w-full max-h-[35vh] md:max-h-[52vh] object-contain rounded border border-slate-800" /><p className="text-[11px] text-sky-300 text-center">{image.sourceLabel} · {image.width} × {image.height}</p><p className="text-[10px] text-slate-400 leading-relaxed select-text">{image.provenance}</p><button onClick={downloadImage} className={button}><Download className="w-3.5 h-3.5" />Görüntüyü indir</button></> : <p className="text-xs text-slate-400 py-8">{busy ? 'Görüntü hazırlanıyor…' : 'Görüntü hazır değil. LOLA DEM veya görsel yükleme seçeneğini deneyin.'}</p>}
          </div>
          <div className="w-full md:w-[25rem] shrink-0 p-4 flex flex-col gap-3 md:overflow-y-auto custom-scrollbar select-text">
            <div role="tablist" aria-label="AI analiz seçenekleri" className="grid grid-cols-4 gap-1 bg-space-950 rounded-lg p-1 border border-slate-800">
              {([['caption', 'Açıklama'], ['detect', 'Tespit'], ['point', 'Noktalama'], ['query', 'Soru-Cevap']] as [Tab, string][]).map(([key, label]) => <button key={key} role="tab" aria-selected={activeTab === key} disabled={busy} onClick={() => setActiveTab(key)} className={`py-2 text-[11px] rounded disabled:opacity-40 ${activeTab === key ? 'bg-space-800 text-sky-300' : 'text-slate-400 hover:text-white'}`}>{label}</button>)}
            </div>
            <p className="text-[11px] text-slate-400">{activeTab === 'caption' ? 'Seçili görüntüyü gerçek modelle inceleyin. Ölçümler bilimsel kayıtlardan ayrı sunulur.' : activeTab === 'query' ? 'Sorunuz seçili görüntü ve kayıtlı bilimsel verilerle birlikte modele gönderilir.' : 'İşaretler modelin yaklaşık görüntü konumlarıdır. Ölçüm veya güvenli iniş alanı önerisi değildir.'}</p>
            {(activeTab === 'detect' || activeTab === 'point') && <label className="text-[11px] text-slate-400">İncelenecek özellikler<input value={focus} disabled={busy} onChange={event => setFocus(event.target.value)} maxLength={500} className="mt-1 w-full bg-space-950 border border-slate-700 rounded px-3 py-2 text-xs text-slate-100" /></label>}
            {activeTab === 'query' && <label className="text-[11px] text-slate-400">Görüntü hakkında sorunuz<textarea value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} maxLength={2000} rows={3} className="mt-1 w-full bg-space-950 border border-slate-700 rounded px-3 py-2 text-xs text-slate-100 resize-y" /></label>}
            <button disabled={busy || !image || !config.configured || (activeTab === 'query' && !question.trim())} onClick={() => void run()} className="w-full py-2.5 rounded bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}{busy ? 'İşleniyor…' : activeTab === 'query' ? 'Soruyu gönder' : activeTab === 'caption' ? 'Yüzeyi analiz et' : activeTab === 'detect' ? 'Özellikleri tespit et' : 'Görsel noktaları incele'}</button>
            <div aria-live="polite" aria-atomic="true">{error && <p role="alert" className="text-xs text-red-300 border border-red-500/40 bg-red-950/20 p-3 rounded flex gap-2"><AlertTriangle className="w-4 h-4 shrink-0" />{error}</p>}{notice && <p className="text-xs text-amber-300 border border-amber-500/30 p-3 rounded">{notice}</p>}</div>
            {!config.configured && <p className="text-xs text-amber-300">Sunucuda NVIDIA_API_KEY yapılandırılmamış. Anahtar yalnızca sunucunun .env dosyasına eklenir.</p>}
            {activeTab === 'query' ? messages.map((message, index) => <div key={index} className="p-3 rounded bg-space-950 border border-slate-800 text-xs leading-relaxed whitespace-pre-wrap"><span className="text-purple-300 block font-semibold mb-1">{message.role}</span>{message.text}</div>) : result && <>
              <p className="text-xs text-slate-200 leading-relaxed">{result.summary}</p>
              {result.observations.map((observation, index) => <div key={index} className="p-3 rounded border border-slate-700 bg-space-950 text-xs leading-relaxed"><p className="text-sky-300 mb-1">{index + 1}. {observation.feature} · {certainty[observation.certainty]}</p><p>{observation.description}</p>{observation.evidence && <p className="text-slate-400 mt-1">Dayanak: {observation.evidence}</p>}{observation.locationInImage && <p className="text-slate-400 mt-1">Konum: {observation.locationInImage}</p>}</div>)}
              {result.terrainInterpretation && <p className="text-xs leading-relaxed">{result.terrainInterpretation}</p>}
              {[...result.potentialHazards, ...result.limitations, ...(analysis?.conflicts || [])].map((text, index) => <p key={index} className="text-[11px] leading-relaxed text-amber-200 border-l-2 border-amber-600 pl-2">{text}</p>)}
              <details className="text-xs border border-slate-700 p-3 rounded"><summary className="cursor-pointer text-sky-300">Kayıtlı bilimsel ölçümler · K2/K3</summary><p className="text-[10px] text-slate-400 my-2">Nominal bölge özeti; seçili UTC anının veya sanal yamanın yeni hesabı değildir.</p><dl className="grid grid-cols-2 gap-2 mt-2">{Object.entries({ 'Ufuk ortalaması (°)': analysis!.scientificAnalysis.horizon_mean_deg, 'En yüksek ufuk (°)': analysis!.scientificAnalysis.horizon_max_deg, 'Ortak görünürlük oranı': analysis!.scientificAnalysis.joint_visible_fraction, 'En uzun ortak pencere (sa)': analysis!.scientificAnalysis.longest_joint_window_hours }).map(([name, value]) => <React.Fragment key={name}><dt className="text-slate-400">{name}</dt><dd>{value === null ? 'Ölçüm yok' : value}</dd></React.Fragment>)}</dl></details>
              <p className="text-[10px] text-slate-500">{analysis!.metadata.timestamp} · {analysis!.metadata.status}</p>
              <button onClick={downloadJSON} className={button}><Download className="w-3.5 h-3.5" />Analiz JSON indir</button>
            </>}
            <p className="text-[10px] text-slate-500 mt-auto pt-3 border-t border-slate-800 break-words">Model: {config.model || 'Sunucu bağlantısı bekleniyor'}<br />{analysis?.metadata.inferenceExecuted ? 'Gerçek model yanıtı alındı.' : 'Görüntüyü hazırlamak modeli çağırmaz.'}</p>
          </div>
        </div>
      </div>
    </div>
  );
};
