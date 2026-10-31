"""CircuitLens Simulation and Netlist Integration Tests.

Verifies deterministic netlist generation, safe ngspice execution,
transient waveform parsing, and numerical verification against textbook equations.
"""

import pytest
from app.schemas.circuit import (
    CircuitModel,
    Component,
    ComponentType,
    SIValue,
    SimulationConfig,
    AnalysisType,
)
from app.schemas.simulation import SimulationRequest
from app.services.netlist_generator import generate_netlist
from app.services.ngspice_runner import run_simulation
from app.services.theory_oracle import analyze_rc_circuit_theory
from app.main import get_seeded_rc_circuit, simulate_circuit_endpoint


def test_generate_netlist_syntax():
    """Verify generated SPICE netlist syntax."""
    circuit = get_seeded_rc_circuit()
    netlist = generate_netlist(circuit)

    assert "* CircuitLens Netlist" in netlist
    assert "V1 in 0 DC 5" in netlist
    assert "R1 in out 1k" in netlist
    assert "C1 out 0 10u IC=0" in netlist
    assert ".tran 1e-05 0.05 UIC" in netlist
    assert ".print tran" in netlist
    assert ".end" in netlist


def test_netlist_collapses_ideal_wire_without_series_resistor():
    circuit = get_seeded_rc_circuit()
    wire = Component(
        id="W1", type=ComponentType.WIRE, value=SIValue(magnitude=0.0, unit="ohm"),
        terminals=["out", "output_alias"],
    )
    load = Component(
        id="R2", type=ComponentType.RESISTOR, value=SIValue(magnitude=10000.0, unit="ohm"),
        terminals=["output_alias", "0"],
    )
    circuit = circuit.model_copy(update={"components": circuit.components + [wire, load]})
    netlist = generate_netlist(circuit)
    assert "R_WIRE" not in netlist
    assert "R2 output_alias 0 10k" in netlist


def test_simulate_showcase_rc_circuit():
    """Verify live ngspice execution of the reference 5V, 1k, 10uF circuit."""
    circuit = get_seeded_rc_circuit()
    res = run_simulation(circuit)

    assert res.status == "success", f"Simulation failed: {res.error_message}\n{res.raw_output}"
    assert len(res.traces) >= 2
    assert res.execution_time_ms > 0

    trace_map = {t.name.lower(): t for t in res.traces}
    assert "v(out)" in trace_map
    assert "v(in)" in trace_map

    v_out = trace_map["v(out)"]
    time_arr = v_out.x
    vout_arr = v_out.y

    # Initial condition: capacitor initially at 0V
    assert abs(vout_arr[0] - 0.0) < 0.05

    # At t = 10 ms (1 tau = 1k * 10u = 10 ms), expected Vout ≈ 3.16 V
    idx_10ms = min(range(len(time_arr)), key=lambda i: abs(time_arr[i] - 0.01))
    v_10ms = vout_arr[idx_10ms]
    assert 3.10 <= v_10ms <= 3.22, f"Expected ~3.16V at 10ms, got {v_10ms}V"

    # At t = 50 ms (5 tau = 50 ms), expected Vout ≈ 4.97 V
    idx_50ms = min(range(len(time_arr)), key=lambda i: abs(time_arr[i] - 0.05))
    v_50ms = vout_arr[idx_50ms]
    assert 4.90 <= v_50ms <= 5.00, f"Expected ~4.97V at 50ms, got {v_50ms}V"

    # Verify analytical theory oracle passed with tight tolerance (<1%)
    assert res.theory_verification is not None
    assert res.theory_verification.passed_tolerance is True
    assert res.theory_verification.max_relative_error_percent < 1.0


def test_simulate_parameter_variation_r_5k():
    """Changing R to 5k should change time constant to 50ms."""
    circuit = get_seeded_rc_circuit()
    # Update R1 to 5000 ohm, extend simulation stop time to 250ms (5 * 50ms)
    updated_comps = []
    for c in circuit.components:
        if c.id == "R1":
            updated_comps.append(
                c.model_copy(update={"value": SIValue(magnitude=5000.0, unit="ohm")})
            )
        else:
            updated_comps.append(c)

    varied_circuit = circuit.model_copy(
        update={
            "components": updated_comps,
            "simulation": SimulationConfig(type=AnalysisType.TRANSIENT, step_seconds=5e-5, stop_seconds=0.25),
        }
    )

    theory = analyze_rc_circuit_theory(varied_circuit)
    assert theory.tau_ms == 50.0  # 5k * 10u = 50 ms

    res = run_simulation(varied_circuit)
    assert res.status == "success"

    trace_map = {t.name.lower(): t for t in res.traces}
    v_out = trace_map["v(out)"]
    time_arr = v_out.x
    vout_arr = v_out.y

    # At t = 50 ms (1 tau for 5k), expected Vout ≈ 3.16 V
    idx_50ms = min(range(len(time_arr)), key=lambda i: abs(time_arr[i] - 0.05))
    v_50ms = vout_arr[idx_50ms]
    assert 3.10 <= v_50ms <= 3.22, f"Expected ~3.16V at 50ms with R=5k, got {v_50ms}V"

    assert res.theory_verification is not None
    assert res.theory_verification.passed_tolerance is True


def test_simulate_pure_resistor_divider_op():
    """Verify operating-point simulation on a 2-resistor voltage divider."""
    circuit = CircuitModel(
        schema_version="1.0",
        name="10V Voltage Divider",
        analysis=AnalysisType.OP,
        ground_node="0",
        components=[
            Component(
                id="V1",
                type=ComponentType.VOLTAGE_SOURCE_DC,
                value=SIValue(magnitude=10.0, unit="V"),
                terminals=["in", "0"],
            ),
            Component(
                id="R1",
                type=ComponentType.RESISTOR,
                value=SIValue(magnitude=1000.0, unit="ohm"),
                terminals=["in", "mid"],
            ),
            Component(
                id="R2",
                type=ComponentType.RESISTOR,
                value=SIValue(magnitude=1000.0, unit="ohm"),
                terminals=["mid", "0"],
            ),
        ],
    )

    res = run_simulation(circuit)
    assert res.status == "success"
    assert "v(mid)" in res.operating_point
    assert abs(res.operating_point["v(mid)"] - 5.0) < 0.01  # Midpoint is exactly 5V
    assert "v(in)" in res.operating_point
    assert abs(res.operating_point["v(in)"] - 10.0) < 0.01


def test_simulate_endpoint_via_api():
    """Verify FastAPI /api/simulate endpoint with interactive override."""
    circuit = get_seeded_rc_circuit()
    req = SimulationRequest(circuit=circuit, override_r_magnitude=5000.0)
    res = simulate_circuit_endpoint(req)

    assert res.status == "success"
    assert res.theory_verification is not None
    assert res.theory_verification.theory.tau_ms == 50.0
