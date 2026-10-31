"""CircuitLens Simulation Request and Result Schemas."""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from .circuit import AnalysisType, CircuitModel
from ..services.theory_oracle import TheoryVerificationResult


class WaveformTrace(BaseModel):
    """A single waveform curve (e.g. node voltage or branch current over time)."""
    name: str = Field(..., description="Vector identifier, e.g. v(out), v(in), i(V1)")
    unit: str = Field(..., description="Measurement unit (V, A, s)")
    x: List[float] = Field(..., description="Time values (seconds)")
    y: List[float] = Field(..., description="Magnitude values")


class SimulationRequest(BaseModel):
    """Request payload to simulate a circuit."""
    circuit: CircuitModel = Field(..., description="Validated circuit to simulate")
    override_r_magnitude: Optional[float] = Field(None, description="Optional override for resistor value (e.g. 5000)")
    override_c_magnitude: Optional[float] = Field(None, description="Optional override for capacitor value")


class SimulationResult(BaseModel):
    """Real simulation execution outputs parsed from ngspice."""
    status: str = Field("success", description="Status ('success', 'error', 'unavailable')")
    analysis_type: AnalysisType = Field(AnalysisType.TRANSIENT, description="Executed analysis type")
    netlist: str = Field(..., description="Exact generated SPICE netlist")
    raw_output: str = Field("", description="Raw simulator stdout and stderr")
    traces: List[WaveformTrace] = Field(default_factory=list, description="Extracted waveform traces")
    operating_point: Dict[str, float] = Field(default_factory=dict, description="DC operating point node voltages and currents")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Numerical milestones and metrics")
    theory_verification: Optional[TheoryVerificationResult] = Field(None, description="Analytical RC theory comparison")
    execution_time_ms: float = Field(0.0, description="Process execution duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Error explanation if status != 'success'")
