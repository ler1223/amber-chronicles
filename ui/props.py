"""Модельки предметов в эффектах: стрелы, сеть, склянка, капкан, обломки. Пиксель-арт, как у юнитов.

Каждая — ASCII-сетка с палитрой ниже (точка — прозрачно), смотрит вправо; контур добавляется сам.
Свой рисунок кладётся в assets/sprites/props/<имя>.png и заменяет заглушку (масштаб в игре — ×2).
"""
import os

import numpy as np
import pygame

PROP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sprites", "props")
CELL = 64
GRID = 8                        # атлас 512×512 — до 64 моделек
OUTLINE = (22, 18, 24)

PALETTE = {
    "F": (232, 228, 214), "f": (196, 62, 52),                         # оперение
    "S": (156, 110, 64), "s": (112, 76, 42),                           # древко
    "H": (206, 212, 222), "h": (128, 134, 150),                        # наконечник
    "G": (232, 190, 80),                                               # золото
    "I": (226, 246, 255), "i": (140, 196, 240), "j": (90, 150, 220),   # лёд
    "O": (255, 196, 80), "o": (226, 96, 30),                           # огонь
    "R": (190, 170, 130), "r": (140, 122, 92),                         # верёвка
    "B": (160, 210, 255), "b": (90, 150, 240), "W": (250, 252, 255),   # стекло склянки
    "C": (170, 120, 70),                                               # пробка
    "M": (132, 100, 66), "m": (96, 70, 46), "n": (170, 136, 96),       # грязь
    "K": (150, 152, 160), "k": (98, 100, 110), "T": (220, 224, 230),   # железо капкана
    "D": (64, 60, 70), "d": (40, 38, 46), "Y": (255, 220, 120),        # бомба, фитиль
    "P": (128, 120, 112), "p": (92, 86, 80), "q": (168, 160, 150),     # камень
    "L": (196, 150, 98), "l": (150, 108, 64),                          # щепа
    "g": (110, 200, 80), "V": (170, 240, 120),                         # зелье яда
}

ART = {
    "arrow": [
        "FF..................H..",
        ".FF.................HH.",
        "fFSSSSSSSSSSSSSSSSSSHHH",
        ".FF.................HH.",
        "FF..................H..",
    ],
    "arrow_heavy": [
        "ff.....................HH...",
        ".ff....................HHH..",
        "fFfSSSSSSSSSSSSSSSSSSGGHHHHH",
        ".ff....................HHH..",
        "ff.....................HH...",
    ],
    "arrow_ice": [
        "ii..................I..",
        ".ii.................II.",
        "jiSSSSSSSSSSSSSSSSSSIII",
        ".ii.................II.",
        "ii..................I..",
    ],
    "arrow_fire": [
        "FF.................oO..",
        ".FF................OOO.",
        "fFSSSSSSSSSSSSSSSSoOHHH",
        ".FF................OOO.",
        "FF.................oO..",
    ],
    "stake": [
        "ll..............",
        "lLLLLLLLLLLLLLL.",
        "lLLLLLLLLLLLLLLL",
        "lllllllllllllll.",
    ],
    "net_ball": [
        "..RrRr..",
        ".rRrRrR.",
        "RrRrRrRr",
        "rRrRrRrR",
        "RrRrRrRr",
        ".rRrRrR.",
        "..RrRr..",
    ],
    "bottle": [
        "...CC...",
        "...CC...",
        "...BB...",
        "..BWBB..",
        ".BWBBbb.",
        "BWBBBBbb",
        "BBBBBBbb",
        "BBBBBbbb",
        ".BBBbbb.",
        "..bbbb..",
    ],
    "mud": [
        "..nMMM....",
        ".nMMMMMm..",
        "nMMMMMMMm.",
        "MMMMMMMMmm",
        ".mMMMMMmm.",
        "..mmmmm...",
    ],
    "trap_open": [
        "T.T.T.T.....T.T.T.T",
        "KKKKKKK.....KKKKKKK",
        ".kkkkkkKKKKKkkkkkk.",
        "......kkkkkkk......",
    ],
    "trap_closed": [
        "...KKKKKKK...",
        "..KTKTKTKTK..",
        "..KkTkTkTkK..",
        "...kkkkkkk...",
    ],
    "smoke_bomb": [
        ".....Y.",
        "....Y..",
        "..DDd..",
        ".DDDDd.",
        "DDDDDDd",
        "DDDDDdd",
        ".DDddd.",
        "..ddd..",
    ],
    "rock": [
        "..qPP...",
        ".qPPPPp.",
        "qPPPPPPp",
        "PPPPPPpp",
        ".pPPPpp.",
        "..ppp...",
    ],
    "pebble": [
        ".qP.",
        "qPPp",
        ".pp.",
    ],
    "ice_chunk": [
        "..I...",
        ".IIi..",
        "IIiij.",
        ".Iijj.",
        "..jj..",
    ],
    "glass": [
        "W.",
        "BB",
    ],
    "splinter": [
        "LLLLl",
        ".lll.",
    ],
    "mud_bit": [
        ".M.",
        "MMm",
    ],
    "dart": [
        "ff.........",
        "fSSSSSSSHHg",
        "ff.........",
    ],
    "grapple": [
        "K..K..",
        ".K..K.",
        ".KKKKK",
        ".K..K.",
        "K..K..",
    ],
    "bomb": [
        "......Y.",
        ".....Y..",
        "...DDd..",
        "..DDDDd.",
        ".DDqDDDd",
        ".DDDDDdd",
        ".DDDDddd",
        "..DDddd.",
        "...ddd..",
    ],
    "oil_bottle": [
        "...CC...",
        "...nn...",
        "..MnnM..",
        ".MnMMMm.",
        "MnMMMMmm",
        "MMMMMMmm",
        ".MMMMmm.",
        "..mmmm..",
    ],
    "potion_red": [
        "...CC...",
        "...WW...",
        "..oWoo..",
        ".oWooOo.",
        "oWooOOoo",
        "ooOOOOoo",
        ".ooOOoo.",
        "..oooo..",
    ],
    "potion_green": [
        "...CC...",
        "...WW...",
        "..gWgg..",
        ".gWggVg.",
        "gWggVVgg",
        "ggVVVVgg",
        ".ggVVgg.",
        "..gggg..",
    ],
    "mine": [
        "...K...",
        "..kKk..",
        ".KKfKK.",
        "KkKKKkK",
        ".kkkkk.",
    ],
    "barrel": [
        ".LLLLL.",
        "LlLLLlL",
        "kkkkkkk",
        "LlLLLlL",
        "LlLLLlL",
        "kkkkkkk",
        ".llLll.",
    ],
}


def _from_art(rows):
    h, w = len(rows), max(len(r) for r in rows)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in PALETTE:
                s.set_at((x, y), (*PALETTE[ch], 255))
    return s


def _net():
    """Раскрытая сеть: ромбы из верёвки, грузики по краю."""
    w, h = 34, 18
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    col, dark = (*PALETTE["R"], 255), (*PALETTE["r"], 255)
    for k in range(-h, w, 5):
        pygame.draw.line(s, col, (k, 0), (k + h, h - 1))
        pygame.draw.line(s, dark, (k + h, 0), (k, h - 1))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255, 255), mask.get_rect())
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    for x in range(3, w - 2, 6):
        s.set_at((x, h - 2 if 6 < x < w - 7 else h // 2 + 3), (*PALETTE["k"], 255))
    return s


def _outline(s):
    """Тёмный контур в 1 пиксель — модельку видно на любом фоне."""
    w, h = s.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    a = pygame.surfarray.array_alpha(s) > 0
    ring = np.zeros((w + 2, h + 2), bool)
    for dx in (0, 1, 2):
        for dy in (0, 1, 2):
            ring[dx:dx + w, dy:dy + h] |= a
    px = pygame.surfarray.pixels3d(out)
    pa = pygame.surfarray.pixels_alpha(out)
    px[ring] = OUTLINE
    pa[ring] = 255
    del px, pa
    out.blit(s, (1, 1))
    return out


def load_props(folder=PROP_DIR):
    """{имя: Surface} — PNG из папки или заглушка с контуром."""
    out = {}
    names = list(ART) + ["net"]
    for name in names:
        path = os.path.join(folder, f"{name}.png")
        if os.path.exists(path):
            img = pygame.image.load(path)
            try:
                img = img.convert_alpha()
            except pygame.error:
                pass
        else:
            img = _outline(_net() if name == "net" else _from_art(ART[name]))
        out[name] = img
    return out


def build_prop_atlas(props):
    """Атлас моделек (uint8 [512, 512, 4], предумноженная альфа), uv и размеры в пикселях.
    Модельки лежат по ячейкам 64×64."""
    size = CELL * GRID
    atlas = np.zeros((size, size, 4), np.float32)
    names = list(props)
    uvs = np.zeros((len(names), 4), np.float32)
    dims = np.zeros((len(names), 2), np.float32)
    for i, n in enumerate(names):
        img = props[n]
        if img.get_width() > CELL or img.get_height() > CELL:
            k = CELL / max(img.get_size())
            img = pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k)))
        w, h = img.get_size()
        gx, gy = (i % GRID) * CELL, (i // GRID) * CELL
        rgb = pygame.surfarray.array3d(img).transpose(1, 0, 2).astype(np.float32) / 255
        a = pygame.surfarray.array_alpha(img).T.astype(np.float32)[..., None] / 255
        atlas[gy:gy + h, gx:gx + w] = np.concatenate([rgb * a, a], -1)
        uvs[i] = (gx / size, gy / size, (gx + w) / size, (gy + h) / size)
        dims[i] = (w, h)
    return (atlas * 255 + 0.5).astype(np.uint8), uvs, dims, {n: i for i, n in enumerate(names)}
