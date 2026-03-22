from PIL import Image
import pillow_heif
from pathlib import Path
import argparse
import fitz  # PyMuPDF
import re
import numpy as np

def heic_to_img(heic_path, output_dir=".", output_format="JPEG", overwrite=False):
    try:
        # Register the HEIF opener plugin
        pillow_heif.register_heif_opener()
        
        # Open the HEIC image file
        image = Image.open(heic_path)
        
        # Convert to RGB color space, required for saving in most formats
        image = image.convert("RGB")
        
        # Save the image in the specified format
        output_path = Path(output_dir, f"{Path(heic_path).stem}.{output_format.lower()}")
        if output_path.exists() and not overwrite:
            print(f"File {output_path} already exists. Skipping conversion for {heic_path}.")
            return
        image.save(output_path, output_format)
        print(f"Successfully converted {heic_path} to {output_path}")
        
    except Exception as e:
        print(f"Error converting file {heic_path}: {e}")

def heic_to_img_batch(heic_paths, output_folder, output_format="JPEG"):
    for heic_path in heic_paths:
        heic_to_img(heic_path, output_folder, output_format)

def pdf_to_img(pdf_path, output_dir=".", output_format="JPEG", overwrite=False):
    try:
        from io import BytesIO
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            output_path = Path(output_dir, f"{Path(pdf_path).stem}_{page_num + 1}.{output_format.lower()}")
            if output_path.exists() and not overwrite:
                print(f"File {output_path} already exists. Skipping conversion for {pdf_path} page {page_num + 1}.")
                continue

            page = doc.load_page(page_num)
            images = page.get_images(full=True)

            if images:
                # Pick the largest embedded image (width * height) to skip thumbnails
                best = max(images, key=lambda img: img[2] * img[3])
                base_image = doc.extract_image(best[0])
                pil_img = Image.open(BytesIO(base_image["image"])).convert("RGB")
            else:
                # Fallback: render at 216 DPI (3× zoom) if no embedded images found
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                pil_img = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")

            pil_img.save(output_path, output_format, quality=95)
            print(f"Successfully converted {pdf_path} page {page_num + 1} to {output_path}")
    except Exception as e:
        print(f"Error converting file {pdf_path}: {e}")

def _mean_brightness(image_path):
    """Return the mean brightness (HSV V-channel, 0–255) of an image."""
    img = Image.open(image_path).convert("RGB")
    # Downsample for speed before converting to HSV
    img.thumbnail((400, 400))
    hsv = img.convert("HSV")
    v_channel = hsv.split()[2]  # V channel
    import numpy as np
    return float(np.array(v_channel).mean())


def remove_darker_duplicates(output_dir, output_format="JPEG", dry_run=False):
    """
    For every group of images that share the same stem up to the last '_N' page
    suffix (e.g. postcard_1.jpg, postcard_2.jpg produced from the same PDF),
    remove images whose brightness is below *half* of the brightest sibling.
    Images with no siblings are kept unless they fall below the absolute floor.

    Parameters
    ----------
    output_dir : str | Path
        Folder containing the converted images.
    output_format : str
        Extension to inspect (default 'JPEG', also matches 'jpg').
    dry_run : bool
        If True, only print what would be removed without deleting.
    """

    ext = output_format.lower()
    # Accept both .jpeg and .jpg when format is JPEG
    if ext == "jpeg":
        pattern = re.compile(r"(.+)_(\d+)\.jpe?g$", re.IGNORECASE)
    else:
        pattern = re.compile(rf"(.+)_(\d+)\.{re.escape(ext)}$", re.IGNORECASE)

    output_dir = Path(output_dir)
    groups: dict[str, list[Path]] = {}

    for img_path in sorted(output_dir.iterdir()):
        m = pattern.match(img_path.name)
        if m:
            stem = m.group(1)
            groups.setdefault(stem, []).append(img_path)

    removed = []
    for stem, paths in groups.items():
        if len(paths) < 2:
            continue  # nothing to compare against
        brightnesses = {p: _mean_brightness(p) for p in paths}
        max_brightness = max(brightnesses.values())
        for p, brightness in brightnesses.items():
            # Remove if less than 60% as bright as the brightest sibling
            if brightness < max_brightness * 0.60:
                if dry_run:
                    print(f"[dry-run] Would remove {p.name} (brightness {brightness:.1f} vs max {max_brightness:.1f})")
                else:
                    p.unlink()
                    print(f"Removed darker image {p.name} (brightness {brightness:.1f} vs max {max_brightness:.1f})")
                removed.append(p)

    if not removed:
        print("No darker duplicates found.")
    return removed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HEIC images to another format.")
    parser.add_argument("heic_paths", nargs="+", help="Paths to HEIC files to convert.")
    parser.add_argument("--output_folder", default=".", help="Folder to save converted images.")
    parser.add_argument("--output_format", default="JPEG", help="Format to convert to (e.g., JPEG, PNG).")
    args = parser.parse_args()
    heic_to_img_batch(args.heic_paths, args.output_folder, args.output_format)