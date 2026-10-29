#!/usr/bin/env python3
"""
Prepares your photos for the birthday site. Run it on your computer, then commit & push.

  pip install pillow
  python optimize_images.py              # makes small thumbnails + media/manifest.json
  python optimize_images.py --shrink     # ALSO downsizes big originals to 1600px (keep a backup first!)

Folder layout expected (same as the site):
  media/            photos + videos for "Look at our memories"
  media/hafsa/      photos for "How you grow"   (change with --grow NAME)

Result:
  media/thumbs/<name>.jpg        small previews (800px) used by the grid
  media/hafsa/thumbs/<name>.jpg  small previews for the growing timeline
  media/manifest.json            file list, so the site does not need the GitHub API
"""
import argparse, json, re, sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is missing. Run:  pip install pillow")

IMG = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp"}   # gifs are left alone
VID = {".mp4", ".webm", ".mov", ".m4v", ".ogv"}
THUMB_SIZE, THUMB_Q = 800, 78
FULL_SIZE, FULL_Q = 1600, 82


def natural(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def kb(p):
    return p.stat().st_size / 1024


def make_thumb(src: Path, thumbs: Path):
    dst = thumbs / (src.stem + ".jpg")
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return False
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
        thumbs.mkdir(exist_ok=True)
        im.save(dst, "JPEG", quality=THUMB_Q, optimize=True, progressive=True)
    return True


def shrink(src: Path):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if max(im.size) <= FULL_SIZE:
            return False
        before = kb(src)
        im.thumbnail((FULL_SIZE, FULL_SIZE), Image.LANCZOS)
        if src.suffix.lower() in (".jpg", ".jpeg"):
            im.convert("RGB").save(src, "JPEG", quality=FULL_Q, optimize=True, progressive=True)
        else:
            im.save(src, optimize=True)
    print(f"    shrunk {src.name}: {before:.0f} KB -> {kb(src):.0f} KB")
    return True


def process(folder: Path, do_shrink: bool):
    files = sorted((f for f in folder.iterdir() if f.is_file()), key=natural)
    thumbs = folder / "thumbs"
    names = []
    for f in files:
        ext = f.suffix.lower()
        if f.name == "manifest.json" or not (ext in IMG or ext in VID or ext == ".gif"):
            continue
        names.append(f.name)
        if ext in IMG:
            try:
                if do_shrink:
                    shrink(f)
                if make_thumb(f, thumbs):
                    print(f"  thumb  {f.name}")
            except Exception as e:           # e.g. AVIF without plugin
                print(f"  skipped {f.name}: {e}")
        elif ext in VID and kb(f) > 8 * 1024:
            print(f"  note: {f.name} is {kb(f)/1024:.1f} MB - consider compressing it (see ffmpeg tip below)")
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", default="media")
    ap.add_argument("--grow", default="hafsa")
    ap.add_argument("--shrink", action="store_true", help="also downsize originals to %dpx" % FULL_SIZE)
    a = ap.parse_args()

    media = Path(a.media)
    if not media.is_dir():
        sys.exit(f"Folder '{media}' not found. Run this next to index.html.")

    print(f"[{media}]")
    manifest = {"media": process(media, a.shrink), "grow": []}

    grow = next((d for d in media.iterdir() if d.is_dir() and d.name.lower() == a.grow.lower()), None)
    if grow:
        print(f"[{grow}]")
        manifest["grow"] = process(grow, a.shrink)
    else:
        print(f"(no '{a.grow}' folder inside {media}, skipping the growing timeline)")

    (media / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nDone: {len(manifest['media'])} files in media, {len(manifest['grow'])} in {a.grow}.")
    print("Now commit and push media/ (including thumbs/ and manifest.json).")
    print("\nVideo tip (needs ffmpeg):")
    print('  ffmpeg -i in.mp4 -vf "scale=\'min(720,iw)\':-2" -c:v libx264 -crf 28 -preset slow -c:a aac -b:a 96k -movflags +faststart out.mp4')


if __name__ == "__main__":
    main()
