"""Generate favicon-32.png and apple-touch-icon.png from favicon.svg.

Uses cairosvg if available, otherwise falls back to Pillow + aggdraw,
otherwise generates a pixel-perfect PNG using only the Python stdlib.
"""
import io
import math
import struct
import zlib
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "public_templates" / "food-trucks"

# Light-mode colours (dark background, white B)
BG = (0x2C, 0x2C, 0x2C, 255)
FG = (0xF8, 0xF9, 0xF8, 255)
TRANSPARENT = (0, 0, 0, 0)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    c = chunk_type + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def _write_png(pixels: list[list[tuple[int, int, int, int]]], path: Path) -> None:
    """Write an RGBA pixel grid as a PNG file using stdlib only."""
    h = len(pixels)
    w = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type None
        for r, g, b, a in row:
            raw.extend([r, g, b, a])
    compressed = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(_png_chunk(b"IDAT", compressed))
        f.write(_png_chunk(b"IEND", b""))


def _in_rounded_rect(
    px: float, py: float,
    x: float, y: float, w: float, h: float, rx: float,
) -> bool:
    """Return True if point (px, py) is inside the rounded rectangle."""
    # Clamp corner radius
    rx = min(rx, w / 2, h / 2)
    if px < x or px > x + w or py < y or py > y + h:
        return False
    # Check corners
    corners = [
        (x + rx, y + rx),
        (x + w - rx, y + rx),
        (x + rx, y + h - rx),
        (x + w - rx, y + h - rx),
    ]
    # If pixel is in a corner quadrant, check circle
    for cx, cy in corners:
        if (px < cx or px > x + w - (cx - x)) and (py < cy or py > y + h - (cy - y)):
            # More precise: only the "cut" corner
            pass
    # Horizontal / vertical bands are always inside
    if x + rx <= px <= x + w - rx:
        return True
    if y + rx <= py <= y + h - rx:
        return True
    # Corner circles
    for cx, cy in corners:
        if (px - cx) ** 2 + (py - cy) ** 2 <= rx ** 2:
            return True
    return False


# Pixel art "B" glyph — 7 wide × 10 tall (1 = foreground)
_B_GLYPH_7x10 = [
    "XXXXX..",
    "XX..XX.",
    "XX..XX.",
    "XXXXX..",
    "XX..XX.",
    "XX..XX.",
    "XX..XX.",
    "XXXXX..",
    ".......",
    ".......",
]


def _render(size: int) -> list[list[tuple[int, int, int, int]]]:
    """Render the favicon at *size* × *size* pixels."""
    scale = size / 100.0

    # Rounded rect parameters (matching SVG viewBox 0 0 100 100)
    rx_svg, ry_svg, rw_svg, rh_svg, rrx_svg = 5, 5, 90, 90, 18

    pixels: list[list[tuple[int, int, int, int]]] = []
    for y in range(size):
        row: list[tuple[int, int, int, int]] = []
        for x in range(size):
            # Centre of this pixel in SVG coordinates
            svgx = (x + 0.5) / scale
            svgy = (y + 0.5) / scale
            if _in_rounded_rect(svgx, svgy, rx_svg, ry_svg, rw_svg, rh_svg, rrx_svg):
                row.append(BG)
            else:
                row.append(TRANSPARENT)
        pixels.append(row)

    # Overlay the "B" glyph
    glyph_rows = 10
    glyph_cols = 7

    # Target glyph height: ~55% of size (matching font-size 64/100 * 90% of size)
    glyph_h = max(8, round(size * 0.55))
    glyph_w = round(glyph_h * glyph_cols / glyph_rows)
    cell_h = glyph_h / glyph_rows
    cell_w = glyph_w / glyph_cols

    # Centre horizontally; baseline at y=72 in SVG coords → pixel row
    baseline_px = round(72 * scale)
    # Ascent is roughly glyph_rows * cell_h
    top_px = baseline_px - round(glyph_rows * cell_h * 0.85)
    left_px = size // 2 - glyph_w // 2

    for row_i, row_str in enumerate(_B_GLYPH_7x10):
        py_start = top_px + round(row_i * cell_h)
        py_end = top_px + round((row_i + 1) * cell_h)
        for col_i, ch in enumerate(row_str):
            if ch != "X":
                continue
            px_start = left_px + round(col_i * cell_w)
            px_end = left_px + round((col_i + 1) * cell_w)
            for py in range(max(0, py_start), min(size, py_end)):
                for px in range(max(0, px_start), min(size, px_end)):
                    if pixels[py][px] != TRANSPARENT:
                        pixels[py][px] = FG

    return pixels


def _try_cairosvg(svg_path: Path, out_path: Path, size: int) -> bool:
    try:
        import cairosvg  # type: ignore[import]
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(out_path),
            output_width=size,
            output_height=size,
        )
        return True
    except Exception:
        return False


def generate(size: int, filename: str) -> None:
    svg_path = TEMPLATE_DIR / "favicon.svg"
    out_path = TEMPLATE_DIR / filename

    # Prefer cairosvg for accurate font rendering
    if _try_cairosvg(svg_path, out_path, size):
        print(f"  cairosvg → {out_path} ({size}×{size})")
        return

    # Stdlib fallback: pixel-art render
    pixels = _render(size)
    _write_png(pixels, out_path)
    print(f"  stdlib PNG → {out_path} ({size}×{size})")


if __name__ == "__main__":
    print("Generating favicon PNGs …")
    generate(32, "favicon-32.png")
    generate(180, "apple-touch-icon.png")
    print("Done.")
