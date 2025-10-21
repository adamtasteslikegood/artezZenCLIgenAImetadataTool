# 🖼️ Image Metadata Generator

A command-line utility that generates, validates, embeds, and exports structured metadata (title, description, caption, tags) for image files using OpenAI’s latest Responses API with strict JSON schema.

## 🚀 Features
- ✨ Generate metadata via OpenAI Responses API (default: `gpt-4o-mini`)
- 🧠 Strict JSON output enforced by the repo’s JSON Schema
- 🧷 Embed metadata into image files (basic key/value; JSON sidecar recommended)
- 📄 Export metadata as a `.json` sidecar
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

Pick a specific model (multimodal):
```bash
python main.py ./static/gallery/your_photo.jpg -a -m gpt-4o
```

## 📂 Structure
```
image-metadata-app/
├── core/                # Main logic
├── cli/                 # (Reserved) extra CLI modules
├── utils/               # Validation helpers
├── schemas/             # JSON Schemas
├── static/gallery/      # Your images
├── tests/               # Tests
├── .env                 # Your API key
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚠️ Notes
- For robust metadata embedding (IPTC/XMP), consider using `exiftool` or `pyexiv2`. Pillow’s JPEG metadata support is limited.
- The generator returns strict JSON using `response_format="json"` to avoid brittle parsing.

## 🧩 Troubleshooting
- 400 bad_request from OpenAI:
  - Ensure `OPENAI_API_KEY` is set and valid.
  - Use supported multimodal models: `gpt-4o` or `gpt-4o-mini` (`-m`).
  - Update `openai` to a recent 1.x (`pip install -U openai`).
- No output/parse error: the app raises a clear error if JSON parsing fails; re-run or try `-m gpt-4o`.
- Embed fails: Pillow can’t reliably write all JPEG/XMP fields. Use JSON sidecar (`-j`) or external tools.

## 🧑‍💻 License
MIT
