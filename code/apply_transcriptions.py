"""Stamp transcription_front / transcription_back onto consolidated_data.csv
from code/manual/transcriptions.csv.

Run after a transcription session:
    python code/apply_transcriptions.py
"""

from pathlib import Path
import pandas as pd

CONSOLIDATED_CSV   = Path("data/processed/consolidated_data.csv")
TRANSCRIPTIONS_CSV = Path("code/manual/transcriptions.csv")


def main() -> None:
    if not TRANSCRIPTIONS_CSV.exists():
        print("transcriptions.csv not found — nothing to apply.")
        return

    df   = pd.read_csv(CONSOLIDATED_CSV)
    txns = pd.read_csv(TRANSCRIPTIONS_CSV, keep_default_na=False)

    for side in ("front", "back"):
        col     = f"transcription_{side}"
        subset  = txns[txns["side"] == side][["filename", "transcription"]]
        mapping = subset.set_index("filename")["transcription"]

        if col not in df.columns:
            df[col] = pd.NA

        matched = df["filename"].isin(mapping.index)
        df.loc[matched, col] = df.loc[matched, "filename"].map(mapping)

        print(f"Stamped {matched.sum()} {side} transcription(s).")

    df.to_csv(CONSOLIDATED_CSV, index=False)
    print(f"Saved → {CONSOLIDATED_CSV}")


if __name__ == "__main__":
    main()
