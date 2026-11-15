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
        <div className="w-full h-full min-h-[300px] flex flex-col items-center justify-center p-6 bg-space-900 border border-slate-800 rounded-lg text-slate-300 text-center">
          <AlertTriangle className="w-10 h-10 text-amber-500 mb-3" />
          <h3 className="text-base font-semibold text-slate-100 mb-1">
            {this.props.fallbackTitle || 'Görsel Bileşen Yüklenemedi (WebGL Fallback)'}
          </h3>
          <p className="text-xs text-slate-400 max-w-md mb-4">
            Tarayıcınızda WebGL donanım hızlandırma kapalı olabilir veya bir render hatası oluştu.
            Analiz paneli, zaman çizelgesi ve grafikler tam işlevsel kalmaya devam etmektedir.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-space-800 hover:bg-space-700 border border-slate-700 rounded transition-colors text-slate-200"
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
