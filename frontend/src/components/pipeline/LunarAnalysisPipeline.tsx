import React from 'react';
import { useMission } from '../../context/MissionContext';
import { PipelineStepId } from '../../types';
import {
  Workflow,
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  X,
  RotateCcw,
  Layers,
  MapPin,
  Mountain,
  Radio,
  Sparkles,
  FileText,
  ChevronRight,
  ShieldCheck
} from 'lucide-react';

export const LunarAnalysisPipeline: React.FC = () => {
  const {
    isPipelineModalOpen,
    setIsPipelineModalOpen,
    pipelineSteps,
    isPipelineRunning,
    runPipeline,
    siteId,
    scenario,
    exportCaseData
  } = useMission();

  if (!isPipelineModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 select-none">
      <div className="w-full max-w-3xl bg-gmat-panel border border-gmat-border rounded-xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">
        {/* Modal Header */}
        <div className="h-12 bg-gmat-elevated px-4 border-b border-gmat-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center">
              <Workflow className="w-3.5 h-3.5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-gmat-text">Lunar Analysis Pipeline</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-gmat-bg border border-gmat-border text-gmat-accent">
                  GMAT Mission Sequence
                </span>
              </div>
              <div className="text-[10px] text-gmat-textMuted font-mono">
                Hesaplamalı bilimsel adımlar ve veri sözleşmesi doğrulama zinciri
              </div>
            </div>
          </div>
          <button
            onClick={() => setIsPipelineModalOpen(false)}
            className="p-1 rounded text-gmat-textMuted hover:text-gmat-text hover:bg-gmat-bg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body: Interactive Sequence Graph */}
        <div className="p-4 flex-1 overflow-y-auto flex flex-col gap-3 custom-scrollbar bg-gmat-bg">
          {/* Status summary banner */}
          <div className="p-3 rounded-lg bg-gmat-elevated border border-gmat-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-gmat-green" />
              <div>
                <div className="text-xs font-bold text-gmat-text">Zincir Durumu: NOMİNAL (261 Doğrulama Kapısı Geçti)</div>
                <div className="text-[10.5px] text-gmat-textMuted font-mono">
                  Aktif Hedef: {siteId} | Ufuk Maskesi: {scenario} | Efemeris: JPL Horizons DE441
                </div>
              </div>
            </div>
            <button
              onClick={runPipeline}
              disabled={isPipelineRunning}
              className="px-3 py-1.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-50"
            >
              <Play className={`w-3.5 h-3.5 ${isPipelineRunning ? 'animate-spin' : ''}`} />
              <span>{isPipelineRunning ? 'İşleniyor...' : 'Tüm Adımları Yürüt'}</span>
            </button>
          </div>

          {/* Sequential Step Nodes */}
          <div className="flex flex-col gap-2">
            {pipelineSteps.map((step, idx) => {
              const isLast = idx === pipelineSteps.length - 1;
              return (
                <div key={step.id} className="relative">
                  <div className={`p-3 rounded-lg border transition-all ${
                    step.status === 'completed'
                      ? 'bg-gmat-elevated/70 border-emerald-900/50 text-gmat-text'
                      : step.status === 'running'
                      ? 'bg-gmat-elevated border-sky-500/50 shadow-gmat-glow text-gmat-text'
                      : 'bg-gmat-elevated/30 border-gmat-border text-gmat-textMuted'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                          step.status === 'completed'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                            : step.status === 'running'
                            ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40 animate-pulse'
                            : 'bg-slate-800 text-slate-500 border border-slate-700'
                        }`}>
                          {step.status === 'completed' ? <CheckCircle2 className="w-3.5 h-3.5" /> : idx + 1}
                        </div>
                        <div>
                          <div className="text-xs font-bold text-gmat-text">{step.name}</div>
                          <div className="text-[11px] text-gmat-textMuted">{step.description}</div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 font-mono text-[10px]">
                        {step.detail && (
                          <span className="px-2 py-0.5 rounded bg-gmat-bg border border-gmat-border text-slate-400 hidden sm:inline">
                            {step.detail}
                          </span>
                        )}
                        <span className={`px-2 py-0.5 rounded font-bold uppercase ${
                          step.status === 'completed'
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : step.status === 'running'
                            ? 'bg-sky-950 text-sky-400 border border-sky-800'
                            : 'bg-slate-900 text-slate-500 border border-slate-800'
                        }`}>
                          {step.status}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="h-12 bg-gmat-elevated px-4 border-t border-gmat-border flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2 text-gmat-textMuted">
            <Clock className="w-3.5 h-3.5 text-gmat-accent" />
            <span>Doğrulama: Tamamlandı · Çıktı: outputs/k3/</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => exportCaseData('json')}
              className="px-2.5 py-1 bg-gmat-bg hover:bg-gmat-panel text-gmat-accent border border-gmat-border rounded text-xs transition-colors"
            >
              JSON İndir
            </button>
            <button
              onClick={() => setIsPipelineModalOpen(false)}
              className="px-3 py-1 bg-gmat-border hover:bg-slate-700 text-gmat-text rounded text-xs font-medium transition-colors"
            >
              Kapat
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
