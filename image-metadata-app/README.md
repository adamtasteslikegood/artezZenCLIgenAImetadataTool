# 🖼️ Image Metadata Generator

A command-line utility that generates, validates, embeds, and exports Image Sidecar JSON files for images using OpenAI’s Responses API with a strict JSON Schema (`schemas/ImageSidecarCopy.schema.json`).

## 🚀 Features
- ✨ Generate metadata via OpenAI Responses API only (default: `gpt-4o-mini`)
- 🧠 Strict JSON output enforced by `ImageSidecarCopy.schema.json`
- 🧷 Embed basic key/value metadata into images (Pillow)
- 📄 Export metadata as a `.json` sidecar next to the image
- ✅ Validate sidecars against the schema; keep invalid files but log failures
- 🖥️ CLI with efficient short flags and a full-mode switch

## 🛠 Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🔐 Environment
Create a `.env` file in the project root:
```env
OPENAI_API_KEY=sk-...
```

## ▶️ Usage
End-to-end (auto + embed + JSON sidecar):
```bash
python main.py ./static/gallery/your_photo.jpg -f
```

Custom selection of actions:
```bash
python main.py ./static/gallery/your_photo.jpg -a -e -j
# -a/--auto, -e/--embed, -j/--write-json (aliases: --json, --create-json)
```

Manual input mode (omit `-a`):
```bash
python main.py ./static/gallery/your_photo.jpg -e -j
```
You will be prompted for `title` and `description`. The tool fills the remaining required fields to match the schema.

Pick a specific model (multimodal):
```bash
python main.py ./static/gallery/your_photo.jpg -a -m gpt-4o
```

After writing a sidecar, the app validates it. If validation fails, the file is kept and a log entry is appended to `logs/validation_failures.log` with details.

## 📂 Structure
```
image-metadata-app/
├── core/                # Main logic
├── cli/                 # (Reserved) extra CLI modules
├── utils/               # Validation helpers
├── schemas/             # JSON Schemas
│   └── ImageSidecarCopy.schema.json
├── static/gallery/      # Your images
├── tests/               # Tests
├── .env                 # Your API key
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚠️ Notes
- The sidecar schema is strict (`additionalProperties: false`). Only the documented fields are written.
- For robust metadata embedding (IPTC/XMP), consider using `exiftool` or `pyexiv2`. Pillow’s JPEG metadata support is limited.
- The generator uses the Responses API with `response_format={ type: "json_schema" }`.

## 🧩 Troubleshooting
- 400 bad_request from OpenAI:
  - Ensure `OPENAI_API_KEY` is set and valid.
  - Use supported multimodal models: `gpt-4o` or `gpt-4o-mini` (`-m`).
  - Update `openai` to a recent 1.x (`pip install -U openai`).
- No output/parse error: the app raises a clear error if JSON parsing fails; re-run or try `-m gpt-4o`.
- Embed fails: Pillow can’t reliably write all JPEG/XMP fields. Use JSON sidecar (`-j`) or external tools.

## 🧾 Schema Overview
Sidecar JSON matches `schemas/ImageSidecarCopy.schema.json` and includes:
- `title: string`
- `description: string`
- `ai_generated: boolean`
- `ai_details: object` (provider, model, prompt, response_id, finish_reason, created, attempted_at, status, error, error_body, raw_response)
- `reviewed: boolean`
- `detected_at: number` (epoch seconds)

## 🧑‍💻 License
MIT
