"""CircuitLens SPICE Netlist Generator.

Generates strictly validated, deterministic SPICE netlists from CircuitModel.
Never interpolates unvalidated user strings into raw shell commands.
"""

from typing import Dict, List, Set
from ..schemas.circuit import CircuitModel, Component, ComponentType, AnalysisType
from .unit_converter import to_spice_value_str


def generate_netlist(circuit: CircuitModel, output_filename: str = "sim_output.txt") -> str:
    """Generate a valid, deterministic SPICE netlist from a validated CircuitModel."""
    # Treat wires as topology and collapse their endpoints. Modeling a wire with
    # a tiny resistor changes the circuit and can distort ideal-source results.
    parent: Dict[str, str] = {}

    def root(node: str) -> str:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = root(parent[node])
        return parent[node]

    for comp in circuit.components:
        if comp.type == ComponentType.WIRE:
            a, b = (root(n.strip()) for n in comp.terminals)
            parent[a] = b
    ground_root = root(circuit.ground_node.strip())

    def spice_node(node: str) -> str:
        node = node.strip()
        return "0" if root(node) == ground_root else root(node)

    lines: List[str] = [
        f"* CircuitLens Netlist: {circuit.name or 'Circuit'}",
        f"* Generated for analysis: {circuit.analysis.value.upper()}",
    ]

    all_nodes: Set[str] = set()

    # 1. Output components
    for comp in circuit.components:
        cid = comp.id.strip().upper()
        t1, t2 = spice_node(comp.terminals[0]), spice_node(comp.terminals[1])
        all_nodes.add(t1)
        all_nodes.add(t2)

        val_str = to_spice_value_str(comp.value, comp.type)

        if comp.type == ComponentType.RESISTOR:
            # R<name> <node1> <node2> <value>
            lines.append(f"{cid} {t1} {t2} {val_str}")

        elif comp.type == ComponentType.CAPACITOR:
            # C<name> <node1> <node2> <value> [IC=<initial_voltage>]
            ic_val = comp.initial_voltage if comp.initial_voltage is not None else 0.0
            lines.append(f"{cid} {t1} {t2} {val_str} IC={ic_val:g}")

        elif comp.type == ComponentType.VOLTAGE_SOURCE_DC:
            # V<name> <node+> <node-> DC <value>
            lines.append(f"{cid} {t1} {t2} DC {val_str}")

        elif comp.type in (ComponentType.WIRE, ComponentType.GROUND):
            # Wires were collapsed above; the ground component denotes node 0.
            continue

    # 2. Simulation control directives
    non_ground_nodes = sorted([n for n in all_nodes if n not in ("0", circuit.ground_node)])
    voltage_vectors = " ".join([f"v({n})" for n in non_ground_nodes])
    current_vectors = " ".join([f"i({c.id.strip().upper()})" for c in circuit.components if c.type == ComponentType.VOLTAGE_SOURCE_DC])
    all_vectors = f"{voltage_vectors} {current_vectors}".strip()

    if circuit.analysis == AnalysisType.TRANSIENT:
        step = circuit.simulation.step_seconds
        stop = circuit.simulation.stop_seconds
        lines.append(f".tran {step:g} {stop:g} UIC")
        if all_vectors:
            lines.append(f".print tran {all_vectors}")
        else:
            lines.append(".print tran")

    elif circuit.analysis == AnalysisType.OP:
        lines.append(".op")
        if all_vectors:
            lines.append(f".print op {all_vectors}")
        else:
            lines.append(".print op")

    lines.append(".end")
    lines.append("")

    return "\n".join(lines)
