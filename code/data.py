import ast
import colorsys
import json
import os
import uuid
from collections import Counter
from glob import glob
from pathlib import Path

import pandas as pd
from PIL import Image, ImageOps

def consolidate_data(data_folder, output_folder=None, output_file="consolidated_data.csv", dry_run=False):
    
    output_folder = os.path.join(data_folder, 'processed') if output_folder is None else output_folder
    os.makedirs(output_folder, exist_ok=True)
    
    all_data = os.listdir(data_folder)
    
    consolidated_df = pd.DataFrame()
    
    for file in all_data:
        file_path = os.path.join(data_folder, file)
        if file.endswith(".csv"):
            df = pd.read_csv(file_path)
            consolidated_df = pd.concat([consolidated_df, df], ignore_index=True)
            
    consolidated_df = consolidated_df.dropna(how='all').dropna(subset=['filename'])
    consolidated_df = consolidated_df.replace(r'\s', ' ', regex=True)
    
    consolidated_df['objectid'] = consolidated_df.apply(lambda _: str(uuid.uuid4()), axis=1)
    consolidated_df['artifacts_location'] = consolidated_df['filename'].apply(lambda x: _locate_artifacts(x, "artifacts", None))

    # Preserve manually-set flags from the existing consolidated CSV (matched on
    # filename, which is stable across re-runs unlike objectid).
    _manual_cols = ['swap_front_back', 'rotation_front', 'rotation_back', 'transcription_front', 'transcription_back']
    existing_path = os.path.join(output_folder, output_file)
    if os.path.exists(existing_path):
        prev = pd.read_csv(existing_path, usecols=lambda c: c in ['filename'] + _manual_cols)
        for col in _manual_cols:
            if col in prev.columns:
                mapping = prev.dropna(subset=[col]).set_index('filename')[col]
                consolidated_df[col] = consolidated_df['filename'].map(mapping)

    if 'swap_front_back' not in consolidated_df.columns:
        consolidated_df['swap_front_back'] = False
    
    if not dry_run:
        consolidated_df.to_csv(os.path.join(output_folder, output_file), index=False)
        print(f"Consolidated data saved to {output_file}")
    else:
        print(f"Dry run: Consolidated data would be saved to {output_file} with {len(consolidated_df)} rows.")
        print(consolidated_df['artifacts_location'].head())

def _locate_artifacts(path, origin, patterns):
    name, extension = os.path.splitext(path)
    if "Fotos" in name:
        origin = os.path.join(origin, "EuroPosts")
    elif "C2-G2" in name:
        origin = os.path.join(origin, "sitiopostales")
    else:
        origin = os.path.join(origin, "Coleccion-MC")
    
    search_pattern = os.path.join(origin, f"{Path(path).stem}-*.*")
    # print(f"Searching for files matching: {search_pattern}")
    matching_files = glob(search_pattern)
    return matching_files


# ---------------------------------------------------------------------------
# Phase 0 helpers
# ---------------------------------------------------------------------------

def _parse_artifacts_location(val):
    """Return (front_path, back_path) from the artifacts_location string."""
    if pd.isna(val):
        return None, None
    try:
        paths = ast.literal_eval(str(val))
    except (ValueError, SyntaxError):
        return None, None
    front = next((p for p in paths if 'front' in Path(p).stem.lower()), None)
    back  = next((p for p in paths if 'back'  in Path(p).stem.lower()), None)
    return front, back


def _normalize_subjects(subject_str):
    """Split semicolon-delimited subjects into a clean list."""
    if pd.isna(subject_str):
        return []
    return [s.strip() for s in str(subject_str).split(';') if s.strip()]


def _normalize_language(lang_str):
    """Lowercase and strip language code."""
    if pd.isna(lang_str):
        return None
    return str(lang_str).strip().lower()


def _extract_dominant_color(image_path, n_palette=4):
    """Return (hex_color, hue_degrees, palette) where:
      - hex_color / hue_degrees: the single most visually distinctive color
      - palette: list of {'hex', 'hue', 'pct'} dicts for the top n_palette
        clusters, sorted highest-score first.  'pct' is raw pixel fraction.

    Scoring = pixel_count × exp(3 × saturation) so vivid minority colors
    (e.g. a blue sky strip) beat large muted sepia backgrounds.  Palette
    entries are also deduplicated by hue (≥15° apart) to maximise variety.
    """
    import math
    if not image_path or not os.path.exists(image_path):
        return None, None, []
    try:
        with Image.open(image_path) as img:
            small = img.convert('RGB').resize((150, 150), Image.LANCZOS)

        # Quantize to 16 representative colors (PIL median-cut)
        n_colors = 16
        quantized = small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
        raw_palette = quantized.getpalette()          # 256*3 ints
        palette = [
            (raw_palette[i * 3], raw_palette[i * 3 + 1], raw_palette[i * 3 + 2])
            for i in range(n_colors)
        ]

        # Count how many pixels belong to each cluster
        counts = Counter(quantized.get_flattened_data())  # keys are palette indices
        total = sum(counts.values()) or 1

        def hsv_of(rgb):
            r, g, b = (x / 255.0 for x in rgb)
            return colorsys.rgb_to_hsv(r, g, b)

        def score(idx):
            """High score = many pixels AND vivid colour. Near-black/white → 0."""
            _h, s, v = hsv_of(palette[idx])
            if v < 0.15 or v > 0.93 or s < 0.06:
                return 0.0
            freq = counts.get(idx, 0) / total
            return freq * math.exp(3.0 * s)   # strong saturation bonus

        # Rank all clusters by score (best first)
        ranked = sorted(range(n_colors), key=score, reverse=True)

        best_idx = ranked[0]
        # If every cluster is near-black/white, fall back to most-populous
        if score(best_idx) == 0.0:
            best_idx = max(counts, key=counts.get)

        dominant = palette[best_idx]
        hex_color = '#{:02x}{:02x}{:02x}'.format(*dominant)
        r, g, b = (x / 255.0 for x in dominant)
        hue = round(colorsys.rgb_to_hsv(r, g, b)[0] * 360)

        # Build diverse palette: top n_palette clusters, deduplicated by hue
        palette_out = []
        seen_hues = []
        candidates = ranked + sorted(counts, key=lambda i: -counts[i])  # score first, then count
        for idx in candidates:
            if len(palette_out) >= n_palette:
                break
            rgb = palette[idx]
            pct = counts.get(idx, 0) / total
            if pct < 0.01:      # skip clusters with < 1% of pixels
                continue
            h_val, _s, _v = hsv_of(rgb)
            h_deg = round(h_val * 360)
            # Skip if too close in hue to an already-added entry (wrap-around safe)
            if any(min((h_deg - sh) % 360, (sh - h_deg) % 360) < 15 for sh in seen_hues):
                continue
            palette_out.append({
                'hex': '#{:02x}{:02x}{:02x}'.format(*rgb),
                'hue': h_deg,
                'pct': round(pct, 3),
            })
            seen_hues.append(h_deg)

        return hex_color, hue, palette_out
    except Exception:
        return None, None, []


def _resize_image(src, dest, max_size, quality=82, extra_rotation=0):
    """Resize so the longest side <= max_size; save JPEG to dest.

    *extra_rotation* is a clockwise rotation in degrees (0, 90, 180, 270)
    applied after EXIF normalisation to correct physical scan orientation.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)  # bake any EXIF rotation into pixels
        if extra_rotation:
            img = img.rotate(-extra_rotation, expand=True)  # PIL rotate is CCW; negate for CW
        img = img.convert('RGB')
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        img.save(dest, 'JPEG', quality=quality, optimize=True)


# ---------------------------------------------------------------------------
# Phase 0 main: prepare_exhibit
# ---------------------------------------------------------------------------

def prepare_exhibit(
    csv_path='data/processed/consolidated_data.csv',
    output_json='exhibit/src/data/postcards.json',
    output_images_dir='exhibit/public/images',
    full_max=1200,
    thumb_max=300,
    dry_run=False,
):
    """
    Enrich consolidated_data.csv and export:
      - postcards.json  →  exhibit/src/data/
      - optimized JPEGs →  exhibit/public/images/
    """
    df = pd.read_csv(csv_path)
    records = []
    missing_fronts = []

    print(f"Processing {len(df)} records …")

    for _, row in df.iterrows():
        front_src, back_src = _parse_artifacts_location(row.get('artifacts_location'))

        # Honour manual front/back swap flag
        if str(row.get('swap_front_back', '')).strip().lower() in ('true', '1', 'yes'):
            front_src, back_src = back_src, front_src

        front_ok = bool(front_src and os.path.exists(front_src))
        back_ok  = bool(back_src  and os.path.exists(back_src))

        if not front_ok:
            missing_fronts.append({
                'filename':           str(row.get('filename', '')),
                'objectid':           str(row.get('objectid', '')),
                'title':              str(row.get('title', '')),
                'artifacts_location': str(row.get('artifacts_location', '')),
                'expected_front':     front_src or '(not resolved)',
                'back_exists':        back_ok,
                'back_path':          back_src or '',
            })

        # dominant color + full palette from front image
        hex_color, hue, color_palette = _extract_dominant_color(front_src) if front_ok else (None, None, [])

        # prefer 'description'; fall back to the typo'd 'descripction' column
        description = row.get('description')
        if pd.isna(description):
            description = row.get('descripction')

        # filenames only — Astro components resolve full URL with BASE_URL + /images/
        # Prefix with lowercased collection folder to avoid collisions between
        # Coleccion-MC and EuroPosts (both use 001-front.jpg … 100-front.jpg).
        def _prefixed(src):
            if not src:
                return None
            p = Path(src)
            prefix = p.parent.name.lower().replace(' ', '-')
            return f"{prefix}_{p.name}"

        front_name = _prefixed(front_src)
        back_name  = _prefixed(back_src)
        thumb_name = f"thumb_{front_name}" if front_name else None

        # CSV stores years as floats (e.g. 1511.0) — normalise to string "1511"
        raw_date = row.get('date')
        date_str = str(int(float(raw_date))) if not pd.isna(raw_date) else None

        def _to_rotation(val):
            try:
                return int(float(val)) if not pd.isna(val) else 0
            except (ValueError, TypeError):
                return 0

        record = {
            'objectid':    str(row['objectid']),
            'title':       str(row['title']).strip()    if not pd.isna(row.get('title'))    else '',
            'date':        date_str,
            'location':    str(row['location']).strip() if not pd.isna(row.get('location')) else None,
            'latitude':    float(row['latitude'])       if not pd.isna(row.get('latitude')) else None,
            'longitude':   float(row['longitude'])      if not pd.isna(row.get('longitude'))else None,
            'description': str(description).strip()     if not pd.isna(description)         else None,
            'subjects':    _normalize_subjects(row.get('subject')),
            'language':    _normalize_language(row.get('language')),
            'source':      str(row['source']).strip()   if not pd.isna(row.get('source'))   else None,
            'image_front': front_name if front_ok else None,
            'image_back':  back_name  if back_ok  else None,
            'image_thumb': thumb_name if front_ok else None,
            'color_hex':     hex_color,
            'color_hue':     hue,
            'color_palette': color_palette,
            # internal — stripped before JSON export
            '_src_front':  front_src,
            '_src_back':   back_src,
            '_front_ok':   front_ok,
            '_back_ok':    back_ok,
            '_rot_front':  _to_rotation(row.get('rotation_front')),
            '_rot_back':   _to_rotation(row.get('rotation_back')),
            'transcription_front': str(row['transcription_front']).strip() if not pd.isna(row.get('transcription_front')) else None,
            'transcription_back':  str(row['transcription_back']).strip()  if not pd.isna(row.get('transcription_back'))  else None,
        }
        records.append(record)

    has_coords = sum(1 for r in records if r['latitude'] is not None)
    has_front  = sum(1 for r in records if r['image_front'])
    n_missing  = len(missing_fronts)
    print(f"  Records with coordinates : {has_coords}/{len(records)}")
    print(f"  Records with front image : {has_front}/{len(records)}")
    print(f"  Missing front images     : {n_missing}")

    if dry_run:
        print("Dry run — skipping image resize and JSON export.\nSample records:")
        for r in records[:3]:
            print({k: v for k, v in r.items() if not k.startswith('_')})
        return records

    # ---- resize images -------------------------------------------------------
    os.makedirs(output_images_dir, exist_ok=True)
    processed = 0
    for r in records:
        src_front = r['_src_front']
        src_back  = r['_src_back']

        if r['_front_ok']:
            _resize_image(src_front, os.path.join(output_images_dir, r['image_front']), full_max, extra_rotation=r['_rot_front'])
            _resize_image(src_front, os.path.join(output_images_dir, r['image_thumb']), thumb_max, quality=75, extra_rotation=r['_rot_front'])
            processed += 1

        if r['_back_ok']:
            _resize_image(src_back, os.path.join(output_images_dir, r['image_back']), full_max, extra_rotation=r['_rot_back'])

    print(f"  Images processed         : {processed}")

    # ---- strip internal keys and export JSON ---------------------------------
    clean = [{k: v for k, v in r.items() if not k.startswith('_')} for r in records]

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(clean)} records → {output_json}")

    # ---- write missing-fronts log -------------------------------------------
    log_path = os.path.join(os.path.dirname(output_json), 'missing_fronts.log')
    with open(log_path, 'w', encoding='utf-8') as lf:
        lf.write(f"Missing front images: {len(missing_fronts)} of {len(records)} records\n")
        lf.write("=" * 72 + "\n\n")
        for m in missing_fronts:
            lf.write(f"filename   : {m['filename']}\n")
            lf.write(f"objectid   : {m['objectid']}\n")
            lf.write(f"title      : {m['title']}\n")
            lf.write(f"expected   : {m['expected_front']}\n")
            lf.write(f"back_exists: {m['back_exists']}")
            if m['back_exists']:
                lf.write(f"  ({m['back_path']})")
            lf.write("\n")
            lf.write(f"artifacts  : {m['artifacts_location']}\n")
            lf.write("-" * 72 + "\n")
    print(f"  Missing-fronts log       : {log_path}")

    return clean


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else ''

    if cmd == 'prepare':
        prepare_exhibit()
    elif cmd == 'dry':
        prepare_exhibit(dry_run=True)
    else:
        consolidate_data(data_folder="data", output_folder="data/processed", output_file="consolidated_data.csv", dry_run=False)