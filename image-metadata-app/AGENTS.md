# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: CLI entrypoint (generate/validate/embed/export).
- `core/`: Domain logic — `generator.py` (OpenAI Responses API), `embedder.py` (Pillow embed).
- `utils/`: Validation helpers — `validation.py` (JSON Schema checks + failure logfile).
- `schemas/`: JSON Schemas (`ImageSidecarCopy.schema.json`).
- `static/`: Assets; put images under `static/gallery/` for local runs.
- `tests/`: Pytest tests (`tests/test_*.py`).

## Build, Test, and Development Commands
- Create venv + install deps:
  ```bash
  python3 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  ```
- Run locally (auto-generate, validate, embed, write sidecar):
  ```bash
  python main.py ./static/gallery/your_photo.jpg --auto --embed --write-json
  ```
- Environment: set `OPENAI_API_KEY` in `.env`. Do not commit keys.
- Tests (install dev tool locally):
  ```bash
  pip install pytest
  pytest -q
  ```

## Coding Style & Naming Conventions
- Python, PEP 8; 4-space indentation.
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Keep public functions small and pure; side effects isolated in CLI or adapters.
- JSON keys follow the sidecar schema: `title`, `description`, `ai_generated`, `ai_details`, `reviewed`, `detected_at`.

## Testing Guidelines
- Framework: `pytest`.
- Location/naming: `tests/test_*.py`; test functions `test_*`.
- Aim to cover `core/generator.py` responses formatting (ImageSidecar shape) and `utils/validation.py` outcomes (including failure logging).
- Run `pytest -q` before opening a PR.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise subject (≤72 chars). Optional scope tag, e.g. `feat(core): strict JSON response_format`.
- PRs: include description, rationale, steps to run, sample input image, and output snippet. Link related issues.
- Checklist: tests pass, README/usage updated if flags/behavior change.

## Security & Configuration Tips
- Secrets: keep `OPENAI_API_KEY` in `.env`; never hardcode or commit.
- Images may contain EXIF; avoid sharing sensitive originals. Prefer JSON sidecars for portability.
- Large binaries go outside Git or use `.gitignore` patterns under `static/`.

## Extending the App
- New features live in `core/` (logic) or `cli/` (argument UX). Update the sidecar schema and add tests when adding or changing fields.
