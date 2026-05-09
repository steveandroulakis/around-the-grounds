/**
 * Generate favicon-32.png and apple-touch-icon.png from favicon.svg.
 * Uses only Node.js stdlib (no npm packages required).
 */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const TEMPLATE_DIR = path.join(__dirname, "public_templates", "food-trucks");

// Light-mode colours (dark background, white B)
const BG = [0x2c, 0x2c, 0x2c, 255];
const FG = [0xf8, 0xf9, 0xf8, 255];
const TRANSPARENT = [0, 0, 0, 0];

function pngChunk(type, data) {
  const buf = Buffer.alloc(12 + data.length);
  buf.writeUInt32BE(data.length, 0);
  buf.write(type, 4, "ascii");
  data.copy(buf, 8);
  const crc = crc32(Buffer.concat([Buffer.from(type, "ascii"), data]));
  buf.writeUInt32BE(crc >>> 0, 8 + data.length);
  return buf;
}

// CRC32 lookup table
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc = CRC_TABLE[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function writePng(pixels, filePath) {
  const h = pixels.length;
  const w = pixels[0].length;

  // Build raw scanlines (filter byte 0 + RGBA)
  const raw = Buffer.alloc(h * (1 + w * 4));
  let offset = 0;
  for (const row of pixels) {
    raw[offset++] = 0; // filter type None
    for (const [r, g, b, a] of row) {
      raw[offset++] = r;
      raw[offset++] = g;
      raw[offset++] = b;
      raw[offset++] = a;
    }
  }
  const compressed = zlib.deflateSync(raw, { level: 9 });

  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 6; // 8-bit RGBA
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const out = Buffer.concat([
    sig,
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", compressed),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
  fs.writeFileSync(filePath, out);
}

function inRoundedRect(px, py, x, y, w, h, rx) {
  rx = Math.min(rx, w / 2, h / 2);
  if (px < x || px > x + w || py < y || py > y + h) return false;
  if (px >= x + rx && px <= x + w - rx) return true;
  if (py >= y + rx && py <= y + h - rx) return true;
  const corners = [
    [x + rx, y + rx],
    [x + w - rx, y + rx],
    [x + rx, y + h - rx],
    [x + w - rx, y + h - rx],
  ];
  for (const [cx, cy] of corners) {
    if ((px - cx) ** 2 + (py - cy) ** 2 <= rx ** 2) return true;
  }
  return false;
}

// Pixel-art "B" glyph — 7 wide × 10 tall
const B_GLYPH = [
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
];

function render(size) {
  const scale = size / 100.0;
  const pixels = Array.from({ length: size }, () =>
    Array.from({ length: size }, () => [...TRANSPARENT]),
  );

  // Draw rounded rect
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const svgx = (x + 0.5) / scale;
      const svgy = (y + 0.5) / scale;
      if (inRoundedRect(svgx, svgy, 5, 5, 90, 90, 18)) {
        pixels[y][x] = [...BG];
      }
    }
  }

  // Overlay "B" glyph
  const glyphRows = 10,
    glyphCols = 7;
  const glyphH = Math.max(8, Math.round(size * 0.55));
  const glyphW = Math.round((glyphH * glyphCols) / glyphRows);
  const cellH = glyphH / glyphRows;
  const cellW = glyphW / glyphCols;
  const baselinePx = Math.round(72 * scale);
  const topPx = baselinePx - Math.round(glyphRows * cellH * 0.85);
  const leftPx = Math.floor(size / 2) - Math.floor(glyphW / 2);

  for (let ri = 0; ri < B_GLYPH.length; ri++) {
    const pyStart = topPx + Math.round(ri * cellH);
    const pyEnd = topPx + Math.round((ri + 1) * cellH);
    for (let ci = 0; ci < B_GLYPH[ri].length; ci++) {
      if (B_GLYPH[ri][ci] !== "X") continue;
      const pxStart = leftPx + Math.round(ci * cellW);
      const pxEnd = leftPx + Math.round((ci + 1) * cellW);
      for (let py = Math.max(0, pyStart); py < Math.min(size, pyEnd); py++) {
        for (let px = Math.max(0, pxStart); px < Math.min(size, pxEnd); px++) {
          if (pixels[py][px][3] !== 0) pixels[py][px] = [...FG];
        }
      }
    }
  }

  return pixels;
}

console.log("Generating favicon PNGs...");

const pixels32 = render(32);
writePng(pixels32, path.join(TEMPLATE_DIR, "favicon-32.png"));
console.log("  favicon-32.png (32×32)");

const pixels180 = render(180);
writePng(pixels180, path.join(TEMPLATE_DIR, "apple-touch-icon.png"));
console.log("  apple-touch-icon.png (180×180)");

console.log("Done.");
