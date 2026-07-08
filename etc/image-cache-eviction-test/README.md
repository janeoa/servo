Image Cache Eviction Test
=========================

HTTP test server for manually putting pressure on Servo's image cache
with many large generated PNG images.

Run `uv run server.py` or `python server.py`, then open
`http://127.0.0.1:8000/?res=1200`.

The page renders 30 images by default, accepts `?count=60`, and serves square
PNGs sized by `?res` while displaying them at a maximum width of 300px.
