# Link preview card

`og.html` draws the 1200×630 card from `cam_d.jpg` (a crop of the room) and the box jev returned
for that exact frame (`.69 .27 .84 .44`, seen 0.91). To re-render:

```
uv run --python 3.12 --with playwright --with pillow python render.py
cp og.jpg ../public/og.jpg
```
