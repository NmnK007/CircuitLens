"""Tests for image intake and the local Gemma adapter without model downloads."""

import base64
import json
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from app.services.gemma_provider import GemmaProvider, GemmaUnavailable
from app.services.image_analysis import normalize_image
from app.schemas.ai import ImageCandidate


def png_bytes(width=64, height=48):
    image = Image.new("RGB", (width, height), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_normalize_image_limits_and_reencodes():
    normalized, width, height = normalize_image(png_bytes())
    assert (width, height) == (64, 48)
    assert Image.open(BytesIO(normalized)).format == "JPEG"


def test_normalize_image_rejects_invalid_and_oversized():
    with pytest.raises(ValueError, match="valid PNG or JPG"):
        normalize_image(b"not an image")
    with pytest.raises(ValueError, match="10 MB"):
        normalize_image(b"x" * (10 * 1024 * 1024 + 1))


def test_gemma_adapter_sends_image_to_documented_ollama_route(monkeypatch):
    captured = {}
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"response": json.dumps({"components": []})}
    response.raise_for_status.return_value = None

    def fake_post(url, json, timeout):
        captured.update(url=url, payload=json, timeout=timeout)
        return response

    monkeypatch.setattr("app.services.gemma_provider.requests.post", fake_post)
    image = b"sample image bytes"
    result = GemmaProvider(base_url="http://localhost:11434", model="gemma4:e2b").generate_json("inspect", image)
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["payload"]["model"] == "gemma4:e2b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["images"] == [base64.b64encode(image).decode("ascii")]
    assert result == {"components": []}


def test_gemma_adapter_rejects_invalid_json(monkeypatch):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": "not json"}
    monkeypatch.setattr("app.services.gemma_provider.requests.post", lambda *a, **kw: response)
    with pytest.raises(GemmaUnavailable, match="unavailable or returned invalid JSON"):
        GemmaProvider().generate_json("inspect")


def test_candidate_bbox_rejects_out_of_range_coordinates():
    with pytest.raises(ValueError):
        ImageCandidate(
            id="R1", type="resistor", value_magnitude=1000, value_unit="ohm",
            bounding_box=[-0.1, 0.2, 0.4, 0.8], confidence=0.5,
        )
