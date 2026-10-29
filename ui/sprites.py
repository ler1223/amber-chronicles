"""Спрайты юнитов: PNG из assets/sprites/ или пиксельная заглушка, нарисованная кодом.

Формат PNG — см. assets/sprites/README.md: смотрит вправо, ноги внизу по центру, прозрачный фон.
Масштаб целочисленный (пиксели остаются чёткими): обычный юнит ~64 px в высоту, босс ~96 px.
"""
import os

import pygame

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sprites")
CANVAS = 32
TARGET_H = {"normal": 64, "boss": 96}
OUTLINE = (22, 18, 24)


def shade(c, k):
    """k < 0 — темнее, k > 0 — светлее."""
    t = (0, 0, 0) if k < 0 else (255, 255, 255)
    k = abs(k)
    return tuple(int(c[i] + (t[i] - c[i]) * k) for i in range(3))


class SpriteBank:
    def __init__(self, folder=ASSET_DIR):
        self.folder = folder
        self.cache = {}
        self.base = {}

    def _base(self, names, kind, color, boss, look=None):
        """Спрайт в итоговом масштабе, смотрит вправо. names — кандидаты имени файла по порядку."""
        key = (tuple(names), boss)
        if key in self.base:
            return self.base[key]
        img = None
        for n in names:
            path = os.path.join(self.folder, f"{n}.png")
            if n and os.path.exists(path):
                img = pygame.image.load(path)
                try:
                    img = img.convert_alpha()
                except pygame.error:      # окно OpenGL или без дисплея — оставляем как загрузилось
                    pass
                break
        if img is None:
            img = placeholder(kind, color, look)
        target = TARGET_H["boss" if boss else "normal"]
        k = max(1, round(target / img.get_height()))
        img = pygame.transform.scale(img, (img.get_width() * k, img.get_height() * k))
        self.base[key] = img
        return img

    def get(self, names, kind, color, boss=False, flip=False, flash=False, look=None):
        key = (tuple(names), boss, flip, flash)
        if key not in self.cache:
            img = self._base(names, kind, color, boss, look)
            if flip:
                img = pygame.transform.flip(img, True, False)
            if flash:
                img = img.copy()
                img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
            self.cache[key] = img
        return self.cache[key]


# ---------- заглушки: пиксельные фигурки 32×32, смотрят вправо ----------

def placeholder(kind, color, look=None):
    if look and "object" in look:                 # объект поля (бочка, источник, обоз)
        from ui.objects_art import draw_object
        return draw_object(look["object"], color)
    s = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    if look and kind not in DRAWERS:              # враги глав: заглушка по облику из данных
        from ui.looks import draw_look
        draw_look(s, look)
        _outline(s)
        return s
    draw = DRAWERS.get(kind)
    if draw is None:
        draw = DRAWERS.get(ROLE_FALLBACK.get(kind, "warrior"))
    draw(s, tuple(color))
    _outline(s)
    return s


def _outline(s):
    mask = pygame.mask.from_surface(s)
    w, h = s.get_size()
    pts = set()
    for x, y in mask.outline():
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + dx, y + dy)
            if 0 <= p[0] < w and 0 <= p[1] < h and not mask.get_at(p):
                pts.add(p)
    for p in pts:
        s.set_at(p, OUTLINE)


def _legs(s, c):
    pygame.draw.rect(s, shade(c, -0.55), (12, 25, 3, 6))
    pygame.draw.rect(s, shade(c, -0.55), (17, 25, 3, 6))


def _body(s, c, skin=(232, 190, 150)):
    _legs(s, c)
    pygame.draw.rect(s, c, (11, 15, 10, 11))
    pygame.draw.rect(s, shade(c, -0.35), (11, 23, 10, 2))       # пояс
    pygame.draw.rect(s, shade(c, -0.2), (9, 16, 2, 7))          # руки
    pygame.draw.rect(s, shade(c, -0.2), (21, 16, 2, 7))
    pygame.draw.circle(s, skin, (16, 11), 4)
    s.set_at((18, 10), OUTLINE)                                  # глаз — смотрит вправо


def _robe(s, c, skin=(232, 190, 150)):
    pygame.draw.polygon(s, c, [(11, 15), (21, 15), (23, 31), (9, 31)])
    pygame.draw.line(s, shade(c, 0.25), (16, 16), (16, 30))
    pygame.draw.rect(s, shade(c, -0.2), (21, 16, 2, 7))
    pygame.draw.circle(s, skin, (16, 11), 4)
    s.set_at((18, 10), OUTLINE)


def draw_warrior(s, c):
    _body(s, c)
    pygame.draw.rect(s, (150, 152, 160), (12, 6, 9, 4))          # шлем
    pygame.draw.rect(s, (190, 60, 50), (14, 3, 3, 3))            # плюмаж
    pygame.draw.line(s, (215, 220, 230), (24, 22), (27, 8), 2)   # меч
    pygame.draw.line(s, (120, 90, 50), (22, 21), (26, 23), 2)
    pygame.draw.rect(s, shade(c, -0.3), (6, 15, 6, 9))           # щит
    s.set_at((8, 19), (230, 200, 90))


def draw_archer(s, c):
    _body(s, c)
    pygame.draw.polygon(s, shade(c, -0.15), [(11, 11), (16, 4), (21, 9), (20, 13), (12, 13)])  # капюшон
    pygame.draw.arc(s, (140, 95, 50), (21, 8, 8, 18), -1.5, 1.5, 2)                        # лук
    pygame.draw.line(s, (230, 230, 220), (25, 9), (25, 25))
    pygame.draw.rect(s, (120, 85, 50), (8, 13, 3, 8))                                       # колчан


def draw_mage(s, c):
    _robe(s, c)
    pygame.draw.polygon(s, shade(c, -0.25), [(10, 9), (23, 9), (17, 0)])    # шляпа
    pygame.draw.line(s, (120, 85, 50), (25, 8), (25, 31), 2)                # посох
    pygame.draw.circle(s, shade(c, 0.6), (25, 6), 3)


def draw_priest(s, c):
    _robe(s, (235, 230, 215))
    pygame.draw.rect(s, c, (11, 15, 10, 4))                                 # накидка
    pygame.draw.ellipse(s, (255, 230, 120), (11, 2, 10, 4), 1)              # нимб
    pygame.draw.line(s, (200, 170, 90), (25, 6), (25, 31), 2)               # посох с навершием
    pygame.draw.line(s, (240, 210, 110), (23, 8), (27, 8), 2)


def draw_slime(s, c, crown=False):
    pygame.draw.ellipse(s, c, (4, 13, 24, 18))
    pygame.draw.ellipse(s, shade(c, 0.35), (8, 15, 9, 5))
    pygame.draw.ellipse(s, shade(c, -0.25), (6, 26, 20, 5))
    for ex in (17, 23):
        pygame.draw.rect(s, (245, 245, 245), (ex, 19, 3, 4))
        s.set_at((ex + 2, 21), OUTLINE)
    if crown:
        pygame.draw.polygon(s, (240, 200, 70), [(9, 13), (11, 6), (14, 11), (16, 5), (18, 11), (21, 6), (23, 13)])


def draw_slime_king(s, c):
    pygame.draw.ellipse(s, c, (1, 10, 30, 21))
    pygame.draw.ellipse(s, shade(c, 0.35), (5, 13, 11, 6))
    for ex in (19, 25):
        pygame.draw.rect(s, (245, 245, 245), (ex, 17, 3, 5))
        s.set_at((ex + 2, 20), OUTLINE)
    pygame.draw.polygon(s, (240, 200, 70), [(9, 11), (11, 2), (14, 8), (16, 1), (18, 8), (21, 2), (23, 11)])


def draw_beetle(s, c):
    for x in (9, 14, 19):
        pygame.draw.line(s, OUTLINE, (x, 24), (x - 2, 30))
    pygame.draw.ellipse(s, c, (4, 14, 20, 13))
    pygame.draw.line(s, shade(c, -0.4), (14, 14), (14, 26))
    pygame.draw.ellipse(s, shade(c, 0.4), (7, 16, 5, 3))
    pygame.draw.circle(s, shade(c, -0.5), (25, 21), 4)
    pygame.draw.line(s, (240, 200, 120), (27, 19), (30, 14), 2)          # рог
    s.set_at((26, 20), (255, 230, 120))


def draw_frog(s, c):
    pygame.draw.ellipse(s, c, (7, 15, 18, 16))
    pygame.draw.ellipse(s, shade(c, 0.45), (11, 21, 10, 9))
    for ex in (13, 20):
        pygame.draw.circle(s, c, (ex, 15), 3)
        pygame.draw.rect(s, (250, 240, 120), (ex - 1, 14, 2, 2))
    pygame.draw.line(s, (120, 85, 50), (26, 8), (26, 31), 2)              # посох шамана
    pygame.draw.circle(s, (230, 90, 160), (26, 6), 2)


def draw_bog_archer(s, c):
    draw_archer(s, c)
    pygame.draw.circle(s, (150, 175, 110), (16, 11), 3)                   # болотная кожа


def draw_witch(s, c):
    _robe(s, c, skin=(205, 225, 240))
    pygame.draw.polygon(s, (40, 50, 80), [(9, 9), (24, 9), (14, 0)])
    pygame.draw.line(s, (170, 200, 230), (25, 8), (25, 31), 2)
    pygame.draw.polygon(s, (220, 245, 255), [(25, 1), (28, 6), (25, 10), (22, 6)])


def draw_assassin(s, c):
    _body(s, c)
    pygame.draw.polygon(s, shade(c, -0.25), [(10, 12), (16, 3), (22, 10), (21, 14), (11, 14)])   # глубокий капюшон
    pygame.draw.rect(s, (40, 30, 40), (13, 10, 7, 3))                                             # маска
    s.set_at((18, 11), (255, 90, 80))                                                              # глаз
    pygame.draw.line(s, (210, 215, 225), (23, 20), (28, 15), 2)                                   # кинжалы
    pygame.draw.line(s, (210, 215, 225), (8, 20), (5, 15), 2)
    pygame.draw.polygon(s, shade(c, -0.4), [(11, 16), (6, 27), (11, 25)])                         # плащ


def draw_druid(s, c):
    _robe(s, shade(c, -0.15))
    pygame.draw.rect(s, (120, 85, 50), (11, 20, 10, 2))                                           # пояс-лоза
    for x, y in ((11, 6), (13, 4), (19, 4), (21, 6)):                                              # рога-ветви
        pygame.draw.line(s, (130, 95, 55), (16, 8), (x, y), 1)
    pygame.draw.line(s, (120, 85, 50), (25, 6), (25, 31), 2)                                      # посох
    pygame.draw.circle(s, (120, 210, 90), (25, 6), 3)
    pygame.draw.circle(s, (170, 240, 120), (27, 9), 2)


def draw_guardian(s, c):
    _body(s, c)
    pygame.draw.rect(s, (160, 162, 170), (11, 5, 10, 6))                                          # шлем с гребнем
    pygame.draw.line(s, (200, 170, 90), (12, 4), (20, 4), 2)
    pygame.draw.line(s, (130, 95, 55), (26, 31), (26, 1), 2)                                      # копьё
    pygame.draw.polygon(s, (220, 225, 235), [(24, 3), (26, -2), (28, 3)])
    pygame.draw.rect(s, shade(c, -0.25), (4, 14, 8, 12), border_radius=2)                         # большой щит
    pygame.draw.line(s, (220, 190, 100), (8, 15), (8, 25))


def draw_shaman(s, c):
    _robe(s, c, skin=(200, 160, 120))
    for i, x in enumerate((11, 13, 15, 17, 19, 21)):                                               # перья
        pygame.draw.line(s, (240, 240, 230) if i % 2 else (90, 140, 230), (16, 8), (x, 2), 1)
    pygame.draw.line(s, (120, 85, 50), (25, 8), (25, 31), 2)
    pygame.draw.lines(s, (200, 220, 255), False, [(24, 1), (27, 4), (24, 6), (27, 9)], 1)          # искра на посохе


def draw_bard(s, c):
    _body(s, c)
    pygame.draw.polygon(s, shade(c, -0.3), [(10, 8), (22, 8), (20, 4), (12, 5)])                  # шляпа
    pygame.draw.line(s, (250, 230, 120), (20, 5), (26, 0), 1)                                     # перо
    pygame.draw.ellipse(s, (170, 110, 60), (19, 18, 8, 7))                                        # лютня
    pygame.draw.line(s, (130, 85, 45), (24, 19), (29, 11), 2)
    s.set_at((22, 21), OUTLINE)


def draw_alchemist(s, c):
    _body(s, (110, 100, 90))
    pygame.draw.rect(s, c, (11, 17, 10, 9))                                                      # фартук
    pygame.draw.rect(s, (80, 70, 60), (12, 9, 8, 3))                                             # очки
    s.set_at((14, 10), (150, 230, 255))
    s.set_at((18, 10), (150, 230, 255))
    pygame.draw.rect(s, (200, 150, 70), (13, 4, 6, 4))                                           # шапка
    pygame.draw.polygon(s, (120, 220, 100), [(24, 16), (28, 16), (29, 22), (23, 22)])            # колба
    pygame.draw.rect(s, (230, 230, 230), (25, 13, 2, 3))
    pygame.draw.circle(s, (230, 110, 40), (7, 20), 3)                                            # бомба на поясе


def draw_bear(s, c):
    pygame.draw.ellipse(s, (120, 86, 56), (3, 12, 24, 16))                                       # туловище
    pygame.draw.circle(s, (130, 94, 60), (25, 14), 6)                                            # голова
    pygame.draw.circle(s, (100, 70, 45), (22, 8), 2)
    pygame.draw.circle(s, (100, 70, 45), (28, 9), 2)
    pygame.draw.rect(s, (90, 64, 42), (6, 25, 4, 6))
    pygame.draw.rect(s, (90, 64, 42), (18, 25, 4, 6))
    pygame.draw.ellipse(s, (180, 150, 110), (27, 15, 4, 3))
    s.set_at((27, 13), OUTLINE)
    pygame.draw.line(s, (120, 210, 90), (8, 13), (16, 12), 1)                                    # лоза — это друид


def draw_wolf(s, c):
    pygame.draw.ellipse(s, (150, 150, 160), (4, 16, 20, 10))
    pygame.draw.polygon(s, (160, 160, 170), [(20, 15), (30, 18), (26, 22), (20, 22)])            # морда
    pygame.draw.polygon(s, (130, 130, 140), [(21, 15), (23, 10), (25, 15)])                      # ухо
    pygame.draw.line(s, (130, 130, 140), (5, 18), (1, 13), 2)                                    # хвост
    for x in (7, 11, 17, 21):
        pygame.draw.line(s, (110, 110, 120), (x, 25), (x, 31), 2)
    s.set_at((26, 18), (255, 220, 90))
    pygame.draw.line(s, (120, 210, 90), (8, 17), (16, 16), 1)


def _totem(s, c, top):
    pygame.draw.rect(s, (120, 86, 52), (12, 10, 8, 21))
    pygame.draw.rect(s, shade(c, -0.1), (11, 12, 10, 6))
    s.set_at((13, 14), OUTLINE)
    s.set_at((18, 14), OUTLINE)
    pygame.draw.line(s, OUTLINE, (14, 16), (17, 16))
    pygame.draw.rect(s, shade(c, 0.2), (11, 21, 10, 3))
    top(s, c)


def draw_totem_storm(s, c):
    _totem(s, c, lambda s, c: pygame.draw.polygon(s, (220, 230, 255), [(16, 1), (12, 9), (16, 7), (14, 12), (21, 4),
                                                                       (17, 5)]))


def draw_totem_thunder(s, c):
    _totem(s, c, lambda s, c: (pygame.draw.circle(s, (180, 170, 255), (16, 6), 4),
                               pygame.draw.circle(s, (240, 240, 255), (16, 6), 2)))


def draw_totem_heal(s, c):
    _totem(s, c, lambda s, c: (pygame.draw.rect(s, (230, 255, 230), (15, 1, 3, 9)),
                               pygame.draw.rect(s, (230, 255, 230), (12, 4, 9, 3))))


def draw_totem_ward(s, c):
    pygame.draw.rect(s, (130, 120, 110), (9, 6, 14, 25), border_radius=3)                        # каменный идол
    pygame.draw.rect(s, (160, 150, 140), (11, 9, 10, 7))
    s.set_at((13, 12), (255, 120, 90))
    s.set_at((18, 12), (255, 120, 90))
    pygame.draw.line(s, OUTLINE, (13, 19), (18, 19))


def draw_spirit_tree(s, c):
    pygame.draw.rect(s, (110, 80, 50), (14, 16, 5, 15))
    pygame.draw.circle(s, c, (16, 11), 9)
    pygame.draw.circle(s, shade(c, 0.3), (13, 8), 4)
    for x, y in ((10, 12), (20, 7), (19, 14)):
        s.set_at((x, y), (250, 240, 150))


def draw_ent(s, c):
    pygame.draw.rect(s, c, (10, 9, 12, 18), border_radius=3)
    pygame.draw.line(s, shade(c, -0.3), (10, 14), (4, 8), 3)                                      # руки-ветви
    pygame.draw.line(s, shade(c, -0.3), (22, 14), (28, 8), 3)
    pygame.draw.rect(s, shade(c, -0.3), (11, 26, 4, 5))
    pygame.draw.rect(s, shade(c, -0.3), (17, 26, 4, 5))
    pygame.draw.circle(s, (100, 180, 70), (16, 6), 6)
    s.set_at((18, 13), (255, 230, 120))
    s.set_at((14, 13), (255, 230, 120))


DRAWERS = {
    "warrior": draw_warrior, "archer": draw_archer, "mage": draw_mage, "priest": draw_priest,
    "slime": draw_slime, "slime_king": draw_slime_king, "beetle": draw_beetle, "frog_shaman": draw_frog,
    "bog_archer": draw_bog_archer, "ice_witch": draw_witch,
    "assassin": draw_assassin, "druid": draw_druid, "guardian": draw_guardian, "shaman": draw_shaman,
    "bard": draw_bard, "alchemist": draw_alchemist, "bear": draw_bear, "wolf": draw_wolf,
    "totem_storm": draw_totem_storm, "totem_thunder": draw_totem_thunder, "totem_heal": draw_totem_heal,
    "totem_ward": draw_totem_ward, "spirit_tree": draw_spirit_tree, "ent": draw_ent,
}
ROLE_FALLBACK = {"melee": "warrior", "ranged": "archer", "caster": "mage", "support": "priest"}
