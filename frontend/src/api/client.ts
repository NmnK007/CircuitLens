import {
  CircuitModel,
  ValidationResult,
  SimulationResult,
  ImageAnalysisResult,
  GroundedExplanation,
} from '../types/circuit';

const API_BASE = '/api';

export async function fetchHealth(): Promise<{
  status: string;
  service: string;
  version: string;
  ngspice_available: boolean;
  ngspice_path: string;
  gemma_provider: string;
  gemma_model: string;
  gemma_available: boolean;
}> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchSeededCircuit(): Promise<CircuitModel> {
  const res = await fetch(`${API_BASE}/circuits/seeded`);
  if (!res.ok) throw new Error(`Failed to load seeded circuit: ${res.statusText}`);
  return res.json();
}

export async function validateCircuit(circuit: CircuitModel): Promise<ValidationResult> {
  const res = await fetch(`${API_BASE}/circuits/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(circuit),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err?.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.errors?.join(' ') || `Validation endpoint error: ${res.statusText}`);
  }
  return res.json();
}

export async function simulateCircuit(
  circuit: CircuitModel,
  overrideR?: number,
  overrideC?: number
): Promise<SimulationResult> {
  const payload: any = { circuit };
  if (overrideR !== undefined) payload.override_r_magnitude = overrideR;
  if (overrideC !== undefined) payload.override_c_magnitude = overrideC;

  const res = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    const msg = errData?.detail?.message || errData?.detail || res.statusText;
    throw new Error(`Simulation failed: ${typeof msg === 'string' ? msg : JSON.stringify(msg)}`);
  }
  return res.json();
}

export async function analyzeImage(file: File): Promise<ImageAnalysisResult> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/analyze-image`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail || `Image analysis failed: ${res.statusText}`);
  }
  return res.json();
}

export async function explainSimulation(
  circuit: CircuitModel,
  simulationResult: SimulationResult,
  userQuestion?: string
): Promise<GroundedExplanation> {
  const res = await fetch(`${API_BASE}/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      circuit,
      user_question: userQuestion,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail || `AI explanation error: ${res.statusText}`);
  }
  return res.json();
}
