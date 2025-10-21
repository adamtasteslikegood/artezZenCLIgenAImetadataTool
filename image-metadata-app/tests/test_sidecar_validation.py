import json
from pathlib import Path
from tempfile import TemporaryDirectory

from utils.validation import validate_file_and_log


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_validate_file_and_log_valid():
    with TemporaryDirectory() as td:
        td_path = Path(td)
        json_path = td_path / "valid.json"
        log_path = td_path / "failures.log"

        valid_sidecar = {
            "title": "Sample",
            "description": "A sample sidecar.",
            "ai_generated": False,
            "ai_details": {},
            "reviewed": False,
            "detected_at": 0,
        }
        _write_json(json_path, valid_sidecar)

        ok, err = validate_file_and_log(str(json_path), str(log_path))
        assert ok is True
        assert err is None
        assert not log_path.exists(), "Logfile should not be created for valid sidecar"


def test_validate_file_and_log_invalid():
    with TemporaryDirectory() as td:
        td_path = Path(td)
        json_path = td_path / "invalid.json"
        log_path = td_path / "failures.log"

        # Missing required field: description
        invalid_sidecar = {
            "title": "Sample",
            "ai_generated": False,
            "ai_details": {},
            "reviewed": False,
            "detected_at": 0,
        }
        _write_json(json_path, invalid_sidecar)

        ok, err = validate_file_and_log(str(json_path), str(log_path))
        assert ok is False
        assert log_path.exists(), "Logfile should be created for invalid sidecar"
        content = log_path.read_text(encoding="utf-8")
        assert str(json_path) in content
        assert content.strip() != ""

