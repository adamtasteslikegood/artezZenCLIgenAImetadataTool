import argparse
import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from core.embedder import create_json_sidecar, embed_metadata
from core.generator import generate_metadata_from_image
from utils.validation import validate_file_and_log, validate_or_print

# Load environment variables
load_dotenv()

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".gif",
    ".webp",
}
WATCH_DELAY_SECONDS = 60
WATCH_POLL_SECONDS = 5


def parse_csv_for_images(csv_path: str) -> list[Path]:
    path = Path(csv_path).expanduser()
    if not path.exists():
        raise ValueError(f"CSV file not found: {csv_path}")

    images: list[Path] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            try:
                sample = handle.read(1024)
                handle.seek(0)
                has_header = csv.Sniffer().has_header(sample)
            except csv.Error:
                handle.seek(0)
                has_header = False

            if has_header:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    return images

                normalized = {name.lower(): name for name in reader.fieldnames}
                column_name = None
                for candidate in ("image_path", "path", "file", "filepath"):
                    if candidate in normalized:
                        column_name = normalized[candidate]
                        break

                if column_name is None:
                    raise ValueError(
                        "CSV must include an 'image_path' column or be a single-column list of paths."
                    )

                for row in reader:
                    value = (row.get(column_name) or "").strip()
                    if value:
                        images.append(Path(value).expanduser())
            else:
                reader = csv.reader(handle)
                for row in reader:
                    if not row:
                        continue
                    value = row[0].strip()
                    if value:
                        images.append(Path(value).expanduser())
    except csv.Error as exc:
        raise ValueError(f"Failed to parse CSV {csv_path}: {exc}") from exc

    return images


def find_images_in_directory(directory: Path, recursive: bool) -> list[Path]:
    if not directory.exists():
        raise ValueError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    iterator = directory.rglob("*") if recursive else directory.iterdir()
    files = []
    for candidate in iterator:
        if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            files.append(candidate)

    return files


def has_sidecar(image_path: Path) -> bool:
    return image_path.with_suffix(".json").exists()


@dataclass
class ProcessResult:
    success: bool
    sidecar_written: bool
    excluded: bool = False


def process_image(image_path: Path, args, log_path: Path) -> ProcessResult:
    if not image_path.exists():
        print(f"❌ File not found: {image_path}")
        return ProcessResult(success=False, sidecar_written=False, excluded=True)
    if not image_path.is_file():
        print(f"⚠️  Skipping non-file: {image_path}")
        return ProcessResult(success=False, sidecar_written=False, excluded=True)

    image_str = str(image_path)
    if args.auto:
        print(f"🔮 Generating metadata using OpenAI -> {image_path}")
        metadata = generate_metadata_from_image(image_str, model=args.model)
    else:
        print(f"⚙️  Manual mode for {image_path}: please enter metadata fields.")
        now = int(time.time())
        metadata = {
            "title": input("Title: "),
            "description": input("Description: "),
            "ai_generated": False,
            "ai_details": {},
            "reviewed": False,
            "detected_at": now,
        }

    validate_or_print(metadata)

    sidecar_written = False
    if args.embed:
        print(f"🧷 Embedding metadata into {image_path}...")
        embed_metadata(image_str, metadata)

    if args.write_json:
        print(f"💾 Writing JSON sidecar for {image_path}...")
        create_json_sidecar(image_str, metadata)
        sidecar_written = True

        json_path = image_path.with_suffix(".json")
        ok, _ = validate_file_and_log(str(json_path), str(log_path))
        if not ok:
            print("⚠️  Sidecar failed schema validation; kept file.")
            print(f"   Logged to: {log_path}")

    print(f"✅ Finished {image_path}")
    return ProcessResult(success=True, sidecar_written=sidecar_written)


def collect_images(args) -> list[Path]:
    images: list[Path] = []
    seen: set[Path] = set()

    def add_candidate(candidate: Path) -> None:
        normalized = candidate.expanduser()
        if normalized not in seen:
            images.append(normalized)
            seen.add(normalized)

    if args.image_path:
        add_candidate(Path(args.image_path))

    if args.batch:
        for candidate in args.batch:
            add_candidate(Path(candidate))

    if args.csv_path:
        for candidate in parse_csv_for_images(args.csv_path):
            add_candidate(candidate)

    if args.directory:
        directory = Path(args.directory).expanduser()
        for candidate in find_images_in_directory(directory, args.recursive):
            add_candidate(candidate)

    return images


def watch_folder(directory: Path, args, log_path: Path) -> None:
    pending: dict[Path, float] = {}
    processed: set[Path] = set()

    print(f"👀 Watching {directory} for new images (processing after {WATCH_DELAY_SECONDS}s without sidecar)...")
    try:
        while True:
            current_images = find_images_in_directory(directory, recursive=True)
            observed = set(current_images)

            # Drop pending entries for files that disappeared
            for tracked in list(pending.keys()):
                if tracked not in observed:
                    pending.pop(tracked, None)

            for image_path in current_images:
                if image_path in processed:
                    continue
                if has_sidecar(image_path):
                    processed.add(image_path)
                    pending.pop(image_path, None)
                    continue

                now = time.time()
                first_seen = pending.get(image_path)
                if first_seen is None:
                    pending[image_path] = now
                    print(f"📸 Detected new image: {image_path}")
                    continue

                if now - first_seen < WATCH_DELAY_SECONDS:
                    continue

                if has_sidecar(image_path):
                    processed.add(image_path)
                    pending.pop(image_path, None)
                    continue

                print(f"⚙️  Processing {image_path} after wait period")
                result = process_image(image_path, args, log_path)
                if result.success:
                    processed.add(image_path)
                pending.pop(image_path, None)

            time.sleep(WATCH_POLL_SECONDS)
    except KeyboardInterrupt:
        print("\n👋 Stopping watch mode.")


def main():
    parser = argparse.ArgumentParser(description="AI-powered Image Metadata Generator")
    parser.add_argument("image_path", nargs="?", help="Path to a single image file")
    parser.add_argument("--batch", nargs="+", help="Paths to multiple image files to process")
    parser.add_argument("--csv", dest="csv_path", help="CSV file with an 'image_path' column or single column of paths")
    parser.add_argument(
        "-d",
        "--directory",
        help="Process every supported image in a directory",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When --directory is used, include images in sub-folders (default: False)",
    )
    parser.add_argument(
        "--watch-folder-mode",
        dest="watch_folder_path",
        metavar="DIRECTORY",
        help="Watch a directory for new images without sidecars and process them automatically",
    )
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

    # Expand combo flag
    if args.full:
        args.auto = True
        args.embed = True
        args.write_json = True

    # Guard for API key when auto-generation is requested
    if args.auto and not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set. Add it to .env or environment.")
        return

    log_path = Path(__file__).resolve().parent / "logs" / "validation_failures.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    watch_directory_arg = args.watch_folder_path
    if watch_directory_arg:
        if not args.auto:
            print("❌ Watch mode requires --auto so metadata can be generated unattended.")
            return
        directory = Path(watch_directory_arg).expanduser()
        try:
            watch_folder(directory, args, log_path)
        except ValueError as err:
            print(f"❌ {err}")
        return

    try:
        images = collect_images(args)
    except ValueError as err:
        print(f"❌ {err}")
        return

    if not images:
        parser.error("No images provided. Supply a path, --batch, --csv, or --directory.")

    results: list[ProcessResult] = []
    for path in images:
        try:
            result = process_image(path, args, log_path)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Unexpected error while processing {path}: {exc}")
            results.append(ProcessResult(success=False, sidecar_written=False, excluded=False))
            continue
        results.append(result)

    total_files = len(images)
    sidecars_created = sum(1 for item in results if item.sidecar_written)
    errors = sum(1 for item in results if not item.success and not item.excluded)
    excluded = sum(1 for item in results if item.excluded)

    summary = (
        "✅ Finished processing all images.\n"
        f"Processed {total_files} file{'s' if total_files != 1 else ''}. "
        f"Generated: {sidecars_created} JSON sidecar file{'s' if sidecars_created != 1 else ''}. "
        f"Errors: {errors}. "
        f"Excluded: {excluded}."
    )
    print(summary)
    if errors:
        print("⚠️  Finished with some errors. Review the log above.")


if __name__ == "__main__":
    main()
