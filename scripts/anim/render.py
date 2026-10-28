"""Reproduz uma gravação `script -T` num terminal virtual (pyte) e salva quadros PNG.

uso: render.py out.raw timing.log cols rows fps outdir [bg_hex]
"""
import os
import sys

import pyte
from PIL import Image, ImageDraw, ImageFont

raw, timing, cols, rows, fps, outdir = sys.argv[1:7]
bg = sys.argv[7] if len(sys.argv) > 7 else "121722"
cols, rows, fps = int(cols), int(rows), int(fps)
os.makedirs(outdir, exist_ok=True)

FONT = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf"
SIZE = 16
font = ImageFont.truetype(FONT, SIZE)
cw = round(font.getlength("M"))
asc, desc = font.getmetrics()
ch = asc + desc
BG = tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4))
FG = (247, 248, 245)

screen = pyte.Screen(cols, rows)
stream = pyte.ByteStream(screen)

NAMED = {"default": None}


def color(c, default):
    if c in NAMED or not c:
        return default
    if len(c) == 6:
        try:
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return default


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def arrow_cells(art_path):
    """Células da seta do monograma: componente conexa que nasce no primeiro ▄ dentro do M."""
    art = open(art_path, encoding="utf-8").read().split("\n")
    filled = {(y, x) for y, l in enumerate(art) for x, c in enumerate(l) if c != " "}
    seed = next((y, l.index("▄▄")) for y, l in enumerate(art) if "████████   ▄▄" in l)
    seen, todo = set(), [seed]
    while todo:
        cur = todo.pop()
        if cur in seen or cur not in filled:
            continue
        seen.add(cur)
        y, x = cur
        todo += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return seen


def snapshot(idx, override=None):
    img = Image.new("RGB", (cols * cw, rows * ch), BG)
    d = ImageDraw.Draw(img)
    for y in range(rows):
        line = screen.buffer[y]
        for x in range(cols):
            c = line[x]
            if c.data == " " and c.bg == "default":
                continue
            fg = override(y, x) if override else color(c.fg, FG)
            b = color(c.bg, None)
            if c.reverse:
                fg, b = (b or BG), fg
            if b:
                d.rectangle([x * cw, y * ch, (x + 1) * cw - 1, (y + 1) * ch - 1], fill=b)
            # blocos desenhados como retângulos para não deixar fresta entre linhas
            px, py = x * cw, y * ch
            if c.data == "█":
                d.rectangle([px, py, px + cw - 1, py + ch - 1], fill=fg)
            elif c.data == "▀":
                d.rectangle([px, py, px + cw - 1, py + ch // 2 - 1], fill=fg)
            elif c.data == "▄":
                d.rectangle([px, py + ch // 2, px + cw - 1, py + ch - 1], fill=fg)
            elif c.data != " ":
                d.text((px, py), c.data, font=font, fill=fg)
    img.save(f"{outdir}/f{idx:05d}.png")
    return img


SPEED = float(os.environ.get("SPEED", "1"))
MIN_CELLS = 600
step = 1.0 / fps
t = 0.0
next_frame = 0.0
idx = 0
with open(raw, "rb") as f, open(timing) as tl:
    for ln in tl:
        delay, n = ln.split()
        t += float(delay) / SPEED
        while t >= next_frame:
            next_frame += step
            # pula o começo vazio: o primeiro quadro (que alguns leitores mostram parado) já tem cifra na tela
            if idx == 0 and sum(c.data != " " for row in screen.buffer.values() for c in row.values()) < MIN_CELLS:
                continue
            snapshot(idx)
            idx += 1
        stream.feed(f.read(int(n)))
last = snapshot(idx)

# Assentamento na cor oficial da marca: crossfade do gradiente do efeito para M + seta
if os.environ.get("BRAND_ART"):
    arrow = arrow_cells(os.environ["BRAND_ART"])
    mark, accent = hexrgb(os.environ["BRAND_MARK"]), hexrgb(os.environ["BRAND_ACCENT"])
    pts = [(y, x) for y in range(rows) for x in range(cols) if screen.buffer[y][x].data != " "]
    y0, x0 = min(p[0] for p in pts), min(p[1] for p in pts)
    brand = snapshot(idx + 1, lambda y, x: accent if (y - y0, x - x0) in arrow else mark)
    n = int(fps * 0.7)
    for i in range(1, n + 1):
        idx += 1
        Image.blend(last, brand, i / n).save(f"{outdir}/f{idx:05d}.png")
print(f"{idx + 1} quadros, {t:.1f}s, {cols * cw}x{rows * ch}px")
