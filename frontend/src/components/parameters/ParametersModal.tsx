import React from 'react';
import { MissionParametersView } from './MissionParametersView';
import { X, SlidersHorizontal } from 'lucide-react';

interface ParametersModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ParametersModal: React.FC<ParametersModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 select-none">
      <div className="w-full max-w-lg bg-gmat-panel border border-gmat-border rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="h-12 px-4 border-b border-gmat-border flex items-center justify-between bg-gmat-elevated">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-sky-950 border border-sky-500/50 flex items-center justify-center">
              <SlidersHorizontal className="w-4 h-4 text-gmat-accent" />
            </div>
            <div>
              <div className="text-sm font-bold text-gmat-text flex items-center gap-2">
                <span>Görev Parametreleri & SUHAIL Kısıtları</span>
              </div>
              <div className="text-[10px] text-gmat-textMuted font-mono">
                Hesaplama motoru zaman penceresi ve operasyonel kabul kriterleri
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gmat-bg text-gmat-textMuted hover:text-gmat-text border border-transparent hover:border-gmat-border transition-colors"
            title="Kapat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-gmat-bg/60">
          <MissionParametersView />
        </div>

        {/* Modal Footer */}
        <div className="h-10 px-4 border-t border-gmat-border flex items-center justify-end bg-gmat-elevated">
          <button
            onClick={onClose}
            className="px-3 py-1 bg-gmat-accent hover:bg-sky-400 text-slate-950 font-bold text-xs rounded transition-colors"
          >
            Parametreleri Uygula
          </button>
        </div>
      </div>
    </div>
  );
};
