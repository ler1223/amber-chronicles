"""Общие элементы экранов забега: кнопки, карточки выбора, карточка бойца."""
import pygame

from ui import theme as T

GOLD = (240, 200, 80)
XP = (170, 140, 255)


def button(surf, rect, label, mouse, enabled=True, accent=(90, 180, 255)):
    hot = enabled and rect.collidepoint(mouse)
    bg = T.mix(accent, (0, 0, 0), 0.55 if hot else 0.7) if enabled else (40, 42, 48)
    pygame.draw.rect(surf, bg, rect, border_radius=8)
    pygame.draw.rect(surf, accent if enabled else T.PANEL_EDGE, rect, 2, border_radius=8)
    T.text(surf, label, rect.center, 18, T.TEXT if enabled else T.TEXT_DIM, True, center=True)


def card(surf, rect, title, lines, mouse, accent=(90, 180, 255), enabled=True, header=None, badge=None):
    """lines: [(текст, цвет)]; длинные строки переносятся."""
    hot = enabled and rect.collidepoint(mouse)
    pygame.draw.rect(surf, (52, 56, 68) if hot else (40, 44, 54), rect, border_radius=10)
    pygame.draw.rect(surf, accent if enabled else T.PANEL_EDGE, rect, 3 if hot else 2, border_radius=10)
    y = rect.y + 12
    if header:
        for line in T.wrap(header, 13, rect.w - 28, True):
            T.text(surf, line, (rect.x + 14, y), 13, accent if enabled else T.TEXT_DIM, True)
            y += 17
        y += 3
    for line in T.wrap(title, 20, rect.w - 28, True):
        T.text(surf, line, (rect.x + 14, y), 20, T.TEXT if enabled else T.TEXT_DIM, True)
        y += 26
    y += 6
    for s, col in lines:
        for line in T.wrap(s, 15, rect.w - 28):
            T.text(surf, line, (rect.x + 14, y), 15, col if enabled else T.TEXT_DIM)
            y += 20
    if badge:
        w = T.font(18, True).size(badge)[0]
        T.text(surf, badge, (rect.right - 14 - w, rect.bottom - 32), 18, GOLD if enabled else (200, 90, 80), True)
    if not enabled:
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 90))
        surf.blit(shade, rect)


def bar(surf, rect, frac, color, bg=(15, 15, 15)):
    pygame.draw.rect(surf, bg, rect, border_radius=3)
    if frac > 0:
        pygame.draw.rect(surf, color, (rect.x, rect.y, max(2, rect.w * min(1, frac)), rect.h), border_radius=3)


SLOT_ORDER = ("weapon", "armor", "trinket")
RARITY_COLORS = {"common": (215, 215, 222), "rare": (110, 170, 255), "epic": (205, 125, 255)}


def item_color(data, iid):
    return RARITY_COLORS[data.items[iid]["rarity"]]


def member_card(surf, rect, run, m, mouse, highlight=False):
    """Карточка героя в вылазке: уровень, опыт, HP, три слота предметов, руны. Возвращает {слот: rect}."""
    from sim.run import SLOT_NAMES
    data = run.data
    proto = run.proto(m)
    pygame.draw.rect(surf, (52, 56, 68) if highlight else T.PANEL, rect, border_radius=10)
    pygame.draw.rect(surf, (120, 255, 140) if highlight else T.PANEL_EDGE, rect, 2, border_radius=10)
    x, y = rect.x + 12, rect.y + 10
    pygame.draw.circle(surf, tuple(proto["color"]), (x + 18, y + 18), 18)
    pygame.draw.circle(surf, T.TEAM_PLAYER, (x + 18, y + 18), 18, 2)
    T.text(surf, proto["label"], (x + 18, y + 18), 18, (255, 255, 255), True, center=True, shadow=True)
    name = proto["name"] + (f" · {data.paths[m.path]['name']}" if m.path else "")
    T.text(surf, name, (x + 46, y), 16 if m.path else 18, T.TEXT, True)
    T.text(surf, f"ур. {m.level}", (rect.right - 60, y + 2), 16, XP, True)
    y += 24
    if m.level < run.cfg["max_level"]:
        bar(surf, pygame.Rect(x + 46, y, rect.w - 70, 6), m.xp / run.xp_to_next(m), XP)
    y += 18
    mx = proto["hp"]
    bar(surf, pygame.Rect(x, y, rect.w - 70, 10), m.hp / mx, T.mix((230, 60, 50), (90, 220, 90), m.hp / mx))
    T.text(surf, f"{m.hp}/{mx}", (rect.right - 54, y - 4), 14, T.TEXT)
    y += 18
    slots = {}
    for slot in SLOT_ORDER:
        r = pygame.Rect(x, y, rect.w - 24, 24)
        iid = m.items.get(slot)
        hot = r.collidepoint(mouse)
        pygame.draw.rect(surf, (60, 56, 40) if hot else (36, 38, 46), r, border_radius=6)
        pygame.draw.rect(surf, item_color(data, iid) if iid else T.PANEL_EDGE, r, 1, border_radius=6)
        label = data.items[iid]["name"] if iid else f"— {SLOT_NAMES[slot].lower()} —"
        T.text(surf, label, (r.x + 8, r.y + 3), 14, item_color(data, iid) if iid else T.TEXT_DIM, bool(iid))
        slots[slot] = r
        y += 28
    y += 2
    for sid, ids in m.runes.items():
        if y > rect.bottom - 18:
            T.text(surf, "…", (x, y - 4), 14, T.TEXT_DIM)
            break
        sk = proto["skill_defs"].get(sid)
        names = ", ".join(data.runes[r]["name"].lower() for r in ids)
        T.text(surf, f"• {sk['name'] if sk else sid}: {names}", (x, y), 13, (255, 200, 120))
        y += 16
    return slots
