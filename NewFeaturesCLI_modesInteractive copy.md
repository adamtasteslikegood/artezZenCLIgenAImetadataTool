🖥️ CLI Modes
-------------

| Mode | Command | Description |
| --- | --- | --- |
| **Auto CLI** | `--auto` | Use OpenAI to auto-generate |
| **Manual CLI** | `--title`, `--caption`, etc. | For power users |
| **Interactive Mode** | `--interactive` | Text-based UI (new) |

* * *

🧠 New Feature: Interactive Mode
--------------------------------

### ✅ How It Works

If the user runs:

```bash
python main.py --interactive
```

It launches a prompt-driven interface:

```
📸 Welcome to AI Photo Metadata Tool!

1. Select an image: [file chooser or prompt]
2. Would you like AI to generate metadata? (Y/n)
3. [If no, prompt for each field]
4. Save metadata to:
   [✓] Embed in image
   [✓] JSON sidecar
5. Confirm and run.

[Done!]
```

* * *

🔧 Implementation Strategy
--------------------------

### 1\. Create `interactive.py`

```python
import questionary
from pathlib import Path
from core.generator import generate_metadata_from_image
from core.embedder import embed_metadata, create_json_sidecar

def run_interactive():
    print("📸 Welcome to AI Photo Metadata Tool (Interactive Mode)")

    image_path = questionary.path("Select an image:").ask()
    use_ai = questionary.confirm("Generate metadata using AI?").ask()

    if use_ai:
        metadata = generate_metadata_from_image(Path(image_path))
    else:
        metadata = {
            "title": questionary.text("Title:").ask(),
            "description": questionary.text("Description:").ask(),
            "caption": questionary.text("Caption:").ask(),
            "tags": questionary.text("Tags (comma-separated):").ask().split(","),
            "author": questionary.text("Author (optional):").ask(),
            "location": questionary.text("Location (optional):").ask()
        }
        metadata = {k: v for k, v in metadata.items() if v}

    output_opts = questionary.checkbox(
        "How would you like to save the metadata?",
        choices=[
            {"name": "Embed in image", "value": "embed"},
            {"name": "Save JSON sidecar", "value": "json"}
        ]
    ).ask()

    if "embed" in output_opts:
        embed_metadata(Path(image_path), metadata)
    if "json" in output_opts:
        create_json_sidecar(Path(image_path), metadata)

    print("✅ Done!")
```

> Uses `questionary` for elegant prompts:

```bash
pip install questionary
```

* * *

### 2\. Update `main.py`

```python
import argparse
from cli.interactive import run_interactive
from cli.main import run_cli  # the flag-based CLI version

def main():
    parser = argparse.ArgumentParser(description="AI Photo Metadata CLI")
    parser.add_argument('--interactive', action='store_true', help='Run in interactive UI mode')
    args, unknown = parser.parse_known_args()

    if args.interactive:
        run_interactive()
    else:
        run_cli(unknown)

if __name__ == "__main__":
    main()
```

> `run_cli()` just wraps your current CLI logic.

* * *

🪄 Extra Suggestions
--------------------

| Feature | Benefit |
| --- | --- |
| `.ini`/`.yaml` config support | Save preferred defaults (e.g. default tags or author) |
| `--watch` mode | Auto-process images dropped into a folder |
| `--batch` mode | Run on all `.jpg` in a directory |
| TUI (Text UI) via `textual` or `rich` | GUI-like terminal interface |
| Export to HTML snippet | For quick static galleries |

* * *

Would you like me to generate this full modular repo scaffold for you as downloadable code, or continue piece-by-piece starting with the new `interactive.py`?

## Prompt:
i’m into all the suggested additions that you just mentioned and for now lets go ahead with piece by piece..

## Response:
Perfect — we’ll go step by step and make this modular, clean, and scalable. Here’s how we’ll proceed:

* * *