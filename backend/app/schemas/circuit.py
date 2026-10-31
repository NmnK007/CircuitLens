"""CircuitLens Typed Circuit and Simulation Schemas.

Strict Pydantic v2 schemas for components, terminals, nodes,
SI units, and simulation configurations.
"""

from enum import Enum
import math
import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class ComponentType(str, Enum):
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    VOLTAGE_SOURCE_DC = "voltage_source_dc"
    GROUND = "ground"
    WIRE = "wire"


class AnalysisType(str, Enum):
    TRANSIENT = "transient"
    OP = "op"


class SIValue(BaseModel):
    """Magnitude with an explicit SI unit."""
    magnitude: float = Field(..., description="Numerical value in base SI units or explicit prefix")
    unit: str = Field(..., description="SI unit symbol, e.g. ohm, F, V, s")

    @field_validator("magnitude")
    @classmethod
    def finite_magnitude(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Magnitude must be a finite number")
        return v

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Unit cannot be empty")
        return v


class Component(BaseModel):
    """Electrical component representation."""
    id: str = Field(..., description="Unique component identifier, e.g., R1, C1, V1")
    type: ComponentType = Field(..., description="Supported component class")
    name: Optional[str] = Field(None, description="Optional human-readable label")
    value: SIValue = Field(..., description="Electrical value with SI unit")
    terminals: List[str] = Field(..., min_length=2, max_length=2, description="List of connected node names [term+, term-]")
    initial_voltage: Optional[float] = Field(0.0, description="Initial voltage for capacitor across terminals (V)")
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Detection confidence score from 0.0 to 1.0")
    is_uncertain: bool = Field(False, description="Whether human confirmation is requested")
    uncertainty_reason: Optional[str] = Field(None, description="Reason if marked uncertain")
    bounding_box: Optional[List[int]] = Field(None, description="[x, y, width, height] in image pixels")

    @model_validator(mode="after")
    def spice_safe_fields(self) -> "Component":
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", self.id):
            raise ValueError("Component id must contain only letters, numbers and underscores and start with a letter")
        expected_prefix = {
            ComponentType.RESISTOR: "R",
            ComponentType.CAPACITOR: "C",
            ComponentType.VOLTAGE_SOURCE_DC: "V",
            ComponentType.WIRE: "W",
            ComponentType.GROUND: "G",
        }[self.type]
        if self.id[0].upper() != expected_prefix:
            raise ValueError(f"{self.type.value} component id must start with '{expected_prefix}'")
        for node in self.terminals:
            if not re.fullmatch(r"(?:0|[A-Za-z_][A-Za-z0-9_]{0,31})", node):
                raise ValueError("Node names must be 0 or use only letters, numbers and underscores")
        expected_unit = {
            ComponentType.RESISTOR: {"ohm", "Ω"},
            ComponentType.CAPACITOR: {"F", "farad"},
            ComponentType.VOLTAGE_SOURCE_DC: {"V", "volt"},
            ComponentType.WIRE: {"ohm", "Ω"},
            ComponentType.GROUND: {"ohm", "Ω"},
        }[self.type]
        if self.value.unit not in expected_unit:
            raise ValueError(f"{self.type.value} value must use one of these units: {', '.join(sorted(expected_unit))}")
        return self

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Component id cannot be empty")
        return v

    @field_validator("terminals")
    @classmethod
    def validate_terminals(cls, v: List[str]) -> List[str]:
        cleaned = [t.strip() for t in v]
        for t in cleaned:
            if not t:
                raise ValueError("Terminal node identifier cannot be empty")
        return cleaned


class SimulationConfig(BaseModel):
    """Circuit simulation parameters."""
    type: AnalysisType = Field(AnalysisType.TRANSIENT, description="Analysis type (transient, op)")
    step_seconds: float = Field(1e-5, gt=0, description="Transient print/sampling step in seconds")
    stop_seconds: float = Field(0.05, gt=0, description="Transient stop time in seconds")

    @model_validator(mode="after")
    def validate_times(self) -> "SimulationConfig":
        if self.type == AnalysisType.TRANSIENT:
            if self.stop_seconds <= self.step_seconds:
                raise ValueError("stop_seconds must be greater than step_seconds")
        return self


class CircuitModel(BaseModel):
    """Complete structured circuit representation."""
    schema_version: str = Field("1.0", description="Schema version")
    name: Optional[str] = Field("Circuit", description="Circuit name")
    description: Optional[str] = Field("", description="Optional circuit description")
    analysis: AnalysisType = Field(AnalysisType.TRANSIENT, description="Target simulation analysis")
    ground_node: str = Field("0", description="Reference ground node identifier (usually '0')")
    components: List[Component] = Field(..., min_length=1, description="List of electrical components")
    simulation: SimulationConfig = Field(default_factory=SimulationConfig, description="Simulation parameters")
    ambiguities: List[str] = Field(default_factory=list, description="List of detected ambiguities or user flags")
    source_image_name: Optional[str] = Field(None, description="Optional associated source image file name")

    @model_validator(mode="after")
    def safe_netlist_metadata(self) -> "CircuitModel":
        if not re.fullmatch(r"[A-Za-z0-9 _.,()\-+/×Ωμ=]{1,96}", self.name or "Circuit"):
            raise ValueError("Circuit name must be a short printable label without control characters")
        if not re.fullmatch(r"(?:0|[A-Za-z_][A-Za-z0-9_]{0,31})", self.ground_node):
            raise ValueError("Ground node must be 0 or use only letters, numbers and underscores")
        return self

    @field_validator("ground_node")
    @classmethod
    def clean_ground(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return "0"
        return v


class ValidationResult(BaseModel):
    """Result of validating a circuit against electrical rules."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    normalized_circuit: Optional[CircuitModel] = None
