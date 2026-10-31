"""CircuitLens Safe ngspice Runner and Output Parser.

Executes ngspice in isolated temporary directories with strict subprocess timeouts,
captures return codes, stdout, and stderr, parses transient/op outputs, and verifies
numerical results with the analytical theory oracle.
"""

import os
import re
import time
import shutil
import tempfile
import subprocess
from typing import List, Dict, Tuple, Optional, Any, Set

from ..core.config import settings
from ..schemas.circuit import CircuitModel, AnalysisType, ComponentType
from ..schemas.simulation import SimulationResult, WaveformTrace
from .netlist_generator import generate_netlist
from .theory_oracle import analyze_rc_circuit_theory, verify_transient_data


def run_simulation(circuit: CircuitModel, timeout_seconds: float = 10.0) -> SimulationResult:
    """Execute ngspice on a validated circuit and return real parsed results."""
    # 1. Check ngspice availability
    ngspice_bin = settings.NGSPICE_PATH
    bin_path = shutil.which(ngspice_bin) or (ngspice_bin if os.path.isfile(ngspice_bin) else None)

    # Check the repository-local bundled executable, then common Windows installs.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    bundled = os.path.join(repo_root, "tools", "ngspice", "bin")
    if not bin_path:
        for candidate in [
            os.path.join(bundled, "ngspice_con.exe"),
            os.path.join(bundled, "ngspice.exe"),
            "C:/Spice64/bin/ngspice_con.exe",
            "C:/Spice64/bin/ngspice.exe",
            "C:/Spice/bin/ngspice.exe",
            "C:/Program Files/ngspice/bin/ngspice.exe",
        ]:
            if os.path.isfile(candidate):
                bin_path = candidate
                break

    output_txt_filename = "sim_output.txt"
    netlist_str = generate_netlist(circuit, output_filename=output_txt_filename)

    if not bin_path:
        # ngspice is not available - report cleanly per NON-NEGOTIABLE principles
        return SimulationResult(
            status="unavailable",
            analysis_type=circuit.analysis,
            netlist=netlist_str,
            raw_output="",
            traces=[],
            operating_point={},
            summary={},
            theory_verification=None,
            execution_time_ms=0.0,
            error_message=(
                "ngspice executable was not found on this system. "
                "To enable live simulation, install ngspice (or place ngspice.exe in tools/ngspice/bin) "
                "or set the NGSPICE_PATH environment variable."
            ),
        )

    # 2. Run ngspice in temporary directory
    start_time = time.perf_counter()
    with tempfile.TemporaryDirectory() as temp_dir:
        netlist_path = os.path.join(temp_dir, "circuit.cir")
        with open(netlist_path, "w", encoding="utf-8") as f:
            f.write(netlist_str)

        cmd = [bin_path, "-b", "-r", "raw.out", "circuit.cir"]

        try:
            proc = subprocess.run(
                cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            raw_output = proc.stdout + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else "")
            exec_time_ms = (time.perf_counter() - start_time) * 1000.0

            if proc.returncode != 0:
                return SimulationResult(
                    status="error",
                    analysis_type=circuit.analysis,
                    netlist=netlist_str,
                    raw_output=raw_output,
                    traces=[],
                    operating_point={},
                    summary={},
                    theory_verification=None,
                    execution_time_ms=exec_time_ms,
                    error_message=f"ngspice exited with error code {proc.returncode}.",
                )

            # 3. Parse output files
            raw_file_path = os.path.join(temp_dir, "raw.out")
            data_file_path = os.path.join(temp_dir, output_txt_filename)

            traces: List[WaveformTrace] = []
            op_data: Dict[str, float] = {}

            if os.path.isfile(raw_file_path):
                raw_content = open(raw_file_path, "r", encoding="utf-8", errors="ignore").read()
                if circuit.analysis == AnalysisType.TRANSIENT:
                    traces = _parse_raw_ascii_content(raw_content)
                elif circuit.analysis == AnalysisType.OP:
                    op_data = _parse_op_raw_content(raw_content, raw_output)

            elif os.path.isfile(data_file_path):
                traces = _parse_wrdata_file(data_file_path, circuit)

            if circuit.analysis == AnalysisType.OP and not op_data:
                op_data = _parse_op_output(raw_output)

            # A zero process status alone is not a successful simulation. Require
            # the analysis results to have been emitted and parsed successfully.
            if circuit.analysis == AnalysisType.TRANSIENT and not any(t.x and t.y for t in traces):
                return SimulationResult(
                    status="error", analysis_type=circuit.analysis, netlist=netlist_str,
                    raw_output=raw_output, traces=[], operating_point={}, summary={},
                    theory_verification=None, execution_time_ms=round(exec_time_ms, 2),
                    error_message="ngspice exited successfully but produced no parseable transient data.",
                )
            if circuit.analysis == AnalysisType.OP and not op_data:
                return SimulationResult(
                    status="error", analysis_type=circuit.analysis, netlist=netlist_str,
                    raw_output=raw_output, traces=[], operating_point={}, summary={},
                    theory_verification=None, execution_time_ms=round(exec_time_ms, 2),
                    error_message="ngspice exited successfully but produced no parseable operating-point data.",
                )

            # 4. Generate summary and run analytical theory oracle
            summary = _compute_transient_summary(traces, circuit)
            theory = analyze_rc_circuit_theory(circuit)
            theory_verif = None

            # Verify output capacitor curve against theory if available
            out_trace = next((t for t in traces if "out" in t.name.lower()), None)
            if out_trace and theory.is_rc_circuit:
                theory_verif = verify_transient_data(out_trace.x, out_trace.y, theory)

            return SimulationResult(
                status="success",
                analysis_type=circuit.analysis,
                netlist=netlist_str,
                raw_output=raw_output,
                traces=traces,
                operating_point=op_data,
                summary=summary,
                theory_verification=theory_verif,
                execution_time_ms=round(exec_time_ms, 2),
                error_message=None,
            )

        except subprocess.TimeoutExpired:
            return SimulationResult(
                status="error",
                analysis_type=circuit.analysis,
                netlist=netlist_str,
                raw_output=f"Simulation timed out after {timeout_seconds} seconds.",
                traces=[],
                operating_point={},
                summary={},
                theory_verification=None,
                execution_time_ms=timeout_seconds * 1000.0,
                error_message=f"Simulation exceeded execution timeout ({timeout_seconds}s).",
            )
        except Exception as e:
            return SimulationResult(
                status="error",
                analysis_type=circuit.analysis,
                netlist=netlist_str,
                raw_output=str(e),
                traces=[],
                operating_point={},
                summary={},
                theory_verification=None,
                execution_time_ms=0.0,
                error_message=f"Simulation runner error: {str(e)}",
            )


def _parse_wrdata_file(filepath: str, circuit: CircuitModel) -> List[WaveformTrace]:
    """Parse ASCII table generated by ngspice wrdata command.
    
    wrdata writes columns in pairs: [time1, val1, time2, val2, ...]
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return []

    # Infer vector names from circuit
    non_ground_nodes = sorted([n for n in _get_all_nodes(circuit) if n not in ("0", circuit.ground_node)])
    v_names = [f"v({n})" for n in non_ground_nodes]
    i_names = [f"i({c.id.upper()})" for c in circuit.components if c.type == ComponentType.VOLTAGE_SOURCE_DC]
    expected_vectors = v_names + i_names

    matrix: List[List[float]] = []
    for line in lines:
        parts = line.split()
        try:
            matrix.append([float(p) for p in parts])
        except ValueError:
            continue

    if not matrix:
        return []

    num_cols = len(matrix[0])
    traces: List[WaveformTrace] = []

    # If wrdata output has 2*N columns (time_k, val_k)
    if num_cols % 2 == 0:
        num_signals = num_cols // 2
        for s_idx in range(num_signals):
            time_col = s_idx * 2
            val_col = s_idx * 2 + 1
            x = [row[time_col] for row in matrix]
            y = [row[val_col] for row in matrix]
            vec_name = expected_vectors[s_idx] if s_idx < len(expected_vectors) else f"signal_{s_idx+1}"
            unit = "A" if vec_name.startswith("i(") else "V"
            traces.append(WaveformTrace(name=vec_name, unit=unit, x=x, y=y))

    # If wrdata output has N+1 columns (time, val1, val2, ...)
    else:
        x = [row[0] for row in matrix]
        for c_idx in range(1, num_cols):
            y = [row[c_idx] for row in matrix]
            vec_name = expected_vectors[c_idx - 1] if (c_idx - 1) < len(expected_vectors) else f"signal_{c_idx}"
            unit = "A" if vec_name.startswith("i(") else "V"
            traces.append(WaveformTrace(name=vec_name, unit=unit, x=x, y=y))

    return traces


def _parse_raw_ascii_content(raw: str) -> List[WaveformTrace]:
    """Parse ngspice ASCII raw file into typed WaveformTraces."""
    var_match = re.search(r"Variables:\s*\n(.*?)\n\s*Values:", raw, re.DOTALL)
    if not var_match:
        return []

    variables = []
    for line in var_match.group(1).strip().splitlines():
        parts = line.split()
        if len(parts) >= 3:
            variables.append((int(parts[0]), parts[1], parts[2]))

    val_match = re.search(r"Values:\s*\n(.*)", raw, re.DOTALL)
    if not val_match:
        return []

    tokens = val_match.group(1).split()
    num_vars = len(variables)
    traces_map: Dict[str, List[float]] = {v[1]: [] for v in variables}

    idx = 0
    while idx < len(tokens):
        # Point index
        idx += 1
        for v in variables:
            if idx < len(tokens):
                traces_map[v[1]].append(float(tokens[idx]))
                idx += 1

    time_var = next((v for v in variables if v[1].lower() == "time"), None)
    if not time_var or time_var[1] not in traces_map:
        return []

    time_vals = traces_map[time_var[1]]
    traces: List[WaveformTrace] = []

    for v in variables:
        if v[1].lower() == "time":
            continue
        v_idx, v_name, v_type = v
        unit = "A" if "current" in v_type.lower() or v_name.lower().startswith("i(") else "V"
        y_vals = traces_map.get(v_name, [])
        if len(y_vals) == len(time_vals):
            traces.append(WaveformTrace(name=v_name, unit=unit, x=time_vals, y=y_vals))

    return traces


def _parse_op_raw_content(raw: str, fallback_text: str) -> Dict[str, float]:
    """Parse DC operating point from ngspice raw file or text."""
    var_match = re.search(r"Variables:\s*\n(.*?)\n\s*Values:", raw, re.DOTALL)
    val_match = re.search(r"Values:\s*\n(.*)", raw, re.DOTALL)
    if var_match and val_match:
        variables = []
        for line in var_match.group(1).strip().splitlines():
            parts = line.split()
            if len(parts) >= 3:
                variables.append(parts[1])
        tokens = val_match.group(1).split()
        if len(tokens) >= len(variables) + 1:
            res: Dict[str, float] = {}
            for i, v in enumerate(variables):
                res[v.lower()] = float(tokens[i + 1])
            return res
    return _parse_op_output(fallback_text)


def _parse_op_output(text: str) -> Dict[str, float]:
    """Parse node voltages and branch currents from DC operating-point output."""
    results: Dict[str, float] = {}
    # Pattern: v(node) = 5.000000e+00 or i(v1) = -5.000000e-03
    pattern = re.compile(r"([vi]\([^\)]+\))\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)", re.I)
    for match in pattern.finditer(text):
        var_name = match.group(1).lower()
        val = float(match.group(2))
        results[var_name] = val
    return results


def _compute_transient_summary(traces: List[WaveformTrace], circuit: CircuitModel) -> Dict[str, Any]:
    """Calculate key electronics milestones from simulated traces."""
    summary: Dict[str, Any] = {}
    if not traces:
        return summary

    out_trace = next((t for t in traces if "out" in t.name.lower()), None)
    if not out_trace:
        out_trace = traces[0]

    y = out_trace.y
    x = out_trace.x

    if not y or not x:
        return summary

    v_init = y[0]
    v_final = y[-1]
    v_peak = max(y)
    v_min = min(y)

    summary["initial_voltage"] = round(v_init, 4)
    summary["final_voltage"] = round(v_final, 4)
    summary["peak_voltage"] = round(v_peak, 4)
    summary["min_voltage"] = round(v_min, 4)
    summary["monitored_node"] = out_trace.name
    summary["num_time_points"] = len(x)
    summary["total_duration_ms"] = round(x[-1] * 1000.0, 3)

    # If charging from 0 towards positive v_final:
    if v_final > v_init:
        v_63 = v_init + 0.632 * (v_final - v_init)
        v_99 = v_init + 0.993 * (v_final - v_init)

        # Find time when voltage reaches 63.2%
        tau_point = next((x[i] for i, val in enumerate(y) if val >= v_63), None)
        if tau_point is not None:
            summary["simulated_tau_ms"] = round(tau_point * 1000.0, 3)

        # Settling time (5 tau or 99.3%)
        settle_point = next((x[i] for i, val in enumerate(y) if val >= v_99), None)
        if settle_point is not None:
            summary["simulated_settling_time_ms"] = round(settle_point * 1000.0, 3)

    return summary


def _get_all_nodes(circuit: CircuitModel) -> Set[str]:
    nodes: Set[str] = set()
    for c in circuit.components:
        for t in c.terminals:
            nodes.add(t.strip())
    return nodes
