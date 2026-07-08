#!/usr/bin/env python3
"""Serve generated image-cache eviction test pages and PNG images.

Run with:
    python server.py
or:
    uv run server.py

Then open:
    http://127.0.0.1:8000/?res=1200
"""

from __future__ import annotations

import argparse
import html
import io
import struct
import zlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse


DEFAULT_COUNT = 30
DEFAULT_RESOLUTION = 300
MAX_COUNT = 500
MAX_RESOLUTION = 8192

FONT = {
    " ": ["000", "000", "000", "000", "000", "000", "000"],
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["111", "001", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "001", "111", "001", "001", "111"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "010", "010", "010", "010"],
    "8": ["111", "101", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "101", "111", "001", "001", "111"],
    "g": ["111", "101", "101", "111", "001", "101", "111"],
    "i": ["010", "000", "110", "010", "010", "010", "111"],
    "m": ["10101", "11111", "11111", "10101", "10101", "10101", "10101"],
}


def clamped_int(values: list[str], default: int, minimum: int, maximum: int) -> int:
    if not values:
        return default
    try:
        value = int(values[0])
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def fill_rect(
    pixels: bytearray,
    width: int,
    height: int,
    left: int,
    top: int,
    rect_width: int,
    rect_height: int,
    color: tuple[int, int, int],
) -> None:
    right = min(width, left + rect_width)
    bottom = min(height, top + rect_height)
    left = max(0, left)
    top = max(0, top)
    if left >= right or top >= bottom:
        return

    row = bytes(color) * (right - left)
    for y in range(top, bottom):
        start = (y * width + left) * 3
        pixels[start : start + len(row)] = row


def text_size(text: str, scale: int) -> tuple[int, int]:
    width = 0
    for char in text:
        glyph = FONT.get(char, FONT[" "])
        width += (len(glyph[0]) + 1) * scale
    return max(0, width - scale), 7 * scale


def draw_text(
    pixels: bytearray,
    width: int,
    height: int,
    text: str,
    left: int,
    top: int,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    cursor = left
    for char in text:
        glyph = FONT.get(char, FONT[" "])
        for row_index, row in enumerate(glyph):
            for column_index, cell in enumerate(row):
                if cell == "1":
                    fill_rect(
                        pixels,
                        width,
                        height,
                        cursor + column_index * scale,
                        top + row_index * scale,
                        scale,
                        scale,
                        color,
                    )
        cursor += (len(glyph[0]) + 1) * scale


def generated_png(index: int, resolution: int) -> bytes:
    # RGB PNG with low compression: easy to generate and intentionally large enough
    # to put pressure on decoded image memory at high resolutions.
    width = resolution
    height = resolution
    red = (index * 47) % 256
    green = (index * 83) % 256
    blue = (index * 131) % 256

    pixels = bytearray(bytes([red, green, blue]) * width * height)

    label = f"img {index}"
    scale = max(1, resolution // 80)
    label_width, label_height = text_size(label, scale)
    padding = max(4, scale * 2)
    label_left = padding
    label_top = padding
    fill_rect(
        pixels,
        width,
        height,
        label_left - padding,
        label_top - padding,
        label_width + padding * 2,
        label_height + padding * 2,
        (0, 0, 0),
    )
    draw_text(
        pixels,
        width,
        height,
        label,
        label_left,
        label_top,
        scale,
        (255, 255, 255),
    )

    raw = b"".join(
        bytes([0]) + pixels[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )

    out = io.BytesIO()
    out.write(b"\x89PNG\r\n\x1a\n")
    out.write(
        png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
    )
    out.write(png_chunk(b"IDAT", zlib.compress(raw, level=1)))
    out.write(png_chunk(b"IEND", b""))
    return out.getvalue()


def page_html(count: int, resolution: int) -> bytes:
    query = urlencode({"res": resolution})
    images = []
    for index in range(1, count + 1):
        src = f"/image/{index}.png?{query}"
        images.append(
            f"""
            <section>
              <h2>pic {index}</h2>
              <img id="generated-png-{index}" data-test-image src="{html.escape(src)}"
                   width="{resolution}" height="{resolution}"
                   alt="Generated color square {index}">
            </section>
            <hr>
            """
        )

    body = f"""<!doctype html>
<meta charset="utf-8">
<title>Servo Image Cache Eviction: Generated PNG Server</title>
<style>
  body {{
    font: 16px/1.4 sans-serif;
    margin: 24px;
  }}

  .toolbar {{
    background: #f2f2f2;
    border: 1px solid #ccc;
    margin-bottom: 24px;
    padding: 12px;
    position: sticky;
    top: 0;
  }}

  img {{
    background: #ddd;
    display: block;
    height: auto;
    max-width: 300px;
    width: 100%;
  }}

  hr {{
    margin: 32px 0;
  }}
</style>
<h1>{count} generated PNG images</h1>
<div class="toolbar">
  <p>Generated image resolution: <strong>{resolution}x{resolution}</strong>.</p>
  <p>Displayed image width is capped at <strong>300px</strong>.</p>
  <p>Change the decoded size with <code>?res=1200</code>. Change count with <code>?count=60</code>.</p>
</div>
<main id="images">
{''.join(images)}
</main>
"""
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "ImageCacheEvictionTest/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        resolution = clamped_int(
            params.get("res", []), DEFAULT_RESOLUTION, 1, MAX_RESOLUTION
        )

        if parsed.path in ("/", "/index.html"):
            count = clamped_int(params.get("count", []), DEFAULT_COUNT, 1, MAX_COUNT)
            self.respond(
                HTTPStatus.OK,
                b"text/html; charset=utf-8",
                page_html(count, resolution),
                cacheable=False,
            )
            return

        if parsed.path.startswith("/image/") and parsed.path.endswith(".png"):
            name = parsed.path.removeprefix("/image/").removesuffix(".png")
            try:
                index = int(name)
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            self.respond(
                HTTPStatus.OK,
                b"image/png",
                generated_png(index, resolution),
                cacheable=True,
            )
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def respond(
        self, status: HTTPStatus, content_type: bytes, body: bytes, cacheable: bool
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type.decode("ascii"))
        self.send_header("Content-Length", str(len(body)))
        if cacheable:
            self.send_header("Cache-Control", "public, max-age=3600")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving on http://{args.host}:{args.port}/?res=1200")
    server.serve_forever()


if __name__ == "__main__":
    main()
