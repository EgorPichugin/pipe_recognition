#!/usr/bin/env python3
"""Combine all per-image OCR JSON files in a folder into a single text file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = REPO_ROOT / "out" / "ocr"
DEFAULT_NAME = "all_results.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="Folder with per-image .json files.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Output text file name (saved into --dir).")
    args = parser.parse_args()

    json_files = sorted(p for p in args.dir.glob("*.json") if p.is_file())
    if not json_files:
        print(f"No JSON files in {args.dir}")
        return 1

    out_path = args.dir / args.name
    chunks: list[str] = []
    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        header = f"=== {jf.name} ==="
        body = json.dumps(data, ensure_ascii=False, indent=2)
        chunks.append(f"{header}\n{body}\n")

    out_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"Wrote {len(json_files)} JSONs into {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
