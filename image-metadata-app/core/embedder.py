import json
from pathlib import Path
from PIL import Image

def embed_metadata(image_path: str, metadata: dict):
    """Embed simple key/value metadata using Pillow (limited for JPEG).
    Saves a new file with _with_meta suffix.
    """
    try:
        p = Path(image_path)
        img = Image.open(p)
        meta = img.info.copy()

        # Flatten lists (e.g., tags) to a comma-separated string
        for key, value in metadata.items():
            if isinstance(value, list):
                meta[key] = ", ".join(map(str, value))
            elif value is not None:
                meta[key] = str(value)

        out_path = p.with_stem(p.stem + "_with_meta")
        img.save(out_path, "JPEG", **meta)
        print(f"[✓] Metadata embedded in: {out_path.name}")
    except Exception as e:
        print(f"[!] Failed to embed metadata: {e}")

def create_json_sidecar(image_path: str, metadata: dict):
    """Write a JSON sidecar next to the image.

    Expects `metadata` to already conform to the ImageSidecarCopy schema.
    """
    p = Path(image_path)
    json_path = p.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    print(f"[✓] JSON sidecar saved as: {json_path.name}")
