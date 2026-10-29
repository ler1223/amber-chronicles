"""Пиксельные заглушки врагов глав по описанию облика из данных (enemies.json → "look"):
body — тип тела, color/accent — цвета, head — головной убор, weapon — оружие, wings — крылья.
Холст 32×32, смотрит вправо, ноги внизу по центру. Свой PNG в assets/sprites/<id>.png заменяет заглушку."""
import pygame

OUTLINE = (22, 18, 24)


def shade(c, k):
    t = (0, 0, 0) if k < 0 else (255, 255, 255)
    k = abs(k)
    return tuple(int(c[i] + (t[i] - c[i]) * k) for i in range(3))


def R(s, c, x, y, w, h):
    pygame.draw.rect(s, c, (x, y, w, h))


def eye(s, x, y, c=OUTLINE):
    s.set_at((x, y), c)


# ---------- головы ----------

def head(s, kind, x, y, c, a):
    if kind == "helm":
        R(s, (150, 152, 162), x - 4, y - 5, 9, 4)
    elif kind == "hood":
        pygame.draw.polygon(s, shade(c, -0.25), [(x - 5, y + 1), (x, y - 7), (x + 5, y - 1), (x + 4, y + 3),
                                                 (x - 4, y + 3)])
    elif kind == "horns":
        pygame.draw.line(s, (230, 220, 200), (x - 3, y - 3), (x - 6, y - 7))
        pygame.draw.line(s, (230, 220, 200), (x + 3, y - 3), (x + 6, y - 7))
    elif kind == "crown":
        pygame.draw.polygon(s, (240, 200, 70), [(x - 4, y - 3), (x - 4, y - 8), (x - 2, y - 5), (x, y - 9),
                                                (x + 2, y - 5), (x + 4, y - 8), (x + 4, y - 3)])
    elif kind == "skull":
        pass
    elif kind == "wrap":
        for i in range(-3, 4, 2):
            pygame.draw.line(s, shade(c, -0.2), (x - 4, y + i), (x + 4, y + i - 1))
    elif kind == "nemes":
        pygame.draw.polygon(s, a, [(x - 5, y + 4), (x - 4, y - 4), (x + 4, y - 4), (x + 5, y + 4)])
        for i in range(-3, 4, 2):
            pygame.draw.line(s, (230, 200, 90), (x - 4, y + i), (x - 5, y + i + 1))
    elif kind == "hat":
        R(s, shade(a, -0.3), x - 5, y - 4, 11, 2)
        pygame.draw.polygon(s, shade(a, -0.3), [(x - 3, y - 4), (x, y - 10), (x + 3, y - 4)])
    elif kind == "fin":
        pygame.draw.polygon(s, a, [(x - 1, y - 4), (x + 2, y - 9), (x + 3, y - 4)])


def weapon(s, kind, x, y, a):
    steel, wood = (215, 220, 230), (130, 92, 52)
    if kind == "sword":
        pygame.draw.line(s, steel, (x, y), (x + 3, y - 12), 2)
    elif kind == "bow":
        pygame.draw.arc(s, wood, (x - 2, y - 10, 8, 18), -1.5, 1.5, 2)
    elif kind == "staff":
        pygame.draw.line(s, wood, (x, y + 10), (x, y - 12), 2)
        pygame.draw.circle(s, a, (x, y - 13), 3)
    elif kind == "spear":
        pygame.draw.line(s, wood, (x, y + 10), (x + 1, y - 14), 2)
        pygame.draw.polygon(s, steel, [(x - 1, y - 13), (x + 1, y - 18), (x + 3, y - 13)])
    elif kind in ("hammer", "club", "axe"):
        pygame.draw.line(s, wood, (x, y + 4), (x + 2, y - 9), 2)
        if kind == "hammer":
            R(s, (140, 140, 150), x - 1, y - 12, 7, 5)
        elif kind == "axe":
            pygame.draw.polygon(s, steel, [(x + 2, y - 10), (x + 7, y - 13), (x + 7, y - 5)])
        else:
            pygame.draw.circle(s, shade(wood, -0.2), (x + 2, y - 10), 4)
    elif kind == "whip":
        pygame.draw.lines(s, (90, 60, 40), False, [(x, y), (x + 4, y - 4), (x + 2, y - 8), (x + 6, y - 11)], 1)


def wings(s, c, x, y, span=9):
    pygame.draw.polygon(s, c, [(x, y), (x - span, y - 6), (x - span + 2, y + 2), (x - span + 4, y + 6)])
    pygame.draw.polygon(s, shade(c, -0.2), [(x, y + 2), (x - span + 3, y + 1), (x - span + 5, y + 7)])


# ---------- тела ----------

def humanoid(s, L, hunch=0, skin=None, robe=False, big=False):
    c, a = tuple(L["color"]), tuple(L["accent"])
    skin = skin or (232, 190, 150)
    w = 12 if big else 10
    x0 = 16 - w // 2
    if L.get("wings"):
        wings(s, shade(a, 0.3), 12, 14)
    if robe:
        pygame.draw.polygon(s, c, [(x0, 15 + hunch), (x0 + w, 15 + hunch), (x0 + w + 2, 31), (x0 - 2, 31)])
        pygame.draw.line(s, shade(a, 0.1), (16, 16 + hunch), (16, 30))
    else:
        R(s, shade(c, -0.55), 12, 25, 3, 6)
        R(s, shade(c, -0.55), 17, 25, 3, 6)
        R(s, c, x0, 15 + hunch, w, 11 - hunch)
        R(s, shade(a, -0.1), x0, 23, w, 2)
    R(s, shade(c, -0.2), x0 - 2, 16 + hunch, 2, 7)
    R(s, shade(c, -0.2), x0 + w, 16 + hunch, 2, 7)
    hx, hy = 16 + hunch // 2, 11 + hunch
    pygame.draw.circle(s, skin, (hx, hy), 5 if big else 4)
    eye(s, hx + 2, hy - 1)
    head(s, L.get("head", "none"), hx, hy, c, a)
    weapon(s, L.get("weapon", "none"), x0 + w + 2, 21, a)


def draw_humanoid(s, L):
    humanoid(s, L)


def draw_robe(s, L):
    humanoid(s, L, robe=True)


def draw_ghoul(s, L):
    humanoid(s, L, hunch=3, skin=shade(tuple(L["color"]), 0.25))
    eye(s, 20, 13, tuple(L["accent"]))


def draw_skeleton(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    if L.get("head") == "helm":
        humanoid(s, L, skin=c)
    else:
        R(s, c, 12, 25, 2, 6)
        R(s, c, 18, 25, 2, 6)
        R(s, c, 15, 15, 2, 11)
        for y in (16, 19, 22):
            pygame.draw.line(s, c, (12, y), (20, y))
        pygame.draw.line(s, c, (11, 16), (10, 23))
        pygame.draw.line(s, c, (21, 16), (22, 23))
        pygame.draw.circle(s, c, (16, 11), 4)
        eye(s, 17, 10)
        eye(s, 15, 10)
        head(s, L.get("head", "none"), 16, 11, c, a)
        weapon(s, L.get("weapon", "none"), 22, 21, a)


def draw_dryad(s, L):
    humanoid(s, L, robe=True, skin=shade(tuple(L["color"]), 0.3))
    for x, y in ((12, 6), (16, 4), (20, 6)):
        pygame.draw.circle(s, shade(tuple(L["color"]), -0.1), (x, y), 2)
    pygame.draw.circle(s, tuple(L["accent"]), (16, 4), 1)


def draw_siren(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.polygon(s, c, [(12, 18), (20, 18), (22, 26), (26, 30), (18, 29), (14, 31), (10, 26)])
    R(s, a, 12, 13, 8, 6)
    pygame.draw.circle(s, (220, 200, 190), (16, 10), 4)
    pygame.draw.line(s, a, (12, 7), (11, 16), 2)
    eye(s, 18, 9)
    head(s, L.get("head", "none"), 16, 10, c, a)


def draw_angel(s, L):
    a = tuple(L["accent"])
    wings(s, (240, 240, 250), 12, 13, 11)
    humanoid(s, dict(L, wings=False), robe=True)
    pygame.draw.ellipse(s, a, (12, 2, 9, 3), 1)


def draw_ogre(s, L):
    humanoid(s, L, big=True, skin=shade(tuple(L["color"]), 0.15))


def draw_rider(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    horse = shade(c, -0.2)
    pygame.draw.ellipse(s, horse, (4, 17, 20, 9))
    pygame.draw.polygon(s, horse, [(20, 18), (28, 13), (29, 17), (23, 22)])
    for x in (6, 10, 17, 21):
        R(s, shade(horse, -0.3), x, 24, 2, 7)
    R(s, a, 12, 9, 7, 9)
    pygame.draw.circle(s, (220, 180, 140), (15, 6), 3)
    eye(s, 17, 5)
    head(s, L.get("head", "none"), 15, 6, c, a)
    weapon(s, L.get("weapon", "none"), 20, 14, a)


def draw_jackal(s, L):
    humanoid(s, L, skin=tuple(L["color"]))
    pygame.draw.polygon(s, tuple(L["color"]), [(17, 8), (23, 11), (17, 13)])
    pygame.draw.polygon(s, tuple(L["color"]), [(13, 7), (14, 1), (16, 7)])
    pygame.draw.line(s, tuple(L["accent"]), (12, 15), (20, 15), 2)


def draw_imp(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    wings(s, shade(c, -0.3), 13, 16, 7)
    R(s, c, 13, 17, 7, 8)
    R(s, shade(c, -0.4), 13, 25, 2, 5)
    R(s, shade(c, -0.4), 18, 25, 2, 5)
    pygame.draw.circle(s, c, (17, 13), 4)
    eye(s, 19, 12, a)
    head(s, "horns", 17, 13, c, a)
    pygame.draw.line(s, a, (20, 22), (25, 26))


def draw_fairy(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    for dx in (-1, 1):
        pygame.draw.ellipse(s, shade(a, 0.4), (16 + dx * 6 - 4, 8, 8, 12), 0)
    pygame.draw.polygon(s, c, [(14, 14), (18, 14), (20, 24), (12, 24)])
    pygame.draw.circle(s, (240, 210, 200), (16, 11), 3)
    eye(s, 17, 10)
    head(s, L.get("head", "none"), 16, 11, c, a)
    pygame.draw.circle(s, a, (21, 18), 1)


def draw_beast(s, L, long=False, big=False):
    c, a = tuple(L["color"]), tuple(L["accent"])
    w = 24 if long else 20
    pygame.draw.ellipse(s, c, (4, 16, w, 10))
    pygame.draw.polygon(s, c, [(4 + w - 4, 15), (31, 18), (27, 22), (4 + w - 4, 22)])
    pygame.draw.polygon(s, shade(c, -0.2), [(4 + w - 3, 15), (4 + w - 1, 10), (4 + w + 1, 15)])
    pygame.draw.line(s, shade(c, -0.2), (5, 18), (1, 13), 2)
    for x in (7, 11, 4 + w - 8, 4 + w - 4):
        pygame.draw.line(s, shade(c, -0.35), (x, 25), (x, 31), 2)
    s.set_at((28, 18), a)
    if L.get("wings"):
        wings(s, shade(a, 0.2), 14, 15, 10)


def draw_lizard(s, L):
    draw_beast(s, L, long=True)
    pygame.draw.line(s, tuple(L["accent"]), (8, 16), (22, 16))


def draw_griffin(s, L):
    draw_beast(s, dict(L, wings=True))
    pygame.draw.polygon(s, (240, 200, 80), [(28, 18), (31, 20), (28, 21)])


def draw_yeti(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.ellipse(s, c, (7, 9, 18, 18))
    R(s, shade(c, -0.15), 9, 24, 5, 7)
    R(s, shade(c, -0.15), 18, 24, 5, 7)
    R(s, shade(c, -0.1), 4, 13, 4, 11)
    R(s, shade(c, -0.1), 24, 13, 4, 11)
    pygame.draw.ellipse(s, a, (14, 11, 9, 7))
    eye(s, 19, 13)
    eye(s, 21, 13)
    head(s, L.get("head", "none"), 16, 9, c, a)


def draw_golem(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    R(s, c, 8, 10, 16, 14)
    R(s, shade(c, -0.2), 4, 12, 5, 12)
    R(s, shade(c, -0.2), 23, 12, 5, 12)
    R(s, shade(c, -0.3), 9, 24, 5, 7)
    R(s, shade(c, -0.3), 18, 24, 5, 7)
    R(s, shade(c, 0.1), 11, 4, 10, 7)
    R(s, a, 17, 6, 3, 2)
    for p in ((11, 14), (19, 18), (14, 21)):
        R(s, a, p[0], p[1], 2, 2)
    head(s, L.get("head", "none"), 16, 6, c, a)


def draw_construct(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.polygon(s, c, [(16, 4), (25, 12), (22, 28), (10, 28), (7, 12)])
    pygame.draw.polygon(s, shade(c, -0.25), [(16, 4), (16, 28), (10, 28), (7, 12)])
    pygame.draw.circle(s, a, (17, 13), 3)
    pygame.draw.circle(s, (255, 255, 255), (17, 13), 1)


def draw_elemental(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    for i, r in enumerate((11, 8, 5)):
        pygame.draw.circle(s, shade(c, 0.15 * i), (16, 15 - i), r)
    pygame.draw.lines(s, a, False, [(16, 2), (13, 8), (18, 10), (14, 16)], 2)
    eye(s, 18, 14, (255, 255, 255))


def draw_spirit(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.polygon(s, c, [(10, 12), (22, 12), (24, 26), (20, 23), (17, 29), (14, 23), (9, 27)])
    pygame.draw.circle(s, c, (16, 11), 6)
    R(s, OUTLINE, 14, 10, 2, 2)
    R(s, OUTLINE, 18, 10, 2, 2)
    pygame.draw.ellipse(s, shade(a, -0.2), (15, 14, 3, 3))


def draw_blob(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.ellipse(s, c, (4, 13, 24, 18))
    pygame.draw.ellipse(s, shade(c, 0.35), (8, 15, 9, 5))
    for x in (17, 23):
        R(s, a, x, 19, 3, 4)
        s.set_at((x + 2, 21), OUTLINE)


def draw_insect(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    for x in (10, 15, 20):
        pygame.draw.line(s, OUTLINE, (x, 25), (x - 2, 30))
    pygame.draw.ellipse(s, c, (6, 17, 18, 10))
    pygame.draw.line(s, a, (15, 17), (15, 26))
    pygame.draw.circle(s, shade(c, -0.4), (25, 22), 3)
    s.set_at((26, 21), a)


def draw_bird(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    wings(s, shade(c, -0.1), 15, 14, 12)
    pygame.draw.ellipse(s, c, (11, 12, 13, 9))
    pygame.draw.circle(s, a, (24, 13), 4)
    pygame.draw.polygon(s, (240, 200, 80), [(27, 13), (31, 15), (27, 16)])
    eye(s, 25, 12)
    pygame.draw.line(s, shade(c, -0.4), (16, 21), (15, 26))
    pygame.draw.line(s, shade(c, -0.4), (19, 21), (20, 26))


def draw_wyrm(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    wings(s, shade(a, -0.1), 15, 12, 11)
    pygame.draw.lines(s, c, False, [(4, 22), (9, 18), (14, 21), (19, 16), (24, 13)], 5)
    pygame.draw.circle(s, c, (25, 12), 4)
    eye(s, 27, 11, a)


def draw_serpent(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.lines(s, c, False, [(3, 26), (8, 21), (13, 25), (18, 19), (23, 17)], 5)
    pygame.draw.circle(s, c, (25, 15), 4)
    for p in ((8, 21), (13, 25), (18, 19)):
        s.set_at(p, a)
    eye(s, 27, 14, a)


def draw_crab(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.ellipse(s, c, (6, 15, 20, 11))
    for x in (8, 12, 20, 24):
        pygame.draw.line(s, shade(c, -0.3), (x, 24), (x - 2 if x < 16 else x + 2, 30), 2)
    pygame.draw.circle(s, c, (27, 14), 4)
    pygame.draw.circle(s, c, (5, 14), 3)
    R(s, a, 13, 13, 2, 3)
    R(s, a, 18, 13, 2, 3)


def draw_tentacle(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.lines(s, c, False, [(14, 31), (12, 24), (17, 17), (13, 10), (18, 4)], 6)
    for p in ((13, 22), (16, 16), (14, 10)):
        pygame.draw.circle(s, a, p, 1)
    pygame.draw.ellipse(s, (60, 80, 100), (6, 27, 20, 5))


def draw_plant(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.line(s, shade(c, -0.2), (16, 31), (16, 18), 3)
    for dx in (-1, 1):
        pygame.draw.ellipse(s, shade(c, 0.1), (16 + dx * 6 - 5, 22, 10, 5))
    pygame.draw.ellipse(s, c, (8, 6, 17, 14))
    pygame.draw.polygon(s, a, [(10, 13), (24, 11), (24, 15)])
    for x in range(12, 24, 3):
        s.set_at((x, 12), (250, 250, 240))


def draw_treant(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    R(s, c, 11, 10, 10, 17)
    pygame.draw.line(s, c, (11, 14), (4, 7), 3)
    pygame.draw.line(s, c, (21, 14), (28, 7), 3)
    R(s, shade(c, -0.3), 11, 26, 4, 5)
    R(s, shade(c, -0.3), 17, 26, 4, 5)
    pygame.draw.circle(s, a, (16, 7), 8)
    pygame.draw.circle(s, shade(a, 0.2), (13, 5), 3)
    s.set_at((18, 14), (255, 220, 120))
    s.set_at((14, 14), (255, 220, 120))


def draw_sarcophagus(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    pygame.draw.polygon(s, c, [(10, 4), (22, 4), (25, 12), (23, 31), (9, 31), (7, 12)])
    pygame.draw.polygon(s, shade(c, -0.25), [(10, 4), (22, 4), (25, 12), (23, 31), (9, 31), (7, 12)], 1)
    pygame.draw.circle(s, (220, 190, 140), (16, 10), 4)
    pygame.draw.line(s, a, (11, 15), (21, 15), 2)
    for y in range(18, 30, 3):
        pygame.draw.line(s, shade(a, -0.2), (11, y), (21, y))


def draw_eye(s, L):
    c, a = tuple(L["color"]), tuple(L["accent"])
    for i in range(6):
        pygame.draw.line(s, shade(c, -0.2), (16, 22), (8 + i * 3, 30), 1)
    pygame.draw.circle(s, c, (16, 14), 10)
    pygame.draw.circle(s, (240, 240, 250), (17, 14), 6)
    pygame.draw.circle(s, a, (18, 14), 3)
    pygame.draw.circle(s, OUTLINE, (18, 14), 1)


BODIES = {
    "humanoid": draw_humanoid, "robe": draw_robe, "ghoul": draw_ghoul, "skeleton": draw_skeleton, "dryad": draw_dryad,
    "siren": draw_siren, "angel": draw_angel, "ogre": draw_ogre, "rider": draw_rider, "jackal": draw_jackal,
    "imp": draw_imp, "fairy": draw_fairy, "beast": draw_beast, "lizard": draw_lizard, "griffin": draw_griffin,
    "yeti": draw_yeti, "golem": draw_golem, "construct": draw_construct, "elemental": draw_elemental,
    "spirit": draw_spirit, "blob": draw_blob, "insect": draw_insect, "bird": draw_bird, "wyrm": draw_wyrm,
    "serpent": draw_serpent, "crab": draw_crab, "tentacle": draw_tentacle, "plant": draw_plant, "treant": draw_treant,
    "sarcophagus": draw_sarcophagus, "eye": draw_eye,
}


def draw_look(s, L):
    BODIES.get(L.get("body"), draw_humanoid)(s, L)
