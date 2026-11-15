import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn('ErrorBoundary yakaladı:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full min-h-[300px] flex flex-col items-center justify-center p-6 bg-gmat-panel border border-gmat-border rounded-lg text-gmat-textMuted text-center select-none">
          <AlertTriangle className="w-10 h-10 text-gmat-amber mb-3" />
          <h3 className="text-base font-semibold text-gmat-text mb-1 font-sans">
            {this.props.fallbackTitle || 'Görsel Bileşen Yüklenemedi (WebGL Fallback)'}
          </h3>
          <p className="text-xs text-gmat-textMuted max-w-md mb-4 font-mono">
            Tarayıcınızda WebGL donanım hızlandırma kapalı olabilir veya bir render hatası oluştu.
            Analiz paneli, zaman çizelgesi ve telemetri tam işlevsel kalmaya devam etmektedir.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-gmat-elevated hover:bg-gmat-border border border-gmat-border rounded transition-colors text-gmat-text"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Yeniden Dene
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
