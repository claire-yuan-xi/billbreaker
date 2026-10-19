# Regenerate billbreaker/static/images/capitol-depth.png after changing the hero photo:
#   python3 scripts/make-depth-map.py billbreaker/static/images/capitol.jpg billbreaker/static/images/capitol-depth.png
# Needs Pillow and numpy. The sky/dome thresholds are tuned for the current photo.
# Builds a depth + sky mask for the Capitol photo: R = depth (white = near), G = sky.
import sys
import numpy as np
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
W = 800
im = Image.open(src).convert("RGB")
im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
a = np.asarray(im).astype(np.float32) / 255
h, w, _ = a.shape
r, g, b = a[..., 0], a[..., 1], a[..., 2]
y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))  # 0 = top

# Sky: blue-dominant, or bright and pale (wispy cloud), and above the roofline.
blue = np.clip((b - r - 0.06) / 0.14, 0, 1)
pale = ((r + g + b) / 3 > 0.72) & (b >= r) & ((b - r) > 0.015)
sky = np.maximum(blue, pale * 0.9)
x = np.linspace(0, 1, w)[None, :] * np.ones((h, 1))
# This photo: high up and away from the dome it is all sky, clouds included.
open_sky = (y < 0.48) & ((x < 0.4) | (x > 0.6))
sky = np.where(open_sky, 1.0, sky)
# Around the dome only clearly blue pixels count, so its shaded side stays stone.
dome = (x > 0.42) & (x < 0.58)
sky = np.where(dome, np.clip((b - r - 0.16) / 0.1, 0, 1), sky)
# Anything below the building's base is never sky.
sky *= np.clip((0.74 - y) / 0.04, 0, 1)
# Flood from the top: keep sky connected to the top edge, so white stone with a
# blue cast (shadowed columns) is not mistaken for sky.
mask = sky > 0.5
conn = np.zeros_like(mask)
conn[0] = mask[0]
for i in range(1, h):
    row = mask[i] & (conn[i - 1] | np.roll(conn[i - 1], 1) | np.roll(conn[i - 1], -1))
    # spread sideways along the row
    for _ in range(3):
        row |= mask[i] & (np.roll(row, 1) | np.roll(row, -1))
    conn[i] = row
sky = np.where(conn, sky, 0)

# Depth: sky far, building a flat plane, the lawn ramps toward the camera.
base = 0.70  # where the terrace meets the lawn, as a fraction from the top
ground = np.clip((y - base) / (1 - base), 0, 1) ** 0.8
depth = 0.42 + 0.58 * ground
# Trees in front of the terraces read a touch nearer than the stone behind them.
green = (g > r * 1.08) & (g > b * 1.05) & (y > 0.55)
depth = np.where(green, np.maximum(depth, 0.55 + 0.4 * ground), depth)
depth = depth * (1 - sky)

def blur(x, rad):
    return np.asarray(
        Image.fromarray((x * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rad))
    ).astype(np.float32) / 255

depth = blur(depth, 2.5)
sky = blur(sky, 1.2)
outa = np.stack([depth, sky, np.zeros_like(depth)], -1)
Image.fromarray((outa * 255).astype(np.uint8)).save(out, optimize=True)
print(out, outa.shape)
