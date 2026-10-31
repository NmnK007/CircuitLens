# CircuitLens — Project Idea, Technical Knowledge & Build Specification

**Category:** Best Use of Gemma 4  
**Project type:** Multimodal AI + electronics simulation + educational/debugging tool  
**Document date:** 31 October 2026  
**Recommended coding agent:** Google Antigravity IDE  

---

## 1. Project at a glance

### One-line pitch

**CircuitLens is a multimodal AI electronics assistant that turns a circuit image into an editable electrical model, simulates its behaviour using a real circuit simulator, and explains or diagnoses the results using Gemma 4.**

### The problem

Students and electronics enthusiasts often struggle to move between a circuit drawing and its actual electrical behaviour. They may recognise a resistor or capacitor but still struggle to understand the connections, calculate voltages and currents, predict time-dependent behaviour, or find a wiring mistake.

Existing chatbots can explain circuit theory, but a text explanation alone does not prove that a circuit has been reconstructed correctly or that its numerical behaviour is right.

### Our solution

A user uploads a circuit schematic. CircuitLens:

1. Analyses the image with Gemma 4 and image-processing tools.
2. Identifies supported components, labels, terminals and likely connections.
3. Converts the interpretation into a structured circuit representation.
4. Shows the reconstructed circuit and asks the user to resolve uncertain connections.
5. Converts the confirmed representation into a SPICE netlist.
6. Runs a real simulation through ngspice.
7. Displays numerical results and plots.
8. Uses Gemma 4 to explain the verified results and discuss possible faults.

### The central design principle

**Gemma 4 interprets and explains; deterministic code and ngspice perform the electrical calculations.** Do not ask a language model to invent simulation results. The AI must be given the actual simulator output when it explains a circuit.

---

## 2. Why this is a strong Gemma 4 project

CircuitLens makes multimodal understanding central to the product: the application begins with an image of an electronic circuit, not just a text prompt. Gemma 4 can help interpret visual information, read labels, reason over the detected circuit, and explain results in natural language.

Gemma 4 model-family capabilities and deployment options should be checked against the current official model card before implementation. The model family includes multimodal text/image capability, reasoning and function-calling support. Audio support applies only to selected variants; audio is not required for this project.

Official model card: https://ai.google.dev/gemma/docs/core/model_card_4  
Google DeepMind model page: https://deepmind.google/models/gemma/gemma-4/

### Where Gemma 4 belongs

| Task | Responsible part |
|---|---|
| Interpret the uploaded circuit image | Gemma 4 vision |
| Suggest component classes and read labels | Gemma 4 + OCR/image processing |
| Locate lines, symbols and candidate terminal positions | OpenCV / geometry processing, assisted by AI |
| Decide exact electrical connectivity | Topology reconstruction + validation + user confirmation |
| Calculate voltages and currents | ngspice / deterministic numerical code |
| Generate a valid netlist | Application code using validated circuit data |
| Explain simulator output | Gemma 4, grounded in actual output |
| Suggest possible corrections | Rule checks + simulation evidence + Gemma 4 explanation |

### Important model-access rule

Use a **Gemma provider adapter** so the application is not tied to one hosting method. At implementation time, verify the current official way to access the selected Gemma 4 variant. It may be hosted or locally served depending on supported availability, model size, hardware and quota. Do not invent API endpoints or model identifiers. Do not silently substitute Gemini or another model and still claim the app uses Gemma 4. Keep model name and provider configurable through environment variables, and show a clear setup message when credentials or local model service are missing.

---

## 3. User journey

1. User opens CircuitLens.
2. User uploads a JPG or PNG circuit schematic.
3. The application validates file type and size.
4. Gemma 4 analyses the image and returns structured candidate detections.
5. Image processing helps locate symbols, text, wire paths and terminal positions.
6. The topology builder groups electrically connected terminals into nodes.
7. CircuitLens displays the proposed circuit as an editable component/node table and, where practical, a reconstructed schematic.
8. Ambiguous connections or values are highlighted. The user confirms or corrects them.
9. The validated circuit is converted to a SPICE netlist.
10. The backend runs ngspice in a controlled process with timeouts and resource limits.
11. CircuitLens displays voltages, currents, warnings and plots.
12. The user asks Gemma 4 a follow-up question. The model receives the validated circuit and actual simulator results as context.

---

## 4. Electronics knowledge required

### 4.1 Fundamental quantities

| Quantity | Symbol | SI unit | Meaning |
|---|---|---|---|
| Voltage | V | volt (V) | Electric potential difference between two points |
| Current | I | ampere (A) | Rate of flow of electric charge |
| Resistance | R | ohm (Ω) | Opposition to current flow |
| Capacitance | C | farad (F) | Charge stored per unit voltage |
| Inductance | L | henry (H) | Property relating voltage to changing current |
| Power | P | watt (W) | Rate of energy transfer |

Useful relationships:

- Current: `I = dQ/dt`
- Ohm's law: `V = I R`
- Power (passive sign convention): `P = V I`
- Resistor power: `P = I²R = V²/R`

### 4.2 Kirchhoff's laws

**Kirchhoff's Current Law (KCL):** the algebraic sum of currents at a node is zero. It follows from conservation of charge.

`Σ I = 0`

**Kirchhoff's Voltage Law (KVL):** the algebraic sum of voltage rises and drops around a closed loop is zero in the lumped-circuit model.

`Σ V = 0`

These principles are useful for understanding circuit connectivity and checking whether a reconstructed model is plausible. A simulator should still be used to solve non-trivial networks.

### 4.3 Series and parallel resistors

For series resistors:

`R_eq = R1 + R2 + ... + Rn`

The same current flows through each ideal series element.

For parallel resistors:

`1/R_eq = 1/R1 + 1/R2 + ... + 1/Rn`

The voltage across each ideal parallel branch is the same. For two resistors, `R_eq = (R1 R2)/(R1 + R2)`.

### 4.4 Components to support

Start with a deliberately limited component library.

| Component | Symbol/reference | Main behaviour | MVP status |
|---|---|---|---|
| Resistor | R | `V = IR` | Required |
| Capacitor | C | `i = C dv/dt` (passive sign convention) | Required |
| DC voltage source | V | Defines a voltage between two nodes | Required |
| Ground | node 0 | Reference node for voltages | Required |
| Ideal wire | connection | Joins electrical terminals into one node | Required |
| Inductor | L | `v = L di/dt` | Later |
| Diode / LED | D | Nonlinear, directional behaviour | Later |
| Transistor | Q / M | Nonlinear device behaviour | Later |
| Op-amp | U | Requires a suitable device model | Later |

Do not claim support for a component unless the schema, netlist generator, simulator path and tests all support it.

---

## 5. RC circuits — the first showcase circuit

An RC circuit contains a resistor and capacitor. It is an ideal first target because its transient behaviour is mathematically understandable and visually demonstrable.

### Example circuit

- Ideal DC voltage step: 5 V
- Series resistor: 1 kΩ
- Capacitor to ground: 10 μF
- Output: voltage across the capacitor
- Initial capacitor voltage: 0 V

Simplified schematic:

```text
       R1 = 1 kΩ
 +5 V ----/\\/\\----+---- Vout
                    |
                 C1 = 10 μF
                    |
 GND ---------------+---- GND
```

### Time constant

`τ = R C`

For the example:

`τ = 1000 Ω × 10 × 10⁻⁶ F = 0.01 s = 10 ms`

### Charging response

For an initially uncharged capacitor driven by an ideal DC step:

`Vc(t) = Vs (1 - e^(-t/RC))`

At one time constant:

`Vc(τ) = Vs (1 - e^(-1)) ≈ 0.632 Vs`

For a 5 V source, this is approximately 3.16 V.

At five time constants:

`Vc(5τ) = Vs (1 - e^(-5)) ≈ 0.993 Vs`

For a 5 V source, this is approximately 4.97 V. The capacitor is practically charged, although the ideal exponential approaches the final voltage asymptotically rather than reaching it at a finite time.

### Discharging response

For an initially charged capacitor discharging through a resistor:

`Vc(t) = V0 e^(-t/RC)`

### What CircuitLens should show

- The detected source, resistor and capacitor values.
- The calculated time constant.
- A transient plot of capacitor voltage against time.
- Optionally, resistor current against time.
- A clear explanation of the 63.2% and approximately 99.3% milestones.
- Controls to change R, C and source voltage and rerun the simulation.

The closed-form equation is useful as an independent test oracle for a simple RC case. The app's displayed simulator output should come from ngspice, not from a hand-written illustrative graph.

---

## 6. Image understanding and circuit reconstruction

This is the most technically challenging part of CircuitLens.

A human sees a schematic as components and electrical connections. A computer initially sees pixels. CircuitLens has to transform those pixels into a structured electrical network.

### 6.1 Important concepts

**Component:** an electrical element such as a resistor, capacitor or voltage source.

**Terminal:** a connection point on a component.

**Wire:** a drawn conductor that may connect two or more terminals.

**Node:** an electrically continuous region. All terminals connected by ideal wires belong to the same node.

**Topology:** the network of components and the nodes to which their terminals connect. The layout of symbols on the page is not the same thing as electrical topology.

A useful abstraction is a graph `G = (V, E)`, where `V` is the set of electrical nodes and `E` is the set of two-terminal components. More complex multi-terminal components can be represented with their own terminal/node schema.

### 6.2 Suggested image-to-circuit pipeline

1. **Image intake:** accept only supported image types, enforce upload limits, rotate/normalize as needed.
2. **Preprocessing:** improve contrast, reduce noise, deskew and resize without destroying fine lines.
3. **Symbol/component detection:** identify likely component symbols and bounding boxes.
4. **Text/value extraction:** use OCR and AI assistance to read labels such as `R1`, `1k`, `C1`, `10uF`, `5V`.
5. **Terminal detection:** estimate the connection points of each symbol.
6. **Wire extraction:** detect line segments and trace candidate wire paths.
7. **Junction analysis:** distinguish a connected junction from a mere crossing where possible.
8. **Topology reconstruction:** group terminals and wire segments into nodes.
9. **Schema validation:** check required terminals, values, units and ground reference.
10. **Human confirmation:** surface uncertain values and connections; never silently guess an ambiguous junction.
11. **Netlist generation:** generate a netlist only from confirmed, validated circuit data.

### 6.3 Image difficulty levels

| Input type | Difficulty | Scope decision |
|---|---|---|
| Clean printed schematic | Lower | MVP target |
| Simple hand-drawn schematic | Medium | Stretch target after clean schematics work |
| Dense multi-page schematic | High | Future feature |
| Breadboard photograph | Very high | Future feature; physical rows/rails and perspective make connectivity hard |
| PCB photograph/layout | Very high | Out of MVP scope |

### 6.4 Ambiguity handling

Examples of uncertainty:

- Two wires cross but may not be joined.
- A junction dot is faint or missing.
- A resistor label could be `1k` or `10k`.
- A capacitor polarity marker is unclear.
- A wire appears to stop just short of a terminal.

The interface must mark uncertainty and ask the user to confirm it. It must not create a false sense of certainty. Store a confidence value or an uncertainty flag per detected component/value/connection, but do not treat uncalibrated LLM confidence as a statistically reliable probability.

### 6.5 Example structured circuit representation

The following is an illustrative application schema, not a complete circuit description language:

```json
{
  "schema_version": "1.0",
  "analysis": "transient",
  "ground_node": "0",
  "components": [
    {
      "id": "V1",
      "type": "voltage_source_dc",
      "value": {"magnitude": 5, "unit": "V"},
      "terminals": ["N1", "0"]
    },
    {
      "id": "R1",
      "type": "resistor",
      "value": {"magnitude": 1000, "unit": "ohm"},
      "terminals": ["N1", "N2"]
    },
    {
      "id": "C1",
      "type": "capacitor",
      "value": {"magnitude": 0.00001, "unit": "F"},
      "terminals": ["N2", "0"],
      "initial_voltage": 0
    }
  ],
  "simulation": {
    "type": "transient",
    "step_seconds": 0.00001,
    "stop_seconds": 0.05
  }
}
```

The application should use a typed schema (for example, Pydantic models) with explicit unit conversion and strict validation. Avoid relying on arbitrary free-form strings for electrical values.

---

## 7. SPICE and ngspice

### 7.1 What is SPICE?

SPICE is a family of circuit-simulation programs. ngspice is an open-source circuit simulator suitable for the project. It solves circuit equations using established numerical methods and device models.

Official site and manuals: https://ngspice.sourceforge.io/  
Documentation: https://ngspice.sourceforge.io/docs.html

### 7.2 What is a netlist?

A netlist is a textual description of components and the nodes connecting their terminals. It represents electrical connectivity, not the visual placement of components on a page.

Example netlist for the simple RC circuit:

```spice
* CircuitLens RC charging example
V1 in 0 DC 5
R1 in out 1k
C1 out 0 10u IC=0
.tran 10u 50m
.end
```

The exact transient directive and initial-condition syntax must be tested against the installed ngspice version. The backend must capture stdout, stderr, exit code and generated data. Do not assume simulation succeeded simply because the process launched.

### 7.3 Simulation modes to know

| Analysis | What it does | MVP priority |
|---|---|---|
| `.op` | DC operating-point voltages and currents | High |
| `.dc` | Sweeps a DC source or parameter | Later |
| `.tran` | Time-domain transient simulation | High |
| `.ac` | Small-signal frequency response | Later |

### 7.4 Example netlist translation

For the example above:

| Netlist line | Meaning |
|---|---|
| `V1 in 0 DC 5` | 5 V source between node `in` and ground node `0` |
| `R1 in out 1k` | 1 kΩ resistor between `in` and `out` |
| `C1 out 0 10u IC=0` | 10 μF capacitor between `out` and ground, initially at 0 V |
| `.tran 10u 50m` | Transient analysis with a 10 μs print step to 50 ms (verify syntax/version) |
| `.end` | End of netlist |

### 7.5 Safe simulator integration

- Generate netlists from validated structured data; do not execute arbitrary user-supplied netlist text.
- Use a temporary isolated working directory for each simulation.
- Invoke ngspice using a safe subprocess argument list, not shell string interpolation.
- Apply execution timeouts, file-size limits and resource limits where available.
- Validate component names, node names, values, units and analysis parameters.
- Capture and parse simulator errors.
- Do not expose server file paths or environment variables to users.
- Keep uploaded images and generated netlists under controlled storage rules.

---

## 8. Proposed product features

### Feature A — Circuit image understanding

- Upload a supported schematic image.
- Detect supported components and labels.
- Extract values and candidate node connectivity.
- Show what the system detected.
- Highlight uncertain interpretations.

### Feature B — Editable circuit reconstruction

- Display a component list and terminal/node connections.
- Let the user edit component values.
- Let the user correct node assignments or junctions.
- Confirm the circuit before simulation.
- Keep the source image linked to the reconstruction for traceability.

### Feature C — Real circuit simulation

- Generate a SPICE netlist from validated data.
- Run ngspice.
- Display numerical results, plots and simulation status.
- Support operating-point and transient analysis first.
- Allow the user to change R, C and source parameters and rerun.

### Feature D — AI circuit tutor

Users can ask:

- Why does the capacitor take time to charge?
- What happens if I double the resistance?
- Why is the current changing over time?
- Explain this circuit using Kirchhoff's laws.
- What is the time constant?
- What happens if I change the capacitor value?

Gemma 4 must receive the validated circuit representation and simulator output in its context. It should distinguish computed facts from hypotheses.

### Feature E — Circuit troubleshooting

- Flag disconnected or floating nodes where detectable.
- Flag missing ground/reference nodes.
- Detect unsupported components.
- Check for duplicate names or invalid values.
- Compare expected behaviour with simulation output.
- Suggest possible corrections with evidence.

Do not label a circuit as faulty merely because its behaviour is unusual. Distinguish a malformed circuit, an unsupported circuit, a suspicious result and a design that is valid but unexpected.

---

## 9. Recommended technology stack

| Layer | Recommended technology | Purpose |
|---|---|---|
| Frontend | React + TypeScript + Vite | Web application |
| Styling | Tailwind CSS | Responsive interface |
| Backend | Python + FastAPI | APIs and orchestration |
| Data validation | Pydantic | Typed circuit schema |
| AI | Gemma 4 through a verified supported provider/runtime | Visual interpretation and explanations |
| Image processing | OpenCV | Preprocessing, line and contour geometry |
| OCR | An actively maintained OCR library chosen after compatibility checks | Read component labels |
| Simulation | ngspice | Electrical simulation |
| Scientific calculations | NumPy / SciPy | Supporting mathematics and data handling |
| Charts | Plotly | Interactive voltage/current plots |
| Storage | SQLite for MVP | Projects and simulation records |
| Tests | pytest + frontend test tooling | Automated verification |

Keep the stack simple. Do not add a database, queue, cloud platform or framework unless a real requirement needs it.

### Suggested repository structure

```text
circuitlens/
├── README.md
├── .env.example
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── circuit-schema.md
│   └── supported-components.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── gemma_provider.py
│   │   │   ├── image_preprocessing.py
│   │   │   ├── circuit_reconstruction.py
│   │   │   ├── topology.py
│   │   │   ├── netlist_generator.py
│   │   │   ├── ngspice_runner.py
│   │   │   └── explanation.py
│   │   └── utils/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api/
│   │   ├── types/
│   │   └── App.tsx
│   └── package.json
├── examples/
│   ├── rc_charging.json
│   └── rc_charging.spice
└── scripts/
```

The coding agent may adjust this structure if there is a clear technical reason, but it must document the final architecture.

---

## 10. MVP scope and feature priorities

### Level 1 — Must build

- Clean printed schematic upload (PNG/JPG).
- Resistor, capacitor, DC voltage source, ground and wire support.
- Structured circuit representation.
- A clear user-review/correction step.
- Netlist generation from validated circuit data.
- ngspice operating-point and transient analysis.
- Voltage/time plot for RC charging.
- Gemma 4 explanation grounded in actual simulation output.
- A working seeded example so the demo does not depend entirely on image recognition.

### Level 2 — Competition differentiators

- Reconstructed circuit visualization.
- Component value editing.
- AI troubleshooting with traceable evidence.
- Simple hand-drawn schematic support.
- Multiple circuit examples and robust error reporting.
- Follow-up chat that understands the current circuit and simulation.

### Level 3 — Future work

- Breadboard photograph understanding.
- Dense/complex schematic support.
- Inductors, diodes, transistors and op-amps.
- AC frequency-response analysis.
- Signal/audio analysis.
- Circuit optimization and component selection.
- Circuit project history and export.

**Do not sacrifice a reliable Level 1 for incomplete Level 3 features.**

---

## 11. Proposed demo scenario

### Demo: Understand and experiment with an RC charging circuit

The user uploads a simple circuit with:

- 5 V ideal DC source.
- 1 kΩ resistor.
- 10 μF capacitor connected from output to ground.

The app should:

1. Identify the components and values.
2. Reconstruct the circuit connections.
3. Ask the user to confirm uncertain details.
4. Generate a netlist and run ngspice.
5. Display the output voltage curve and the calculated time constant.
6. Explain that `τ = RC = 10 ms`.
7. Explain that the output is approximately 63.2% of its final value at one time constant (approximately 3.16 V for a 5 V step).
8. Let the user change the resistor to 5 kΩ.
9. Rerun the simulation and demonstrate that the time constant becomes 50 ms.
10. Answer a follow-up question using the new simulation results.

This is a better demo than a broad list of incomplete capabilities because it proves an end-to-end workflow.

### Visual presentation

Use a polished engineering dashboard:

- Left: source image and upload controls.
- Centre: reconstructed schematic and editable component/node list.
- Right: AI explanation and detected circuit summary.
- Lower section: simulation controls, plots and numerical results.

Show loading, error, ambiguity and success states. Never show sample/placeholder results as if they came from a real simulation.

---

## 12. Key technical risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Misread component value | Changes electrical results | OCR + AI + user confirmation |
| Misread crossing/junction | Changes topology | Geometry analysis + explicit confirmation |
| Unsupported symbol | Invalid or wrong netlist | Explicit unsupported-component warning |
| Invalid netlist | Simulation fails | Typed schema, whitelist and unit tests |
| Simulator executable missing | App cannot run transient analysis | Installation check and clear setup instructions |
| Simulator output parsing error | Wrong/missing plots | Test parser against known fixtures |
| Model hallucination | False explanation | Provide only validated circuit and actual results; label uncertainty |
| API unavailable or quota exceeded | AI path fails | Provider abstraction, graceful error and seeded offline simulation demo |
| Hardware constraints | Local large model may be impractical | Use a verified hosted endpoint or appropriately sized local variant |
| Time lost on frontend polish | Core engineering remains unfinished | Build simulator path before advanced UI |

### Honest capability statements

- MVP support for clean schematics does not imply support for every schematic.
- Breadboard photo understanding is a separate, harder computer-vision task.
- CircuitLens is an educational prototype, not a certified electronic design or safety-verification tool.
- A simulation is only as correct as the reconstructed topology, component values, model assumptions and simulator configuration.

---

## 13. Suggested team split (if four people)

| Member | Responsibility |
|---|---|
| 1 | Gemma 4 provider integration, prompting and AI explanation |
| 2 | Image preprocessing, component detection and topology reconstruction |
| 3 | Circuit schema, validation, netlist generation and ngspice integration |
| 4 | React frontend, visualizations and end-to-end integration |

All members should understand the end-to-end flow. The responsibility split is not a reason to build isolated modules without agreed data contracts.

---

## 14. Development roadmap

Build in this order. A working simulator path is the foundation; image recognition comes after that.

### Phase 0 — Inspect and plan

- Inspect the environment, operating system and installed tools.
- Check whether Python, Node.js and ngspice are available.
- Verify current Gemma 4 access methods and model identifiers from official documentation.
- Create the project plan and architecture document.
- List assumptions and blockers.

### Phase 1 — Establish the backend and circuit schema

- Create the FastAPI application.
- Define typed Pydantic schemas for components, terminals, nodes and simulation configuration.
- Validate supported component types and SI units.
- Create a known RC test circuit as JSON.
- Add unit tests for schema validation.

### Phase 2 — Build netlist generation and simulation first

- Convert the known RC circuit JSON into a SPICE netlist.
- Run ngspice from Python.
- Capture process status, stdout and stderr.
- Parse transient output into structured arrays.
- Plot the result.
- Compare the result against the analytical RC charging equation within a sensible numerical tolerance.
- Add tests for a resistor network and an RC transient.

### Phase 3 — Build the frontend shell

- Create a polished responsive dashboard.
- Add upload screen, circuit summary, component table and simulation panel.
- Add a seeded example circuit that works without AI or an uploaded image.
- Add API integration and clear loading/error states.

### Phase 4 — Integrate Gemma 4

- Implement a provider adapter.
- Use current, verified Gemma 4 API or local-runtime documentation.
- Send the image and a strict task prompt.
- Request structured JSON matching the application's schema.
- Validate the output in backend code; retry or ask the user for correction on invalid data.
- Keep provider keys on the backend only.

### Phase 5 — Circuit image reconstruction

- Implement preprocessing and OCR.
- Detect supported symbols and terminal locations.
- Trace simple wire geometry.
- Build candidate nodes and topology.
- Add an uncertainty review UI.
- Do not proceed to simulation until the circuit passes validation and the user confirms ambiguous connections.

### Phase 6 — End-to-end testing and demo hardening

- Test several clean schematic images.
- Test unclear images and unsupported symbols.
- Test invalid values and ambiguous crossings.
- Test simulator failures and timeouts.
- Verify all numerical outputs against known examples.
- Record a repeatable demo path.
- Prepare architecture and model-use explanation for judges.

---

## 15. Acceptance tests — what “working” means

The agent must not claim the MVP is complete until the following are demonstrated.

### Backend / simulation

- A known 5 V, 1 kΩ, 10 μF RC circuit is accepted by the schema.
- The netlist generator produces valid netlist syntax for the installed ngspice version.
- ngspice runs successfully and returns transient data.
- The output curve rises toward 5 V.
- At approximately 10 ms, the capacitor voltage is close to 3.16 V.
- At approximately 50 ms, the capacitor voltage is close to 4.97 V.
- Changing R from 1 kΩ to 5 kΩ changes the time constant from 10 ms to 50 ms.
- Invalid units, missing nodes or unsupported components are rejected with useful errors.

### AI / image path

- A supported clean schematic produces a structured candidate circuit.
- The backend validates every returned component and terminal reference.
- Uncertain values or junctions are flagged rather than silently accepted.
- The user can edit the detected values/connections before simulation.
- The model explanation references actual numerical simulation results.
- If the model provider is unavailable, the app displays a clear error and the seeded simulator demo still works.

### Frontend

- Upload works for supported images.
- The app displays detected components and their connections.
- The user can correct at least component values and relevant node assignments.
- The app can run and rerun a simulation after edits.
- Graphs and numerical values update after rerunning.
- The UI is usable at common laptop and mobile viewport sizes.

---

## 16. Recommended coding agent: Google Antigravity

**Recommendation: Google Antigravity IDE.**

Official website: https://antigravity.google/  
Official IDE overview: https://antigravity.google/docs/overview?tab=ide

Why it fits:

- Agent-first development workflow.
- Works across an editor and terminal.
- Can help implement frontend and backend changes across a repository.
- Browser-oriented development/testing workflows are available.
- Can produce plans and artifacts that are useful for reviewing progress.

Use the IDE agent to build the repository in milestones. Keep the code in version control. Review its diffs, especially simulator execution, environment variables, API calls and model outputs. Do not accept claims of success without tests or a live demonstration.

---

# 17. MASTER PROMPT — paste this into Google Antigravity

Copy the entire prompt below into a new Antigravity project/workspace. Put this `CircuitLens_idea.md` file in the workspace so the agent can use it as the project specification.

```text
You are the lead full-stack engineer, AI engineer, computer-vision engineer, and test engineer responsible for building a hackathon-ready product named CircuitLens.

READ THE ENTIRE CircuitLens_idea.md FILE FIRST. Treat it as the product specification and technical context. Do not skip the electronics, topology, simulation, safety, scope, or acceptance-test sections.

PROJECT GOAL
Build CircuitLens: a multimodal AI electronics assistant that accepts a circuit schematic image, uses Gemma 4 to help interpret it, reconstructs an editable structured circuit, generates a SPICE netlist, runs ngspice, displays real simulation results, and uses Gemma 4 to explain those results.

NON-NEGOTIABLE PRODUCT PRINCIPLES
1. Gemma 4 must be a meaningful part of the product, especially for image understanding and contextual explanation. Do not replace Gemma 4 with Gemini or another model without explicitly telling me and obtaining approval.
2. Verify the current official Gemma 4 API or local-runtime integration method and exact model identifier from official documentation before writing the integration. Do not invent SDK methods, endpoints, model names or capabilities. Put provider configuration behind an adapter and environment variables.
3. The AI is not the circuit simulator. Use ngspice for circuit simulation and deterministic Python code for calculations, parsing, unit conversions and validation.
4. Never silently guess ambiguous wire connections, component values or polarity. Highlight uncertainty and make the user confirm or edit it.
5. Never claim a simulation succeeded unless ngspice ran, returned a successful status and valid data was parsed.
6. Do not show placeholder charts or fabricated numerical values as real simulation results. A clearly labelled seeded example is allowed.
7. Generate netlists only from validated, typed circuit data. Never execute arbitrary user-uploaded netlist text or shell commands.
8. Keep all API keys and secrets on the backend. Add `.env.example`; never commit a real `.env` file.
9. Build the smallest reliable MVP first. Do not expand into breadboard or PCB recognition before clean schematic recognition and the simulator pipeline work.
10. This is an educational hackathon prototype, not a certified electrical safety or professional EDA tool. Reflect that limitation in the UI and README.

REQUIRED MVP
- Upload PNG/JPG circuit schematic.
- Initially support resistors, capacitors, ideal DC voltage sources, ground and wires.
- Use Gemma 4 vision to assist with interpreting supported circuit images and reading component labels.
- Use OCR/image processing and geometry where useful; do not expect a language model alone to produce reliable exact wire topology.
- Produce a validated structured circuit JSON representation with components, values, terminals, nodes, ground and analysis configuration.
- Show detected components/connections and let the user correct values or node assignments.
- Flag ambiguous crossings, junctions, low-confidence readings and unsupported symbols.
- Generate a SPICE netlist from confirmed data.
- Run ngspice for at least operating-point and transient analysis.
- Display actual voltage/current values and Plotly graphs.
- Use Gemma 4 to explain the validated circuit and actual simulation outputs.
- Include a fully working seeded RC example even if the AI provider is not configured.

FIRST SHOWCASE CIRCUIT
Use this reference circuit:
- DC source: 5 V
- Resistor: 1 kΩ
- Capacitor: 10 μF from output node to ground
- Initially uncharged capacitor
- Expected time constant: 10 ms
- Expected output voltage at 10 ms: approximately 3.16 V
- Expected output voltage at 50 ms: approximately 4.97 V
- If R changes to 5 kΩ while C stays at 10 μF, the time constant becomes 50 ms.
Use these expected values as tests/oracles, not as hardcoded simulator output. Verify ngspice's actual output against the RC equation with a numerical tolerance.

RECOMMENDED STACK
- Frontend: React + TypeScript + Vite + Tailwind CSS.
- Backend: Python + FastAPI + Pydantic.
- AI: Gemma 4 through a verified current provider/runtime.
- Image processing: OpenCV.
- OCR: choose a compatible maintained OCR library after checking setup requirements.
- Circuit simulation: ngspice.
- Scientific computing: NumPy/SciPy.
- Charts: Plotly.
- Storage: SQLite only if project persistence is needed for MVP.
- Testing: pytest plus suitable frontend tests.
You may propose a change if a dependency is unavailable or creates unnecessary complexity, but explain the reason first.

IMPLEMENTATION ORDER — FOLLOW THIS SEQUENCE
PHASE 0: INSPECT AND PLAN
- Inspect the workspace and available runtimes.
- Check Python, Node.js, npm and ngspice availability.
- Verify current Gemma 4 access documentation from official sources.
- Create a concise implementation plan, architecture diagram and task checklist.
- Identify environment setup requirements and risks.
- Do not start by building a large polished frontend.

PHASE 1: BACKEND FOUNDATION
- Create a FastAPI backend.
- Define strict Pydantic schemas for components, terminal connections, nodes and simulation configuration.
- Use SI units internally and explicit input/output unit conversions.
- Validate component types, values, terminal counts, node references, ground and simulation parameters.
- Add a seeded RC circuit JSON fixture.
- Add schema tests.

PHASE 2: NETLIST + NGSPICE BEFORE IMAGE AI
- Implement deterministic SPICE netlist generation from validated circuit JSON.
- Implement a safe ngspice runner using subprocess argument arrays, temporary directories, timeouts, output capture and return-code checks.
- Never interpolate user strings into a shell command.
- Parse the simulator's actual transient and operating-point results.
- Verify the exact netlist syntax against the installed ngspice version.
- Add tests for the RC charging circuit and simple resistor network.
- Compare the RC output against Vc(t)=Vs*(1-exp(-t/(R*C))) within a documented tolerance.
- Make sure changing R from 1kΩ to 5kΩ changes the simulated time constant accordingly.
- If ngspice cannot be installed in the environment, do not fake it. Document the blocker, provide exact setup steps, and continue implementing the runner/tests with a clearly labelled unavailable state.

PHASE 3: FRONTEND MVP
- Build a clean, responsive engineering dashboard.
- Include image upload, source-image preview, detected component list, node/connection editor, simulation controls, result cards, graphs and AI explanation panel.
- Include a seeded RC example that works without a Gemma API key.
- Provide useful loading, error, empty, unsupported and ambiguity states.
- Do not show fabricated data as real simulation results.

PHASE 4: GEMMA 4 INTEGRATION
- Build a dedicated Gemma provider adapter with model/provider settings in environment variables.
- Verify exact supported image input and response formatting against current official docs.
- Send the circuit image with a clear task prompt.
- Request structured data matching the application's schema. Treat model output as untrusted and validate it server-side.
- Ask the model to list component candidates, visual positions, values, terminal candidates and ambiguities. Do not ask it to pretend uncertain connections are certain.
- Implement retries or a user correction flow for invalid JSON/schema output.
- Keep provider errors from breaking the seeded simulation path.

PHASE 5: IMAGE RECONSTRUCTION
- Implement image preprocessing and OCR.
- Detect supported symbol candidates and approximate terminal positions.
- Implement simple wire/line geometry and junction analysis.
- Reconstruct nodes and component-to-node connections.
- Clearly mark uncertain crossings/labels and ask for user confirmation.
- Start with clean printed schematics. Add hand-drawn schematics only after the clean path works.
- Do not implement breadboard photo recognition in the MVP.

PHASE 6: AI EXPLANATION AND TROUBLESHOOTING
- Give Gemma the validated circuit JSON plus actual simulator output, including units and analysis settings.
- Ask for explanations grounded in those results.
- In the response, distinguish measured/simulated facts, textbook calculations, assumptions and hypotheses.
- Add simple checks for missing ground, unconnected nodes, invalid values, unsupported devices and simulator warnings.
- Never claim an unverified physical fault from an image alone.

PHASE 7: END-TO-END VALIDATION
- Run backend tests and frontend tests.
- Run the app locally and inspect the UI in a browser.
- Test the full upload → interpret → edit/confirm → netlist → ngspice → plot → Gemma explanation flow.
- Test ambiguous wire crossings, unreadable labels, unsupported symbols, invalid values, missing ground, unavailable model key and simulator timeout.
- Fix the real issues found; do not merely list them.
- Update README with exact install/run commands, environment variables, architecture and known limitations.
- Create a repeatable demo walkthrough and screenshots if browser tools permit.

SUGGESTED PROJECT STRUCTURE
circuitlens/
  README.md
  .env.example
  .gitignore
  docs/
  backend/app/{api,core,schemas,services,utils}/
  backend/tests/
  frontend/src/{components,pages,api,types}/
  examples/
  scripts/
Keep the architecture modular but do not over-engineer it.

BACKEND API IDEAS
- GET /api/health
- POST /api/analyze-image — accepts an image and returns candidate detections/circuit representation.
- POST /api/circuits/validate — validates edited structured circuit data.
- POST /api/simulate — generates netlist, runs ngspice and returns parsed outputs.
- POST /api/explain — sends validated circuit + actual results to Gemma 4.
Use typed request/response models, sensible status codes and clear error messages. You may adjust endpoint names if you document them.

QUALITY REQUIREMENTS
- Type hints and clear module boundaries.
- Centralized configuration and logging.
- No secrets committed.
- File upload validation and size limits.
- Safe subprocess usage and timeouts.
- No arbitrary shell/code execution from model output.
- Input validation on both client and server.
- Unit tests for schemas, netlist generation and simulation parsing.
- Integration tests for the known RC example when ngspice is available.
- Frontend must be responsive and accessible.
- Keep the user informed about what is detected, uncertain, confirmed and simulated.

HOW TO WORK WITH ME
- First inspect the environment and produce a concrete plan.
- Work in small milestones, not one giant code dump.
- Before each milestone, state what files/modules you will change and what success looks like.
- Implement the milestone, run its tests, and fix failures before moving on.
- Do not stop after creating scaffolding. Build a working end-to-end vertical slice.
- Do not ask me to make decisions that can reasonably be made from this specification. Use sensible defaults and record assumptions.
- If blocked by missing credentials, model access or ngspice installation, make as much progress as possible and provide exact setup instructions. Never fabricate successful integration.
- Preserve working functionality when making UI changes.
- At the end of each phase, summarize completed work, tests run, remaining blockers and the exact command to run the app.

FINAL DEFINITION OF DONE
A user can open CircuitLens, load the seeded RC circuit or upload a supported clean RC schematic, review/correct its component values and connections, run a real ngspice transient simulation, see the actual output-voltage curve and time constant, change R or C and rerun, and ask Gemma 4 to explain the actual results. If AI access is unavailable, the seeded simulator experience must still work and the limitation must be clearly reported.

Begin with PHASE 0. Inspect the workspace, verify the available environment and current official Gemma 4 integration method, then produce the plan. Do not jump ahead to a decorative frontend.
```

---

## 18. How to use the prompt

1. Download this file and place `CircuitLens_idea.md` in a new Antigravity workspace folder.
2. Open that folder in Google Antigravity IDE.
3. Start a new agent conversation in the workspace.
4. Paste the complete **MASTER PROMPT** from Section 17.
5. Let the agent inspect the environment and return its plan.
6. Ask it to execute one phase at a time and show test results after each phase.
7. Review all code changes, especially model API usage, netlist generation and subprocess execution.
8. Do not move to image-recognition polish until the seeded RC circuit runs correctly through ngspice.

Useful follow-up instruction after the agent gives its plan:

```text
Proceed with Phase 1 only. Implement the backend foundation and typed circuit schema. Add tests and run them. Do not start the frontend or image recognition yet. Report the files changed, commands executed, test results and any blockers.
```

After Phase 1 passes, repeat with Phase 2, then Phase 3, and so on.

---

## 19. Learning resources and official references

### Gemma 4
- Model card: https://ai.google.dev/gemma/docs/core/model_card_4
- Google DeepMind page: https://deepmind.google/models/gemma/gemma-4/
- Gemma documentation: https://ai.google.dev/gemma/docs

### Google Antigravity
- Official website: https://antigravity.google/
- IDE overview: https://antigravity.google/docs/overview?tab=ide

### Circuit simulation
- ngspice official site: https://ngspice.sourceforge.io/
- ngspice documentation: https://ngspice.sourceforge.io/docs.html
- Falstad circuit simulator for learning: https://www.falstad.com/circuit/

### Image processing and backend
- OpenCV documentation: https://docs.opencv.org/
- FastAPI documentation: https://fastapi.tiangolo.com/
- NumPy documentation: https://numpy.org/doc/
- SciPy documentation: https://docs.scipy.org/doc/scipy/
- Plotly Python documentation: https://plotly.com/python/

---

## 20. Final recommendation

Build CircuitLens around one reliable end-to-end workflow:

**Circuit image → Gemma 4 interpretation → editable circuit representation → validated SPICE netlist → ngspice simulation → interactive plots → Gemma 4 explanation.**

The biggest differentiator is not that CircuitLens can chat about electronics. It is that it connects multimodal AI to an actual engineering computation tool, then explains the computation in a way a student can understand.

Start with the seeded RC simulation, make it numerically correct, and then add image understanding. A small, verified engineering workflow will make a stronger project than a broad collection of unreliable AI features.
