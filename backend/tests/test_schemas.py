"""Unit Tests for CircuitLens Pydantic Schemas, Unit Conversions, and Circuit Validation."""

import json
from pathlib import Path
import pytest

from app.schemas.circuit import (
    CircuitModel,
    Component,
    ComponentType,
    SIValue,
    SimulationConfig,
    AnalysisType,
)
from app.services.circuit_validator import validate_circuit
from app.services.unit_converter import (
    parse_value_string,
    format_value,
    to_spice_value_str,
)


def get_seeded_rc_circuit_data() -> dict:
    json_path = Path(__file__).resolve().parent.parent.parent / "examples" / "rc_charging.json"
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_seeded_rc_circuit_schema_parsing():
    """Verify the reference RC circuit JSON parses cleanly into CircuitModel."""
    data = get_seeded_rc_circuit_data()
    circuit = CircuitModel.model_validate(data)

    assert circuit.schema_version == "1.0"
    assert circuit.ground_node == "0"
    assert len(circuit.components) == 3

    comp_ids = {c.id: c for c in circuit.components}
    assert "V1" in comp_ids
    assert "R1" in comp_ids
    assert "C1" in comp_ids

    assert comp_ids["V1"].type == ComponentType.VOLTAGE_SOURCE_DC
    assert comp_ids["V1"].value.magnitude == 5.0
    assert comp_ids["V1"].value.unit == "V"

    assert comp_ids["R1"].type == ComponentType.RESISTOR
    assert comp_ids["R1"].value.magnitude == 1000.0
    assert comp_ids["R1"].value.unit == "ohm"

    assert comp_ids["C1"].type == ComponentType.CAPACITOR
    assert comp_ids["C1"].value.magnitude == 0.00001
    assert comp_ids["C1"].value.unit == "F"

    assert circuit.simulation.type == AnalysisType.TRANSIENT
    assert circuit.simulation.step_seconds == 1e-5
    assert circuit.simulation.stop_seconds == 0.05


def test_validate_seeded_rc_circuit_passes():
    """Seeded RC circuit must pass electrical validation with zero errors."""
    data = get_seeded_rc_circuit_data()
    circuit = CircuitModel.model_validate(data)
    result = validate_circuit(circuit)

    assert result.valid is True
    assert len(result.errors) == 0
    assert result.normalized_circuit is not None
    assert result.normalized_circuit.ground_node == "0"


def test_validate_missing_ground_rejected():
    """A circuit with no connection to ground node must fail validation."""
    circuit = CircuitModel(
        components=[
            Component(
                id="V1",
                type=ComponentType.VOLTAGE_SOURCE_DC,
                value=SIValue(magnitude=5.0, unit="V"),
                terminals=["N1", "N2"],
            ),
            Component(
                id="R1",
                type=ComponentType.RESISTOR,
                value=SIValue(magnitude=1000.0, unit="ohm"),
                terminals=["N1", "N2"],
            ),
        ],
        ground_node="0",
        simulation=SimulationConfig(type=AnalysisType.TRANSIENT, step_seconds=1e-5, stop_seconds=0.01),
    )
    result = validate_circuit(circuit)
    assert result.valid is False
    assert any("ground" in err.lower() for err in result.errors)


def test_validate_non_positive_resistor_rejected():
    """Resistor with 0 or negative resistance must be rejected."""
    circuit = CircuitModel(
        components=[
            Component(
                id="R1",
                type=ComponentType.RESISTOR,
                value=SIValue(magnitude=0.0, unit="ohm"),
                terminals=["in", "0"],
            ),
            Component(
                id="V1",
                type=ComponentType.VOLTAGE_SOURCE_DC,
                value=SIValue(magnitude=5.0, unit="V"),
                terminals=["in", "0"],
            ),
        ],
        ground_node="0",
        simulation=SimulationConfig(type=AnalysisType.TRANSIENT, step_seconds=1e-5, stop_seconds=0.01),
    )
    result = validate_circuit(circuit)
    assert result.valid is False
    assert any("positive" in err.lower() for err in result.errors)


def test_validate_self_loop_short_rejected():
    """A component connected to the same node on both terminals must be rejected."""
    circuit = CircuitModel(
        components=[
            Component(
                id="R1",
                type=ComponentType.RESISTOR,
                value=SIValue(magnitude=100.0, unit="ohm"),
                terminals=["N1", "N1"],
            ),
            Component(
                id="V1",
                type=ComponentType.VOLTAGE_SOURCE_DC,
                value=SIValue(magnitude=5.0, unit="V"),
                terminals=["N1", "0"],
            ),
        ],
        ground_node="0",
        simulation=SimulationConfig(type=AnalysisType.TRANSIENT, step_seconds=1e-5, stop_seconds=0.01),
    )
    result = validate_circuit(circuit)
    assert result.valid is False
    assert any("short circuit self-loop" in err.lower() for err in result.errors)


def test_validate_parallel_voltage_sources_conflict():
    """Two different ideal voltage sources in parallel between same nodes must fail KVL."""
    circuit = CircuitModel(
        components=[
            Component(
                id="V1",
                type=ComponentType.VOLTAGE_SOURCE_DC,
                value=SIValue(magnitude=5.0, unit="V"),
                terminals=["N1", "0"],
            ),
            Component(
                id="V2",
                type=ComponentType.VOLTAGE_SOURCE_DC,
                value=SIValue(magnitude=10.0, unit="V"),
                terminals=["N1", "0"],
            ),
        ],
        ground_node="0",
        simulation=SimulationConfig(type=AnalysisType.TRANSIENT, step_seconds=1e-5, stop_seconds=0.01),
    )
    result = validate_circuit(circuit)
    assert result.valid is False
    assert any("parallel" in err.lower() for err in result.errors)


def test_validate_floating_node_generates_warning():
    """A dangling node connected to only 1 terminal must emit a warning."""
    data = get_seeded_rc_circuit_data()
    # Add a dangling resistor connected to 'out' and an unused node 'floating_node'
    data["components"].append({
        "id": "R2",
        "type": "resistor",
        "value": {"magnitude": 10000.0, "unit": "ohm"},
        "terminals": ["out", "floating_node"],
        "confidence": 1.0,
        "is_uncertain": False,
    })
    circuit = CircuitModel.model_validate(data)
    result = validate_circuit(circuit)

    # Circuit may still be valid to simulate, but must flag the dangling terminal
    assert any("floating_node" in w for w in result.warnings)


def test_unit_converter_parsing():
    """Test standard electronics values and prefixes."""
    # Resistors
    assert parse_value_string("1k", default_unit="ohm").magnitude == 1000.0
    assert parse_value_string("1kΩ").magnitude == 1000.0
    assert parse_value_string("4.7k ohm").magnitude == 4700.0
    assert parse_value_string("4k7", default_unit="ohm").magnitude == 4700.0
    assert parse_value_string("100R").magnitude == 100.0
    assert parse_value_string("1meg", default_unit="ohm").magnitude == 1e6
    assert parse_value_string("2.2MΩ").magnitude == 2.2e6

    # Capacitors
    assert parse_value_string("10uF").magnitude == 1e-5
    assert parse_value_string("10μF").magnitude == 1e-5
    assert parse_value_string("100n", default_unit="F").magnitude == 1e-7
    assert parse_value_string("47pF").magnitude == 4.7e-11

    # Voltage
    assert parse_value_string("5V").magnitude == 5.0
    assert parse_value_string("500mV").magnitude == 0.5
    assert parse_value_string("3.3 V").magnitude == 3.3

    # Time
    assert parse_value_string("10ms").magnitude == 0.01
    assert parse_value_string("50m", default_unit="s").magnitude == 0.05
    assert parse_value_string("10us").magnitude == 1e-5


def test_unit_converter_formatting():
    """Test human readable engineering display formatting."""
    assert "1 kΩ" in format_value(SIValue(magnitude=1000.0, unit="ohm"))
    assert "10 μF" in format_value(SIValue(magnitude=1e-5, unit="F"))
    assert "5 V" in format_value(SIValue(magnitude=5.0, unit="V"))
    assert "10 ms" in format_value(SIValue(magnitude=0.01, unit="s"))
    assert "500 mV" in format_value(SIValue(magnitude=0.5, unit="V"))


def test_to_spice_value_str():
    """Test SPICE scale string conventions."""
    assert to_spice_value_str(SIValue(magnitude=1000.0, unit="ohm")) == "1k"
    assert to_spice_value_str(SIValue(magnitude=1e6, unit="ohm")) == "1meg"
    assert to_spice_value_str(SIValue(magnitude=1e-5, unit="F")) == "10u"
    assert to_spice_value_str(SIValue(magnitude=1e-9, unit="F")) == "1n"
    assert to_spice_value_str(SIValue(magnitude=5.0, unit="V")) == "5"


def test_schema_rejects_spice_injection_tokens():
    data = get_seeded_rc_circuit_data()
    data["components"][0]["terminals"][0] = "in\n.end"
    with pytest.raises(ValueError):
        CircuitModel.model_validate(data)


def test_schema_rejects_non_finite_values_and_wrong_units():
    data = get_seeded_rc_circuit_data()
    data["components"][1]["value"]["magnitude"] = float("inf")
    with pytest.raises(ValueError):
        CircuitModel.model_validate(data)
    data = get_seeded_rc_circuit_data()
    data["components"][1]["value"]["unit"] = "V"
    with pytest.raises(ValueError):
        CircuitModel.model_validate(data)
