"""Interactive handwritten-text transcription tool.

Shows each postcard image alongside a markdown text area so you can
transcribe any handwritten content.  Results are written incrementally to
code/manual/transcriptions.csv — safe to stop and resume at any time.

Keyboard shortcuts
------------------
  Ctrl+Return  — save transcription and advance
  n            — mark as "no handwritten text" (saves empty string) and advance
  s / Escape   — skip (not written; image will reappear next session)
  q            — quit

Usage
-----
  # review all unreviewed backs (default)
  python code/transcribe.py

  # fronts as well
  python code/transcribe.py --fronts

  # one collection only
  python code/transcribe.py --collection EuroPosts

  # re-transcribe specific objectids
  python code/transcribe.py --redo <objectid> [<objectid> ...]

  # start fresh
  python code/transcribe.py --reset
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageOps, ImageTk

try:
    import tkinter as tk
    from tkinter import font as tkfont
except ImportError:
    sys.exit("tkinter is required (it ships with Python on macOS).")

CONSOLIDATED_CSV  = Path("data/processed/consolidated_data.csv")
TRANSCRIPTIONS_CSV = Path("code/manual/transcriptions.csv")

IMG_MAX_W, IMG_MAX_H = 700, 800
PANEL_W = 460   # right-panel fixed width


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


def _load_existing() -> dict[tuple[str, str], str]:
    """Return {(filename, side): transcription} for already-reviewed items."""
    if not TRANSCRIPTIONS_CSV.exists():
        return {}
    df = pd.read_csv(TRANSCRIPTIONS_CSV, keep_default_na=False)
    return {
        (str(r["filename"]), str(r["side"])): str(r["transcription"])
        for _, r in df.iterrows()
    }


def _remove_objectids(objectids: list[str]) -> None:
    """Drop all rows for the given objectids from transcriptions.csv in-place."""
    if not TRANSCRIPTIONS_CSV.exists():
        return
    df = pd.read_csv(TRANSCRIPTIONS_CSV)
    before = len(df)
    df = df[~df["objectid"].astype(str).isin(objectids)]
    df.to_csv(TRANSCRIPTIONS_CSV, index=False)
    print(f"Removed {before - len(df)} entries for {len(objectids)} objectids.")


def _build_queue(
    fronts: bool,
    backs: bool,
    collection: str | None,
    existing: dict[tuple[str, str], str],
    redo_ids: set[str] | None,
) -> list[dict]:
    df = pd.read_csv(CONSOLIDATED_CSV)
    queue: list[dict] = []

    for _, row in df.iterrows():
        filename = str(row.get("filename", ""))
        objectid = str(row.get("objectid", ""))

        if redo_ids and objectid not in redo_ids:
            continue

        if collection:
            front_src, back_src = _parse_artifacts_location(row.get("artifacts_location"))
            ref = front_src or back_src or ""
            if collection.lower() not in ref.lower():
                continue

        front_src, back_src = _parse_artifacts_location(row.get("artifacts_location"))

        if str(row.get("swap_front_back", "")).strip().lower() in ("true", "1", "yes"):
            front_src, back_src = back_src, front_src

        if fronts and front_src and Path(front_src).exists():
            if (filename, "front") not in existing:
                queue.append({
                    "filename": filename, "objectid": objectid,
                    "side": "front", "path": front_src,
                    "title": str(row.get("title", "")),
                    "existing_text": existing.get((filename, "front"), ""),
                })

        if backs and back_src and Path(back_src).exists():
            if (filename, "back") not in existing:
                queue.append({
                    "filename": filename, "objectid": objectid,
                    "side": "back", "path": back_src,
                    "title": str(row.get("title", "")),
                    "existing_text": existing.get((filename, "back"), ""),
                })

    return queue


# ---------------------------------------------------------------------------
# Transcription UI
# ---------------------------------------------------------------------------

class TranscriptionReviewer:
    def __init__(self, queue: list[dict], output_csv: Path) -> None:
        self.queue  = queue
        self.total  = len(queue)
        self.index  = 0
        self.output = output_csv
        self._results: list[dict] = []

        self.root = tk.Tk()
        self.root.title("Transcription Reviewer")
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(True, True)

        # ---- top: progress + title ---
        self.info_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.info_var,
            font=("Helvetica", 12), bg="#1e1e1e", fg="#cccccc",
            wraplength=IMG_MAX_W + PANEL_W, anchor="w", justify="left",
        ).pack(fill="x", padx=14, pady=(10, 4))

        # ---- main content row ----
        content = tk.Frame(self.root, bg="#1e1e1e")
        content.pack(fill="both", expand=True, padx=14, pady=4)

        # Left: image
        left = tk.Frame(content, bg="#1e1e1e")
        left.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(
            left, width=IMG_MAX_W, height=IMG_MAX_H,
            bg="#121212", highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Right: text panel
        right = tk.Frame(content, bg="#1e1e1e", width=PANEL_W)
        right.pack(side="right", fill="both", padx=(14, 0))
        right.pack_propagate(False)

        tk.Label(
            right, text="Transcription  (markdown supported)",
            font=("Helvetica", 11, "bold"), bg="#1e1e1e", fg="#aaaaaa",
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        mono = tkfont.Font(family="Menlo", size=13)
        self.text_area = tk.Text(
            right, font=mono,
            bg="#2a2a2a", fg="#e8e0d0", insertbackground="#e8e0d0",
            relief="flat", bd=0, wrap="word",
            padx=10, pady=10,
            undo=True,
        )
        self.text_area.pack(fill="both", expand=True)

        hint = tk.Label(
            right,
            text="Ctrl+Return / Ctrl+S  save & next  |  n  no text  |  →  skip  |  Ctrl+Q  quit",
            font=("Helvetica", 9), bg="#1e1e1e", fg="#666666",
        )
        hint.pack(pady=(6, 4))

        # Buttons
        btn_row = tk.Frame(right, bg="#1e1e1e")
        btn_row.pack(fill="x", pady=(0, 10))

        btn_cfg = dict(font=("Helvetica", 12, "bold"), pady=7, relief="flat", cursor="hand2", fg="white")

        tk.Button(
            btn_row, text="Save & Next",
            bg="#2e7d32", activebackground="#1b5e20", activeforeground="white",
            command=self._save_and_next, **btn_cfg,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))


        tk.Button(
            btn_row, text="Skip",
            bg="#555555", activebackground="#333333", activeforeground="white",
            command=self._skip, **btn_cfg,
        ).pack(side="left", fill="x", expand=True)

        # Key bindings
        self.root.bind("<Control-Return>", lambda _: self._save_and_next())
        self.root.bind("<Control-s>",       lambda _: self._save_and_next())
        self.root.bind("<Control-r>",   lambda _: self._skip())
        self.root.bind("<Control-q>",       lambda _: self._quit())
        self.root.bind("<Escape>",          lambda _: self._quit())
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

        img.thumbnail((IMG_MAX_W, IMG_MAX_H), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)

        self.canvas.config(width=img.width, height=img.height)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        # Pre-fill text area with any existing transcription (e.g. from --redo)
        self.text_area.delete("1.0", "end")
        existing = item.get("existing_text", "")
        if existing:
            self.text_area.insert("1.0", existing)
        self.text_area.focus_set()

    def _save_and_next(self) -> None:
        transcription = self.text_area.get("1.0", "end").rstrip("\n")
        self._write(transcription)
        self.index += 1
        self._show_current()

    def _skip(self) -> None:
        self.index += 1
        self._show_current()

    def _write(self, transcription: str) -> None:
        item = self.queue[self.index]
        self._results.append({
            "filename":      item["filename"],
            "objectid":      item["objectid"],
            "side":          item["side"],
            "transcription": transcription,
        })
        self._flush()

    def _flush(self) -> None:
        if not self._results:
            return
        TRANSCRIPTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
        write_header = not TRANSCRIPTIONS_CSV.exists()
        with TRANSCRIPTIONS_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "objectid", "side", "transcription"],
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
            print(f"All {reviewed} images reviewed.")
        else:
            print(f"Saved progress ({reviewed} / {self.total} reviewed). "
                  f"Run again to continue from where you left off.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe handwritten text on postcard images."
    )
    parser.add_argument(
        "--fronts", action="store_true",
        help="Include front images (backs are always included)",
    )
    parser.add_argument(
        "--backs-only", action="store_true",
        help="Only show backs (default behaviour, explicit flag for clarity)",
    )
    parser.add_argument(
        "--collection", metavar="NAME",
        help="Filter to one collection, e.g. EuroPosts, Coleccion-MC, sitiopostales",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Ignore existing transcriptions.csv and review everything",
    )
    parser.add_argument(
        "--redo", metavar="OBJECTID", nargs="+",
        help="Re-transcribe specific objectids (removes existing entries first)",
    )
    args = parser.parse_args()

    fronts = args.fronts and not args.backs_only
    backs  = True  # always include backs

    if args.redo:
        _remove_objectids(args.redo)
        existing  = _load_existing()
        full_queue = _build_queue(fronts, backs, args.collection, existing, None)
        redo_set  = set(args.redo)
        queue     = [item for item in full_queue if item["objectid"] in redo_set]
    else:
        existing = {} if args.reset else _load_existing()
        queue    = _build_queue(fronts, backs, args.collection, existing, None)

    if not queue:
        print("Nothing left to transcribe (all images already reviewed).")
        print("Use --reset to start over.")
        sys.exit(0)

    print(f"Images to transcribe: {len(queue)}")
    TranscriptionReviewer(queue, TRANSCRIPTIONS_CSV)
