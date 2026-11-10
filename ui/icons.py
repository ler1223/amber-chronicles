"""Значки состояний над юнитами и в панелях: теги-статусы, контроль (оглушение, корни, сеть…), баффы и дебаффы.

Значок — рисунок на тёмной плашке с рамкой: зелёная — полезное, красная — вредное, у тегов — цвет стихии.
Под значком полоска оставшегося времени. Всё рисуется кодом и кэшируется по (вид, размер, рамка).
"""
import math

import pygame

from ui import theme as T

OUT = (18, 16, 22)
GOOD, BAD = (110, 220, 120), (240, 90, 80)
CONTROL_NAMES = {"stun": "Оглушение", "root": "Корни", "net": "Сеть", "trap": "Капкан", "freeze": "Заморожен",
                 "shock": "Электрошок", "blind": "Ослеплён", "sleep": "Сон", "stasis": "Стазис",
                 "levitate": "Невесомость"}
CONTROL_COLORS = {"stun": (255, 225, 90), "root": (120, 200, 80), "net": (210, 180, 130), "trap": (190, 190, 200),
                  "freeze": (160, 220, 255), "shock": (150, 200, 255), "blind": (150, 130, 170),
                  "sleep": (200, 180, 255), "stasis": (240, 205, 110),
                  "levitate": (190, 160, 255)}
BUFF_NAMES = {"armor": "броня", "atk_mult": "урон", "atk_speed": "быстрые атаки", "dmg_taken": "получаемый урон",
              "thorns": "шипы", "regen": "восстановление", "slow": "скорость", "immune": "иммунитет",
              "stealth": "в тени", "ap_rate": "AP быстрее", "atk_tag": "клинок с ядом", "heal_taken": "лечение",
              "range_add": "дальность", "exposed": "раскрыт — удар в спину от всех",
              "trance": "кровавый транс: лечение → ярость", "undying": "не умирает",
              "bleed": "кровотечение", "silence": "безмолвие — без навыков",
              "banner": "у знамени: приказы сильнее", "zoc_free": "стойка часового", "zoc_range": "длинное древко",
              "collide_stun": "стенобой: столкновения оглушают", "billiard": "бильярд: толчки по цепочке",
              "all_arrows": "все стрелы сразу", "inferno": "инферно: огонь не гаснет",
              "stable": "стабилизатор: теги не реагируют"}
MARK_GLYPH = {"challenge": "duel", "duel": "duel", "cold": "ice", "bomb": "bomb"}

_cache = {}


def _star(s, c, x, y, r):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    pygame.draw.polygon(s, c, pts)
    pygame.draw.polygon(s, OUT, pts, 1)


def _drop(s, c, x, y, r, hi=(255, 255, 255)):
    pygame.draw.polygon(s, c, [(x, y - r * 1.5), (x - r * 0.9, y + r * 0.1), (x + r * 0.9, y + r * 0.1)])
    pygame.draw.circle(s, c, (x, y + r * 0.25), r)
    pygame.draw.circle(s, hi, (x - r * 0.35, y + r * 0.05), max(1, r * 0.28))


def _heart(s, c, x, y, r):
    pygame.draw.circle(s, c, (x - r * 0.5, y - r * 0.2), r * 0.6)
    pygame.draw.circle(s, c, (x + r * 0.5, y - r * 0.2), r * 0.6)
    pygame.draw.polygon(s, c, [(x - r * 1.05, y), (x + r * 1.05, y), (x, y + r * 1.1)])


def _shield(s, c, x, y, r, mark=None):
    pts = [(x - r, y - r), (x + r, y - r), (x + r, y), (x, y + r * 1.25), (x - r, y)]
    pygame.draw.polygon(s, c, pts)
    pygame.draw.polygon(s, OUT, pts, 1)
    if mark == "+":
        pygame.draw.line(s, (255, 255, 255), (x - r * 0.5, y - r * 0.2), (x + r * 0.5, y - r * 0.2), 2)
        pygame.draw.line(s, (255, 255, 255), (x, y - r * 0.7), (x, y + r * 0.3), 2)
    elif mark == "-":
        pygame.draw.line(s, (255, 255, 255), (x - r * 0.5, y - r * 0.2), (x + r * 0.5, y - r * 0.2), 2)
    elif mark == "crack":
        pygame.draw.lines(s, OUT, False, [(x, y - r), (x - r * 0.3, y - r * 0.2), (x + r * 0.2, y + r * 0.2),
                                          (x - r * 0.1, y + r)], 2)


def _arrow(s, up, x, y, c):
    if up:
        pygame.draw.polygon(s, c, [(x, y - 4), (x - 4, y + 1), (x + 4, y + 1)])
    else:
        pygame.draw.polygon(s, c, [(x, y + 4), (x - 4, y - 1), (x + 4, y - 1)])
    pygame.draw.polygon(s, OUT, [(x, y - 4), (x - 4, y + 1), (x + 4, y + 1)] if up else
                        [(x, y + 4), (x - 4, y - 1), (x + 4, y - 1)], 1)


def _sword(s, x, y, r):
    pygame.draw.line(s, (225, 230, 240), (x - r, y + r), (x + r * 0.7, y - r * 0.7), 3)
    pygame.draw.line(s, (150, 110, 60), (x - r * 0.7, y + r * 0.1), (x - r * 0.1, y + r * 0.7), 2)


def glyph(s, kind, size):
    """Рисунок значка на холсте size×size (без плашки)."""
    c = size / 2
    r = size * 0.36
    if kind == "fire":
        pygame.draw.polygon(s, (255, 120, 40), [(c, c - r * 1.5), (c + r, c), (c + r * 0.7, c + r), (c - r * 0.7, c + r),
                                                (c - r, c), (c - r * 0.3, c - r * 0.4)])
        pygame.draw.polygon(s, (255, 220, 90), [(c, c - r * 0.6), (c + r * 0.5, c + r * 0.3), (c, c + r * 0.9),
                                                (c - r * 0.5, c + r * 0.3)])
    elif kind == "water":
        _drop(s, (80, 150, 255), c, c + r * 0.2, r)
    elif kind == "oil":
        _drop(s, (70, 52, 30), c, c + r * 0.2, r, (200, 170, 110))
    elif kind == "poison":
        _drop(s, (110, 210, 70), c, c + r * 0.2, r, (220, 255, 180))
        pygame.draw.circle(s, (60, 120, 40), (c + r * 0.3, c + r * 0.4), max(1, r * 0.25))
    elif kind in ("ice", "freeze"):
        if kind == "freeze":
            box = pygame.Rect(c - r * 1.1, c - r * 1.1, r * 2.2, r * 2.2)
            pygame.draw.rect(s, (150, 210, 250), box, border_radius=2)
            pygame.draw.line(s, (240, 250, 255), (box.x + 2, box.y + 2), (box.x + 2, box.bottom - 4), 2)
        for i in range(3):
            a = i * math.pi / 3
            dx, dy = math.cos(a) * r * 1.1, math.sin(a) * r * 1.1
            pygame.draw.line(s, (230, 245, 255) if kind == "ice" else (60, 120, 190), (c - dx, c - dy), (c + dx, c + dy), 2)
    elif kind in ("storm", "shock"):
        pts = [(c + r * 0.3, c - r * 1.4), (c - r * 0.7, c + r * 0.1), (c, c + r * 0.1), (c - r * 0.4, c + r * 1.4),
               (c + r * 0.8, c - r * 0.3), (c + r * 0.1, c - r * 0.3)]
        pygame.draw.polygon(s, (255, 240, 120) if kind == "storm" else (170, 220, 255), pts)
        pygame.draw.polygon(s, OUT, pts, 1)
    elif kind == "stun":
        _star(s, (255, 225, 90), c - r * 0.3, c + r * 0.25, r * 1.05)
        _star(s, (255, 245, 170), c + r * 0.75, c - r * 0.6, r * 0.62)
    elif kind == "root":
        col = (90, 170, 60)
        pygame.draw.arc(s, col, (c - r * 1.2, c - r * 0.6, r * 1.6, r * 2.2), 0, math.pi, 3)
        pygame.draw.arc(s, (120, 90, 50), (c - r * 0.4, c - r * 1.0, r * 1.6, r * 2.4), math.pi, 2 * math.pi, 3)
        pygame.draw.ellipse(s, (140, 220, 90), (c + r * 0.3, c - r * 1.2, r * 0.9, r * 0.6))
    elif kind == "net":
        for i in range(-1, 2):
            pygame.draw.line(s, (220, 190, 140), (c - r + i * r * 0.7, c - r), (c + r + i * r * 0.7, c + r), 2)
            pygame.draw.line(s, (220, 190, 140), (c + r + i * r * 0.7, c - r), (c - r + i * r * 0.7, c + r), 2)
    elif kind == "trap":
        pygame.draw.arc(s, (200, 200, 210), (c - r * 1.2, c - r * 0.8, r * 2.4, r * 2.2), 0, math.pi, 3)
        for i in range(5):
            x = c - r + i * r * 0.5
            pygame.draw.line(s, (230, 230, 240), (x, c + r * 0.2), (x + r * 0.2, c - r * 0.4), 1)
        pygame.draw.line(s, (120, 120, 130), (c - r * 1.2, c + r * 0.3), (c + r * 1.2, c + r * 0.3), 2)
    elif kind == "stasis":
        col = (240, 205, 110)
        pts = [(c - r, c - r * 1.2), (c + r, c - r * 1.2), (c, c), (c + r, c + r * 1.2), (c - r, c + r * 1.2), (c, c)]
        pygame.draw.polygon(s, col, pts)
        pygame.draw.polygon(s, OUT, pts, 1)
        pygame.draw.polygon(s, (255, 245, 210), [(c - r * 0.5, c + r * 1.1), (c + r * 0.5, c + r * 1.1),
                                                 (c, c + r * 0.4)])
    elif kind == "levitate":
        pygame.draw.ellipse(s, (190, 160, 255), (c - r, c + r * 0.6, r * 2, r * 0.7), 2)
        _arrow(s, True, c, c - r * 0.2, (190, 160, 255))
    elif kind == "exposed":
        pygame.draw.circle(s, (240, 90, 80), (c, c), r * 1.1, 2)
        pygame.draw.circle(s, (240, 90, 80), (c, c), r * 0.5, 2)
        pygame.draw.line(s, (240, 90, 80), (c - r * 1.4, c), (c + r * 1.4, c), 1)
        pygame.draw.line(s, (240, 90, 80), (c, c - r * 1.4), (c, c + r * 1.4), 1)
    elif kind == "blind":
        pygame.draw.ellipse(s, (230, 230, 240), (c - r * 1.2, c - r * 0.6, r * 2.4, r * 1.2))
        pygame.draw.circle(s, (60, 50, 80), (c, c), r * 0.45)
        pygame.draw.line(s, (240, 90, 80), (c - r * 1.2, c + r), (c + r * 1.2, c - r), 2)
    elif kind == "sleep":
        f = T.font(max(9, int(size * 0.6)), True)
        s.blit(f.render("z", True, (210, 190, 255)), (c - r * 1.1, c - r * 0.2))
        s.blit(T.font(max(8, int(size * 0.45)), True).render("z", True, (230, 220, 255)), (c + r * 0.2, c - r * 1.2))
    elif kind == "charm":
        _heart(s, (255, 120, 200), c, c, r)
    elif kind == "taunt":
        pygame.draw.rect(s, (240, 80, 70), (c - 2, c - r * 1.3, 4, r * 1.6))
        pygame.draw.rect(s, (240, 80, 70), (c - 2, c + r * 0.6, 4, 4))
    elif kind == "shield":
        _shield(s, (200, 225, 255), c, c - r * 0.2, r)
    elif kind in ("atk_up", "atk_down"):
        _sword(s, c - 1, c + 1, r)
        _arrow(s, kind == "atk_up", c + r * 0.8, c - r * 0.6, GOOD if kind == "atk_up" else BAD)
    elif kind in ("armor_up", "armor_down"):
        _shield(s, (150, 170, 200), c, c - r * 0.2, r, "+" if kind == "armor_up" else "-")
    elif kind in ("tough", "vuln"):
        _shield(s, (220, 200, 120) if kind == "tough" else (200, 120, 110), c, c - r * 0.2, r,
                None if kind == "tough" else "crack")
        if kind == "tough":
            _star(s, (255, 250, 200), c, c - r * 0.2, r * 0.5)
    elif kind == "regen":
        pygame.draw.rect(s, (110, 230, 120), (c - r * 0.35, c - r * 1.1, r * 0.7, r * 2.2))
        pygame.draw.rect(s, (110, 230, 120), (c - r * 1.1, c - r * 0.35, r * 2.2, r * 0.7))
    elif kind in ("haste", "fast", "slow", "ap_rate"):
        col = {"haste": (255, 220, 100), "fast": (140, 230, 140), "slow": (120, 170, 255),
               "ap_rate": (90, 190, 255)}[kind]
        d = -1 if kind == "slow" else 1
        for k in (-0.5, 0.4):
            x = c + k * r * 1.4 * d
            pygame.draw.lines(s, col, False, [(x - r * 0.5 * d, c - r), (x + r * 0.4 * d, c), (x - r * 0.5 * d, c + r)], 3)
    elif kind == "thorns":
        pygame.draw.circle(s, (120, 160, 80), (c, c), r * 0.7)
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(s, (200, 220, 160), (c + math.cos(a) * r * 0.6, c + math.sin(a) * r * 0.6),
                             (c + math.cos(a) * r * 1.3, c + math.sin(a) * r * 1.3), 2)
    elif kind == "immune":
        pygame.draw.circle(s, (255, 230, 140), (c, c), r * 1.1, 2)
        _star(s, (255, 250, 210), c, c, r * 0.7)
    elif kind == "stealth":
        pygame.draw.ellipse(s, (170, 130, 230), (c - r * 1.2, c - r * 0.5, r * 2.4, r))
        pygame.draw.arc(s, (60, 40, 90), (c - r, c - r * 0.2, r * 2, r), math.pi, 2 * math.pi, 2)
    elif kind == "atk_tag":
        _sword(s, c - 1, c + 1, r)
        pygame.draw.circle(s, (110, 210, 70), (c + r * 0.6, c + r * 0.6), r * 0.35)
    elif kind == "heal_down":
        _heart(s, (200, 90, 100), c, c, r)
        pygame.draw.line(s, OUT, (c, c - r * 0.6), (c - r * 0.2, c + r * 0.8), 2)
    elif kind.startswith("mark:"):                 # метка механики: рисунок и число стаков
        _, mid, n = kind.split(":")
        base = MARK_GLYPH.get(mid, "other")
        glyph(s, base, size)
        if int(n) > 1:
            f = pygame.font.SysFont("arial", max(9, int(size * 0.55)), bold=True)
            img = f.render(n, True, (255, 255, 255))
            s.blit(img, (size - img.get_width() - 1, size - img.get_height() + 1))
    elif kind == "duel":
        pygame.draw.line(s, (235, 235, 245), (c - r, c + r), (c + r, c - r), 2)
        pygame.draw.line(s, (235, 235, 245), (c - r, c - r), (c + r, c + r), 2)
        pygame.draw.circle(s, (255, 190, 80), (c, c), max(2, r * 0.35))
    elif kind == "bomb":
        pygame.draw.circle(s, (60, 60, 70), (c, c + r * 0.2), r * 0.9)
        pygame.draw.line(s, (200, 170, 110), (c + r * 0.4, c - r * 0.5), (c + r * 0.9, c - r * 1.1), 2)
        pygame.draw.circle(s, (255, 200, 80), (c + r * 0.95, c - r * 1.15), max(1, r * 0.3))
    elif kind == "bleed":
        _drop(s, (200, 30, 40), c, c + r * 0.2, r, (255, 150, 140))
        _drop(s, (150, 20, 30), c + r * 0.7, c - r * 0.5, r * 0.45)
    elif kind == "silence":
        pygame.draw.ellipse(s, (200, 190, 220), (c - r, c - r * 0.45, r * 2, r * 0.9), 2)
        pygame.draw.line(s, (230, 70, 70), (c - r * 1.1, c + r * 0.9), (c + r * 1.1, c - r * 0.9), 2)
    elif kind == "range_down":
        pygame.draw.circle(s, (220, 200, 150), (c, c), r, 2)
        pygame.draw.line(s, (220, 200, 150), (c - r * 1.3, c), (c + r * 1.3, c), 1)
        pygame.draw.line(s, (220, 200, 150), (c, c - r * 1.3), (c, c + r * 1.3), 1)
    else:
        pygame.draw.circle(s, (200, 200, 210), (c, c), r * 0.6)


def icon(kind, size, border):
    key = (kind, size, border)
    img = _cache.get(key)
    if img is None:
        img = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(img, (22, 22, 30, 235), img.get_rect(), border_radius=4)
        inner = pygame.Surface((size, size), pygame.SRCALPHA)
        glyph(inner, kind, size)
        img.blit(inner, (0, 0))
        pygame.draw.rect(img, border, img.get_rect(), 2 if size >= 16 else 1, border_radius=4)
        _cache[key] = img
    return img


def buff_icon(stat, value):
    """Вид значка для баффа и полезный ли он."""
    if stat == "armor":
        return ("armor_up", True) if value > 0 else ("armor_down", False)
    if stat == "atk_mult":
        return ("atk_up", True) if value > 1 else ("atk_down", False)
    if stat == "dmg_taken":
        return ("tough", True) if value < 1 else ("vuln", False)
    if stat == "slow":
        return ("fast", True) if value < 1 else ("slow", False)
    if stat == "heal_taken":
        return ("heal_down", False) if value < 1 else ("regen", True)
    if stat == "range_add":
        return ("range_down", value >= 0)
    if stat == "exposed":
        return ("exposed", False)
    if stat == "trance":
        return ("atk_up", True)
    if stat == "undying":
        return ("immune", True)
    if stat in ("bleed", "silence"):
        return (stat, False)
    if stat == "stable":
        return ("other", False)
    if stat in ("banner", "zoc_free", "zoc_range", "collide_stun"):
        return ("armor_up", True)
    if stat in ("billiard", "all_arrows", "inferno"):
        return ("atk_up", True)
    if stat == "atk_speed":
        return ("haste", True) if value < 1 else ("slow", False)
    return {"atk_speed": ("haste", True), "thorns": ("thorns", True), "regen": ("regen", True),
            "immune": ("immune", True), "stealth": ("stealth", True), "ap_rate": ("ap_rate", True),
            "atk_tag": ("atk_tag", True)}.get(stat, ("other", True))


def unit_states(u, data, combat=None):
    """Все состояния юнита для значков: [(вид, цвет рамки, доля оставшегося времени, подпись)], контроль — первым."""
    out = []
    if u.stun > 0:
        look = "sleep" if u.asleep else u.stun_look
        out.append((look, CONTROL_COLORS.get(look, BAD), u.stun / max(u.stun_total, 0.01),
                    f"{CONTROL_NAMES.get(look, 'Оглушение')} {u.stun:.1f} с"))
    if u.charm_time > 0:
        out.append(("charm", (255, 120, 200), min(1.0, u.charm_time / 6), f"Очарован {u.charm_time:.1f} с"))
    if u.taunted_by is not None and u.taunt_time > 0:
        out.append(("taunt", BAD, min(1.0, u.taunt_time / 6), f"Провокация {u.taunt_time:.1f} с"))
    dur = data.config["status_duration"]
    for tag, left in u.statuses.items():
        tg = data.tags[tag]
        dot = getattr(u, "dots", {}).get(tag)
        total = dot.get("total", dur) if dot else dur
        stacks = dot.get("stacks", 1) if dot else 1
        stack_s = f" ×{stacks}" if stacks > 1 else ""
        dps = dot.get("dps", 0.0) if dot else 0.0
        if dot and dot.get("dps_pct"):
            dps += u.max_hp * (dot["dps_pct"] / 100.0 if dot["dps_pct"] > 1 else dot["dps_pct"])
        dps_s = f", {dps * stacks:.1f}/с" if dot else ""
        out.append((tag, tuple(tg["color"]), max(0.0, min(1.0, left / max(total, 0.01))),
                    f"{tg['name']}{stack_s} {left:.1f} с — {tg['status']}{dps_s}"))
    if u.shield > 0:
        out.append(("shield", GOOD, 1.0, f"Щит {u.shield}"))
    if u.tethered_by is not None and u.tether_time > 0:
        out.append(("charm", (255, 170, 200), min(1.0, u.tether_time / 15),
                    f"Привязь: {u.tethered_by.name} берёт половину урона, {u.tether_time:.1f} с"))
    if u.guarded_by is not None and u.guard_time > 0:
        out.append(("shield", (150, 200, 255), min(1.0, u.guard_time / 8), f"Под защитой: {u.guarded_by.name}, "
                                                                          f"{u.guard_time:.1f} с"))
    marks = data.config.get("marks", {})
    for mid, m in u.marks.items():                 # стаки механик: вызов, холод, бомба
        d = marks.get(mid, {})
        n = f" ×{m['n']}" if d.get("max", 1) > 1 else ""
        src = f" ({m['src'].name})" if m.get("src") is not None else ""
        out.insert(0 if mid in ("challenge", "duel") else len(out), (f"mark:{mid}:{m['n']}", tuple(d.get("color", (255, 220, 120))),
                    max(0.0, min(1.0, m["t"] / max(m["total"], 0.01))), f"{d.get('name', mid)}{n}{src} {m['t']:.1f} с"))
    mut = getattr(u, "mutator", None)
    if mut and mut in getattr(data, "mutators", {}):     # механика врага — первой, чтобы её видели
        d = data.mutators[mut]
        out.insert(0, (d.get("icon", "other"), tuple(d["color"]), 1.0, f"{d['name']}: {d['desc']}"))
    if getattr(u, "quiver", None):
        q = data.config.get("quiver", {}).get(u.quiver, {})
        out.append(("atk_tag", (255, 220, 150), 1.0, f"Колчан: {q.get('name', u.quiver)}"))
    if combat is not None:
        for name, left, total in combat.pending_on(u):
            out.append(("regen", (255, 240, 170), left / max(total, 0.01), f"{name} через {left:.1f} с"))
    if u.watch:
        out.append(("range_down", (255, 200, 110), u.watch["left"] / max(u.watch["total"], 0.01),
                    f"Дозор {u.watch['left']:.1f} с, выстрелов {u.watch['shots']}"))
    if u.song:
        out.append(("ap_rate", (255, 170, 220), 1 - u.song["beat"] / u.song["beats"],
                    f"Ритм: такт {u.song['beat']}/{u.song['beats']}, нот {u.song['notes']}"))
    for stat, (val, left) in u.buffs.items():
        if stat == "bleed" and "bleed" in u.statuses:
            continue                              # кровотечение уже показано как дот-статус
        kind, good = buff_icon(stat, val)
        total = u.buff_total.get(stat, left) or 1
        out.append((kind, GOOD if good else BAD, max(0.0, min(1.0, left / total)),
                    f"{BUFF_NAMES.get(stat, stat)} {left:.1f} с"))
    return out


def draw_row(surf, states, cx, y, size=18, gap=2, limit=6, center=True):
    """Ряд значков с полосками времени. Возвращает прямоугольники значков (для подсказок)."""
    shown = states[:limit]
    extra = len(states) - len(shown)
    w = len(shown) * (size + gap) - gap + (16 if extra else 0)
    x = cx - w / 2 if center else cx
    rects = []
    for kind, border, frac, _ in shown:
        surf.blit(icon(kind, size, border), (x, y))
        bar = pygame.Rect(x + 1, y + size + 1, size - 2, 3)
        pygame.draw.rect(surf, (15, 15, 18), bar)
        pygame.draw.rect(surf, border, (bar.x, bar.y, max(1, int(bar.w * frac)), bar.h))
        rects.append(pygame.Rect(x, y, size, size))
        x += size + gap
    if extra:
        T.text(surf, f"+{extra}", (x + 1, y + size / 2 - 7), 12, (230, 230, 240), True, shadow=True)
    return rects
