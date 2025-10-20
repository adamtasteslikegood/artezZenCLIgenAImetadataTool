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
    parser.add_argument("--auto", action="store_true", help="Use OpenAI to automatically generate metadata")
    parser.add_argument("--embed", action="store_true", help="Embed metadata into the image file")
    parser.add_argument("--write-json", action="store_true", help="Write metadata to a JSON sidecar file")
    parser.add_argument("--model", type=str, default="gpt-4o", help="OpenAI model to use for generation")
    args = parser.parse_args()

    image_path = args.image_path
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
