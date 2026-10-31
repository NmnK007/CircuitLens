"""CircuitLens Theory Verification Oracle.

Calculates exact closed-form analytical solutions (e.g. Vc(t) = Vs*(1 - exp(-t/(RC))))
for reference circuits and verifies actual simulator outputs against theory.
"""

import math
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ..schemas.circuit import CircuitModel, ComponentType


class RCTheorySummary(BaseModel):
    is_rc_circuit: bool = False
    vs: Optional[float] = None
    r: Optional[float] = None
    c: Optional[float] = None
    tau_seconds: Optional[float] = None
    tau_ms: Optional[float] = None
    v_at_tau: Optional[float] = None
    v_at_5tau: Optional[float] = None
    formula: Optional[str] = None


class TheoryVerificationResult(BaseModel):
    verified: bool
    is_rc: bool
    theory: Optional[RCTheorySummary] = None
    simulated_v_at_tau: Optional[float] = None
    expected_v_at_tau: Optional[float] = None
    error_at_tau_volts: Optional[float] = None
    simulated_v_at_5tau: Optional[float] = None
    expected_v_at_5tau: Optional[float] = None
    error_at_5tau_volts: Optional[float] = None
    max_relative_error_percent: Optional[float] = None
    tolerance_percent: float = 5.0
    passed_tolerance: bool = False
    explanation: str = ""


def analyze_rc_circuit_theory(circuit: CircuitModel) -> RCTheorySummary:
    """Analyze circuit to detect and calculate exact RC time-domain parameters."""
    v_source = None
    resistor = None
    capacitor = None

    for comp in circuit.components:
        if comp.type == ComponentType.VOLTAGE_SOURCE_DC:
            v_source = comp
        elif comp.type == ComponentType.RESISTOR:
            resistor = comp
        elif comp.type == ComponentType.CAPACITOR:
            capacitor = comp

    if not (v_source and resistor and capacitor):
        return RCTheorySummary(is_rc_circuit=False)

    vs = v_source.value.magnitude
    r = resistor.value.magnitude
    c = capacitor.value.magnitude

    if r <= 0 or c <= 0:
        return RCTheorySummary(is_rc_circuit=False)

    tau = r * c
    tau_ms = tau * 1000.0

    # Charging curve from 0V initial condition: Vc(t) = Vs * (1 - exp(-t / tau))
    v_at_tau = vs * (1.0 - math.exp(-1.0))
    v_at_5tau = vs * (1.0 - math.exp(-5.0))

    formula = f"Vc(t) = {vs:g} * (1 - e^(-t / {tau:g}))"

    return RCTheorySummary(
        is_rc_circuit=True,
        vs=vs,
        r=r,
        c=c,
        tau_seconds=tau,
        tau_ms=tau_ms,
        v_at_tau=v_at_tau,
        v_at_5tau=v_at_5tau,
        formula=formula,
    )


def verify_transient_data(
    time_points: List[float],
    voltage_points: List[float],
    theory: RCTheorySummary,
    tolerance_percent: float = 5.0,
) -> TheoryVerificationResult:
    """Verify actual numerical transient data against analytical RC equations."""
    if not theory.is_rc_circuit or not time_points or not voltage_points:
        return TheoryVerificationResult(
            verified=False,
            is_rc=False,
            explanation="Not a recognized RC circuit or empty transient data.",
        )

    vs = theory.vs
    tau = theory.tau_seconds
    v_tau_expected = theory.v_at_tau
    v_5tau_expected = theory.v_at_5tau

    # Find closest simulated points to t = tau and t = 5*tau
    idx_tau = min(range(len(time_points)), key=lambda i: abs(time_points[i] - tau))
    idx_5tau = min(range(len(time_points)), key=lambda i: abs(time_points[i] - 5.0 * tau))

    sim_v_tau = voltage_points[idx_tau]
    sim_v_5tau = voltage_points[idx_5tau]

    err_tau = abs(sim_v_tau - v_tau_expected)
    err_5tau = abs(sim_v_5tau - v_5tau_expected)

    # Relative error against Vs
    rel_err_tau_pct = (err_tau / vs) * 100.0 if vs != 0 else 0.0
    rel_err_5tau_pct = (err_5tau / vs) * 100.0 if vs != 0 else 0.0
    max_err_pct = max(rel_err_tau_pct, rel_err_5tau_pct)

    passed = max_err_pct <= tolerance_percent

    explanation = (
        f"At t = {theory.tau_ms:.2f} ms (1 tau): Expected {v_tau_expected:.3f} V, Simulated {sim_v_tau:.3f} V "
        f"(error: {rel_err_tau_pct:.2f}%). "
        f"At t = {5*theory.tau_ms:.2f} ms (5 tau): Expected {v_5tau_expected:.3f} V, Simulated {sim_v_5tau:.3f} V "
        f"(error: {rel_err_5tau_pct:.2f}%)."
    )

    return TheoryVerificationResult(
        verified=True,
        is_rc=True,
        theory=theory,
        simulated_v_at_tau=sim_v_tau,
        expected_v_at_tau=v_tau_expected,
        error_at_tau_volts=err_tau,
        simulated_v_at_5tau=sim_v_5tau,
        expected_v_at_5tau=v_5tau_expected,
        error_at_5tau_volts=err_5tau,
        max_relative_error_percent=max_err_pct,
        tolerance_percent=tolerance_percent,
        passed_tolerance=passed,
        explanation=explanation,
    )
