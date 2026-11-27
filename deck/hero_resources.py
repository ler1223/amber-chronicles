"""Animated resource counters for the Descent HUD."""

import math
import os
from functools import lru_cache

import pygame

from ui import pixfx
from . import skin as SK


def _glass(radius, colors):
    bright, mid, deep = colors
    aperture = SK.mask((radius * 2, radius * 2), circle=((radius, radius), radius - .5))
    empty = SK.rgrad(radius, [(0, (52, 44, 39)), (.65, (26, 22, 21)), (1, (9, 8, 9))])
    liquid = SK.rgrad(radius, [(0, SK.lighter(mid, .24)), (.48, mid), (.82, deep), (1, SK.darker(deep, .38))],
                      center=(.37, .35))
    reflection = pygame.Surface(empty.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(reflection, (255, 252, 240, 38), (radius * .28, radius * .19, radius * .73, radius * .37))
    reflection = SK.blur(reflection, 4)
    pygame.draw.arc(reflection, (*bright, 65), (radius * .16, radius * .12, radius * 1.66, radius * 1.65),
                    .34, 2.58, max(1, round(radius * .044)))
    return aperture, empty, liquid, reflection


def liquid_orb(surf, sk, center, value, maximum, fraction, t):
    native, scale, point = SK.ctx(surf)
    radius = max(4, round(36 * scale))
    colors = sk.p["energy"]
    aperture, empty, liquid, reflection = SK._remember(
        ("hero-liquid", radius, colors), lambda: _glass(radius, colors))
    glass = empty.copy()
    size = 2 * radius
    if fraction > .002:
        level = size * (1 - fraction)
        amp = radius * .064 * min(1, 8 * fraction, 8 * (1 - fraction))
        wave = [(x, level + amp * (math.sin(x * 8 / size - t * 3.5) +
                                   .42 * math.sin(x * 16 / size + t * 2.2))) for x in range(size)]
        wet = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.polygon(wet, (255, 255, 255), wave + [(size - 1, size), (0, size)])
        fluid = liquid.copy()
        band = pygame.Surface((size, size), pygame.SRCALPHA)
        for y, speed, opacity in ((.34, 2.4, 35), (.72, -1.8, 24)):
            depth = size - level
            path = [(x, level + depth * (y + .13 * math.sin(x * 8 / size + t * speed))) for x in range(size)]
            pygame.draw.lines(band, (*colors[0], opacity), False, path, max(1, round(radius * .11)))
        fluid.blit(band, (0, 0))
        glass.blit(SK.apply_mask(fluid, wet), (0, 0))
        if .008 < fraction < .993:
            pygame.draw.aalines(glass, SK.lighter(colors[0], .32), False, wave)
    glass.blit(reflection, (0, 0))
    glass = SK.apply_mask(glass, aperture)
    ring = SK._remember(("ring", sk.id, radius, round(scale, 3)), lambda: sk._ring(radius, scale))
    dest = point(center)
    native.blit(glass, glass.get_rect(center=dest))
    native.blit(ring, ring.get_rect(center=dest))
    for i in range(maximum):
        angle = math.pi * (1.15 + .7 * (i + .5) / maximum)
        distance = ring.get_width() / 2 + 2 * scale
        x = dest[0] + math.cos(angle) * distance
        y = dest[1] + math.sin(angle) * distance
        pygame.draw.aacircle(native, SK.darker(sk.p["metal"][2], .4), (x, y), 5.2 * scale)
        pygame.draw.aacircle(native, colors[1] if i < value else (60, 50, 44), (x, y), 3.8 * scale)
        if i < value:
            pygame.draw.aacircle(native, colors[0], (x - scale, y - scale), 1.6 * scale)
    sk.text(surf, f"{value}/{maximum}", center, 22, (255, 250, 231), center=True, title=True)


def heat(surf, sk, center, value, limit, shown, t):
    native, scale, point = SK.ctx(surf)
    x, y = center
    strength = min(1.22, shown / max(1, limit))
    tray = pygame.Rect(x - 30, y + 8, 60, 16)
    sk.panel(surf, tray, 243, cut=5)
    if strength > .025:
        lib = _flames()
        frame = int(t * (11 + 7 * strength)) % lib.count("flame")
        art = lib.get("flame")[frame][0]
        size = (max(1, round((31 + 18 * strength) * scale)), max(1, round((28 + 55 * strength) * scale)))
        art = SK._remember(("hud-flame", frame, size), lambda: pygame.transform.scale(art, size))
        native.blit(art, art.get_rect(midbottom=point((x, y + 15))))
        for i in range(9):
            age = (t * (.76 + strength * .5) + i * .193) % 1
            if age > .65 + .23 * strength:
                continue
            px = x + math.sin(i * 3.1 + age * 2) * (8 + 21 * age) * strength
            py = y + 7 - age * (27 + 55 * strength)
            dot = max(1, round(scale * (2 if age < .3 else 1)))
            pygame.draw.rect(native, (255, 209, 116) if age < .3 else (188, 72, 34), (*point((px, py)), dot, dot))
    sk.text(surf, f"{value} / {limit}", (x, y + 16), 14, (255, 158, 90) if value >= limit else (255, 235, 198),
            center=True, title=True)
    sk.text(surf, "жар", (x, y + 37), 12, sk.p["dim"], center=True)


@lru_cache(maxsize=1)
def _flames():
    return pixfx.Lib()


def _prayer_sprite(name, width):
    def make():
        source = SK._load(os.path.join(SK.ART, "priest", name + ".png"))
        height = max(1, round(width * source.get_height() / source.get_width()))
        return pygame.transform.scale(source, (width, height))
    return SK._remember(("prayer-sprite", name, width), make)


def beads(surf, sk, center, value, maximum, shown, t):
    native, scale, point = SK.ctx(surf)
    x, y = center
    bob = math.sin(t * 3) * 1.15
    cord = _prayer_sprite("prayer_cord", max(1, round(88 * scale)))
    pendant = _prayer_sprite("prayer_pendant", max(1, round(17 * scale)))
    native.blit(cord, cord.get_rect(center=point((x, y - 8 + bob))))
    native.blit(pendant, pendant.get_rect(midtop=point((x, y + 10 + bob))))
    slots = max(1, maximum, value, math.ceil(shown))
    bead_width = max(2, round(scale * min(18, 91 / slots)))
    bead = _prayer_sprite("prayer_bead", bead_width)
    for i in range(slots):
        visibility = max(0.0, min(1.0, shown - i))
        if visibility < .02:
            continue
        angle = math.pi * (1.07 + .86 * (i + .5) / slots)
        px = x + math.cos(angle) * 40
        py = y - 9 + math.sin(angle) * 19 + bob + (1 - visibility) * 10
        art = bead
        if visibility < 1:
            art = bead.copy()
            art.set_alpha(round(255 * visibility))
        native.blit(art, art.get_rect(center=point((px, py))))
    sk.text(surf, f"{value}/{maximum}", (x, y - 7), 18, (255, 236, 193), center=True, title=True)
    sk.text(surf, "шаги", (x, y + 42), 12, sk.p["dim"], center=True)
