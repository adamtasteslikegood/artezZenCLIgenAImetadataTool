import os
import base64
import json
from pathlib import Path
from openai import OpenAI

def _image_to_data_url(image_path: str) -> str:
    p = Path(image_path)
    mime = "image/jpeg" if p.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def generate_metadata_from_image(image_path: str, model: str = "gpt-4o") -> dict:
    """Send image to OpenAI and request strict JSON metadata."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    data_url = _image_to_data_url(image_path)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You output ONLY valid JSON for image metadata."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze the image and return a JSON object with keys: "
                            "title (string), description (string), caption (string), "
                            "tags (array of 3-6 short strings). Respond ONLY with JSON."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        response_format="json",
        temperature=0.5,
        max_tokens=400,
    )

    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except Exception:
        # If the model returns already-parsed content in SDK types, just return as-is
        if isinstance(content, dict):
            return content
        raise
