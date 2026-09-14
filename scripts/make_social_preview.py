#!/usr/bin/env python3
"""Generate assets/social-preview.png (1280x640) for the GitHub Social preview.

House style matches the moysklad-mcp-ru and marketplaces-mcp-ru siblings: dark
background, bold monospace title with a coloured accent, stat chips, a
before/after diff line, footer bottom-right. Brand colours: ochre #B5491F,
orange #D97757, green #2D7D4F.

Все цифры на картинке взяты из README этого репозитория: 2 200 строк ядра,
66 строк сервер поверх, пять серверов на одном ядре, классы доступа
read / write / destructive. Новых чисел тут придумывать нельзя.

Run: python3 scripts/make_social_preview.py
"""
from __future__ import annotations

import glob
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
MARGIN = 80

BG_TOP = (13, 17, 23)
BG_BOT = (17, 22, 33)
TITLE = (230, 237, 243)
ORANGE = (217, 119, 87)     # #D97757
OCHRE = (181, 73, 31)       # #B5491F
GREEN = (84, 184, 124)
SUBTITLE = (148, 158, 169)
CHIP_BORDER = (52, 60, 70)
CHIP_TEXT = (201, 209, 217)
RED = (229, 99, 91)

_MPL = glob.glob(
    os.path.join(os.path.dirname(__import__("matplotlib").__file__),
                 "mpl-data/fonts/ttf")
)[0]
BOLD = os.path.join(_MPL, "DejaVuSansMono-Bold.ttf")
REG = os.path.join(_MPL, "DejaVuSansMono.ttf")


def font(path, size):
    return ImageFont.truetype(path, size)


def text_w(draw, s, f):
    return draw.textbbox((0, 0), s, font=f)[2]


def chip(draw, x, y, label, f, *, accent=None):
    pad_x, h = 22, 56
    tw = text_w(draw, label, f)
    w = tw + pad_x * 2
    border = accent or CHIP_BORDER
    draw.rounded_rectangle([x, y, x + w, y + h], radius=14, outline=border, width=2)
    ty = y + (h - (draw.textbbox((0, 0), label, font=f)[3])) // 2 - 4
    draw.text((x + pad_x, ty), label, font=f, fill=accent or CHIP_TEXT)
    return x + w


def main():
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for yy in range(H):
        t = yy / H
        c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        for xx in range(W):
            px[xx, yy] = c
    d = ImageDraw.Draw(img)

    f_title = font(BOLD, 78)
    f_sub = font(REG, 32)
    f_chip = font(REG, 28)
    f_diff = font(BOLD, 30)
    f_foot = font(REG, 27)

    ty = 132
    x = MARGIN
    d.text((x, ty), "schema-mcp", font=f_title, fill=TITLE)
    x += text_w(d, "schema-mcp", f_title)
    d.text((x, ty), "-core", font=f_title, fill=ORANGE)
    x += text_w(d, "-core", f_title) + 18
    sq = 58
    sy = ty + 12
    d.rounded_rectangle([x, sy, x + sq, sy + sq], radius=10, fill=OCHRE)

    d.text((MARGIN, 268), "Ядро MCP-серверов над российскими деловыми API",
           font=f_sub, fill=SUBTITLE)

    cy = 348
    cx = MARGIN
    cx = chip(d, cx, cy, "5 серверов на одном ядре", f_chip, accent=GREEN) + 18
    cx = chip(d, cx, cy, "read / write / destructive", f_chip) + 18
    cx = chip(d, cx, cy, "MIT", f_chip)

    dx = MARGIN
    d.text((dx, 466), "- ", font=f_diff, fill=RED)
    d.text((dx + 34, 466), "пять копий одного кода в пяти репозиториях", font=f_diff, fill=RED)
    d.text((dx, 510), "+ ", font=f_diff, fill=GREEN)
    d.text((dx + 34, 510), "правка безопасности чинит все сразу", font=f_diff, fill=GREEN)

    foot = "2 200 строк ядра · 66 строк сервер поверх"
    fw = text_w(d, foot, f_foot)
    d.text((W - MARGIN - fw, 578), foot, font=f_foot, fill=SUBTITLE)

    out = os.path.join(os.path.dirname(__file__), "..", "assets", "social-preview.png")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    main()
