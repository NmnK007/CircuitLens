import React from 'react';
import { Cpu, Zap, Activity, AlertCircle, RefreshCw } from 'lucide-react';

interface NavbarProps {
  ngspiceAvailable: boolean;
  gemmaProvider: string;
  gemmaModel: string;
  onResetSeeded: () => void;
  isLoading: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  ngspiceAvailable,
  gemmaProvider,
  gemmaModel,
  onResetSeeded,
  isLoading,
}) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Zap className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-bold tracking-tight text-white">CircuitLens</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-sky-950 text-sky-400 border border-sky-800 font-mono">
                Gemma 4 + ngspice
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Multimodal AI Electronics Assistant & Simulator
            </p>
          </div>
        </div>

        {/* Status Indicators & Controls */}
        <div className="flex items-center space-x-3">
          {/* Simulator Status */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              ngspiceAvailable
                ? 'bg-emerald-950/60 border-emerald-800 text-emerald-400'
                : 'bg-amber-950/60 border-amber-800 text-amber-400'
            }`}
            title={ngspiceAvailable ? 'ngspice simulator ready' : 'ngspice not detected in PATH'}
          >
            <Activity className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Simulator:</span>
            <span>{ngspiceAvailable ? 'ngspice Live' : 'ngspice Missing'}</span>
          </div>

          {/* AI Provider Status */}
          <div
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-indigo-950/60 border-indigo-800 text-indigo-300"
            title={`Gemma 4 Mode: ${gemmaProvider} (${gemmaModel})`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span className="hidden md:inline">AI Tutor:</span>
            <span>{gemmaProvider === 'google_ai' ? 'Gemma 4 Online' : 'Gemma 4 Seeded'}</span>
          </div>

          {/* Reset to Reference RC Showcase */}
          <button
            onClick={onResetSeeded}
            disabled={isLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition shadow-sm disabled:opacity-50"
            title="Load the 5V, 1kΩ, 10μF RC showcase circuit"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Reset Showcase</span>
          </button>
        </div>
      </div>

      {/* Educational Prototype Banner */}
      <div className="bg-slate-950 border-t border-slate-800/80 px-4 py-1 text-center text-[11px] text-slate-500 flex items-center justify-center space-x-2">
        <AlertCircle className="w-3 h-3 text-sky-400" />
        <span>
          Educational hackathon prototype — not a certified EDA safety tool. All simulations run deterministic ngspice code.
        </span>
      </div>
    </header>
  );
};
