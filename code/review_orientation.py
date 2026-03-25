"""Interactive orientation reviewer.

Shows each postcard image full-screen with keyboard shortcuts to mark the
clockwise correction needed.  Results are written incrementally to
code/manual/rotations.csv so you can stop and resume at any time.

Key bindings
------------
  0          — already upright (no rotation)
  9 / ←      — rotate left  90° CCW  (= 270° CW stored)
  1 / →      — rotate right 90° CW
  2 / ↓      — upside down  180°
  s / Space  — skip / unsure (not written to CSV)
  q / Esc    — quit and save progress

Usage
-----
  # review all front images not yet in rotations.csv
  python code/review_orientation.py

  # backs only
  python code/review_orientation.py --backs-only

  # fronts only, a specific collection
  python code/review_orientation.py --fronts-only --collection EuroPosts

  # re-review everything, ignoring previous results
  python code/review_orientation.py --reset
"""

from __future__ import annotations

import argparse
import ast
import csv
import os
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageOps, ImageTk

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    sys.exit("tkinter is required (it ships with Python on macOS).")

CONSOLIDATED_CSV = Path("data/processed/consolidated_data.csv")
ROTATIONS_CSV = Path("code/manual/rotations.csv")

# Maximum display dimensions (will be scaled to fit)
MAX_W, MAX_H = 900, 700


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_artifacts_location(val) -> tuple[str | None, str | None]:
    if pd.isna(val):
        return None, None
    try:
        paths = ast.literal_eval(str(val))
    except (ValueError, SyntaxError):
        return None, None
    front = next((p for p in paths if "front" in Path(p).stem.lower()), None)
    back  = next((p for p in paths if "back"  in Path(p).stem.lower()), None)
    return front, back


def _load_existing_rotations() -> set[tuple[str, str]]:
    """Return a set of (filename, side) pairs already in rotations.csv."""
    if not ROTATIONS_CSV.exists():
        return set()
    df = pd.read_csv(ROTATIONS_CSV)
    return set(zip(df["filename"].astype(str), df["side"].astype(str)))


def _remove_objectids_from_rotations(objectids: list[str]) -> None:
    """Drop all rows for the given objectids from rotations.csv in-place."""
    if not ROTATIONS_CSV.exists():
        return
    df = pd.read_csv(ROTATIONS_CSV)
    before = len(df)
    df = df[~df["objectid"].astype(str).isin(objectids)]
    df.to_csv(ROTATIONS_CSV, index=False)
    print(f"Removed {before - len(df)} entries for {len(objectids)} objectids from rotations.csv.")


def _build_queue(
    fronts: bool,
    backs: bool,
    collection: str | None,
    existing: set[tuple[str, str]],
) -> list[dict]:
    df = pd.read_csv(CONSOLIDATED_CSV)
    queue: list[dict] = []

    for _, row in df.iterrows():
        filename = str(row.get("filename", ""))

        # Collection filter (matches on artifacts subfolder name)
        if collection:
            front_src, back_src = _parse_artifacts_location(row.get("artifacts_location"))
            ref = front_src or back_src or ""
            if collection.lower() not in ref.lower():
                continue

        front_src, back_src = _parse_artifacts_location(row.get("artifacts_location"))

        # Honour the same swap flag that data.py applies during export so that
        # the reviewer assigns rotations to the correct logical side.
        if str(row.get("swap_front_back", "")).strip().lower() in ("true", "1", "yes"):
            front_src, back_src = back_src, front_src

        if fronts and front_src and Path(front_src).exists():
            if (filename, "front") not in existing:
                queue.append({
                    "filename": filename,
                    "objectid": str(row["objectid"]),
                    "side": "front",
                    "path": front_src,
                    "title": str(row.get("title", "")),
                })

        if backs and back_src and Path(back_src).exists():
            if (filename, "back") not in existing:
                queue.append({
                    "filename": filename,
                    "objectid": str(row["objectid"]),
                    "side": "back",
                    "path": back_src,
                    "title": str(row.get("title", "")),
                })

    return queue


# ---------------------------------------------------------------------------
# Reviewer UI
# ---------------------------------------------------------------------------

class OrientationReviewer:
    def __init__(self, queue: list[dict], output_csv: Path) -> None:
        self.queue   = queue
        self.total   = len(queue)
        self.index   = 0
        self.output  = output_csv
        self._results: list[dict] = []

        self.root = tk.Tk()
        self.root.title("Orientation Reviewer")
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(True, True)

        # ---- image canvas ----
        self.canvas = tk.Canvas(
            self.root, width=MAX_W, height=MAX_H,
            bg="#1e1e1e", highlightthickness=0,
        )
        self.canvas.pack(pady=(12, 6))

        # ---- info label ----
        self.info_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.info_var,
            font=("Helvetica", 13), bg="#1e1e1e", fg="#cccccc",
            wraplength=MAX_W,
        ).pack(pady=2)

        # ---- hint label ----
        hint = (
            "[ 0 ] upright  |  [ 9 / ← ] rotate left 90°  |  [ 1 / → ] rotate right 90°  "
            "|  [ 2 / ↓ ] 180°  |  [ s / Space ] skip  |  [ q / Esc ] quit"
        )
        tk.Label(
            self.root, text=hint,
            font=("Helvetica", 11), bg="#1e1e1e", fg="#888888",
        ).pack(pady=(2, 10))

        # ---- button bar ----
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=(0, 12))
        btn_cfg = dict(font=("Helvetica", 13, "bold"), width=16, pady=8, relief="flat", cursor="hand2")
        tk.Button(btn_frame, text="← Left 90°  [9]",  bg="#4a6fa5", fg="#ffffff",
                  activebackground="#6a8fc5", activeforeground="#ffffff",
                  command=lambda: self._save(270), **btn_cfg).grid(row=0, column=0, padx=6)
        tk.Button(btn_frame, text="✓ Upright  [0]",   bg="#2e7d32", fg="#ffffff",
                  activebackground="#4caf50", activeforeground="#ffffff",
                  command=lambda: self._save(0),   **btn_cfg).grid(row=0, column=1, padx=6)
        tk.Button(btn_frame, text="↓ Flip 180°  [2]", bg="#b71c1c", fg="#ffffff",
                  activebackground="#e53935", activeforeground="#ffffff",
                  command=lambda: self._save(180), **btn_cfg).grid(row=0, column=2, padx=6)
        tk.Button(btn_frame, text="Right 90° →  [1]", bg="#4a6fa5", fg="#ffffff",
                  activebackground="#6a8fc5", activeforeground="#ffffff",
                  command=lambda: self._save(90),  **btn_cfg).grid(row=0, column=3, padx=6)
        tk.Button(btn_frame, text="Skip  [s]",         bg="#555555", fg="#ffffff",
                  activebackground="#777777", activeforeground="#ffffff",
                  command=self._skip, **btn_cfg).grid(row=0, column=4, padx=6)

        # key bindings
        self.root.bind("0", lambda _: self._save(0))
        self.root.bind("9", lambda _: self._save(270))
        self.root.bind("1", lambda _: self._save(90))
        self.root.bind("2", lambda _: self._save(180))
        self.root.bind("<Left>",  lambda _: self._save(270))
        self.root.bind("<Right>", lambda _: self._save(90))
        self.root.bind("<Down>",  lambda _: self._save(180))
        self.root.bind("s",       lambda _: self._skip())
        self.root.bind("<space>", lambda _: self._skip())
        self.root.bind("q",       lambda _: self._quit())
        self.root.bind("<Escape>", lambda _: self._quit())
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        self._show_current()
        self.root.mainloop()

    # ------------------------------------------------------------------

    def _show_current(self) -> None:
        if self.index >= self.total:
            self._quit(done=True)
            return

        item = self.queue[self.index]
        self.info_var.set(
            f"[{self.index + 1} / {self.total}]  {item['side'].upper()}  —  "
            f"{Path(item['path']).name}\n{item['title']}"
        )

        with Image.open(item["path"]) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")

        # Fit to canvas preserving aspect ratio
        img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)  # keep reference

        self.canvas.config(width=img.width, height=img.height)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

    def _save(self, angle: int) -> None:
        if self.index >= self.total:
            return
        item = self.queue[self.index]
        result = {
            "filename":   item["filename"],
            "objectid":   item["objectid"],
            "side":       item["side"],
            "angle":      angle,
            "confidence": 1.0,
            "method":     "manual",
        }
        self._results.append(result)
        self._flush()
        self.index += 1
        self._show_current()

    def _skip(self) -> None:
        self.index += 1
        self._show_current()

    def _flush(self) -> None:
        """Append any unsaved results to the CSV."""
        if not self._results:
            return
        ROTATIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
        write_header = not ROTATIONS_CSV.exists()
        with ROTATIONS_CSV.open("a", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["filename", "objectid", "side", "angle", "confidence", "method"],
            )
            if write_header:
                writer.writeheader()
            writer.writerows(self._results)
        self._results.clear()

    def _quit(self, done: bool = False) -> None:
        self._flush()
        reviewed = self.index
        self.root.destroy()
        if done:
            print(f"All {self.total} images reviewed.")
        else:
            print(f"Stopped after {reviewed} of {self.total} images.")
        print(f"Corrections saved → {ROTATIONS_CSV}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manually review postcard image orientations."
    )
    parser.add_argument("--fronts-only", action="store_true")
    parser.add_argument("--backs-only",  action="store_true")
    parser.add_argument(
        "--collection", metavar="NAME",
        help="Filter to one collection, e.g. EuroPosts, Coleccion-MC, sitiopostales",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Ignore existing rotations.csv and re-review everything",
    )
    parser.add_argument(
        "--redo", metavar="OBJECTID", nargs="+",
        help="Re-review specific objectids (removes their existing entries first)",
    )
    args = parser.parse_args()

    fronts = not args.backs_only
    backs  = not args.fronts_only

    if args.redo:
        _remove_objectids_from_rotations(args.redo)
        # Build a queue restricted to only these objectids
        existing = _load_existing_rotations()
        full_queue = _build_queue(fronts, backs, args.collection, existing)
        redo_set = set(args.redo)
        queue = [item for item in full_queue if item["objectid"] in redo_set]
    else:
        existing = set() if args.reset else _load_existing_rotations()
        queue = _build_queue(fronts, backs, args.collection, existing)

    if not queue:
        print("Nothing left to review (all images already in rotations.csv).")
        print("Use --reset to start over.")
        sys.exit(0)

    print(f"Images to review: {len(queue)}")
    OrientationReviewer(queue, ROTATIONS_CSV)
