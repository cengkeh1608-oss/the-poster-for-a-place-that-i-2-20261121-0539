"""LUMARA — The Falls That Climb the Sky.
Travel poster for a place that does not exist.
Pure-stdlib Python 3.13: own PNG encoder/decoder, own drawing primitives,
glyph atlas (Liberation Sans, OFL) shipped in assets/ as data.
Deterministic: same bytes on every run. Writes /output/entry.png (1024x1024).
"""
import json
import os
import struct
import zlib

W = H = 1024
BASE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- PNG codec
def read_png_gray(path):
    """Decode a non-interlaced 8-bit grayscale PNG -> (w, h, bytes)."""
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    w = h = None
    bitdepth = ctype = None
    idat = b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitdepth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + ln
    assert ctype == 0 and bitdepth == 8, (ctype, bitdepth)
    raw = zlib.decompress(idat)
    px = bytearray(w * h)
    prev = bytearray(w)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        row = bytearray(raw[p:p + w])
        p += w
        if f == 1:
            for i in range(1, w):
                row[i] = (row[i] + row[i - 1]) & 255
        elif f == 2:
            for i in range(w):
                row[i] = (row[i] + prev[i]) & 255
        elif f == 3:
            for i in range(w):
                a = row[i - 1] if i else 0
                row[i] = (row[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(w):
                a = row[i - 1] if i else 0
                b = prev[i]
                c = prev[i - 1] if i else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + pr) & 255
        px[y * w:(y + 1) * w] = row
        prev = row
    return w, h, bytes(px)


def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def png_encode_rgb(w, h, px):
    """Encode RGB bytearray as PNG (per-row filter 0 or 2, whichever is smaller)."""
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    prev = bytes(w * 3)
    for y in range(h):
        row = bytes(px[y * w * 3:(y + 1) * w * 3])
        up = bytes((a - b) & 255 for a, b in zip(row, prev))
        s_up = sum(v if v < 128 else 256 - v for v in up)
        s_raw = sum(v if v < 128 else 256 - v for v in row)
        if s_up <= s_raw:
            raw.append(2)
            raw += up
        else:
            raw.append(0)
            raw += row
        prev = row
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b""))


# ---------------------------------------------------------------- canvas
cv = bytearray(W * H * 3)


def _blend(i, r, g, b, a):
    if a >= 255:
        cv[i] = r
        cv[i + 1] = g
        cv[i + 2] = b
    elif a > 0:
        ia = 255 - a
        cv[i] = (r * a + cv[i] * ia) // 255
        cv[i + 1] = (g * a + cv[i + 1] * ia) // 255
        cv[i + 2] = (b * a + cv[i + 2] * ia) // 255


def fill_rect(x0, y0, x1, y1, color, alpha=255):
    x0 = max(0, int(x0))
    y0 = max(0, int(y0))
    x1 = min(W, int(x1))
    y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = color
    if alpha >= 255:
        row = bytes((r, g, b)) * (x1 - x0)
        for y in range(y0, y1):
            cv[y * W * 3 + x0 * 3: y * W * 3 + x1 * 3] = row
    else:
        for y in range(y0, y1):
            base = y * W * 3
            for x in range(x0, x1):
                _blend(base + x * 3, r, g, b, alpha)


def fill_span(y, x0, x1, color, alpha=255):
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    if x1 <= x0:
        return
    r, g, b = color
    if alpha >= 255:
        cv[y * W * 3 + x0 * 3: y * W * 3 + x1 * 3] = bytes((r, g, b)) * (x1 - x0)
    else:
        base = y * W * 3
        for x in range(x0, x1):
            _blend(base + x * 3, r, g, b, alpha)


def vgrad(y0, y1, stops):
    """Vertical gradient; stops = [(pos0to1, (r,g,b)), ...] sorted by pos."""
    y0 = max(0, int(y0))
    y1 = min(H, int(y1))
    n = y1 - y0
    if n <= 0:
        return
    for y in range(y0, y1):
        t = (y - y0) / max(1, n - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                r = int(c0[0] + (c1[0] - c0[0]) * f)
                g = int(c0[1] + (c1[1] - c0[1]) * f)
                b = int(c0[2] + (c1[2] - c0[2]) * f)
                break
        else:
            r, g, b = stops[-1][1]
        cv[y * W * 3:(y + 1) * W * 3] = bytes((r, g, b)) * W


def fill_poly(pts, color, alpha=255):
    ys = [p[1] for p in pts]
    y0 = max(0, int(min(ys)))
    y1 = min(H - 1, int(max(ys)))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, yy0 = pts[i]
            x1, yy1 = pts[(i + 1) % n]
            if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                t = (y - yy0) / (yy1 - yy0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            fill_span(y, xs[j], xs[j + 1], color, alpha)


def ellipse(cx, cy, rx, ry, color, alpha=255, soft=0.0):
    """Filled ellipse; soft>0 fades the rim over that fraction of the radius."""
    x0 = max(0, int(cx - rx))
    x1 = min(W, int(cx + rx) + 1)
    y0 = max(0, int(cy - ry))
    y1 = min(H, int(cy + ry) + 1)
    r, g, b = color
    for y in range(y0, y1):
        dy = (y - cy) / ry
        base = y * W * 3
        for x in range(x0, x1):
            dx = (x - cx) / rx
            d2 = dx * dx + dy * dy
            if d2 > 1.0:
                continue
            a = alpha
            if soft > 0.0:
                d = d2 ** 0.5
                if d > 1.0 - soft:
                    a = int(alpha * (1.0 - d) / soft)
            if a > 0:
                _blend(base + x * 3, r, g, b, a)


def radial_glow(cx, cy, rad, color, peak):
    """Soft radial glow, alpha ~ (1 - d/r)^2 * peak."""
    x0 = max(0, int(cx - rad))
    x1 = min(W, int(cx + rad) + 1)
    y0 = max(0, int(cy - rad))
    y1 = min(H, int(cy + rad) + 1)
    r, g, b = color
    for y in range(y0, y1):
        dy = y - cy
        base = y * W * 3
        for x in range(x0, x1):
            dx = x - cx
            d = (dx * dx + dy * dy) ** 0.5
            if d >= rad:
                continue
            f = 1.0 - d / rad
            a = int(peak * f * f)
            if a > 0:
                _blend(base + x * 3, r, g, b, a)


def thick_line(x0, y0, x1, y1, w, color, alpha=255):
    import math
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln * w / 2.0, dx / ln * w / 2.0
    fill_poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
               (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color, alpha)


# ---------------------------------------------------------------- text
ATLAS_W, ATLAS_H, ATLAS = read_png_gray(os.path.join(BASE, "assets", "atlas.png"))
with open(os.path.join(BASE, "assets", "metrics.json")) as f:
    METRICS = json.load(f)


def text_width(text, font, size, tracking=0):
    m = METRICS["fonts"][font]
    s = size / METRICS["size"]
    w = 0.0
    for ch in text:
        g = m["glyphs"].get(ch)
        if g is None:
            continue
        w += g["adv"] * s + tracking
    return w - tracking if text else 0.0


def _blit_glyph(g, dx0, dy0, dw, dh, color, alpha):
    ax, ay, sw, sh = g["ax"], g["ay"], g["w"], g["h"]
    x0 = max(0, int(dx0))
    x1 = min(W, int(dx0 + dw + 1))
    y0 = max(0, int(dy0))
    y1 = min(H, int(dy0 + dh + 1))
    r, gg, b = color
    for y in range(y0, y1):
        sy = (y + 0.5 - dy0) / dh * sh - 0.5
        sy0 = int(sy)
        fy = sy - sy0
        sy0 = 0 if sy0 < 0 else (sh - 2 if sy0 > sh - 2 else sy0)
        row0 = (ay + sy0) * ATLAS_W + ax
        row1 = (ay + sy0 + 1) * ATLAS_W + ax
        base = y * W * 3
        for x in range(x0, x1):
            sx = (x + 0.5 - dx0) / dw * sw - 0.5
            sx0 = int(sx)
            fx = sx - sx0
            sx0 = 0 if sx0 < 0 else (sw - 2 if sx0 > sw - 2 else sx0)
            a00 = ATLAS[row0 + sx0]
            a10 = ATLAS[row0 + sx0 + 1]
            a01 = ATLAS[row1 + sx0]
            a11 = ATLAS[row1 + sx0 + 1]
            a = (a00 * (1 - fx) * (1 - fy) + a10 * fx * (1 - fy)
                 + a01 * (1 - fx) * fy + a11 * fx * fy) * alpha / 255.0
            if a > 0.5:
                _blend(base + x * 3, r, gg, b, int(a))


def draw_text(text, font, size, cx, baseline_y, color, tracking=0, alpha=255):
    """Draw centred text; baseline_y is the text baseline."""
    m = METRICS["fonts"][font]
    s = size / METRICS["size"]
    total = text_width(text, font, size, tracking)
    pen = cx - total / 2.0
    for ch in text:
        g = m["glyphs"].get(ch)
        if g is None:
            pen += 12 * s
            continue
        if g["w"] > 0:
            _blit_glyph(g, pen + g["bx"] * s, baseline_y + g["by"] * s,
                        g["w"] * s, g["h"] * s, color, alpha)
        pen += g["adv"] * s + tracking


# ---------------------------------------------------------------- scene
CREAM = (255, 244, 220)
INK = (28, 34, 52)


def _edge_x(pts, y):
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if y0 <= y <= y1:
            t = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
            return x0 + t * (x1 - x0)
    return pts[-1][0] if y > pts[-1][1] else pts[0][0]


def fill_tapered(left_pts, right_pts, y_top, y_bot, c_top, c_bot, alpha=255):
    import math
    for y in range(int(y_top), int(y_bot) + 1):
        t = (y - y_top) / max(1, y_bot - y_top)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        wob = 3.5 * math.sin(y * 0.02)
        fill_span(y, _edge_x(left_pts, y) + wob, _edge_x(right_pts, y) + wob,
                  (r, g, b), alpha)


def sailboat(cx, cy, s, flip=1):
    fill_poly([(cx - 26 * s, cy), (cx + 26 * s, cy),
               (cx + 16 * s, cy + 12 * s), (cx - 16 * s, cy + 12 * s)], INK)
    fill_poly([(cx, cy - 4 * s), (cx, cy - 42 * s), (cx + 30 * s * flip, cy - 4 * s)],
              (250, 240, 214))
    thick_line(cx, cy - 42 * s, cx, cy, 2, INK)


def house(x, y, w, h):
    fill_rect(x, y - h, x + w, y, (26, 32, 54))
    fill_poly([(x - 3, y - h), (x + w / 2, y - h - 10), (x + w + 3, y - h)], (20, 24, 44))
    fill_rect(x + w * 0.25, y - h * 0.55, x + w * 0.25 + 5, y - h * 0.55 + 6, (255, 200, 110))
    fill_rect(x + w * 0.60, y - h * 0.55, x + w * 0.60 + 5, y - h * 0.55 + 6, (255, 200, 110))


def lighthouse(x, y_base):
    fill_rect(x - 8, y_base - 55, x + 8, y_base, (240, 235, 220))
    fill_rect(x - 11, y_base - 64, x + 11, y_base - 55, (200, 60, 50))
    ellipse(x, y_base - 67, 6, 6, (255, 230, 140))
    radial_glow(x, y_base - 67, 40, (255, 220, 130), 80)


def bird(cx, cy, s):
    c = (38, 38, 66)
    thick_line(cx - 7 * s, cy, cx, cy - 4 * s, 2, c)
    thick_line(cx, cy - 4 * s, cx + 7 * s, cy, 2, c)


def draw_poster():
    # ---- sky: deep violet -> rose -> amber at the horizon (y=620)
    vgrad(0, 620, [(0.0, (38, 32, 74)), (0.42, (126, 66, 104)),
                   (0.72, (214, 116, 72)), (1.0, (245, 176, 74))])
    # ---- sun + glow, upper right of the falls
    radial_glow(712, 296, 300, (255, 190, 110), 180)
    ellipse(712, 296, 92, 92, (255, 200, 120), alpha=40, soft=0.7)
    ellipse(712, 296, 68, 68, (205, 115, 70), alpha=130)
    ellipse(712, 296, 56, 56, (255, 250, 232))
    # ---- soft clouds
    ellipse(170, 170, 120, 26, (255, 240, 215), alpha=120, soft=0.6)
    ellipse(860, 140, 140, 30, (255, 240, 215), alpha=110, soft=0.6)
    ellipse(830, 430, 90, 20, (255, 240, 215), alpha=90, soft=0.6)
    # ---- birds
    for (bx, by, bs) in [(250, 280, 1.0), (330, 240, 0.8), (640, 220, 0.9),
                         (780, 200, 0.7), (880, 260, 0.9), (180, 330, 0.8)]:
        bird(bx, by, bs)
    # ---- cliffs framing the falls
    fill_poly([(0, 620), (0, 430), (70, 400), (150, 440), (210, 380),
               (290, 420), (330, 470), (300, 620)], (30, 42, 68))
    fill_poly([(1024, 620), (1024, 450), (950, 420), (880, 460), (820, 400),
               (760, 450), (700, 480), (730, 620)], (30, 42, 68))
    # rim light on the falls-facing cliff edges and along the ridges
    thick_line(300, 620, 330, 470, 5, (96, 132, 150), alpha=170)
    thick_line(730, 620, 700, 480, 5, (96, 132, 150), alpha=170)
    for (ax, ay, bx, by) in [(0, 430, 70, 400), (70, 400, 150, 440),
                             (150, 440, 210, 380), (210, 380, 290, 420),
                             (290, 420, 330, 470)]:
        thick_line(ax, ay, bx, by, 5, (110, 150, 170), alpha=220)
    for (ax, ay, bx, by) in [(1024, 450, 950, 420), (950, 420, 880, 460),
                             (880, 460, 820, 400), (820, 400, 760, 450),
                             (760, 450, 700, 480)]:
        thick_line(ax, ay, bx, by, 5, (110, 150, 170), alpha=220)
    # ---- the falls: a river that climbs the sky (bright at top -> aqua at lake)
    left = [(484, 250), (470, 360), (452, 470), (388, 620)]
    right = [(540, 250), (554, 360), (572, 470), (636, 620)]
    fill_tapered(left, right, 250, 620, (238, 250, 248), (118, 204, 214))
    # white streaks inside the ribbon
    for (sx0, sx1, a) in [(500, 506, 110), (516, 520, 90), (492, 495, 80),
                          (528, 533, 100), (508, 511, 70), (536, 540, 85),
                          (484, 487, 75)]:
        fill_poly([(sx0, 620), (sx0 + 6, 250), (sx1 + 6, 250), (sx1, 620)],
                  (255, 255, 255), alpha=a)
    # inner shadow on the falls' left edge gives the ribbon volume
    fill_poly([(484, 250), (470, 360), (452, 470), (398, 620),
               (414, 620), (464, 470), (480, 360), (492, 250)],
              (90, 170, 185), alpha=45)
    # mist where the falls leave the sky (base mist is drawn after the lake,
    # so the lake fill does not paint over it)
    ellipse(512, 246, 58, 26, (255, 250, 235), alpha=70, soft=0.7)
    ellipse(512, 246, 36, 18, (255, 255, 255), alpha=90, soft=0.7)
    # ---- town on the right cliff (bases sit exactly on the ridge line)
    def ridge_y(pts, x):
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            if x0 <= x <= x1:
                t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return pts[-1][1]

    ridge_r = [(700, 480), (760, 450), (820, 400), (880, 460), (950, 420), (1024, 450)]
    for hx, hw, hh in [(788, 34, 26), (826, 28, 20), (862, 38, 30),
                        (906, 30, 22), (938, 36, 28)]:
        house(hx, int(ridge_y(ridge_r, hx + hw / 2)) + 2, hw, hh)
    lighthouse(150, 440)
    # ---- lake: deep teal, darker toward the bottom
    vgrad(620, 1024, [(0.0, (16, 66, 84)), (1.0, (8, 38, 56))])
    # warm mist band softening the horizon line
    fill_rect(0, 612, 1024, 622, (245, 190, 110), alpha=55)
    # mist where the falls meet the lake (drawn after the lake fill)
    ellipse(512, 600, 130, 30, (235, 245, 245), alpha=60, soft=0.6)
    ellipse(512, 612, 90, 22, (235, 245, 245), alpha=50, soft=0.6)
    ellipse(512, 618, 150, 24, (240, 250, 250), alpha=55, soft=0.6)
    # reflections: soft fading columns, strongest near the horizon
    for i in range(8):
        yy = 625 + i * 20
        fill_rect(478, yy, 546, yy + 20, (190, 225, 225), alpha=int(42 * (1 - i / 8)))
    for i in range(8):
        yy = 625 + i * 20
        fill_rect(694, yy, 732, yy + 20, (245, 190, 110), alpha=int(32 * (1 - i / 8)))
    # a few short dashes close under the falls, fading with depth
    for (yy, a) in [(640, 30), (672, 22), (704, 15)]:
        fill_rect(500, yy, 524, yy + 10, (200, 230, 230), alpha=a)
    # faint sloped wave lines
    thick_line(140, 700, 300, 706, 2, (140, 190, 200), alpha=35)
    thick_line(640, 740, 820, 734, 2, (140, 190, 200), alpha=30)
    thick_line(120, 940, 330, 934, 2, (140, 190, 200), alpha=30)
    # ---- boats
    sailboat(280, 820, 1.0, flip=1)
    sailboat(740, 900, 0.75, flip=-1)
    # tiny boat riding the rising falls (warm sail so it reads on the pale ribbon)
    fill_poly([(496, 352), (528, 352), (521, 364), (503, 364)], INK)
    fill_poly([(512, 350), (512, 316), (534, 350)], (255, 205, 115))
    # ---- frame
    fill_rect(26, 26, 998, 30, CREAM, alpha=235)
    fill_rect(26, 994, 998, 998, CREAM, alpha=235)
    fill_rect(26, 26, 30, 998, CREAM, alpha=235)
    fill_rect(994, 26, 998, 998, CREAM, alpha=235)
    # ---- type
    draw_text("LUMARA", "bold", 150, 512, 148, CREAM, tracking=14)
    # ornament under the name
    fill_rect(392, 168, 488, 171, CREAM, alpha=220)
    fill_rect(536, 168, 632, 171, CREAM, alpha=220)
    fill_poly([(512, 160), (520, 169), (512, 178), (504, 169)], CREAM)
    draw_text("THE FALLS THAT CLIMB THE SKY", "regular", 33, 512, 214,
              CREAM, tracking=4, alpha=240)
    draw_text("SKYFERRY DAILY  \u2022  SUNSET CRUISES  \u2022  EST. 1924",
              "regular", 21, 512, 978, (230, 240, 235), tracking=2, alpha=230)


def main():
    import hashlib
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    draw_poster()
    data = png_encode_rgb(W, H, cv)
    path = os.path.join(out, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print("wrote", path, len(data), "bytes sha256",
          hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
