"""API Tests for CircuitLens Backend Endpoints."""

import pytest
from fastapi import HTTPException
from app.main import health_check, get_seeded_rc_circuit, validate_circuit_endpoint, simulate_circuit_endpoint, explain_endpoint
from app.schemas.circuit import CircuitModel, Component, ComponentType, SIValue, SimulationConfig, AnalysisType
from app.schemas.simulation import SimulationRequest
from app.schemas.ai import ExplainRequest


def test_health_check_endpoint():
    """Verify health endpoint returns valid status and metadata."""
    data = health_check()
    assert data["status"] == "healthy"
    assert data["service"] == "CircuitLens"
    assert "ngspice_available" in data
    assert "gemma_provider" in data
    assert "gemma_model" in data


def test_seeded_circuit_endpoint():
    """Verify get_seeded_rc_circuit loads the valid showcase RC circuit."""
    circuit = get_seeded_rc_circuit()
    assert circuit.schema_version == "1.0"
    assert len(circuit.components) == 3
    comp_types = [c.type for c in circuit.components]
    assert ComponentType.RESISTOR in comp_types
    assert ComponentType.CAPACITOR in comp_types
    assert ComponentType.VOLTAGE_SOURCE_DC in comp_types


def test_validate_circuit_endpoint_valid():
    """Verify validate_circuit_endpoint succeeds on valid circuit."""
    circuit = get_seeded_rc_circuit()
    result = validate_circuit_endpoint(circuit)
    assert result.valid is True
    assert len(result.errors) == 0
    assert result.normalized_circuit is not None
    assert result.normalized_circuit.ground_node == "0"


def test_validate_circuit_endpoint_invalid_short():
    """Verify validate_circuit_endpoint flags errors for short circuits."""
    invalid_circuit = CircuitModel(
        schema_version="1.0",
        analysis=AnalysisType.TRANSIENT,
        ground_node="0",
        components=[
            Component(
                id="R1",
                type=ComponentType.RESISTOR,
                value=SIValue(magnitude=100.0, unit="ohm"),
                terminals=["0", "0"],
            )
        ],
        simulation=SimulationConfig(type=AnalysisType.TRANSIENT, step_seconds=1e-5, stop_seconds=0.01),
    )
    result = validate_circuit_endpoint(invalid_circuit)
    assert result.valid is False
    assert any("self-loop" in e for e in result.errors)


def test_simulation_refuses_unconfirmed_image_candidates():
    circuit = get_seeded_rc_circuit()
    components = [c.model_copy(update={"is_uncertain": True}) if c.id == "R1" else c for c in circuit.components]
    uncertain = circuit.model_copy(update={"components": components})
    with pytest.raises(HTTPException) as exc:
        simulate_circuit_endpoint(SimulationRequest(circuit=uncertain))
    assert exc.value.status_code == 409


def test_explanation_requires_confirmed_components():
    circuit = get_seeded_rc_circuit()
    uncertain = circuit.model_copy(update={"ambiguities": ["crossing unclear"]})
    with pytest.raises(HTTPException) as exc:
        explain_endpoint(ExplainRequest(circuit=uncertain))
    assert exc.value.status_code == 409


