"""Validated contracts for Gemma assisted image review and explanations."""

import math
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from .circuit import ComponentType, CircuitModel


class ImageCandidate(BaseModel):
    id: str = Field(..., min_length=1, max_length=32)
    type: ComponentType
    value_text: Optional[str] = None
    value_magnitude: Optional[float] = None
    value_unit: Optional[str] = None
    terminal_candidates: List[str] = Field(default_factory=list, max_length=2)
    bounding_box: Optional[List[float]] = Field(None, min_length=4, max_length=4)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    visual_evidence: str = Field("", max_length=500)

    @field_validator("id")
    @classmethod
    def safe_candidate_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", value):
            raise ValueError("Candidate id must be a safe component label")
        return value

    @field_validator("value_magnitude")
    @classmethod
    def finite_value(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not math.isfinite(value):
            raise ValueError("Candidate value must be finite")
        return value

    @field_validator("bounding_box")
    @classmethod
    def validate_box(cls, box: Optional[List[float]]) -> Optional[List[float]]:
        if box is not None and (any(v < 0 or v > 1 for v in box) or box[2] <= box[0] or box[3] <= box[1]):
            raise ValueError("bounding_box coordinates must be normalized [left, top, right, bottom]")
        return box

    @model_validator(mode="after")
    def value_has_unit(self) -> "ImageCandidate":
        if self.value_magnitude is not None and not self.value_unit:
            raise ValueError("A numeric candidate value requires an explicit unit")
        return self


class ImageAnalysisResult(BaseModel):
    status: str = "review_required"
    provider: str
    model: str
    image_width: int
    image_height: int
    components: List[ImageCandidate] = Field(default_factory=list)
    observed_text: List[str] = Field(default_factory=list)
    line_segments: List[List[float]] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    unsupported_symbols: List[str] = Field(default_factory=list)
    message: str


class ExplainRequest(BaseModel):
    circuit: CircuitModel
    user_question: Optional[str] = Field(None, max_length=1000)


class GroundedExplanation(BaseModel):
    status: str = "success"
    circuit_summary: str
    physics_explanation: str
    measured_facts: List[str] = Field(default_factory=list)
    theoretical_calculations: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    hypotheses: List[str] = Field(default_factory=list)
    troubleshooting_notes: List[str] = Field(default_factory=list)
    suggested_experiments: List[str] = Field(default_factory=list)
    model_used: str
    provider: str
