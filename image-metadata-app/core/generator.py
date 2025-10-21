import os
import base64
import json
from pathlib import Path
from openai import OpenAI

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
    # Load JSON Schema from repository to align model output with validator
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "metadata_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_metadata_from_image(image_path: str, model: str = "gpt-4o-mini") -> dict:
    """Generate image metadata using OpenAI Responses API with strict JSON schema."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    data_url = _image_to_data_url(image_path)
    schema = _load_metadata_schema()

    # Compose multimodal input: short, directive, model-friendly
    input_payload = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "Analyze this image and produce metadata fields strictly matching the schema: "
                        "title (string), description (string), caption (string), tags (3-6 short strings)."
                    ),
                },
                {"type": "input_image", "image_url": {"url": data_url}},
            ],
        }
    ]

    resp = client.responses.create(
        model=model,
        input=input_payload,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema.get("title", "ImageMetadata"),
                "schema": schema,
                "strict": True,
            },
        },
        temperature=0.4,
        max_output_tokens=500,
    )

    # Extract the model's JSON output
    text = None
    # Prefer output_text if available; otherwise, traverse structure
    if hasattr(resp, "output_text") and resp.output_text:
        text = resp.output_text
    else:
        try:
            # responses output: list -> content -> text
            text = resp.output[0].content[0].text  # type: ignore[attr-defined]
        except Exception:
            pass

    if not text:
        raise RuntimeError("No text output received from Responses API.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from model output: {e}\nRaw: {text[:300]}...")
