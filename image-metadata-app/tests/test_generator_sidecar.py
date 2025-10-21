import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import core.generator as gen


class _FakeResp:
    def __init__(self, payload_text: str):
        self.output_text = payload_text
        self.id = "resp_123"
        self.created = 1_700_000_000

        class _Out0:
            def __init__(self, text: str):
                self.finish_reason = "stop"

                class _Content0:
                    def __init__(self, text: str):
                        self.text = text

                self.content = [_Content0(text)]

        self.output = [_Out0(payload_text)]


class _FakeResponses:
    def __init__(self, payload_text: str):
        self._payload_text = payload_text

    def create(self, **kwargs):
        # Ensure response_format requests json_schema
        rf = kwargs.get("response_format", {})
        assert rf.get("type") == "json_schema"
        assert "json_schema" in rf
        return _FakeResp(self._payload_text)


class _FakeOpenAI:
    def __init__(self, api_key=None):
        # Emit minimal valid model JSON for sidecar fields the generator lifts
        payload = json.dumps({
            "title": "Test Title",
            "description": "Test Description"
        })
        self.responses = _FakeResponses(payload)


def _write_tiny_png(path: Path):
    # 1x1 transparent PNG bytes
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xe2\x9c\xb3\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path.write_bytes(png_bytes)


def test_generate_metadata_from_image_sidecar_shape(monkeypatch):
    monkeypatch.setattr(gen, "OpenAI", _FakeOpenAI)

    with TemporaryDirectory() as td:
        img_path = Path(td) / "img.png"
        _write_tiny_png(img_path)

        sidecar = gen.generate_metadata_from_image(str(img_path), model="gpt-4o-mini")

        # Basic shape checks
        assert sidecar["title"] == "Test Title"
        assert sidecar["description"] == "Test Description"
        assert sidecar["ai_generated"] is True
        assert isinstance(sidecar["ai_details"], dict)
        assert sidecar["ai_details"].get("provider") == "openai"
        assert sidecar["ai_details"].get("model") == "gpt-4o-mini"
        assert isinstance(sidecar["detected_at"], int)
        assert isinstance(sidecar["reviewed"], bool)

