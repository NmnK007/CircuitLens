export type ComponentType = 'resistor' | 'capacitor' | 'voltage_source_dc' | 'ground' | 'wire';

export type AnalysisType = 'transient' | 'op';

export interface SIValue {
  magnitude: number;
  unit: string;
}

export interface Component {
  id: string;
  type: ComponentType;
  name?: string;
  value: SIValue;
  terminals: string[];
  initial_voltage?: number;
  confidence?: number;
  is_uncertain?: boolean;
  uncertainty_reason?: string;
  bounding_box?: number[];
}

export interface SimulationConfig {
  type: AnalysisType;
  step_seconds: number;
  stop_seconds: number;
}

export interface CircuitModel {
  schema_version: string;
  name?: string;
  description?: string;
  analysis: AnalysisType;
  ground_node: string;
  components: Component[];
  simulation: SimulationConfig;
  ambiguities: string[];
  source_image_name?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  normalized_circuit?: CircuitModel;
}

export interface WaveformTrace {
  name: string;
  unit: string;
  x: number[];
  y: number[];
}

export interface TheoryVerificationResult {
  verified: boolean;
  is_rc: boolean;
  theory?: {
    is_rc_circuit: boolean;
    vs?: number;
    r?: number;
    c?: number;
    tau_seconds?: number;
    tau_ms?: number;
    v_at_tau?: number;
    v_at_5tau?: number;
    formula?: string;
  };
  simulated_v_at_tau?: number;
  expected_v_at_tau?: number;
  error_at_tau_volts?: number;
  simulated_v_at_5tau?: number;
  expected_v_at_5tau?: number;
  error_at_5tau_volts?: number;
  max_relative_error_percent?: number;
  tolerance_percent: number;
  passed_tolerance: boolean;
  explanation: string;
}

export interface SimulationResult {
  status: 'success' | 'error' | 'unavailable';
  analysis_type: AnalysisType;
  netlist: string;
  raw_output: string;
  traces: WaveformTrace[];
  operating_point: Record<string, number>;
  summary: {
    initial_voltage?: number;
    final_voltage?: number;
    peak_voltage?: number;
    min_voltage?: number;
    monitored_node?: string;
    num_time_points?: number;
    total_duration_ms?: number;
    simulated_tau_ms?: number;
    simulated_settling_time_ms?: number;
  };
  theory_verification?: TheoryVerificationResult;
  execution_time_ms: number;
  error_message?: string;
}

export interface AIExplanationResponse {
  status: string;
  circuit_summary: string;
  physics_explanation: string;
  milestones: {
    tau_formula: string;
    tau_value_ms: number;
    v_at_tau: number;
    v_at_5tau: number;
    charging_formula: string;
  };
  facts_vs_hypotheses: {
    measured_facts: string[];
    theoretical_calculations: string[];
    assumptions: string[];
    hypotheses: string[];
  };
  troubleshooting_notes: string[];
  suggested_experiments: string[];
  model_used: string;
  is_fallback: boolean;
}

export interface ImageCandidate {
  id: string;
  type: ComponentType;
  value_text?: string | null;
  value_magnitude?: number | null;
  value_unit?: string | null;
  terminal_candidates: string[];
  bounding_box?: number[] | null;
  confidence: number;
  visual_evidence: string;
}

export interface ImageAnalysisResult {
  status: string;
  provider: string;
  model: string;
  image_width: number;
  image_height: number;
  components: ImageCandidate[];
  observed_text: string[];
  line_segments: number[][];
  ambiguities: string[];
  unsupported_symbols: string[];
  message: string;
}

export interface GroundedExplanation {
  status: string;
  circuit_summary: string;
  physics_explanation: string;
  measured_facts: string[];
  theoretical_calculations: string[];
  assumptions: string[];
  hypotheses: string[];
  troubleshooting_notes: string[];
  suggested_experiments: string[];
  model_used: string;
  provider: string;
}
