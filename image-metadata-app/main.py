import argparse
import os
import json
from core.generator import generate_metadata_from_image
from core.embedder import embed_metadata, create_json_sidecar
from utils.validation import validate_or_print
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="AI-powered Image Metadata Generator")
    parser.add_argument("image_path", help="Path to the image file")
    # Core action flags with short forms
    parser.add_argument("-a", "--auto", action="store_true", help="Use OpenAI to automatically generate metadata")
    parser.add_argument("-e", "--embed", action="store_true", help="Embed metadata into the image file")
    parser.add_argument(
        "-j",
        "--write-json",
        "--json",
        "--create-json",
        dest="write_json",
        action="store_true",
        help="Write metadata to a JSON sidecar file",
    )
    # Convenience combo flag
    parser.add_argument(
        "-f",
        "--full",
        action="store_true",
        help="Do everything: --auto + --embed + --write-json",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use (multimodal, e.g. gpt-4o or gpt-4o-mini)",
    )
    args = parser.parse_args()

    image_path = args.image_path
    # Expand combo flag
    if args.full:
        args.auto = True
        args.embed = True
        args.write_json = True

    # Guard for API key when auto-generation is requested
    if args.auto and not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set. Add it to .env or environment.")
        return
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return

    # Step 1: Generate or collect metadata
    if args.auto:
        print("🔮 Generating metadata using OpenAI...")
        metadata = generate_metadata_from_image(image_path, model=args.model)
    else:
        print("⚙️  Manual mode: please enter metadata fields.")
        metadata = {
            "title": input("Title: "),
            "description": input("Description: "),
            "caption": input("Caption: "),
            "tags": [t.strip() for t in input("Tags (comma-separated): ").split(",") if t.strip()],
        }

    # Step 2: Validate metadata
    validate_or_print(metadata)

    # Step 3: Embed and/or write JSON
    if args.embed:
        print("🧷 Embedding metadata into image...")
        embed_metadata(image_path, metadata)

    if args.write_json:
        print("💾 Writing JSON sidecar...")
        create_json_sidecar(image_path, metadata)

    print("✅ Done!")

if __name__ == "__main__":
    main()
