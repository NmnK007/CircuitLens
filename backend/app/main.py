"""CircuitLens FastAPI Main Application."""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .core.config import settings
from .schemas.circuit import CircuitModel, ValidationResult, ComponentType
from .schemas.simulation import SimulationRequest, SimulationResult
from .schemas.ai import ExplainRequest, GroundedExplanation, ImageAnalysisResult
from .services.circuit_validator import validate_circuit
from .services.ngspice_runner import run_simulation
from .services.gemma_provider import GemmaProvider, GemmaUnavailable
from .services.image_analysis import normalize_image, detect_line_hints

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multimodal AI Electronics Assistant (Gemma 4 + ngspice)",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.API_PREFIX}/health")
def health_check():
    """Health status and environment capabilities check."""
    provider = GemmaProvider()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "ngspice_available": settings.is_ngspice_available,
        "ngspice_path": settings.NGSPICE_PATH,
        "gemma_provider": settings.GEMMA_PROVIDER,
        "gemma_model": settings.GEMMA_MODEL_ID,
        "gemma_available": settings.GEMMA_PROVIDER == "ollama" and provider.available(),
    }


@app.post(f"{settings.API_PREFIX}/circuits/validate", response_model=ValidationResult)
def validate_circuit_endpoint(circuit: CircuitModel):
    """Validate a structured circuit representation against electrical rules."""
    result = validate_circuit(circuit)
    return result


@app.get(f"{settings.API_PREFIX}/circuits/seeded", response_model=CircuitModel)
def get_seeded_rc_circuit():
    """Fetch the verified showcase RC low-pass filter circuit."""
    # Look for examples/rc_charging.json in project root or relative path
    possible_paths = [
        Path(__file__).resolve().parents[2] / "examples" / "rc_charging.json",
        Path("examples/rc_charging.json"),
        Path("c:/CircuitLens/examples/rc_charging.json"),
    ]

    for p in possible_paths:
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return CircuitModel.model_validate(data)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse seeded circuit: {e}")

    raise HTTPException(status_code=404, detail="Seeded RC circuit fixture not found on server")


@app.post(f"{settings.API_PREFIX}/simulate", response_model=SimulationResult)
def simulate_circuit_endpoint(req: SimulationRequest):
    """Simulate circuit via ngspice and return real waveform data."""
    circuit = req.circuit

    if circuit.ambiguities or any(c.is_uncertain for c in circuit.components):
        raise HTTPException(status_code=409, detail="Resolve and confirm all ambiguous image detections before simulation.")

    # Apply interactive component overrides if provided
    if req.override_r_magnitude is not None:
        updated_comps = []
        for c in circuit.components:
            if c.type == ComponentType.RESISTOR:
                updated_comps.append(
                    c.model_copy(update={"value": c.value.model_copy(update={"magnitude": req.override_r_magnitude})})
                )
            else:
                updated_comps.append(c)
        circuit = circuit.model_copy(update={"components": updated_comps})

    if req.override_c_magnitude is not None:
        updated_comps = []
        for c in circuit.components:
            if c.type == ComponentType.CAPACITOR:
                updated_comps.append(
                    c.model_copy(update={"value": c.value.model_copy(update={"magnitude": req.override_c_magnitude})})
                )
            else:
                updated_comps.append(c)
        circuit = circuit.model_copy(update={"components": updated_comps})

    # Validate circuit before execution
    validation = validate_circuit(circuit)
    if not validation.valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Circuit validation failed", "errors": validation.errors},
        )

    sim_circuit = validation.normalized_circuit or circuit
    result = run_simulation(sim_circuit)
    return result


@app.post(f"{settings.API_PREFIX}/analyze-image", response_model=ImageAnalysisResult)
async def analyze_image_endpoint(file: UploadFile = File(...)):
    """Ask Gemma to propose visual candidates; never auto-confirm topology."""
    image_upload = await file.read(10 * 1024 * 1024 + 1)
    if len(image_upload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MB upload limit.")
    try:
        image_bytes, width, height = normalize_image(image_upload)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    segments, geometry_warnings = detect_line_hints(image_bytes, width, height)
    provider = GemmaProvider()
    if settings.GEMMA_PROVIDER != "ollama":
        raise HTTPException(status_code=503, detail="Set GEMMA_PROVIDER=ollama to enable Gemma 4 image analysis.")
    prompt = (
        "Inspect this clean circuit schematic image. Return only a JSON object with this shape: "
        '{"components":[{"id":"R1","type":"resistor|capacitor|voltage_source_dc|ground|wire",'
        '"value_text":"as printed or null","value_magnitude":1000,"value_unit":"ohm",'
        '"terminal_candidates":["candidate node label or UNKNOWN"],"bounding_box":[0.1,0.2,0.3,0.4],'
        '"confidence":0.0,"visual_evidence":"brief evidence"}],"observed_text":[],"ambiguities":[],"unsupported_symbols":[]}. '
        "Bounding boxes are normalized left,top,right,bottom coordinates from 0 to 1. Use null for unreadable values. "
        "List only supported components. Terminal candidates and node groupings are hypotheses: if any wire, crossing, "
        "junction, polarity, or label is unclear, say so in ambiguities and use UNKNOWN. Do not invent values or claim "
        "electrical connectivity is certain. Confidence is a qualitative model estimate, not a calibrated probability."
    )
    try:
        generated = provider.generate_json(prompt, image_bytes)
        return ImageAnalysisResult.model_validate({
            "provider": provider.provider,
            "model": provider.model,
            "image_width": width,
            "image_height": height,
            "components": generated.get("components", []),
            "observed_text": generated.get("observed_text", []),
            "line_segments": segments,
            "ambiguities": list(generated.get("ambiguities", [])) + geometry_warnings,
            "unsupported_symbols": generated.get("unsupported_symbols", []),
            "message": "Gemma produced visual candidates. Review every value and connection before building a confirmed circuit.",
        })
    except GemmaUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValidationError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="Gemma returned data that did not match the candidate schema; retry or review manually.") from exc


@app.post(f"{settings.API_PREFIX}/explain", response_model=GroundedExplanation)
def explain_endpoint(req: ExplainRequest):
    """Rerun ngspice on the server, then explain only those actual results."""
    validation = validate_circuit(req.circuit)
    if not validation.valid:
        raise HTTPException(status_code=400, detail={"message": "Circuit validation failed", "errors": validation.errors})
    if req.circuit.ambiguities or any(c.is_uncertain for c in req.circuit.components):
        raise HTTPException(status_code=409, detail="Resolve and confirm all image detections before requesting an explanation.")
    if settings.GEMMA_PROVIDER != "ollama":
        raise HTTPException(status_code=503, detail="Set GEMMA_PROVIDER=ollama to enable Gemma 4 explanations.")
    result = run_simulation(validation.normalized_circuit or req.circuit)
    if result.status != "success":
        raise HTTPException(status_code=422, detail="A successful ngspice run is required before asking Gemma to explain results.")
    evidence = {
        "analysis": result.analysis_type.value,
        "summary": result.summary,
        "operating_point": result.operating_point,
        "traces": [{"name": t.name, "unit": t.unit, "sample_count": len(t.x),
                    "samples": list(zip(t.x[::max(1, len(t.x)//40)], t.y[::max(1, len(t.y)//40)]))}
                   for t in result.traces],
        "theory_verification": result.theory_verification.model_dump() if result.theory_verification else None,
    }
    prompt = (
        "Explain this validated educational circuit using ONLY the supplied circuit and ngspice evidence. "
        "Return JSON with keys circuit_summary, physics_explanation, measured_facts, theoretical_calculations, "
        "assumptions, hypotheses, troubleshooting_notes, suggested_experiments. Clearly separate simulated facts "
        "from theory, assumptions, and hypotheses. Do not invent measurements, claim an unverified physical fault, "
        "or claim simulation success beyond the evidence.\nCircuit JSON:\n"
        + json.dumps((validation.normalized_circuit or req.circuit).model_dump(mode="json"), allow_nan=False)
        + "\nServer-run ngspice results:\n" + json.dumps(evidence, allow_nan=False)
        + ("\nUser question: " + req.user_question if req.user_question else "")
    )
    try:
        generated = GemmaProvider().generate_json(prompt)
        return GroundedExplanation.model_validate({
            **generated, "model_used": settings.GEMMA_MODEL_ID, "provider": "ollama"
        })
    except GemmaUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValidationError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Gemma returned an explanation that did not match the response schema.") from exc
