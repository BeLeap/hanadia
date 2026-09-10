#!/usr/bin/env python3
"""Render the Hanadia Mono README specimen as a PNG."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SAMPLE_LINES = (
    "abcdefghijklmnopqrstuvwxyz",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "0123456789",
    "",
    "Hello, 세계!",
    "가나다라마바사아자차카타파하",
    "한글 English 1234",
    "ABC가나다DEF",
    "가A나B다C",
    "",
    "-> => != === !== >= <=",
    "ffi fi fl",
    "",
    "│ ─ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_font(
    path: Path, size: int
) -> tuple[ImageFont.FreeTypeFont, list[str] | None]:
    try:
        return (
            ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM),
            ["calt"],
        )
    except (AttributeError, OSError, ValueError):
        # Keep the renderer usable with a Pillow build without libraqm.  The
        # Nix package enables it, so CI and release images use the same shaping
        # path whenever it is available.
        return ImageFont.truetype(str(path), size), None


def main() -> None:
    arguments = parse_args()
    font, features = load_font(arguments.font, 29)
    text = "\n".join(SAMPLE_LINES)
    spacing = 13
    padding = 40

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1), "white"))
    left, top, right, bottom = probe.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        spacing=spacing,
        features=features,
    )
    width = (right - left) + (padding * 2)
    height = (bottom - top) + (padding * 2)

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text(
        (padding - left, padding - top),
        text,
        font=font,
        fill="black",
        spacing=spacing,
        features=features,
    )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(arguments.output, format="PNG", optimize=False)


if __name__ == "__main__":
    main()
