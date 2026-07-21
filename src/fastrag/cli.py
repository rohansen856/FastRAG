from __future__ import annotations

import argparse
import json
from pathlib import Path

from .jobs import rebuild_documents


def main() -> None:
    parser = argparse.ArgumentParser(prog="fastrag")
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest", help="copy documents and rebuild the active index")
    ingest.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    if args.command == "ingest":
        from .config import Settings

        settings = Settings()
        target = settings.data_dir / "documents"
        target.mkdir(parents=True, exist_ok=True)
        for source in args.paths:
            if source.suffix.casefold() not in {".pdf", ".md", ".markdown", ".txt"}:
                parser.error(f"unsupported document: {source}")
            (target / source.name).write_bytes(source.read_bytes())
        print(json.dumps(rebuild_documents(), indent=2))


if __name__ == "__main__":
    main()
