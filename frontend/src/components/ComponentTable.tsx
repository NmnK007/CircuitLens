import React from 'react';
import { Component } from '../types/circuit';
import { AlertTriangle, CheckCircle, Edit3 } from 'lucide-react';

function formatValue(magnitude: number, unit: string): string {
  const u = unit.toLowerCase();
  let symbol = u === 'ohm' ? 'Ω' : u === 'f' ? 'F' : u === 'v' ? 'V' : u === 'a' ? 'A' : u === 's' ? 's' : unit;
  const abs = Math.abs(magnitude);
  if (abs === 0) return `0 ${symbol}`;
  if (abs >= 1e9) return `${(magnitude / 1e9).toPrecision(3)} G${symbol}`;
  if (abs >= 1e6) return `${(magnitude / 1e6).toPrecision(3)} M${symbol}`;
  if (abs >= 1e3) return `${(magnitude / 1e3).toPrecision(3)} k${symbol}`;
  if (abs >= 1) return `${magnitude.toPrecision(4)} ${symbol}`;
  if (abs >= 1e-3) return `${(magnitude * 1e3).toPrecision(3)} m${symbol}`;
  if (abs >= 1e-6) return `${(magnitude * 1e6).toPrecision(3)} μ${symbol}`;
  if (abs >= 1e-9) return `${(magnitude * 1e9).toPrecision(3)} n${symbol}`;
  if (abs >= 1e-12) return `${(magnitude * 1e12).toPrecision(3)} p${symbol}`;
  return `${magnitude.toExponential(3)} ${symbol}`;
}

function componentIcon(type: string): string {
  switch (type) {
    case 'resistor': return '⟊';
    case 'capacitor': return '⊣⊢';
    case 'voltage_source_dc': return '⊕';
    default: return '?';
  }
}

function componentLabel(type: string): string {
  switch (type) {
    case 'resistor': return 'Resistor';
    case 'capacitor': return 'Capacitor';
    case 'voltage_source_dc': return 'DC Source';
    case 'ground': return 'Ground';
    case 'wire': return 'Wire';
    default: return type;
  }
}

function componentColors(type: string): string {
  switch (type) {
    case 'resistor': return 'bg-amber-950/40 border-amber-700/50 text-amber-300';
    case 'capacitor': return 'bg-sky-950/40 border-sky-700/50 text-sky-300';
    case 'voltage_source_dc': return 'bg-emerald-950/40 border-emerald-700/50 text-emerald-300';
    default: return 'bg-slate-800/40 border-slate-700 text-slate-300';
  }
}

interface EditableComponentRowProps {
  component: Component;
  onValueChange: (id: string, newMagnitude: number) => void;
}

const EditableComponentRow: React.FC<EditableComponentRowProps> = ({ component, onValueChange }) => {
  const [editing, setEditing] = React.useState(false);
  const [inputVal, setInputVal] = React.useState('');

  const startEdit = () => {
    setInputVal(String(component.value.magnitude));
    setEditing(true);
  };

  const commitEdit = () => {
    const parsed = parseFloat(inputVal);
    if (!isNaN(parsed) && parsed > 0) {
      onValueChange(component.id, parsed);
    }
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') commitEdit();
    if (e.key === 'Escape') setEditing(false);
  };

  return (
    <tr className={`border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors ${component.is_uncertain ? 'ring-1 ring-inset ring-amber-700/40' : ''}`}>
      {/* ID */}
      <td className="px-3 py-2.5 font-mono text-sm font-bold text-white whitespace-nowrap">{component.id}</td>

      {/* Type badge */}
      <td className="px-3 py-2.5">
        <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border font-medium ${componentColors(component.type)}`}>
          <span className="font-mono">{componentIcon(component.type)}</span>
          {componentLabel(component.type)}
        </span>
      </td>

      {/* Value - Editable */}
      <td className="px-3 py-2.5">
        {editing ? (
          <div className="flex items-center gap-1">
            <input
              autoFocus
              type="number"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={handleKeyDown}
              className="w-28 px-2 py-1 text-sm bg-slate-700 border border-sky-500 rounded text-white font-mono focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
            <span className="text-xs text-slate-400">{component.value.unit === 'ohm' ? 'Ω' : component.value.unit}</span>
          </div>
        ) : (
          <button
            onClick={startEdit}
            className="group flex items-center gap-1.5 hover:text-sky-300 transition-colors text-sm font-mono"
            title="Click to edit value"
          >
            <span className="text-slate-200">{formatValue(component.value.magnitude, component.value.unit)}</span>
            <Edit3 className="w-3 h-3 text-slate-500 group-hover:text-sky-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        )}
      </td>

      {/* Terminals */}
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-1">
          {component.terminals.map((t, i) => (
            <React.Fragment key={i}>
              <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-300 font-mono border border-slate-600">{t}</span>
              {i < component.terminals.length - 1 && (
                <span className="text-slate-600 text-xs">→</span>
              )}
            </React.Fragment>
          ))}
        </div>
      </td>

      {/* Confidence / Status */}
      <td className="px-3 py-2.5">
        {component.is_uncertain ? (
          <div className="flex items-center gap-1 text-amber-400 text-xs">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="truncate max-w-[120px]" title={component.uncertainty_reason || 'Uncertain'}>
              {component.uncertainty_reason || 'Uncertain — verify'}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-emerald-400 text-xs">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Confirmed</span>
            {component.confidence !== undefined && component.confidence < 1.0 && (
              <span className="text-slate-500">({Math.round(component.confidence * 100)}%)</span>
            )}
          </div>
        )}
      </td>
    </tr>
  );
};

interface ComponentTableProps {
  components: Component[];
  onValueChange: (id: string, newMagnitude: number) => void;
  ambiguities?: string[];
  warnings?: string[];
}

export const ComponentTable: React.FC<ComponentTableProps> = ({
  components,
  onValueChange,
  ambiguities = [],
  warnings = [],
}) => {
  return (
    <div className="flex flex-col gap-3">
      {/* Ambiguity Alerts */}
      {(ambiguities.length > 0 || warnings.length > 0) && (
        <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs font-semibold text-amber-300 mb-1">
                {ambiguities.length + warnings.length} issue(s) require your review
              </p>
              <ul className="text-xs text-amber-200/80 space-y-0.5">
                {[...ambiguities, ...warnings].map((a, i) => (
                  <li key={i} className="leading-snug">• {a}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-700/60">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-slate-800/80 border-b border-slate-700">
              <th className="px-3 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">ID</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">Type</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">Value <span className="text-sky-400 normal-case font-normal">(click to edit)</span></th>
              <th className="px-3 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">Nodes</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">Status</th>
            </tr>
          </thead>
          <tbody>
            {components.map((c) => (
              <EditableComponentRow key={c.id} component={c} onValueChange={onValueChange} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-500 flex items-center gap-1">
        <Edit3 className="w-3 h-3" />
        Click any value to edit it inline, then re-run the simulation.
      </p>
    </div>
  );
};
