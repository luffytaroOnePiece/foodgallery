#!/usr/bin/env python3
"""
Image to JPG Converter
- Converts all images to high-quality JPGs under 500 KB
- Renames them sequentially starting from a user-provided number
- Place this script in the same folder as your images and run it
"""

import os
import sys
import importlib
import importlib.util
import io
from pathlib import Path


def ensure_dependencies():
    for package, import_name in [("Pillow", "PIL"), ("pillow-heif", "pillow_heif")]:
        if importlib.util.find_spec(import_name) is None:
            print(f"Installing {package}...")
            os.system(f"{sys.executable} -m pip install {package}")


ensure_dependencies()

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".ico", ".heic", ".heif"}
TARGET_SIZE_KB = 500
TARGET_BYTES   = TARGET_SIZE_KB * 1024


def get_images_in_folder(folder: Path) -> list[Path]:
    script_name = Path(__file__).stem
    return [
        f for f in sorted(folder.iterdir())
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXTENSIONS
        and f.stem != script_name
    ]


def convert_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
        bg.paste(img, mask=mask)
        return bg
    elif img.mode != "RGB":
        return img.convert("RGB")
    return img


def compress_to_target(img: Image.Image, target_bytes: int) -> tuple[bytes, int]:
    """
    Binary-search JPEG quality (95 → 20) until output fits within target_bytes.
    Also downscales if even quality=20 is still too large.
    Returns (jpeg_bytes, quality_used).
    """
    lo, hi = 20, 95
    best_bytes = None
    best_quality = lo

    # First quick check: does quality=95 already fit?
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, optimize=True)
    if buf.tell() <= target_bytes:
        return buf.getvalue(), 95

    # Binary search for the highest quality that fits
    while lo <= hi:
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=mid, optimize=True)
        size = buf.tell()

        if size <= target_bytes:
            best_bytes = buf.getvalue()
            best_quality = mid
            lo = mid + 1          # try higher quality
        else:
            hi = mid - 1          # try lower quality

    if best_bytes:
        return best_bytes, best_quality

    # Even quality=20 is too large — downscale progressively
    scale = 0.9
    while scale >= 0.2:
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, "JPEG", quality=20, optimize=True)
        if buf.tell() <= target_bytes:
            return buf.getvalue(), 20
        scale -= 0.05

    # Last resort: return quality=20 original-size
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=20, optimize=True)
    return buf.getvalue(), 20


def convert_images(start_number: int):
    script_dir = Path(__file__).parent.resolve()
    images = get_images_in_folder(script_dir)

    if not images:
        print("No supported image files found in this folder.")
        return

    print(f"\nFound {len(images)} image(s) to convert.")
    print(f"Target size : ≤ {TARGET_SIZE_KB} KB per image")
    print(f"Numbering   : starting from {start_number}\n")

    temp_prefix = "__temp_converting__"
    temp_files  = []
    failed      = 0

    for i, img_path in enumerate(images):
        counter     = start_number + i
        output_name = f"{counter}.jpg"
        temp_name   = f"{temp_prefix}{counter}.jpg"
        temp_path   = script_dir / temp_name

        try:
            with Image.open(img_path) as img:
                img = convert_to_rgb(img)
                jpeg_bytes, quality = compress_to_target(img, TARGET_BYTES)

            temp_path.write_bytes(jpeg_bytes)
            size_kb = len(jpeg_bytes) / 1024
            temp_files.append((temp_path, script_dir / output_name, img_path))
            print(f"  ✔ {img_path.name:45s} → {output_name}  ({size_kb:.0f} KB, q={quality})")

        except Exception as e:
            print(f"  ✘ Failed: {img_path.name} — {e}")
            failed += 1

    print("\nFinalising files...")
    for temp_path, final_path, original_path in temp_files:
        try:
            if original_path.resolve() != final_path.resolve():
                original_path.unlink()
            temp_path.rename(final_path)
        except Exception as e:
            print(f"  ✘ Error finalising {final_path.name}: {e}")

    print(f"\nDone! {len(temp_files)} converted, {failed} failed.")


def main():
    print("=" * 55)
    print("   Image → JPG Converter  (target ≤ 500 KB)")
    print("=" * 55)

    if len(sys.argv) == 2:
        try:
            start_number = int(sys.argv[1])
        except ValueError:
            print("Error: Starting number must be an integer.")
            sys.exit(1)
    else:
        while True:
            try:
                start_number = int(input("\nEnter starting number (e.g. 15): ").strip())
                break
            except ValueError:
                print("Please enter a valid integer.")

    convert_images(start_number)


if __name__ == "__main__":
    main()


# python3 -m venv path/to/venv 
#source path/to/venv/bin/activate