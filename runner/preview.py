#!/usr/bin/env python3
"""Offscreen nahled animace do GIF/PNG (na PC, bez rgbmatrix).

Snimky renderuje izolovany podproces z runner/validate.py, tento proces
kod animace nespousti. Zvetseni nearest-neighbor (vychozi 8x).

Pouziti:
    python -m runner.preview library/plasma_ocean.py
    python -m runner.preview library/plasma_ocean.py --seconds 15 --scale 6
    python -m runner.preview library/plasma_ocean.py --png     # + PNG s nahledy
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from runner import contract as C  # noqa: E402
from runner.validate import render_frames, static_check  # noqa: E402

DEFAULT_OUT = ROOT / "previews"


def to_images(frames, scale):
    size = (C.WIDTH * scale, C.HEIGHT * scale)
    return [Image.fromarray(f, "RGB").resize(size, Image.NEAREST) for f in frames]


def save_gif(images, fps, path):
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=round(1000 / fps), loop=0, optimize=False)


def save_sheet(images, path, count=8, cols=4, gap=4):
    """PNG s `count` snimky rovnomerne rozlozenymi v case."""
    step = max(1, len(images) // count)
    picked = images[::step][:count]
    w, h = picked[0].size
    rows = (len(picked) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap),
                      (40, 40, 40))
    for i, img in enumerate(picked):
        sheet.paste(img, ((i % cols) * (w + gap), (i // cols) * (h + gap)))
    sheet.save(path)


def main(argv=None):
    p = argparse.ArgumentParser(description="Náhled animace do GIF/PNG.")
    p.add_argument("file", type=Path)
    p.add_argument("--seconds", type=float, default=10.0,
                   help="délka náhledu v s (výchozí 10; 0 = celé DURATION)")
    p.add_argument("--scale", type=int, default=8)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="výstupní adresář")
    p.add_argument("--png", action="store_true", help="uložit i PNG s 8 snímky")
    a = p.parse_args(argv)

    source = a.file.read_text(encoding="utf-8")
    errors, _ = static_check(source)
    if errors:
        print("Statická kontrola neprošla:", *errors, sep="\n  ", file=sys.stderr)
        return 1
    try:
        meta, frames = render_frames(source, str(a.file), a.seconds)
    except RuntimeError as e:
        print(f"Render selhal: {e}", file=sys.stderr)
        return 1

    a.out.mkdir(parents=True, exist_ok=True)
    images = to_images(frames, a.scale)
    gif = a.out / f"{a.file.stem}.gif"
    save_gif(images, meta["fps"], gif)
    print(f"{gif}  ({len(frames)} snímků, {meta['fps']} FPS)")
    if a.png:
        png = a.out / f"{a.file.stem}.png"
        save_sheet(images, png)
        print(png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
