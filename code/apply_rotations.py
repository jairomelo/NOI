"""Stamp rotation_front / rotation_back corrections onto consolidated_data.csv.

Reads  : code/manual/rotations.csv  (filename, objectid, side, angle, …)
Writes : data/processed/consolidated_data.csv  (adds/updates rotation columns)

Matching is done by *filename* (stable across re-runs of consolidate_data)
rather than objectid (which is regenerated each time).

Usage
-----
  python code/apply_rotations.py
"""

from __future__ import annotations

import pandas as pd

CONSOLIDATED_CSV = "data/processed/consolidated_data.csv"
ROTATIONS_CSV = "code/manual/rotations.csv"


def main() -> None:
    df = pd.read_csv(CONSOLIDATED_CSV)
    rot = pd.read_csv(ROTATIONS_CSV)

    # Initialise columns with NaN so only explicitly corrected rows carry a value.
    # prepare_exhibit() treats NaN as 0 (no rotation).
    for col in ("rotation_front", "rotation_back"):
        if col not in df.columns:
            df[col] = float("nan")

    matched_front = matched_back = 0
    unmatched: list[str] = []

    for _, r in rot.iterrows():
        filename = str(r["filename"]).strip()
        side = str(r["side"]).strip().lower()
        angle = int(r["angle"])

        mask = df["filename"] == filename
        if not mask.any():
            unmatched.append(filename)
            continue

        if side == "front":
            df.loc[mask, "rotation_front"] = angle
            matched_front += 1
        elif side == "back":
            df.loc[mask, "rotation_back"] = angle
            matched_back += 1
        else:
            print(f"WARNING: unknown side {side!r} for {filename!r}")

    df.to_csv(CONSOLIDATED_CSV, index=False)
    print(
        f"Stamped {matched_front} front and {matched_back} back rotation corrections "
        f"→ {CONSOLIDATED_CSV}"
    )
    if unmatched:
        print(f"WARNING: {len(unmatched)} filenames in rotations.csv not found in CSV:")
        for fn in sorted(set(unmatched)):
            print(f"  {fn}")


if __name__ == "__main__":
    main()
