#!/usr/bin/env python3
"""Roll up all per-image GPS JSONs into a single CSV + Markdown table.

Reads ``*.json`` files produced by extract_gps_paddle_v2.py (or any of the
GPS extractor variants) in a folder and emits two summary files in the same
folder:
- ``gps_summary.csv``  — for spreadsheets / scripts
- ``gps_summary.md``   — for quick visual check in any markdown viewer

Each row carries the image filename, overall flag, lat/lon decimal values,
the raw OCR substrings that produced them (so you can eyeball them against
the watermark on the photo), and OCR confidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_DIR = Path("/Users/olegkulikov/Desktop/hackathon Vienna/photo/GeoData")
CSV_NAME = "gps_summary.csv"
MD_NAME = "gps_summary.md"

COLUMNS = [
    "filename",
    "lat",
    "lon",
    "confidence_level",
]


def gather_rows(json_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(json_dir.glob("*.json")):
        if path.name in {CSV_NAME, MD_NAME}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "overall_flag" not in data:
            continue
        gps = data.get("gps") or {}
        lat = gps.get("lat") or {}
        lon = gps.get("lon") or {}
        rows.append({
            "filename": data.get("image", path.stem),
            "lat": lat.get("decimal", ""),
            "lon": lon.get("decimal", ""),
            "confidence_level": data.get("overall_flag", ""),
        })
    return rows


def write_csv(rows: list[dict], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_md(rows: list[dict], out_path: Path) -> None:
    flag_order = {"GPS_HIGH": 0, "GPS_LOW": 1, "NO_GPS": 2, "": 3}
    rows_sorted = sorted(rows, key=lambda r: (flag_order.get(r["confidence_level"], 9), r["filename"]))

    lines: list[str] = []
    lines.append(f"# GPS extraction summary ({len(rows)} images)\n")

    summary: dict[str, int] = {}
    for r in rows:
        summary[r["confidence_level"]] = summary.get(r["confidence_level"], 0) + 1
    lines.append("**Flag counts:**")
    for flag, count in sorted(summary.items(), key=lambda kv: flag_order.get(kv[0], 9)):
        lines.append(f"- `{flag or '(missing)'}` — {count}")
    lines.append("")

    lines.append("| # | filename | lat | lon | confidence_level |")
    lines.append("|---|---|---|---|---|")
    for idx, r in enumerate(rows_sorted, 1):
        lat = r["lat"] if r["lat"] != "" else "—"
        lon = r["lon"] if r["lon"] != "" else "—"
        lines.append(f"| {idx} | `{r['filename']}` | {lat} | {lon} | `{r['confidence_level']}` |")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="Folder containing per-image *.json files.")
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"Not a directory: {args.dir}", file=sys.stderr)
        return 1

    rows = gather_rows(args.dir)
    if not rows:
        print(f"No GPS JSONs found in {args.dir}", file=sys.stderr)
        return 1

    csv_path = args.dir / CSV_NAME
    md_path = args.dir / MD_NAME
    write_csv(rows, csv_path)
    write_md(rows, md_path)

    print(f"Wrote {len(rows)} rows")
    print(f"  CSV: {csv_path}")
    print(f"  MD:  {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
