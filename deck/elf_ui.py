"""Феи, пороги карт и рост растений в интерфейсе Эльфа."""

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


def draw_garden(surf, sk, garden, x, y, mouse, hovered_cell):
    plants = sorted((u for u in garden.plants if u.alive), key=lambda u: plant_progress(garden, u)[1])
    # Панель привязана к прежнему нижнему краю и растёт вверх, не закрывая руку.
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
    height = 73 + 23 * len(shown) + 15 * len(notes)
    panel = pygame.Rect(x, y + 62 - height, 208, height)
    fae = garden.fae()
    charged = fae >= FAE_THRESHOLD
    sk.panel(surf, panel, 239, accent=True)
    sk.text(surf, "Феи", (panel.x + 14, panel.y + 9), 17, sk.p["title"], title=True)
    sk.text(surf, f"{fae} / {FAE_MAX}", (panel.right - 13, panel.y + 8), 17,
            GOLD if charged else sk.p["text"], right=True, title=True)
    for i in range(FAE_MAX):
        lit = i < fae
        color = GOLD if i + 1 in (FAE_THRESHOLD, GREATER_THRESHOLD) else MINT
        _fae_glyph(surf, panel.x + 18 + 19 * i, panel.y + 35,
                   color if lit else SK.mix(sk.p["fill"][0], color, 0.26), lit)
    threshold = ("Порог 8 активен" if fae >= GREATER_THRESHOLD else
                 "Порог 6 активен" if charged else f"До порога 6 · ещё {FAE_THRESHOLD - fae}")
    sk.text(surf, threshold, (panel.x + 14, panel.y + 48), 12, GOLD if charged else sk.p["dim"])
    hits = []
    for i, plant in enumerate(shown):
        _, turns, fast = plant_progress(garden, plant)
        row = pygame.Rect(panel.x + 9, panel.y + 65 + 23 * i, panel.w - 18, 21)
        hits.append((row, plant))
        hot = row.collidepoint(mouse) or hovered_cell == plant.cell
        color = PLANTS[plant.plant_id]["color"]
        if hot:
            pygame.draw.rect(surf, (51, 80, 67), row, border_radius=5)
        pygame.draw.circle(surf, color, (row.x + 8, row.centery), 3)
        sk.text(surf, plant.name, (row.x + 17, row.y + 2), 12, sk.p["text"])
        sk.text(surf, f"{turns} х.", (row.right - 7, row.y + 2), 12,
                GOLD if fast or turns <= 1 else color, right=True)
    for i, note in enumerate(notes):
        sk.text(surf, note, (panel.x + 15, panel.y + 65 + 23 * len(shown) + 15 * i), 11, sk.p["dim"])
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
