import json
import os
from pathlib import Path
from datetime import datetime, UTC
from jsonschema import validate, ValidationError

SCHEMA_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "schemas", "ImageSidecarCopy.schema.json")
)


def _load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_response(data: dict):
    schema = _load_schema()
    try:
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)


def validate_or_print(data: dict):
    ok, err = validate_response(data)
    if ok:
        print("✅ Metadata is valid.")
    else:
        print("❌ Validation failed:")
        print(err)


def validate_file_and_log(json_path: str, log_path: str) -> tuple[bool, str | None]:
    """Validate a JSON sidecar file and append failures to a logfile.

    Returns (ok, error_message_or_None). Always keeps the file.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        msg = f"Failed to read JSON: {e}"
        _append_log(log_path, json_path, msg)
        return False, msg

    ok, err = validate_response(data)
    if not ok:
        _append_log(log_path, json_path, err or "Unknown validation error")
    return ok, err


def _append_log(log_path: str, json_path: str, message: str) -> None:
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as logf:
        logf.write(f"[{ts}] {json_path}: {message}\n")
