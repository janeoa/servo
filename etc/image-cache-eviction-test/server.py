#!/usr/bin/env python3
"""Serve a tall page of generated PNGs for manual image-cache testing."""

from __future__ import annotations

import html
import struct
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def generated_png(index: int, resolution: int) -> bytes:
    color = bytes(((index * 47) % 256, (index * 83) % 256, (index * 131) % 256))
    row = b"\0" + color * resolution
    header = struct.pack(">IIBBBBB", resolution, resolution, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(row * resolution, level=1))
        + png_chunk(b"IEND", b"")
    )


def bounded_parameter(query: dict[str, list[str]], name: str, default: int, maximum: int) -> int:
    try:
        value = int(query.get(name, [str(default)])[0])
    except ValueError:
        value = default
    return max(1, min(value, maximum))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        request = urlparse(self.path)
        query = parse_qs(request.query)
        count = bounded_parameter(query, "count", 100, 500)
        resolution = bounded_parameter(query, "res", 1200, 8192)

        if request.path == "/":
            images = "\n".join(
                f'<figure><img src="/image/{index}.png?res={resolution}">'
                f"<figcaption>Image {index}</figcaption></figure>"
                for index in range(count)
            )
            document = f"""<!doctype html>
<meta charset="utf-8">
<title>Image cache eviction test</title>
<style>
  body {{ margin: 0 auto; max-width: 1040px; font: 16px sans-serif; }}
  figure {{ margin: 40px 0; min-height: 1040px; }}
  img {{ display: block; width: 1000px; height: 1000px; object-fit: cover; }}
</style>
<h1>{html.escape(str(count))} generated images</h1>
{images}
""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(document)))
            self.end_headers()
            self.wfile.write(document)
            return

        if request.path.startswith("/image/"):
            try:
                index = int(request.path.removeprefix("/image/").removesuffix(".png"))
            except ValueError:
                self.send_error(404)
                return
            image = generated_png(index, resolution)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)
            return

        self.send_error(404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
