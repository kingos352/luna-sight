import React from 'react';
import { MissionComparisonView } from './MissionComparisonView';
import { X, Scale, FileText, Maximize2 } from 'lucide-react';

interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ComparisonModal: React.FC<ComparisonModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 select-none">
      <div className="w-full max-w-5xl max-h-[92vh] bg-gmat-panel border border-gmat-border rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="h-12 px-4 border-b border-gmat-border flex items-center justify-between bg-gmat-elevated">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-sky-950 border border-sky-500/50 flex items-center justify-center">
              <Scale className="w-4 h-4 text-gmat-accent" />
            </div>
            <div>
              <div className="text-sm font-bold text-gmat-text flex items-center gap-2">
                <span>Site01 vs Site04 Karşılaştırmalı Değerlendirme & Uçuş Kartları</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gmat-bg border border-gmat-border text-gmat-accent font-semibold">
                  SUHAIL Kriterleri
                </span>
              </div>
              <div className="text-[10px] text-gmat-textMuted font-mono">
                LUNA SIGHT Çoklu Kriter Karar Matrisi ve Taktik İniş Önerisi
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-gmat-bg text-gmat-textMuted hover:text-gmat-text border border-transparent hover:border-gmat-border transition-colors"
              title="Kapat"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-gmat-bg/60">
          <MissionComparisonView />
        </div>

        {/* Modal Footer */}
        <div className="h-10 px-4 border-t border-gmat-border flex items-center justify-between bg-gmat-elevated text-xs font-mono text-gmat-textMuted">
          <div>
            Standart: <span className="text-gmat-text">NASA GMAT / JPL Horizons DE441</span>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-gmat-elevated hover:bg-gmat-border text-gmat-text text-xs rounded border border-gmat-border transition-colors font-sans"
          >
            Tamam (Kapat)
          </button>
        </div>
      </div>
    </div>
  );
};
