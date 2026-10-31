"""CircuitLens Electrical Circuit Validator.

Deterministic validation of circuit topology, terminal counts,
node references, ground existence, and electrical sanity rules.
"""

from typing import Dict, List, Set, Tuple
from collections import defaultdict
from ..schemas.circuit import CircuitModel, Component, ComponentType, ValidationResult


def validate_circuit(circuit: CircuitModel) -> ValidationResult:
    """Validate a CircuitModel against strict electrical and topology rules.
    
    Returns ValidationResult containing:
      - valid: bool (True only if there are zero fatal errors)
      - errors: List of blocking issues (missing ground, non-positive R/C, self-loops)
      - warnings: List of non-blocking issues (floating terminals, high impedance, uncertainty flags)
      - normalized_circuit: Cleaned and normalized CircuitModel
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Ground node checks
    ground_id = circuit.ground_node.strip()
    if not ground_id:
        ground_id = "0"

    # Map of node -> list of (component_id, terminal_index)
    node_connections: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    component_ids: Set[str] = set()

    # Track voltage sources across nodes to detect parallel source shorts
    voltage_source_nodes: Dict[Tuple[str, str], List[Tuple[str, float]]] = defaultdict(list)

    # 2. Iterate and validate each component
    for comp in circuit.components:
        cid = comp.id.strip()
        if cid in component_ids:
            errors.append(f"Duplicate component ID '{cid}' found. Every component must have a unique ID.")
        component_ids.add(cid)

        # Check terminals count
        if len(comp.terminals) != 2:
            errors.append(f"Component '{cid}' ({comp.type.value}) has {len(comp.terminals)} terminals. Exactly 2 required.")
            continue

        t1, t2 = comp.terminals[0].strip(), comp.terminals[1].strip()

        # Check self-loops (short circuits)
        if t1 == t2:
            errors.append(f"Component '{cid}' is connected to the same node '{t1}' on both terminals (short circuit self-loop).")

        # Check values
        mag = comp.value.magnitude
        if comp.type == ComponentType.RESISTOR:
            if mag <= 0:
                errors.append(f"Resistor '{cid}' must have a positive non-zero resistance (got {mag} {comp.value.unit}).")
            elif mag < 1e-3:
                warnings.append(f"Resistor '{cid}' has an unusually low resistance ({mag} {comp.value.unit}). Did you intend a wire?")
            elif mag > 1e9:
                warnings.append(f"Resistor '{cid}' has very high resistance ({mag} {comp.value.unit}).")

        elif comp.type == ComponentType.CAPACITOR:
            if mag <= 0:
                errors.append(f"Capacitor '{cid}' must have a positive non-zero capacitance (got {mag} {comp.value.unit}).")
            elif mag < 1e-15:
                warnings.append(f"Capacitor '{cid}' has an extremely small capacitance ({mag} {comp.value.unit}).")

        elif comp.type == ComponentType.VOLTAGE_SOURCE_DC:
            # Check parallel voltage sources
            node_pair = tuple(sorted([t1, t2]))
            voltage_source_nodes[node_pair].append((cid, mag))

        # Register node connections
        node_connections[t1].append((cid, 0))
        node_connections[t2].append((cid, 1))

        # Collect uncertainties
        if comp.is_uncertain:
            reason = comp.uncertainty_reason or "Flagged as uncertain during recognition"
            warnings.append(f"Uncertain component '{cid}': {reason}. Please verify value and connections.")

    # 3. Check for parallel voltage source conflicts
    for node_pair, sources in voltage_source_nodes.items():
        if len(sources) > 1:
            names = [s[0] for s in sources]
            mags = [s[1] for s in sources]
            if len(set(mags)) > 1:
                errors.append(
                    f"Conflicting DC voltage sources {names} are connected in parallel between nodes '{node_pair[0]}' and '{node_pair[1]}' with different voltages {mags} V (KVL violation)."
                )

    # 4. Check ground node presence
    if ground_id not in node_connections:
        # Check if "0" or "GND" exists
        alt_grounds = [n for n in node_connections if n.lower() in ("0", "gnd", "ground")]
        if alt_grounds:
            warnings.append(f"Ground node '{ground_id}' was not referenced, but node '{alt_grounds[0]}' appears to be ground. Automatically mapping to '{alt_grounds[0]}'.")
            ground_id = alt_grounds[0]
        else:
            errors.append(
                f"Missing ground reference. No component connects to ground node '{ground_id}'. Circuit simulation requires a reference node 0."
            )

    # 5. Check node degrees (detect floating/dangling nodes)
    for node_name, conns in node_connections.items():
        if len(conns) < 2 and node_name != ground_id:
            c_id = conns[0][0]
            warnings.append(
                f"Node '{node_name}' is connected to only one terminal ({c_id}). This node is floating/dangling."
            )

    # 6. Check graph connectivity to ground
    # Breadth-first search from ground_id
    if ground_id in node_connections:
        visited_nodes: Set[str] = {ground_id}
        queue = [ground_id]

        # Build adjacency: node -> set of adjacent nodes
        node_adj: Dict[str, Set[str]] = defaultdict(set)
        for comp in circuit.components:
            if len(comp.terminals) == 2:
                n1, n2 = comp.terminals[0].strip(), comp.terminals[1].strip()
                node_adj[n1].add(n2)
                node_adj[n2].add(n1)

        while queue:
            curr = queue.pop(0)
            for neighbor in node_adj.get(curr, set()):
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append(neighbor)

        unreachable_nodes = set(node_connections.keys()) - visited_nodes
        if unreachable_nodes:
            errors.append(
                f"Nodes {list(unreachable_nodes)} have no DC or AC path to ground node '{ground_id}'. These nodes are floating islands."
            )

    # 7. Collect any ambiguities recorded in circuit
    for amb in circuit.ambiguities:
        if amb not in warnings:
            warnings.append(f"Circuit Ambiguity: {amb}")

    # Build normalized circuit copy with verified ground_node
    normalized_circuit = None
    if not errors:
        norm_comps = []
        for c in circuit.components:
            # Map GND aliases to canonical "0" if ground is 0
            new_terminals = []
            for t in c.terminals:
                t_clean = t.strip()
                if t_clean.lower() in ("gnd", "ground") or t_clean == ground_id:
                    new_terminals.append("0")
                else:
                    new_terminals.append(t_clean)
            norm_c = c.model_copy(update={"terminals": new_terminals})
            norm_comps.append(norm_c)

        normalized_circuit = circuit.model_copy(update={
            "ground_node": "0",
            "components": norm_comps,
        })

    is_valid = len(errors) == 0
    return ValidationResult(
        valid=is_valid,
        errors=errors,
        warnings=warnings,
        normalized_circuit=normalized_circuit,
    )
