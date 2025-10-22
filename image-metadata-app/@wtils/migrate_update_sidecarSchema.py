#!/usr/bin/env python3
"""
Migration tool for Image Sidecar schema updates.

Responsibilities:
1. Detect changes between the last-run schema snapshot (if any) and the
   current on-disk schema (`schemas/ImageSidecarCopy.schema.json`).
2. Ensure code responsible for generating sidecars (`core/generator.py`)
   includes newly added properties so freshly generated metadata remains valid.
3. Upgrade existing JSON sidecar files in `static/gallery/` to satisfy the
   latest schema: add new fields, prune deprecated ones, and (optionally)
   call OpenAI to populate new textual fields.

Usage example:

    python @wtils/migrate_update_sidecarSchema.py \
        --use-openai --model gpt-4o-mini
    python @wtils/migrate_update_sidecarSchema.py \
        --batch ./static/gallery --recursive
    python @wtils/migrate_update_sidecarSchema.py \
        --use-openai --watch-folder-mode ./static/gallery

The script is idempotent and can be run repeatedly. It writes a snapshot of the
current schema into `@wtils/.latest_schema_snapshot.json` to serve as the
baseline for future migrations.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    from ast import unparse as ast_unparse
except ImportError:  # pragma: no cover - Python < 3.9 is not officially supported
    ast_unparse = None  # type: ignore

SCHEMA_DEFAULT_PATH = Path("schemas") / "ImageSidecarCopy.schema.json"
SNAPSHOT_PATH = Path("@wtils") / ".latest_schema_snapshot.json"
GALLERY_PATH = Path("static") / "gallery"
GENERATOR_PATH = Path("core") / "generator.py"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".heic"}


@dataclass(frozen=True)
class SchemaDiff:
    added_top_level: set[str]
    removed_top_level: set[str]
    changed_top_level: set[str]
    added_ai_details: set[str]
    removed_ai_details: set[str]
    changed_ai_details: set[str]

    def has_changes(self) -> bool:
        return any(
            [
                self.added_top_level,
                self.removed_top_level,
                self.changed_top_level,
                self.added_ai_details,
                self.removed_ai_details,
                self.changed_ai_details,
            ]
        )


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
        f.write("\n")


def _default_for_spec(spec: Dict[str, Any]) -> Any:
    if "default" in spec:
        return spec["default"]
    spec_type = spec.get("type")
    if isinstance(spec_type, list):
        # Take the first type that has a sensible default
        for t in spec_type:
            candidate = _default_for_spec({"type": t})
            if candidate is not None:
                return candidate
        return None
    if spec_type == "string":
        return ""
    if spec_type == "boolean":
        return False
    if spec_type in {"number", "integer"}:
        return 0
    if spec_type == "array":
        return []
    if spec_type == "object":
        return {}
    # Fallback when type is omitted or is `null`
    return None


def _coerce_to_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the dict matches the provided schema shape by:
      - pruning unknown properties if `additionalProperties` is false
      - adding missing entries with defaults
      - recursively coerce nested objects
    """
    properties = schema.get("properties", {})
    additional_allowed = schema.get("additionalProperties", True)

    if not additional_allowed:
        for key in list(data.keys()):
            if key not in properties:
                data.pop(key, None)

    for key, subschema in properties.items():
        if key not in data:
            data[key] = _default_for_spec(subschema)
        else:
            if subschema.get("type") == "object" and isinstance(data.get(key), dict):
                data[key] = _coerce_to_schema(data[key], subschema)
    return data


def _diff_schemas(
    previous: Optional[Dict[str, Any]], current: Dict[str, Any]
) -> SchemaDiff:
    prev_props = (previous or {}).get("properties", {})
    curr_props = current.get("properties", {})

    added_top = set(curr_props) - set(prev_props)
    removed_top = set(prev_props) - set(curr_props)
    changed_top = {
        key
        for key in (set(prev_props) & set(curr_props))
        if prev_props[key] != curr_props[key]
    }

    prev_ai = prev_props.get("ai_details", {}).get("properties", {}) if prev_props else {}
    curr_ai = curr_props.get("ai_details", {}).get("properties", {})

    added_ai = set(curr_ai) - set(prev_ai)
    removed_ai = set(prev_ai) - set(curr_ai)
    changed_ai = {
        key for key in (set(prev_ai) & set(curr_ai)) if prev_ai[key] != curr_ai[key]
    }

    return SchemaDiff(
        added_top_level=added_top,
        removed_top_level=removed_top,
        changed_top_level=changed_top,
        added_ai_details=added_ai,
        removed_ai_details=removed_ai,
        changed_ai_details=changed_ai,
    )


def _schema_default_ast(spec: Dict[str, Any]) -> ast.expr:
    value = _default_for_spec(spec)
    if isinstance(value, bool):
        return ast.Constant(value=value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ast.Constant(value=value)
    if isinstance(value, str):
        return ast.Constant(value=value)
    if value == []:
        return ast.List(elts=[], ctx=ast.Load())
    if value == {}:
        return ast.Dict(keys=[], values=[])
    if value is None:
        return ast.Constant(value=None)
    # Fallback to repr string for any unhandled cases
    return ast.Constant(value=value)


class GeneratorSidecarUpdater(ast.NodeTransformer):
    """Ensures the sidecar dict literal aligns with schema properties."""

    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.modified = False

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "sidecar"
            and isinstance(node.value, ast.Dict)
        ):
            node.value = self._update_sidecar_dict(node.value)
            ast.fix_missing_locations(node.value)
            return node
        return self.generic_visit(node)

    def _update_sidecar_dict(self, dict_node: ast.Dict) -> ast.Dict:
        properties = self.schema.get("properties", {})
        existing_keys: Dict[str, int] = {}
        for idx, key_node in enumerate(dict_node.keys):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                existing_keys[key_node.value] = idx

        for prop_name, prop_spec in properties.items():
            if prop_name in existing_keys:
                idx = existing_keys[prop_name]
                if prop_name == "ai_details" and isinstance(dict_node.values[idx], ast.Dict):
                    dict_node.values[idx] = self._update_ai_details_dict(
                        dict_node.values[idx], prop_spec
                    )
                    ast.fix_missing_locations(dict_node.values[idx])
                continue

            value_node = self._build_value_for_property(prop_name, prop_spec)
            dict_node.keys.append(ast.Constant(value=prop_name))
            dict_node.values.append(value_node)
            existing_keys[prop_name] = len(dict_node.keys) - 1
            self.modified = True

        # Prune properties removed from schema if they exist and additionalProperties is false
        allowed = set(properties)
        for idx in reversed(range(len(dict_node.keys))):
            key_node = dict_node.keys[idx]
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                if key_node.value not in allowed:
                    dict_node.keys.pop(idx)
                    dict_node.values.pop(idx)
                    self.modified = True
        return dict_node

    def _update_ai_details_dict(self, dict_node: ast.Dict, schema: Dict[str, Any]) -> ast.Dict:
        props = schema.get("properties", {})
        existing: Dict[str, int] = {}
        for idx, key_node in enumerate(dict_node.keys):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                existing[key_node.value] = idx

        for prop_name, prop_spec in props.items():
            if prop_name in existing:
                continue
            dict_node.keys.append(ast.Constant(value=prop_name))
            dict_node.values.append(self._schema_default_value(prop_spec))
            self.modified = True

        allowed = set(props)
        for idx in reversed(range(len(dict_node.keys))):
            key_node = dict_node.keys[idx]
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                if key_node.value not in allowed:
                    dict_node.keys.pop(idx)
                    dict_node.values.pop(idx)
                    self.modified = True
        return dict_node

    def _schema_default_value(self, spec: Dict[str, Any]) -> ast.expr:
        return _schema_default_ast(spec)

    def _build_value_for_property(self, name: str, spec: Dict[str, Any]) -> ast.expr:
        if name == "ai_details":
            nested = ast.Dict(keys=[], values=[])
            return self._update_ai_details_dict(nested, spec)

        getter = ast.Name(id="model_obj", ctx=ast.Load())
        call = ast.Call(
            func=ast.Attribute(value=getter, attr="get", ctx=ast.Load()),
            args=[ast.Constant(value=name), self._schema_default_value(spec)],
            keywords=[],
        )
        return call


def _ensure_generator_matches_schema(schema: Dict[str, Any]) -> bool:
    """
    Update `core/generator.py` so its sidecar literal includes any new schema
    properties. Returns True if the file was modified.
    """
    if ast_unparse is None:
        print("⚠️  Python runtime lacks ast.unparse; skipping generator refactor.", file=sys.stderr)
        return False

    source_path = GENERATOR_PATH
    original_text = source_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(original_text)
    except SyntaxError as exc:  # pragma: no cover - defensive
        print(f"⚠️  Unable to parse {source_path}: {exc}", file=sys.stderr)
        return False

    updater = GeneratorSidecarUpdater(schema)
    updated_tree = updater.visit(tree)
    ast.fix_missing_locations(updated_tree)

    if not updater.modified:
        return False

    new_text = ast_unparse(updated_tree)
    source_path.write_text(new_text + "\n", encoding="utf-8")
    return True


def _iter_sidecars_in_dir(directory: Path, recursive: bool) -> Iterable[Path]:
    iterator = directory.rglob("*.json") if recursive else directory.glob("*.json")
    for path in iterator:
        if path.is_file():
            yield path


def _iter_images_in_dir(directory: Path, recursive: bool) -> Iterable[Path]:
    iterator = directory.rglob("*") if recursive else directory.glob("*")
    for path in iterator:
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def _find_image_for_sidecar(sidecar_path: Path) -> Optional[Path]:
    stem = sidecar_path.stem
    for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".heic"]:
        candidate = sidecar_path.with_name(stem + ext)
        if candidate.exists():
            return candidate
    return None


def _find_sidecar_for_image(image_path: Path) -> Path:
    return image_path.with_suffix(".json")


def _generate_metadata_for_image(image_path: Path, model: str) -> Optional[Dict[str, Any]]:
    try:
        from core.generator import generate_metadata_from_image
    except Exception as exc:  # pragma: no cover - defensive
        print(f"⚠️  Unable to import generator: {exc}", file=sys.stderr)
        return None

    try:
        return generate_metadata_from_image(str(image_path), model=model)
    except Exception as exc:
        print(f"⚠️  OpenAI generation failed for {image_path.name}: {exc}", file=sys.stderr)
        return None


def _should_use_llm_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _migrate_sidecar_file(
    sidecar_path: Path,
    schema: Dict[str, Any],
    diff: SchemaDiff,
    use_openai: bool,
    model: str,
    dry_run: bool,
) -> bool:
    original_data = _load_json(sidecar_path)
    migrated = json.loads(json.dumps(original_data))  # deep copy

    migrated = _coerce_to_schema(migrated, schema)

    llm_payload: Optional[Dict[str, Any]] = None
    if use_openai and diff.added_top_level:
        image_path = _find_image_for_sidecar(sidecar_path)
        if image_path:
            llm_payload = _generate_metadata_for_image(image_path, model)
        else:
            print(
                f"⚠️  No companion image found for {sidecar_path.name}; skipping OpenAI enrichment.",
                file=sys.stderr,
            )

    new_fields = diff.added_top_level
    for field in new_fields:
        if field == "ai_details":
            continue
        spec = schema["properties"][field]
        if _should_use_llm_value(migrated.get(field)) and llm_payload:
            candidate = llm_payload.get(field)
            if candidate not in (None, "", []):
                migrated[field] = candidate

    if "ai_details" in schema.get("properties", {}):
        details_spec = schema["properties"]["ai_details"]
        details_props = details_spec.get("properties", {})
        migrated.setdefault("ai_details", {})
        migrated["ai_details"] = _coerce_to_schema(migrated["ai_details"], details_spec)

        if llm_payload and "ai_details" in llm_payload:
            for field in diff.added_ai_details:
                candidate = llm_payload["ai_details"].get(field)
                if candidate not in (None, "", []):
                    migrated["ai_details"][field] = candidate

    if migrated == original_data:
        return False

    if dry_run:
        print(f"🛈 Would update {sidecar_path}")
        return False

    _dump_json(sidecar_path, migrated)
    print(f"✅ Updated {sidecar_path}")
    return True


def _resolve_sidecar_targets(
    gallery_path: Path,
    batch_inputs: Optional[Iterable[Path]],
    recursive: bool,
) -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()

    def add_target(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            targets.append(resolved)
            seen.add(resolved)

    def handle_entry(entry_path: Path) -> None:
        if entry_path.is_dir():
            for candidate in _iter_sidecars_in_dir(entry_path, recursive):
                add_target(candidate)
            return

        suffix = entry_path.suffix.lower()
        if suffix == ".json":
            if entry_path.exists():
                add_target(entry_path)
            else:
                print(f"⚠️  Sidecar file not found: {entry_path}", file=sys.stderr)
            return

        if suffix in IMAGE_EXTENSIONS:
            sidecar = _find_sidecar_for_image(entry_path)
            if sidecar.exists():
                add_target(sidecar)
            else:
                print(
                    f"⚠️  No sidecar found for image {entry_path}; will rely on watch mode or manual generation.",
                    file=sys.stderr,
                )
            return

        print(f"⚠️  Unsupported --batch item: {entry_path}", file=sys.stderr)

    if batch_inputs:
        for raw in batch_inputs:
            path = raw if raw.is_absolute() else (Path.cwd() / raw)
            if path.suffix.lower() == ".csv":
                try:
                    with path.open("r", encoding="utf-8") as csv_file:
                        reader = csv.reader(csv_file)
                        for row in reader:
                            if not row:
                                continue
                            candidate = row[0].strip()
                            if not candidate:
                                continue
                            candidate_path = (path.parent / candidate).resolve()
                            handle_entry(candidate_path)
                except Exception as exc:
                    print(f"⚠️  Failed to read CSV {path}: {exc}", file=sys.stderr)
                continue

            handle_entry(path.resolve())

    if not targets:
        for sidecar in _iter_sidecars_in_dir(gallery_path, recursive):
            add_target(sidecar)

    return targets


def _print_diff_summary(diff: SchemaDiff) -> None:
    if not diff.has_changes():
        print("No schema differences detected since the last snapshot.")
        return

    def fmt(items: Iterable[str]) -> str:
        return ", ".join(sorted(items)) if items else "—"

    print("Schema changes detected:")
    print(f"  • Added top-level fields: {fmt(diff.added_top_level)}")
    print(f"  • Removed top-level fields: {fmt(diff.removed_top_level)}")
    print(f"  • Changed top-level fields: {fmt(diff.changed_top_level)}")
    print(f"  • Added ai_details fields: {fmt(diff.added_ai_details)}")
    print(f"  • Removed ai_details fields: {fmt(diff.removed_ai_details)}")
    print(f"  • Changed ai_details fields: {fmt(diff.changed_ai_details)}")


def watch_directory_for_new_images(
    directory: Path,
    schema: Dict[str, Any],
    model: str,
    dry_run: bool,
    recursive: bool,
) -> None:
    directory = directory.resolve()
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Watch directory not found or not a directory: {directory}")

    print(
        f"👀 Watching {directory} for new images without sidecars "
        f"({'recursive' if recursive else 'non-recursive'}). Press Ctrl+C to stop."
    )
    pending: dict[Path, float] = {}
    processed: set[Path] = set()

    try:
        while True:
            now = time.monotonic()
            for image_path in _iter_images_in_dir(directory, recursive):
                resolved_image = image_path.resolve()
                if resolved_image in processed:
                    continue
                sidecar_path = _find_sidecar_for_image(resolved_image)
                if sidecar_path.exists():
                    processed.add(resolved_image)
                    pending.pop(resolved_image, None)
                    continue
                pending.setdefault(resolved_image, now)

            ready_to_process: list[Path] = []
            for image_path, first_seen in list(pending.items()):
                sidecar_path = _find_sidecar_for_image(image_path)
                if sidecar_path.exists():
                    processed.add(image_path)
                    pending.pop(image_path, None)
                    continue
                if now - first_seen >= 60:
                    ready_to_process.append(image_path)

            for image_path in ready_to_process:
                sidecar_path = _find_sidecar_for_image(image_path)
                if sidecar_path.exists():
                    processed.add(image_path)
                    pending.pop(image_path, None)
                    continue

                print(f"✨ Generating sidecar for {image_path.name}")
                if dry_run:
                    print(f"🛈 Dry-run: would create {sidecar_path}")
                    processed.add(image_path)
                    pending.pop(image_path, None)
                    continue

                payload = _generate_metadata_for_image(image_path, model)
                if not payload:
                    print(f"⚠️  Failed to generate metadata for {image_path}", file=sys.stderr)
                    pending[image_path] = time.monotonic()  # reset timer to retry later
                    continue

                payload = _coerce_to_schema(payload, schema)
                _dump_json(sidecar_path, payload)
                print(f"✅ Created sidecar {sidecar_path}")
                processed.add(image_path)
                pending.pop(image_path, None)

            time.sleep(5)
    except KeyboardInterrupt:
        print("🛑 Watch mode interrupted by user.")


def migrate(
    schema_path: Path,
    gallery_path: Path,
    snapshot_path: Path,
    use_openai: bool,
    model: str,
    dry_run: bool,
    batch_inputs: Optional[Iterable[Path]] = None,
    recursive: bool = False,
) -> Dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    schema = _load_json(schema_path)
    previous = _load_json(snapshot_path) if snapshot_path.exists() else None
    diff = _diff_schemas(previous, schema)
    _print_diff_summary(diff)

    generator_modified = _ensure_generator_matches_schema(schema)
    if generator_modified:
        print("✅ Updated core/generator.py with new schema fields.")

    sidecar_paths = _resolve_sidecar_targets(
        gallery_path=gallery_path,
        batch_inputs=batch_inputs,
        recursive=recursive,
    )
    if not sidecar_paths:
        if batch_inputs:
            print("No sidecar files found for supplied --batch inputs.")
        else:
            print(f"No sidecar files found in {gallery_path}")
    else:
        print(f"Scanning {len(sidecar_paths)} existing sidecar file(s)...")

    for sidecar in sidecar_paths:
        _migrate_sidecar_file(sidecar, schema, diff, use_openai, model, dry_run)

    if not dry_run:
        _dump_json(snapshot_path, schema)
        print(f"Snapshot wrote to {snapshot_path}")

    return schema


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update code and JSON sidecars to align with the latest schema version.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            OpenAI usage:
              Supply --use-openai to populate new textual fields via the Responses API.
              Ensure OPENAI_API_KEY is present in the environment and that the model
              you specify is available to your account.
            """
        ),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=SCHEMA_DEFAULT_PATH,
        help="Path to the JSON Schema file. Defaults to schemas/ImageSidecarCopy.schema.json",
    )
    parser.add_argument(
        "--gallery",
        type=Path,
        default=GALLERY_PATH,
        help="Directory containing image sidecar JSON files.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=SNAPSHOT_PATH,
        help="Path for storing the previous schema snapshot.",
    )
    parser.add_argument(
        "--use-openai",
        action="store_true",
        help="Call OpenAI (via core.generator) to fill new fields when possible.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use when --use-openai is enabled.",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        action="append",
        help=(
            "Process specific items: accepts JSON sidecars, image files (will look for matching JSON), "
            "directories, or CSV files listing paths (first column). May be used multiple times."
        ),
    )
    parser.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        help="When directories are supplied (via --batch or --gallery), process subdirectories recursively.",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Limit directory processing to the top level (default).",
    )
    parser.set_defaults(recursive=False)
    parser.add_argument(
        "--watch-folder-mode",
        type=Path,
        help=(
            "Watch a directory for new images missing sidecars. Requires --use-openai to generate metadata. "
            "Continues running until interrupted."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files or snapshots.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    try:
        schema = migrate(
            schema_path=args.schema,
            gallery_path=args.gallery,
            snapshot_path=args.snapshot,
            use_openai=args.use_openai,
            model=args.model,
            dry_run=args.dry_run,
            batch_inputs=args.batch,
            recursive=args.recursive,
        )
        if args.watch_folder_mode:
            if not args.use_openai:
                print(
                    "⚠️  --watch-folder-mode requires --use-openai to call OpenAI for metadata generation.",
                    file=sys.stderr,
                )
                return
            watch_directory_for_new_images(
                directory=args.watch_folder_mode,
                schema=schema,
                model=args.model,
                dry_run=args.dry_run,
                recursive=args.recursive,
            )
    except Exception as exc:  # pragma: no cover - entrypoint guard
        print(f"❌ Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main(sys.argv[1:])
