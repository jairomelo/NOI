import os
import re
import zipfile
from pathlib import Path

import helpers.file_converter as file_converter
            
def converter(origin, destination, remove_darker_duplicates=True, exclude_extensions=None):
    os.makedirs(destination, exist_ok=True)
    
    for r, d, f in os.walk(origin):
        for file in f:
            name, extension = os.path.splitext(file)
            if exclude_extensions and extension.lower() in exclude_extensions:
                continue
            if not extension or extension.lower() in [".heic"]:
                full_path = os.path.join(r, file)
                file_converter.heic_to_img(full_path, destination)
            elif extension.lower() in [".pdf"]:
                full_path = os.path.join(r, file)
                file_converter.pdf_to_img(full_path, destination)

    if remove_darker_duplicates:
        file_converter.remove_darker_duplicates(destination)
    
def artifact_cleaner(artifacts_folder, exclude_extensions=[".pdf", ".heic"]):
    # remove PDFs and HEICs from the artifacts folder
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() in exclude_extensions:
                full_path = os.path.join(r, file)
                os.remove(full_path)


def _rename_ab_to_front_back(folder, replace=True):
    """Rename *-a.jp(e)g → *-front.jpg and *-b.jp(e)g → *-back.jpg in-place."""
    ab_pattern = re.compile(r'^(.+)-([ab])\.jpe?g$', re.IGNORECASE)
    mapping = {'a': 'front', 'b': 'back'}
    for fname in os.listdir(folder):
        m = ab_pattern.match(fname)
        if m:
            stem, side = m.group(1), m.group(2).lower()
            new_name = f"{stem}-{mapping[side]}.jpg"
            src = os.path.join(folder, fname)
            dst = os.path.join(folder, new_name)
            if not os.path.exists(dst) or replace:
                    os.rename(src, dst)     
            else:
                print(f"  [skip rename] target already exists: {new_name}")


def prepare_artifacts(
    coleccion_mc_src='repos/Coleccion-MC/objects',
    europosts_src='repos/EuroPosts/Fotos',
    sitiopostales_zip='artifacts/sitiopostales.zip',
    artifacts_root='artifacts',
    overwrite=False,
):
    """
    Build all three artifacts/ sub-folders from their original sources.

    Sources
    -------
    Coleccion-MC : PDFs in repos/Coleccion-MC/objects/
                   → each PDF yields NNN-front.jpg + NNN-back.jpg via embedded images
    EuroPosts    : Extension-less HEIC files in repos/EuroPosts/Fotos/ (nested sub-dirs)
                   → NNN-a (HEIC) converted to JPEG, then renamed:
                     *-a → *-front, *-b → *-back
    sitiopostales: Mix of JPEGs and HEICs (with .heic extension) packed in
                   artifacts/sitiopostales.zip under a Postales/ prefix.
                   HEICs are extracted to a temp file, converted with EXIF
                   rotation baked in, then renamed -a → -front, -b → -back.

    After this completes, run `python3 code/data.py prepare` to resize images and
    regenerate postcards.json.
    """
    # ---- Coleccion-MC: PDF → front/back images --------------------------------
    dst_mc = os.path.join(artifacts_root, 'Coleccion-MC')
    print(f"\n[Coleccion-MC] Converting PDFs: {coleccion_mc_src} → {dst_mc}")
    converter(coleccion_mc_src, dst_mc, remove_darker_duplicates=False,
              exclude_extensions=['.jpg', '.jpeg', '.png', '.heic'])
    print(f"[Coleccion-MC] Normalising extensions (.jpeg → .jpg)")
    consolidate_file_extensions(dst_mc, target_extension='.jpg')
    print(f"[Coleccion-MC] Renaming page numbers (_1/_2 → -back/-front)")
    front_back_switch(dst_mc)

    # ---- EuroPosts: extension-less HEICs → front/back images -----------------
    dst_eu = os.path.join(artifacts_root, 'EuroPosts')
    print(f"\n[EuroPosts] Converting HEICs: {europosts_src} → {dst_eu}")
    # PDFs exist alongside HEICs in the source; skip them here — the HEICs are
    # the definitive images (PDFs are low-res duplicates from the same scanner).
    converter(europosts_src, dst_eu, remove_darker_duplicates=False,
              exclude_extensions=['.pdf', '.jpg', '.jpeg', '.png'])
    print(f"[EuroPosts] Renaming -a/-b → -front/-back in {dst_eu}")
    _rename_ab_to_front_back(dst_eu)

    # ---- sitiopostales: extract JPEGs + HEICs from zip, convert HEICs --------
    dst_sp = os.path.join(artifacts_root, 'sitiopostales')
    if os.path.exists(sitiopostales_zip):
        import tempfile
        os.makedirs(dst_sp, exist_ok=True)
        print(f"\n[sitiopostales] Extracting {sitiopostales_zip} → {dst_sp}")
        with zipfile.ZipFile(sitiopostales_zip) as z:
            for member in z.namelist():
                name = Path(member).name
                if not name or name.startswith('.') or '__MACOSX' in member:
                    continue
                suffix = Path(name).suffix.lower()
                if suffix not in ('.jpg', '.jpeg', '.png', '.heic'):
                    continue

                # Fix over-padded numbers in source zip: C2-G2-0012-a → C2-G2-012-a
                name = re.sub(r'(C2-G2-)0+(\d{3}[-.])', r'\1\2', name)

                if suffix == '.heic':
                    # Extract HEIC to a temp file, convert to JPEG in dst_sp
                    stem = Path(name).stem
                    target_jpg = os.path.join(dst_sp, f"{stem}.jpg")
                    if not overwrite and os.path.exists(target_jpg):
                        continue
                    with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as tmp:
                        tmp.write(z.read(member))
                        tmp_path = tmp.name
                    try:
                        file_converter.heic_to_img(tmp_path, dst_sp, overwrite=overwrite)
                        # heic_to_img saves as <original_tmp_stem>.jpeg — rename to target
                        saved_jpeg = os.path.join(dst_sp, f"{Path(tmp_path).stem}.jpeg")
                        if os.path.exists(saved_jpeg):
                            os.rename(saved_jpeg, target_jpg)
                    finally:
                        os.unlink(tmp_path)
                else:
                    target = os.path.join(dst_sp, name)
                    if not overwrite and os.path.exists(target):
                        continue
                    with z.open(member) as src_f, open(target, 'wb') as out_f:
                        out_f.write(src_f.read())

        print(f"[sitiopostales] Renaming -a/-b → -front/-back in {dst_sp}")
        _rename_ab_to_front_back(dst_sp)
    else:
        print(f"\n[sitiopostales] Zip not found at {sitiopostales_zip} — skipping")

    print("\nprepare_artifacts() complete.")
    print("Next step: python3 code/data.py prepare")

                
def consolidate_file_extensions(artifacts_folder, target_extension=".jpg"):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() != target_extension and extension.lower() in [".jpeg", ".jpg"]:
                full_path = os.path.join(r, file)
                new_full_path = os.path.join(r, name + target_extension)
                os.rename(full_path, new_full_path)

def front_back_switch(artifacts_folder, dry_run=False):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() in [".jpg", ".jpeg"]:
                if "_1" in name:
                    new_name = name.replace("_1", "-back")
                    if not dry_run:
                        os.rename(os.path.join(r, file), os.path.join(r, new_name + extension))
                    else:
                        print(f"Dry run: Would rename {file} to {new_name + extension}")
                elif "_2" in name:
                    new_name = name.replace("_2", "-front")
                    if not dry_run:
                        os.rename(os.path.join(r, file), os.path.join(r, new_name + extension))
                    else:
                        print(f"Dry run: Would rename {file} to {new_name + extension}")

def front_back_bypattern(artifacts_folder, pattern={"-a": "-front", "-b": "-back"}, dry_run=False):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() in [".jpg", ".jpeg"]:
                # check if the pattern match the end of the filename
                for key, value in pattern.items():
                    if name.endswith(key):
                        new_name = name[:-len(key)] + value
                        if not dry_run:
                            os.rename(os.path.join(r, file), os.path.join(r, new_name + extension))
                        else:
                            print(f"Dry run: Would rename {file} to {new_name + extension}")

def remove_non_jpg(artifacts_folder, dry_run=False):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() not in [".jpg", ".jpeg"]:
                full_path = os.path.join(r, file)
                if not dry_run:
                    os.remove(full_path)
                else:
                    print(f"Dry run: Would remove {full_path}")

if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'prepare':
        prepare_artifacts()
    elif cmd == 'clean':
        artifact_cleaner('artifacts')
    else:
        print("Usage: python3 code/artifacts.py prepare | clean")
    