import os
import base64
import json
import time
from pathlib import Path
from openai import OpenAI
from typing import Any, Dict

def _image_to_data_url(image_path: str) -> str:
    p = Path(image_path)
    ext = p.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    elif ext in [".png"]:
        mime = "image/png"
    else:
        # Default to jpeg; many models accept generic data URLs regardless
        mime = "image/jpeg"
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _load_metadata_schema() -> dict:
    """Load the ImageSidecarCopy JSON Schema used by the target app."""
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "ImageSidecarCopy.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_json_or_raise(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to parse JSON from model output: {e}\nRaw: {text[:300]}..."
        )


def generate_metadata_from_image(image_path: str, model: str = "gpt-4o-mini") -> dict:
    """Generate image sidecar metadata using OpenAI Responses API only.

    Returns an object conforming to ImageSidecarCopy.schema.json.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    data_url = _image_to_data_url(image_path)
    schema = _load_metadata_schema()

    instruction = (
        "Analyze this image and produce STRICT JSON matching the schema. "
        "Focus on high-quality `title` and `description` suitable for a gallery item."
    )

    input_payload = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": instruction},
                {"type": "input_image", "image_url": data_url},
            ],
        }
    ]

    create_fn = client.responses.create

    call_kwargs: Dict[str, Any] = {
        "model": model,
        "input": input_payload,
        "temperature": 0.4,
    }

    call_kwargs["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("title", "ImageSidecar"),
            "schema": schema,
            "strict": True,
        },
    }
    call_kwargs["max_output_tokens"] = 500

    try:
        resp = create_fn(**call_kwargs)
    except TypeError as exc:
        message = str(exc).lower()
        retried = False
        if "response_format" in message:
            call_kwargs.pop("response_format", None)
            input_payload[0]["content"][0]["text"] += (
                " Your reply must be raw JSON (no backticks, no commentary)."
            )
            retried = True
        if "max_output_tokens" in message:
            call_kwargs.pop("max_output_tokens", None)
            call_kwargs["max_tokens"] = 500
            retried = True
        if retried:
            resp = create_fn(**call_kwargs)
        else:
            raise

    # Extract text content
    text = None
    if hasattr(resp, "output_text") and resp.output_text:
        text = resp.output_text
    else:
        try:
            text = resp.output[0].content[0].text  # type: ignore[attr-defined]
        except Exception:
            text = None
    if not text:
        raise RuntimeError("No text output received from Responses API.")

    model_obj = _parse_json_or_raise(text)

    # Compose final object ensuring required fields and provenance
    now = int(time.time())
    # Some SDKs expose finish_reason differently; try best-effort extraction
    finish_reason = None
    try:
        finish_reason = getattr(resp, "output", [])[0].finish_reason  # type: ignore[attr-defined]
    except Exception:
        finish_reason = None

    sidecar = {
        "title": model_obj.get("title", ""),
        "description": model_obj.get("description", ""),
        "ai_generated": True,
        "ai_details": {
            "provider": "openai",
            "model": model,
            "prompt": instruction,
            "response_id": getattr(resp, "id", ""),
            "finish_reason": finish_reason or "",
            "created": getattr(resp, "created", 0) or 0,
            "attempted_at": now,
            "status": "ok",
            "error": "",
            "error_body": "",
            "raw_response": {},
        },
        "reviewed": False,
        "detected_at": now,
    }

    return sidecar
