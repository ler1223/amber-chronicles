"""Феи, энергия и рост растений в интерфейсе Эльфа."""

import math
import pygame

from . import cardface as CF
from . import skin as SK
from .fae import FAE_MAX, PLANTS

FAE_THRESHOLD = 6
GREATER_THRESHOLD = 8
MINT = (177, 242, 168)
GOLD = (249, 212, 123)


def portrait(size):
    art = SK.use("elf").art("portrait")
    if art is None:
        return CF.illustration(("card_e_astral_step", 0.43, 0.55, 0.57), size)

    def crop():
        w, h = art.get_size()
        target_w, target_h = size
        scale = max(target_w / w, target_h / h)
        cut = pygame.Rect(0, 0, min(w, round(target_w / scale)), min(h, round(target_h / scale)))
        cut.center = art.get_rect().center
        return pygame.transform.smoothscale(art.subsurface(cut), size)

    return SK._remember(("elf-portrait", size), crop)


def plant_progress(garden, plant):
    """Оценка созревания при текущем числе фей и оставшихся ходах кольца."""
    needed = PLANTS[plant.plant_id]["grow"]
    left = max(0, needed - plant.growth)
    ring_turns = (max((ring["turns"] for ring in garden.rings if plant.cell in ring["cells"]), default=0)
                  if garden.fae() >= FAE_THRESHOLD else 0)
    turns = left - min(ring_turns, left // 2)
    return needed, turns, ring_turns > 0


def _fae_glyph(surf, x, y, color, lit):
    native, scale, point = SK.ctx(surf)

    def poly(coords):
        return [point((x + dx, y + dy)) for dx, dy in coords]

    pygame.draw.polygon(native, color, poly(((-1, 2), (-7, -1), (-8, -6), (-4, -5), (-1, -2))))
    pygame.draw.polygon(native, color, poly(((1, 2), (7, -1), (8, -6), (4, -5), (1, -2))))
    if lit:
        pygame.draw.line(native, (237, 255, 213), point((x, y - 3)), point((x, y + 4)),
                         max(1, round(scale)))


def _icon(surf, sk, name, x, y, size, opacity=255):
    art = sk.art(name)
    if art is None:
        return False
    native, scale, point = SK.ctx(surf)
    side = max(1, round(size * scale))

    def make():
        ratio = side / max(art.get_size())
        icon = pygame.transform.smoothscale(art, tuple(max(1, round(n * ratio)) for n in art.get_size()))
        icon.set_alpha(opacity)
        return icon

    icon = SK._remember(("elf-icon", sk.id, name, side, opacity), make)
    native.blit(icon, icon.get_rect(center=point((x, y))))
    return True


def energy_fraction(value, maximum):
    return max(0.0, min(1.0, value / max(1, maximum)))


def _reservoir_parts(sk, art, aperture, size):
    ratio = size / max(art.get_size())
    shape = tuple(max(1, round(n * ratio)) for n in art.get_size())
    bezel = pygame.transform.smoothscale(art, shape)
    opening = pygame.transform.smoothscale(aperture, shape)
    rect = opening.get_bounding_rect()
    _, mid, _ = sk.p["energy"]
    shade = SK.darker(sk.p["fill"][1], .36)
    glass = SK.vgrad(*shape, [(0, SK.mix(shade, mid, .20)), (.43, shade), (1, SK.darker(shade, .4))])
    return bezel, opening, rect, glass


def _reservoir(sk, art, aperture, size, fraction, t):
    bezel, opening, rect, glass = SK._remember(("elf-orb-parts", sk.id, size),
                                               lambda: _reservoir_parts(sk, art, aperture, size))
    out = glass.copy()
    if fraction:
        width = out.get_width()
        bright, mid, deep = sk.p["energy"]
        level = rect.bottom - rect.h * fraction
        amplitude = max(1, rect.h * .038) * min(1, fraction * 4)
        top = max(0, math.floor(level - amplitude * 1.4))
        depth = max(2, rect.bottom - top)
        liquid = SK.vgrad(width, depth, [(0, bright), (.18, mid), (.62, SK.mix(mid, deep, .64)), (1, deep)])
        reflection = pygame.Surface(liquid.get_size(), pygame.SRCALPHA)
        for i, (position, speed) in enumerate(((.40, 1.6), (.70, -1.15))):
            band = [(px, depth * (position + .06 * math.sin(t * speed + i)) +
                     depth * .11 * math.sin((px / width) * 6 + t * speed))
                    for px in range(width)]
            pygame.draw.lines(reflection, (*bright, 16 + i * 6), False, band, max(1, round(rect.h * .043)))
            pygame.draw.aalines(reflection, (*bright, 30 + i * 3), False, band)
        liquid.blit(reflection, (0, 0))
        if fraction < 1:
            wave = [(px, level - top + amplitude * (
                math.sin((px - rect.left) * 6 / rect.w - t * 2.7) +
                .4 * math.sin((px - rect.left) * 11 / rect.w + t * 1.9)))
                    for px in range(width)]
            wet = pygame.Surface(liquid.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(wet, (255, 255, 255, 255), wave + [(width - 1, depth), (0, depth)])
            liquid = SK.apply_mask(liquid, wet)
            pygame.draw.aalines(liquid, bright, False, wave)
        out.blit(liquid, (0, top))
    out = SK.apply_mask(out, opening)
    out.blit(bezel, (0, 0))
    return out


def draw_energy(surf, sk, x, y, value, maximum, *, fraction=None, t=0.0):
    art, aperture = sk.art("orb"), sk.art("orb_mask")
    label = f"{value} / {maximum}"
    if art is None or aperture is None:
        sk.orb(surf, (x, y), 36, value, maximum)
        return
    native, scale, point = SK.ctx(surf)
    size = max(4, round(84 * scale))
    fraction = energy_fraction(value, maximum) if fraction is None else fraction
    img = _reservoir(sk, art, aperture, size, fraction, t)
    native.blit(img, img.get_rect(center=point((x, y))))
    sk.text(surf, label, (x, y + 52), 15, sk.p["text"], title=True, center=True)


def draw_garden(surf, sk, garden, x, bottom, mouse, hovered_cell):
    plants = sorted((u for u in garden.plants if u.alive), key=lambda u: plant_progress(garden, u)[1])
    # Панель растёт вверх от верхней границы руки.
    shown = plants[:3]
    notes = []
    if not shown:
        notes.append("На поле нет растений")
    elif len(plants) > len(shown):
        notes.append(f"Ещё {len(plants) - len(shown)} на поле")
    beasts = sum(u.alive for u in garden.beasts.values())
    active = ([f"Звери {beasts}"] if beasts else []) + (
        [f"Прививки {len(garden.attachments)}"] if garden.attachments else [])
    if active:
        notes.append(" · ".join(active))
    height = 95 + 23 * len(shown) + 15 * len(notes)
    panel = pygame.Rect(x, bottom - height, 240, height)
    left, right = panel.left + 25, panel.right - 25
    fae = garden.fae()
    charged = fae >= FAE_THRESHOLD
    sk.panel(surf, panel, 239, accent=True)
    sk.text(surf, "Феи", (left, panel.y + 13), 17, sk.p["title"], title=True)
    sk.text(surf, f"{fae} / {FAE_MAX}", (right, panel.y + 13), 17,
            GOLD if charged else sk.p["text"], right=True, title=True)
    for i in range(FAE_MAX):
        lit = i < fae
        cx, cy = left + 9 + 19 * i, panel.y + 44
        native, scale, point = SK.ctx(surf)
        if i + 1 in (FAE_THRESHOLD, GREATER_THRESHOLD):
            rect = pygame.Rect(point((cx - 9, cy - 9)), (round(18 * scale), round(18 * scale)))
            color = GOLD if lit else SK.mix(sk.p["fill"][0], GOLD, .46)
            pygame.draw.rect(native, color, rect, max(1, round(scale)), border_radius=round(4 * scale))
        if not _icon(surf, sk, "fairy", cx, cy, 14, 255 if lit else 74):
            _fae_glyph(surf, cx, cy, sk.p["accent"] if lit else sk.p["dim"], lit)
    threshold = ("Порог 8 активен" if fae >= GREATER_THRESHOLD else
                 f"Порог 6 активен · до 8: {GREATER_THRESHOLD - fae}" if charged else
                 f"До порога 6 · ещё {FAE_THRESHOLD - fae}")
    sk.text(surf, threshold, (left, panel.y + 59), 12, GOLD if charged else sk.p["dim"])
    hits = []
    for i, plant in enumerate(shown):
        _, turns, fast = plant_progress(garden, plant)
        row = pygame.Rect(left, panel.y + 77 + 23 * i, right - left, 21)
        hits.append((row, plant))
        hot = row.collidepoint(mouse) or hovered_cell == plant.cell
        color = PLANTS[plant.plant_id]["color"]
        native, scale, point = SK.ctx(surf)
        if hot:
            hot_row = surf.rect(row) if native is not surf else row
            pygame.draw.rect(native, SK.mix(sk.p["fill"][0], sk.p["accent"], .26), hot_row,
                             border_radius=round(5 * scale))
        if not _icon(surf, sk, "bud", row.x + 8, row.centery, 14):
            pygame.draw.circle(native, color, point((row.x + 8, row.centery)), max(1, round(3 * scale)))
        sk.text(surf, plant.name, (row.x + 20, row.y + 2), 12, sk.p["text"])
        sk.text(surf, f"{turns} х.", (row.right, row.y + 2), 12,
                GOLD if fast or turns <= 1 else color, right=True)
    for i, note in enumerate(notes):
        sk.text(surf, note, (left, panel.y + 77 + 23 * len(shown) + 15 * i), 11, sk.p["dim"])
    return panel.y, hits


def draw_plant(surf, sk, garden, plant, x, y, hot=False):
    needed, turns, fast = plant_progress(garden, plant)
    color = PLANTS[plant.plant_id]["color"]
    r = pygame.Rect(round(x) - 32, round(y) - 25, 64, 28)
    sk.panel(surf, r, 227, accent=hot or turns <= 1, cut=6)
    sk.text(surf, f"{turns} х.", (x, r.y + 9), 12, GOLD if fast or turns <= 1 else sk.p["text"],
            center=True, title=True)
    sk.pips(surf, r.x + 8, r.y + 17, needed, min(needed, plant.growth),
            w=(48 - (needed - 1) * 2) / needed, h=4, gap=2, col=color)
    if hot:
        sk.text(surf, plant.name, (x, r.y - 10), 14, color, center=True, title=True)
