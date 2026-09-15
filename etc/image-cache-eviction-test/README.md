# Image cache eviction test

This local page creates enough independently decoded PNGs to exercise the viewport-aware image
cache budget.

Run `python server.py`, then open `http://127.0.0.1:8000/?count=100&res=1200` with
`image_layout_driven_decode_downscaling_enabled` enabled. Scroll through the page and back again;
images within one viewport of the visible area should decode before entering the viewport, while
older offscreen decodes are evicted when the configured byte limit is exceeded.

The `count` and `res` query parameters control the number and natural resolution of the images.
At the defaults, the 1000×1000 display decodes total about 381 MiB, exceeding the default cap.
