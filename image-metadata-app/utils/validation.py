import json
import os
from jsonschema import validate, ValidationError

SCHEMA_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "schemas", "metadata_schema.json"))

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
