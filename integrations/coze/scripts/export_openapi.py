"""Export or check the 11 Skill documents without starting the backend."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import backend_url, read_config
from app.openapi import TEMPLATE_BASE_URL, export_documents


def serialize(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--site", choices=("cn", "global"), help="Use only this site's BACKEND_BASE_URL from the config file.")
    source.add_argument("--base-url", help="Public HTTPS backend base URL, optionally with a proxy prefix.")
    parser.add_argument("--env-file", type=Path, help="Config file for --site (defaults to integrations/coze/.env); requires --site.")
    parser.add_argument("--output-dir", type=Path, help="Destination; defaults to schemas for templates, output/schemas/<site|custom> otherwise.")
    parser.add_argument("--check", action="store_true", help="Validate and compare existing documents without writing files.")
    args = parser.parse_args(argv)
    if args.env_file is not None and args.site is None:
        parser.error("--env-file requires --site cn or --site global")
    try:
        from openapi_spec_validator import OpenAPIV30SpecValidator
        from jsonschema.exceptions import ValidationError
    except ImportError:
        print("Install the locked dev dependencies to export and validate schemas.", file=sys.stderr)
        return 1
    try:
        base = args.base_url if args.base_url is not None else TEMPLATE_BASE_URL
        if args.site:
            key = f"COZE_{args.site.upper()}_BACKEND_BASE_URL"
            try:
                values = read_config(args.env_file or ROOT / ".env")
            except ValueError:
                print("Export failed: the configuration file is missing or invalid.", file=sys.stderr)
                return 1
            base = values.get(key, "")
            if not base:
                print(f"Export failed: set {key} before exporting deployment schemas.", file=sys.stderr)
                return 1
        try:
            base = backend_url(base)
        except ValueError:
            print("Export failed: use an HTTPS backend domain and optional proxy prefix, without credentials, query or fragment; platform API domains and IP addresses are not supported.", file=sys.stderr)
            return 1
        output = args.output_dir or (ROOT / "output" / "schemas" / (args.site or "custom")
                                    if args.site or args.base_url else ROOT / "schemas")
        documents = export_documents(base)
        # Validate every document before any file is written. Only local refs are generated.
        for document in documents.values():
            OpenAPIV30SpecValidator(document).validate()
        rendered = {skill + ".json": serialize(doc) for skill, doc in documents.items()}
        if args.check:
            different = [name for name, value in rendered.items()
                         if not (output / name).is_file() or (output / name).read_text(encoding="utf-8") != value]
            extra = {path.name for path in output.glob("*.json")} - rendered.keys()
            if different or extra:
                print("Schema files are missing, stale or unexpected; regenerate into a dedicated directory.", file=sys.stderr)
                return 1
        else:
            if {path.name for path in output.glob("*.json")} - rendered.keys():
                raise ValueError("The output directory contains unexpected JSON files; use a dedicated directory.")
            output.mkdir(parents=True, exist_ok=True)
            for name, content in rendered.items():
                (output / name).write_text(content, encoding="utf-8", newline="\n")
        print(f"{'Checked' if args.check else 'Exported'} 11 OpenAPI 3.0.3 documents / 24 tools ({args.site or ('custom' if args.base_url else 'templates')}).")
        return 0
    except (OSError, UnicodeError, ValueError, ValidationError):
        # Never print configuration values, paths or raw schema validation errors.
        print("Export failed: check the backend URL, configuration, schema compatibility and output directory.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
