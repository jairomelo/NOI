"""Detect orientation corrections for all postcard images.

Reads  : data/processed/consolidated_data.csv
Writes : code/manual/rotations.csv

Only rows where the detected angle != 0 are written (upright images are
omitted to keep the file small).  Run ``apply_rotations.py`` afterwards to
stamp the corrections into consolidated_data.csv, which is then consumed by
``prepare_exhibit()`` in data.py.

Usage
-----
  # backs via OSD, fronts via VLM (default)
  python code/detect_orientation.py

  # only backs (no VLM needed)
  python code/detect_orientation.py --backs-only

  # only fronts (VLM only)
  python code/detect_orientation.py --fronts-only

  # preview without writing
  python code/detect_orientation.py --dry-run

  # use a different MLX model for fronts
  python code/detect_orientation.py --model mlx-community/moondream2
"""

from __future__ import annotations

import argparse
import ast
import csv
import logging
import sys
from pathlib import Path

import pandas as pd

# Allow running as  python code/detect_orientation.py  from project root
sys.path.insert(0, str(Path(__file__).parent))
from helpers.orientation import detect_orientation, load_vlm  # noqa: E402

CONSOLIDATED_CSV = Path("data/processed/consolidated_data.csv")
OUTPUT_CSV = Path("code/manual/rotations.csv")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def _parse_artifacts_location(val) -> tuple[str | None, str | None]:
    """Return (front_path, back_path) from the artifacts_location column value."""
    if pd.isna(val):
        return None, None
    try:
        paths = ast.literal_eval(str(val))
    except (ValueError, SyntaxError):
        return None, None
    front = next((p for p in paths if "front" in Path(p).stem.lower()), None)
    back = next((p for p in paths if "back" in Path(p).stem.lower()), None)
    return front, back


def run(
    *,
    fronts: bool = True,
    backs: bool = True,
    dry_run: bool = False,
    vlm_model: str = "mlx-community/Qwen2-VL-2B-Instruct-4bit",
    osd_confidence_threshold: float = 3.0,
    sample: int | None = None,
) -> None:
    df = pd.read_csv(CONSOLIDATED_CSV)
    if sample is not None:
        df = df.sample(n=min(sample, len(df)), random_state=42).reset_index(drop=True)
        logger.info("Sampling %d of %d records.", len(df), len(pd.read_csv(CONSOLIDATED_CSV)))
    results: list[dict] = []

    # Pre-load the VLM model once if it will be needed (fronts always use it;
    # backs use it as a fallback when OSD confidence is too low).
    vlm_context = None
    if fronts:
        logger.info("Loading VLM model %s …", vlm_model)
        vlm_context = load_vlm(vlm_model)
        logger.info("VLM model loaded.")

    for _, row in df.iterrows():
        oid = str(row["objectid"])
        filename = str(row.get("filename", ""))
        front_src, back_src = _parse_artifacts_location(row.get("artifacts_location", ""))

        # List of (path, is_back, side) pairs to process for this record
        pairs: list[tuple[str, bool, str]] = []
        if backs and back_src and Path(back_src).exists():
            pairs.append((back_src, True, "back"))
        if fronts and front_src and Path(front_src).exists():
            pairs.append((front_src, False, "front"))

        for path, is_back, side in pairs:
            try:
                angle, conf, method = detect_orientation(
                    path,
                    is_back=is_back,
                    osd_confidence_threshold=osd_confidence_threshold,
                    vlm_model=vlm_model,
                    vlm_context=vlm_context,
                )
            except Exception as exc:
                logger.warning("Failed %s %s: %s", oid[:8], side, exc)
                continue

            if angle != 0:
                logger.info(
                    "CORRECTION  %-8s  %s  →  %d°  (conf=%.1f  method=%s)",
                    oid[:8], side, angle, conf, method,
                )
                results.append({
                    "filename":   filename,
                    "objectid":   oid,
                    "side":       side,
                    "angle":      angle,
                    "confidence": round(conf, 2),
                    "method":     method,
                })
            else:
                logger.debug("ok  %s  %s  (conf=%.1f  method=%s)", oid[:8], side, conf, method)

    if dry_run:
        print(f"\nDry run — {len(results)} corrections found (not written)")
        for r in results:
            print(r)
        return

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["filename", "objectid", "side", "angle", "confidence", "method"],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {len(results)} corrections → {OUTPUT_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Detect postcard image orientations and write a corrections CSV."
    )
    parser.add_argument(
        "--fronts-only", action="store_true", help="Only process front images (VLM)"
    )
    parser.add_argument(
        "--backs-only", action="store_true", help="Only process back images (OSD)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print results without writing the CSV"
    )
    parser.add_argument(
        "--model",
        default="mlx-community/Qwen2-VL-2B-Instruct-4bit",
        metavar="MODEL",
        help="MLX-VLM model for front images (default: %(default)s)",
    )
    parser.add_argument(
        "--osd-threshold",
        type=float,
        default=3.0,
        metavar="CONF",
        help="Min OSD confidence to accept without VLM fallback (default: %(default)s)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Process a random sample of N records instead of all (useful for testing)",
    )
    args = parser.parse_args()

    run(
        fronts=not args.backs_only,
        backs=not args.fronts_only,
        dry_run=args.dry_run,
        vlm_model=args.model,
        osd_confidence_threshold=args.osd_threshold,
        sample=args.sample,
    )
