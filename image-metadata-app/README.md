# 🖼️ Image Metadata Generator

A command-line utility that generates, validates, embeds, and exports structured metadata (title, description, caption, tags) for image files using OpenAI’s GPT models.

## 🚀 Features
- ✨ Generate metadata via OpenAI (GPT-4o by default)
- 🧠 Validate metadata against a JSON Schema
- 🧷 Embed metadata into image files (basic key/value; JSON sidecar recommended)
- 📄 Export metadata as a `.json` sidecar
- 🖥️ CLI now; interactive mode coming next

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
Auto-generate with OpenAI, validate, embed and write JSON:
```bash
python main.py ./static/gallery/your_photo.jpg --auto --embed --write-json
```

Manual input mode (no API call):
```bash
python main.py ./static/gallery/your_photo.jpg --embed --write-json
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

## 🧑‍💻 License
MIT
