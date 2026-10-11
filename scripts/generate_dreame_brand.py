"""Build official-format Home Assistant integration branding from source art.

This script modifies only custom_components/dreame_wet_dry_vacuum/brand/.
It does not touch the standalone dashboard. Requires cairoSVG + Pillow.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "branding" / "dreame-logo.svg"
DEST = ROOT / "custom_components" / "dreame_wet_dry_vacuum" / "brand"


def render_svg(height: int) -> Image.Image:
    """Rasterize a vector brand asset to RGBA at the requested height."""
    data = cairosvg.svg2png(
        bytestring=SOURCE.read_bytes(), output_height=height
    )
    return Image.open(BytesIO(data)).convert("RGBA")


def fitted_image(image: Image.Image, size: tuple[int, int], margin: int = 0) -> Image.Image:
    """Fit visible nontransparent pixels into a transparent canvas."""
    bounds = image.getbbox()
    if not bounds:
        raise ValueError("Brand SVG rendered as a blank image")
    image = image.crop(bounds)
    max_width, max_height = size[0] - 2 * margin, size[1] - 2 * margin
    scale = min(max_width / image.width, max_height / image.height)
    newsize = (
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
    )
    image = image.resize(newsize, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size)
    canvas.alpha_composite(
        image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2)
    )
    return canvas


def build() -> None:
    """Generate square integration icon and landscape logo, normal and 2x."""
    DEST.mkdir(parents=True, exist_ok=True)
    # First Dreame emblem is to the left of the wordmark in the source SVG.
    # Crop proportionally by the viewBox width (24 out of 128 units).
    source = render_svg(1400)
    emblem = source.crop((0, 0, round(source.width * 24 / 128), source.height))
    for size, suffix in ((256, ""), (512, "@2x")):
        icon = fitted_image(emblem, (size, size), margin=round(size * 0.09))
        icon.save(DEST / f"icon{suffix}.png", format="PNG", optimize=True)
        # Logos use the complete source wordmark and a height of 256 or 512.
        landscape = fitted_image(source, (round(size * 128 / 26), size))
        landscape.save(DEST / f"logo{suffix}.png", format="PNG", optimize=True)
    for filename in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        with Image.open(DEST / filename) as image:
            if image.mode != "RGBA" or not image.getbbox():
                raise AssertionError(f"Invalid brand image: {filename}")
            print(f"{filename}: {image.size[0]}x{image.size[1]}")


if __name__ == "__main__":
    build()
