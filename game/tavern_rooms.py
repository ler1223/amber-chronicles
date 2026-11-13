"""Таверна из комнат (квиз 2026-11-11): полоса комнат внизу — Зал, Сборы, Мастерская, Двор, Стройка, Зал славы
(клавиши 1–6). В каждой комнате своя иллюстрация (assets/illustrations/hd/room_<id>.png, промпты — лист R) и только
свои действия. Объекты комнат (доска поручений, сундук, станции мастеров, кровать, надгробия) — спрайты
assets/sprites/obj_*.png (лист O); пока их нет — рисуются заглушки.

Зал — атмосфера и осмотр героев; Сборы — отряд, артефакты, глава и ступень, «В поход»; Мастерская — станции
мастеров (ковка, огранка, алхимия) и сундук-хранилище; Двор — доска поручений внизу, выше — этажи общежития;
Стройка — постройки таверны; Зал славы — кладбище павших (идти вперёд-назад) и летопись-книга."""
import math
import os
import random

import pygame

from game import expedition_scenes as E
from game.expedition_scenes import XScene, BLESS, CURSE, GLORY, GOLD, hero_sprite, icon, title_of, tint_of
from game import jewel_view as JV
from game import workshop_games as G
from game import workshop_scenes as WS
from sim import artifacts as A
from ui import aa as AA
from sim import expedition as X
from sim import gems as GM
from sim import story_meta
from ui import illustrations as IL
from ui import theme as T
from ui import widgets as W
from ui.battle_view import fit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_H, STRIP_H = 56, 76
SECOND = (176, 146, 104)            # вторичные кнопки — светлое дерево; главные — янтарь (GOLD)
WOOD = (70, 50, 32)
WOOD_DARK = (24, 17, 11)
ROOMS = (("hall", "Зал", "map_camp", "Герои таверны: осмотреть, вести с поручений"),
         ("muster", "Сборы", "map_battle", "Собрать отряд, надеть артефакты и выйти в поход"),
         ("workshop", "Мастер", "map_anvil", "Станции мастеров: ковка, огранка, алхимия; сундук-хранилище"),
         ("yard", "Двор", "map_event", "Доска поручений и общежитие ветеранов"),
         ("build", "Строй", "map_shop", "Постройки таверны за золото и трофеи глав"),
         ("fame", "Слава", "map_boss", "Кладбище павших и летопись героев"),
         ("market", "Рынок", "gem_ruby", "Самоцветы: купить необработанные и огранённые, продать свои"),
         ("mine", "Шахта", "mat_ore", "Шахта: рабочие добывают руды и самоцветы, пока игра открыта"),
         ("chapters", "Главы", "map_boss", "Выбрать главу, ступень и прочитать её механики"))
FEATS = (("kills", "убийств"), ("battles", "боёв"), ("boss_kills", "боссов"), ("elite_kills", "элиты"),
         ("tasks", "поручений"), ("runs_won", "побед в походах"), ("falls", "падений"))


def hero_fit(data, cls, height):
    """Спрайт героя заданной высоты в пикселях (масштаб спрайтов разный у классов)."""
    base = hero_sprite(data, cls, 1.0).get_height()
    return hero_sprite(data, cls, height / max(1, base))


def strip_y():
    return T.SCREEN_H - STRIP_H


# ---------- общее состояние сборов (между комнатами) ----------

def sel(app):
    """Глава, ступень и выбранные герои — общие для всех комнат таверны."""
    s = getattr(app, "tavern_sel", None)
    prof = app.profile
    if s is None:
        ch = next((c for c, _, ok in reversed(prof.chapters()) if ok), "swamp")
        s = {"chapter": ch, "tier": prof.tier_open_of(ch), "picked": []}
        app.tavern_sel = s
    heroes = {h.uid for h in prof.recruitable()}
    s["picked"] = [u for u in s["picked"] if u in heroes]
    return s


def toggle_pick(app, uid):
    """В отряд / из отряда. Возвращает сообщение для игрока или None."""
    prof = app.profile
    s = sel(app)
    h = next((x for x in prof.recruitable() if x.uid == uid), None)
    if h is None:
        return None
    if uid in s["picked"]:
        s["picked"].remove(uid)
        return None
    if not prof.ready(h):
        return f"{h.name} ранен на поручении — пропускает этот поход"
    cap = prof.squad_cfg(s["chapter"])["squad_start"]
    if len(s["picked"]) < cap:
        s["picked"].append(uid)
    elif cap == 1:
        s["picked"] = [uid]
    else:
        return f"В эту главу берут не больше {cap} героев — остальные присоединятся в пути"
    return None


def go(app, room, **kw):
    app.exp = None
    app.switch(ROOM_CLASSES[room](app, **kw))


def room_art(iid, fallback="tavern"):
    return iid if os.path.exists(os.path.join(IL.DIR, "hd", f"{iid}.png")) or IL.has(iid) else fallback


# ---------- значки и объекты комнат ----------

def coin(surf, center, r=9):
    pygame.draw.circle(surf, (120, 80, 20), center, r + 1)
    pygame.draw.circle(surf, (240, 196, 80), center, r)
    pygame.draw.circle(surf, (255, 230, 150), (center[0] - r // 3, center[1] - r // 3), max(2, r // 3))
    pygame.draw.circle(surf, (170, 120, 40), center, r, 1)


def res_icon(xd, k, size):
    """Значок ресурса: материал — иконка, трофей главы — камень его цвета, золото — монета (None)."""
    if k == "glory":
        return None
    img = icon(f"mat_{k}", size)
    if img is not None:
        return img
    col = tuple((xd.get("materials", {}).get(k) or xd.get("trophies", {}).get(k) or {}).get("color", (200, 200, 200)))
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.polygon(s, T.mix(col, (0, 0, 0), 0.5), [(c, 1), (size - 2, c), (c, size - 1), (1, c)])
    pygame.draw.polygon(s, col, [(c, 3), (size - 4, c), (c, size - 3), (3, c)])
    pygame.draw.polygon(s, T.mix(col, (255, 255, 255), 0.5), [(c, 4), (c + size // 5, c - 2), (c, c)])
    return s


_MINE = {}


def mine_frames(h):
    """Кадры горняка (лист MH) на общем холсте — без обрезки полей, иначе фигура прыгает между кадрами."""
    if h not in _MINE:
        out = []
        for i in (1, 2, 3):
            p = os.path.join(ROOT, "assets", "sprites", f"mine_miner_{i}.png")
            if not os.path.exists(p):
                out = None
                break
            img = pygame.image.load(p)
            out.append(pygame.transform.smoothscale(img, (max(1, round(img.get_width() * h / img.get_height())), h)))
        _MINE[h] = out
    return _MINE[h]


_FICON = {}


def forge_icon(name, size, tint=None):
    """Значок кузни (лист KI, assets/sprites/fic_*.png, высокое разрешение) по высоте size; tint — окрасить
    серый примитив в цвет сплава. Нет картинки — None (рисуется формой)."""
    key = (name, size, tint)
    if key not in _FICON:
        from game import metal_view as MV
        img = MV.prop("fic_" + name, None, size)
        if img is not None and tint is not None:
            img = img.copy()
            img.fill(tuple(min(255, int(c * 1.25)) for c in tint) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        _FICON[key] = img
    return _FICON[key]


def res_name(xd, k):
    if k == "glory":
        return "Золото"
    return (xd.get("materials", {}).get(k) or xd.get("trophies", {}).get(k) or {}).get("name", k)


def cost_icons(scene, surf, prof, cost, x, y, size=24):
    """Цена значками: «[монета] 400 [руда] 12 …», нехватка — красным. Возвращает правый край."""
    xd = prof.xd
    for k, v in cost.items():
        have = prof.have(k)
        ok = have >= v
        r0 = x
        img = res_icon(xd, k, size)
        if img is None:
            coin(surf, (x + size // 2, y + size // 2), size // 2 - 2)
        else:
            surf.blit(img, (x, y))
        x += size + 3
        x = T.text(surf, str(v), (x, y + size // 2 - 9), 17, T.TEXT if ok else CURSE, True).right + 12
        scene.hit(pygame.Rect(r0, y, x - r0 - 8, size), None,
                  [res_name(xd, k), f"нужно {v}, есть {have}" + ("" if ok else " — не хватает")])
    return x


_OBJ = {}


def obj_img(name, height):
    """Объект комнаты: спрайт assets/sprites/<name>.png (лист O) или заглушка; масштаб — по высоте, без сглаживания."""
    key = (name, height)
    if key not in _OBJ:
        img = None
        for path in (os.path.join(ROOT, "assets", "sprites", f"{name}.png"),):
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path)
                except pygame.error:
                    img = None
        if img is None and name.startswith("grave"):
            p = os.path.join(ROOT, "assets", "sprites", "env", "dirt_tombstone.png")
            if os.path.exists(p):
                img = pygame.image.load(p)
        if img is None:
            img = _PX.get(name, _px_box)()
        k = max(1, height) / img.get_height()
        _OBJ[key] = pygame.transform.scale(img, (max(1, round(img.get_width() * k)), max(1, round(height))))
    return _OBJ[key]


def sprite_exists(name):
    return os.path.exists(os.path.join(ROOT, "assets", "sprites", f"{name}.png"))


_FIT = {}


def sprite_fit(name, w, h):
    """Спрайт ровно w×h (модули дома, слои двора) или None, если картинки нет."""
    key = (name, w, h)
    if key not in _FIT:
        img = None
        if sprite_exists(name):
            try:
                img = _trimmed(name)
                img = pygame.transform.scale(img, (max(1, w), max(1, h)))
            except pygame.error:
                img = None
        _FIT[key] = img
    return _FIT[key]


def _trimmed(name):
    """Спрайт без пустых полей холста (модули дома и слои ставятся впритык)."""
    img = pygame.image.load(os.path.join(ROOT, "assets", "sprites", f"{name}.png"))
    r = img.get_bounding_rect()
    return img.subsurface(r).copy() if r.w and r.h else img


def sprite_w(name, w):
    """Спрайт по ширине w с сохранением пропорций или None."""
    if not sprite_exists(name):
        return None
    key = (name, w, -1)
    if key not in _FIT:
        img = _trimmed(name)
        _FIT[key] = pygame.transform.scale(img, (w, max(1, round(img.get_height() * w / img.get_width()))))
    return _FIT[key]


def _cv(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _px_box():
    s = _cv(24, 24)
    pygame.draw.rect(s, (110, 80, 50), (2, 4, 20, 18))
    return s


def _px_board():
    s = _cv(52, 48)
    for x in (6, 42):
        pygame.draw.rect(s, (60, 40, 24), (x, 12, 5, 36))
    pygame.draw.polygon(s, (88, 58, 34), [(0, 10), (26, 1), (52, 10), (48, 12), (4, 12)])
    pygame.draw.rect(s, (40, 26, 16), (3, 12, 46, 26))
    pygame.draw.rect(s, (128, 92, 56), (5, 14, 42, 22))
    for y in (19, 25, 31):
        pygame.draw.line(s, (108, 76, 44), (5, y), (46, y))
    return s


def _px_chest():
    s = _cv(30, 22)
    pygame.draw.rect(s, (40, 24, 14), (1, 6, 28, 15))
    pygame.draw.rect(s, (120, 76, 40), (2, 8, 26, 12))
    pygame.draw.rect(s, (96, 60, 32), (2, 2, 26, 7), border_top_left_radius=5, border_top_right_radius=5)
    for x in (6, 22):
        pygame.draw.rect(s, (90, 90, 100), (x, 2, 3, 18))
    pygame.draw.rect(s, (230, 190, 80), (13, 9, 4, 5))
    return s


def _px_forge():
    s = _cv(52, 52)
    pygame.draw.rect(s, (70, 66, 64), (2, 6, 30, 44))
    pygame.draw.rect(s, (96, 92, 88), (4, 8, 26, 40))
    pygame.draw.rect(s, (30, 20, 16), (8, 22, 18, 14))
    pygame.draw.polygon(s, (255, 150, 40), [(9, 35), (13, 26), (17, 34), (21, 24), (25, 35)])
    pygame.draw.polygon(s, (255, 230, 120), [(13, 35), (16, 29), (20, 35)])
    pygame.draw.rect(s, (60, 60, 66), (10, 0, 14, 8))
    pygame.draw.polygon(s, (90, 90, 98), [(30, 34), (50, 34), (46, 40), (36, 40)])
    pygame.draw.rect(s, (70, 70, 78), (37, 40, 8, 6))
    pygame.draw.rect(s, (56, 56, 62), (33, 46, 16, 4))
    return s


def _table(s, w, h, top):
    pygame.draw.rect(s, (70, 46, 28), (2, top, w - 4, 5))
    for x in (4, w - 9):
        pygame.draw.rect(s, (56, 36, 22), (x, top + 5, 5, h - top - 5))


def _px_jewel():
    s = _cv(48, 44)
    _table(s, 48, 44, 22)
    pygame.draw.circle(s, (180, 200, 220), (16, 14), 7, 2)
    pygame.draw.line(s, (120, 100, 70), (16, 21), (16, 22), 2)
    for i, col in enumerate(((230, 70, 80), (80, 140, 255), (80, 220, 120))):
        pygame.draw.polygon(s, col, [(28 + i * 6, 16), (31 + i * 6, 19), (28 + i * 6, 22), (25 + i * 6, 19)])
    return s


def _px_leather():
    s = _cv(48, 48)
    pygame.draw.rect(s, (70, 46, 28), (2, 4, 4, 44))
    pygame.draw.rect(s, (70, 46, 28), (42, 4, 4, 44))
    pygame.draw.rect(s, (70, 46, 28), (2, 4, 44, 4))
    pygame.draw.ellipse(s, (160, 104, 60), (8, 9, 32, 30))
    pygame.draw.ellipse(s, (130, 82, 46), (12, 13, 24, 22), 2)
    for y in (12, 22, 32):
        pygame.draw.line(s, (200, 180, 140), (6, y), (10, y))
        pygame.draw.line(s, (200, 180, 140), (38, y), (42, y))
    return s


def _px_alchemy():
    s = _cv(48, 48)
    _table(s, 48, 48, 28)
    for x, col, hh in ((8, (120, 220, 120), 14), (20, (220, 120, 240), 20), (34, (120, 180, 255), 12)):
        pygame.draw.rect(s, (200, 220, 230), (x + 3, 28 - hh - 4, 4, 5))
        pygame.draw.circle(s, col, (x + 5, 28 - hh // 2), max(4, hh // 2 - 1))
        pygame.draw.circle(s, (230, 240, 250), (x + 5, 28 - hh // 2), max(4, hh // 2 - 1), 1)
    return s


def _px_bed():
    s = _cv(44, 22)
    pygame.draw.rect(s, (80, 54, 32), (0, 4, 4, 18))
    pygame.draw.rect(s, (80, 54, 32), (40, 10, 4, 12))
    pygame.draw.rect(s, (96, 66, 40), (2, 14, 40, 6))
    pygame.draw.rect(s, (150, 50, 46), (10, 9, 31, 6))
    pygame.draw.rect(s, (220, 214, 196), (4, 9, 8, 5))
    return s


def _px_grave():
    s = _cv(18, 24)
    pygame.draw.rect(s, (90, 92, 96), (2, 6, 14, 18), border_top_left_radius=6, border_top_right_radius=6)
    pygame.draw.rect(s, (120, 122, 126), (4, 8, 10, 14), border_top_left_radius=4, border_top_right_radius=4)
    pygame.draw.line(s, (70, 72, 76), (9, 10), (9, 18), 2)
    pygame.draw.line(s, (70, 72, 76), (6, 13), (12, 13), 2)
    return s


_PX = {"obj_board": _px_board, "obj_chest": _px_chest, "obj_ws_forge": _px_forge, "obj_ws_jewel": _px_jewel,
       "obj_ws_leather": _px_leather, "obj_ws_alchemy": _px_alchemy, "obj_bed": _px_bed, "grave_1": _px_grave,
       "grave_2": _px_grave, "grave_3": _px_grave}


_GLOW = {}


def light(surf, center, radius, color=(255, 190, 110), strength=0.45):
    """Мягкий свет (фонарь, лампа): радиальное пятно, складывается с картинкой."""
    key = (radius, color, strength)
    if key not in _GLOW:
        g = pygame.Surface((radius * 2, radius * 2))
        g.fill((0, 0, 0))
        n = 16
        for k in range(n, 0, -1):
            f = strength * (1 - (k - 1) / n) ** 1.6
            pygame.draw.circle(g, tuple(int(c * f) for c in color), (radius, radius), max(1, radius * k // n))
        _GLOW[key] = g
    surf.blit(_GLOW[key], (center[0] - radius, center[1] - radius), special_flags=pygame.BLEND_RGB_ADD)


def glow_outline(surf, img, pos, color=(255, 230, 170)):
    m = pygame.mask.from_surface(img)
    o = m.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        surf.blit(o, (pos[0] + dx, pos[1] + dy))


def plate(surf, center, title, sub=None, col=None, w=None):
    """Табличка под объектом комнаты: название и строка состояния."""
    tw = max(T.font(17, True).size(title)[0], T.font(13).size(sub or "")[0]) + 28
    w = w or tw
    r = pygame.Rect(0, 0, w, 50 if sub else 30)
    r.midtop = center
    T.frame(surf, r, 235, accent=col or T.AMBER_DIM)
    T.text(surf, title, (r.centerx, r.y + 6), 17, col or T.TEXT, True, center=True)
    if sub:
        T.text(surf, fit(sub, 13, w - 16), (r.centerx, r.y + 28), 13, T.TEXT_DIM, center=True)
    return r


# ---------- каркас комнаты ----------

class Overlay:
    """Окно поверх комнаты (сундук, станция мастера, доска, герой). Esc или клик по комнате внизу — закрыть."""
    title = ""

    def __init__(self, scene):
        self.scene = scene
        self.app = scene.app

    full = False                     # окно — отдельный экран (мастерская): весь экран под шапкой

    @property
    def rect(self):
        if self.full:
            return pygame.Rect(12, TOP_H + 8, T.SCREEN_W - 24, T.SCREEN_H - TOP_H - 18)
        return pygame.Rect(24, TOP_H + 8, T.SCREEN_W - 48, strip_y() - TOP_H - 16)

    def frame(self, surf, title=None):
        r = self.rect
        T.frame(surf, r, 255, accent=T.AMBER_DIM)
        tr = T.text(surf, title or self.title, (r.x + 18, r.y + 12), 24, GLORY, True)
        self.head_x = tr.right + 16                             # где кончается заголовок (для подписи рядом)
        if T.orn("ui_flourish", None, 22) is not None:          # завиток после заголовка (лист UI)
            fl = T.orn("ui_flourish", None, 22)
            surf.blit(fl, (tr.right + 12, tr.centery - 11))
            self.head_x = tr.right + 12 + fl.get_width() + 10
        c = pygame.Rect(r.right - 46, r.y + 10, 34, 34)
        hot = c.collidepoint(self.scene.mouse)
        close = T.orn("ui_close", 34, 34)
        if close is not None:                                   # кнопка «закрыть» (лист UI)
            surf.blit(close, c)
            if hot:
                pygame.draw.rect(surf, (255, 220, 150), c, 1, border_radius=8)
        else:
            pygame.draw.rect(surf, (90, 60, 40) if hot else (50, 36, 24), c, border_radius=6)
            pygame.draw.rect(surf, T.AMBER_DIM, c, 1, border_radius=6)
            T.text(surf, "×", c.center, 24, T.TEXT, True, center=True)
        self.scene.hit(c, "close", "Закрыть (Esc)")
        return r

    def draw(self, surf):
        pass

    def act(self, action, button=1):
        pass

    def key(self, k):
        return False

    def wheel(self, dy):
        pass

    def update(self, dt):
        pass


class RoomScene(XScene):
    room = "hall"
    title = ""
    sub = ""
    art = "tavern"
    dim = 120
    mats = False

    def __init__(self, app):
        super().__init__(app)
        self.overlay = None

    # совместимость с листом героя таверны (TavernHeroScene: глава, отряд, «взять в поход»)
    @property
    def chapter(self):
        return sel(self.app)["chapter"]

    @property
    def tier(self):
        return sel(self.app)["tier"]

    @property
    def picked(self):
        return sel(self.app)["picked"]

    def handle(self, ev):
        if self.scroll_event(ev):
            return
        if self.overlay is not None and hasattr(self.overlay, "pointer"):
            if ev.type == pygame.MOUSEMOTION:
                self.mouse = ev.pos
            if self.overlay.pointer(ev):
                return
        if ev.type == pygame.MOUSEWHEEL:
            (self.overlay or self).wheel(ev.y)
            return
        if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and ev.button in (4, 5, 6, 7):
            return
        super().handle(ev)

    def wheel(self, dy):
        pass

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "room":
            go(self.app, action[1])
        elif kind == "menu":
            self.app.to_title()
        elif kind == "close":
            back = getattr(self.overlay, "back", None)
            self.overlay = back if isinstance(back, Overlay) else None
        elif self.overlay is not None:
            self.overlay.act(action, button)
        else:
            self.room_act(action, button)

    def room_act(self, action, button=1):
        pass

    def key(self, k):
        if self.overlay is not None:
            if k == pygame.K_ESCAPE:
                back = getattr(self.overlay, "back", None)
                self.overlay = back if isinstance(back, Overlay) else None
                return
            if self.overlay.key(k):
                return
        if pygame.K_1 <= k <= pygame.K_9 and k - pygame.K_1 < len(ROOMS):
            go(self.app, ROOMS[k - pygame.K_1][0])
        elif k == pygame.K_ESCAPE:
            self.escape()
        elif self.overlay is None:
            self.room_key(k)

    def escape(self):
        self.app.to_title()

    def room_key(self, k):
        pass

    def update(self, dt):
        super().update(dt)
        if self.overlay is not None:
            self.overlay.update(dt)

    def btn(self, surf, rect, label, action, enabled=True, primary=False, tip=None):
        W.button(surf, rect, label, self.mouse, enabled, GOLD if primary else SECOND)
        self.hit(rect, action if enabled else None, tip)

    def seg(self, surf, x, y, options, cur, kind, h=32):
        """Переключатель из нескольких вариантов (одна строка, общий стиль)."""
        for val, label in options:
            w = T.font(14, True).size(label)[0] + 26
            r = pygame.Rect(x, y, w, h)
            on = val == cur
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (96, 68, 36) if on else (56, 40, 26) if hot else (36, 26, 18), r, border_radius=6)
            pygame.draw.rect(surf, T.AMBER if on else (96, 70, 44), r, 1, border_radius=6)
            T.text(surf, label, r.center, 14, T.TEXT if on else T.TEXT_DIM, True, center=True)
            self.hit(r, (kind, val))
            x += w + 4
        return x

    def draw_backdrop(self, surf):
        self.backdrop(surf, room_art(self.art), "tavern", dim=self.dim)

    def draw(self, surf):
        self.hits = []
        surf.fill(T.BG)
        self.draw_backdrop(surf)
        self.draw_room(surf)
        if self.overlay is not None:
            self.hits = []
            sh = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
            sh.fill((4, 3, 2, 150))
            surf.blit(sh, (0, 0))
            self.overlay.draw(surf)
        self.draw_top(surf)
        self.draw_strip(surf)
        self.draw_tip(surf)
        self.draw_toast(surf, strip_y() - 24)

    def draw_room(self, surf):
        pass

    def room_title(self):
        return self.title

    def draw_top(self, surf):
        prof = self.app.profile
        band = pygame.Surface((T.SCREEN_W, TOP_H), pygame.SRCALPHA)
        band.fill((12, 9, 7, 215))
        surf.blit(band, (0, 0))
        pygame.draw.line(surf, T.AMBER_DIM, (0, TOP_H), (T.SCREEN_W, TOP_H))
        t = T.text(surf, self.room_title(), (22, 10), 26, GLORY, True, shadow=True)
        x = T.SCREEN_W - 18
        label = str(prof.glory)
        x -= T.font(20, True).size(label)[0]
        T.text(surf, label, (x, 16), 20, GOLD, True)
        coin(surf, (x - 16, 28), 10)
        self.hit(pygame.Rect(x - 28, 12, T.SCREEN_W - x + 10, 32), None, ["Золото таверны",
                                                                         "за походы, поручения; тратится на всё вне похода"])
        x -= 44
        if self.mats:
            for k in reversed(self.mat_keys()):
                n = str(prof.mats.get(k, 0))
                w = T.font(16, True).size(n)[0]
                x -= w
                T.text(surf, n, (x, 18), 16, T.TEXT, True)
                img = res_icon(prof.xd, k, 26)
                surf.blit(img, (x - 29, 15))
                self.hit(pygame.Rect(x - 30, 12, w + 32, 32), None,
                         [res_name(prof.xd, k), prof.xd["materials"][k].get("desc", "материал для мастерских")])
                x -= 42
        if self.sub:
            T.text(surf, fit(self.sub, 14, x - t.right - 40), (t.right + 18, 22), 14, T.TEXT_DIM)

    def mat_keys(self):
        """Ресурсы в шапке (комната может показать только свои)."""
        return list(self.app.profile.xd.get("materials", {}))

    def badge_for(self, rid):
        prof = self.app.profile
        if rid == "muster" and self.picked:
            return str(len(self.picked))
        if rid == "yard" and prof.news:
            return "!"
        return None

    def draw_strip(self, surf):
        y = strip_y()
        pygame.draw.rect(surf, WOOD_DARK, (0, y, T.SCREEN_W, STRIP_H))
        pygame.draw.line(surf, T.AMBER_DIM, (0, y), (T.SCREEN_W, y), 2)
        menu_w, gap = 116, 6
        n = len(ROOMS)
        tw = (T.SCREEN_W - 16 - menu_w - gap * n) // n
        x = 8
        for i, (rid, name, ic, tip) in enumerate(ROOMS):
            r = pygame.Rect(x, y + 8, tw, STRIP_H - 14)
            on = rid == self.room
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (82, 58, 34) if on else (52, 37, 24) if hot else (36, 26, 17), r, border_radius=8)
            pygame.draw.rect(surf, T.AMBER if on else (92, 68, 42), r, 2 if on else 1, border_radius=8)
            if on:
                pygame.draw.rect(surf, T.AMBER, (r.x + 10, r.y, r.w - 20, 3))
            img = icon(f"tab_{rid}", 40) or icon(ic, 40)
            if img is not None:
                surf.blit(img, (r.x + 10, r.centery - 20))
            fs = 18 if T.font(18, True).size(name)[0] <= r.w - 70 else 15
            T.text(surf, fit(name, fs, r.w - 66), (r.x + 58, r.centery - fs * 0.6), fs, T.AMBER if on else T.TEXT, True)
            T.text(surf, str(i + 1), (r.right - 14, r.y + 6), 12, T.TEXT_DIM, True)
            b = self.badge_for(rid)
            if b:
                pygame.draw.circle(surf, (200, 70, 50), (r.x + 46, r.y + 12), 9)
                T.text(surf, b, (r.x + 46, r.y + 12), 12, (255, 240, 220), True, center=True)
            self.hit(r, ("room", rid), [(name, T.AMBER), tip, f"клавиша {i + 1}"])
            x += tw + gap
        r = pygame.Rect(T.SCREEN_W - 8 - menu_w, y + 8, menu_w, STRIP_H - 14)
        hot = r.collidepoint(self.mouse)
        pygame.draw.rect(surf, (52, 37, 24) if hot else (30, 22, 15), r, border_radius=8)
        pygame.draw.rect(surf, (92, 68, 42), r, 1, border_radius=8)
        T.text(surf, "Меню", (r.centerx, r.centery - 10), 17, T.TEXT, True, center=True)
        T.text(surf, "Esc", (r.centerx, r.centery + 11), 12, T.TEXT_DIM, center=True)
        self.hit(r, "menu", "Главное меню")


# ---------- Зал ----------

def hero_tag(prof, h):
    """Метка героя: ранен на поручении, общежитие, вернулся, уходит, цена найма."""
    if not prof.ready(h):
        return ("ранен · отдыхает", CURSE)
    if h.dorm:
        return ("общежитие", (150, 220, 170))
    if h.vet.get("back"):
        return ("вернулся", GOLD)
    if h.vet and "stay" in h.vet:
        return ("уйдёт после похода", (220, 170, 120))
    cost = prof.hire_cost(h)
    return (f"найм {cost}", GLORY) if cost else None


def hero_info(scene, surf, h, anchor_x, top, hint):
    """Карточка героя при наведении: класс, ранг, черта, навыки с ультимейтом, артефакты."""
    prof = scene.app.profile
    data, xd = prof.data, prof.xd
    rk = xd["tavern"]["ranks"][str(h.rank)]
    tr = xd["tavern"]["traits"][h.trait]
    rows = [(f"{h.name} {title_of(xd, h)}".strip(), T.TEXT, 22, True),
            (f"{data.classes[h.cls]['name']} · {rk['name']} (ранг {h.rank}) · ур. {h.level}", GLORY, 15, True)]
    tag = hero_tag(prof, h)
    if tag:
        rows.append((tag[0], tag[1], 14, True))
    if h.vet:
        rows.append((f"Ветеран: побед {h.vet.get('wins', 0)}", (150, 220, 170), 14, True))
    rows += [None, (f"{tr['name']}: {tr['desc']}", (220, 200, 160), 14, False), None]
    ult = story_meta.ult_of(data, h.cls, h.skills)
    for k, sid in enumerate(h.skills):
        sk = data.skills[sid]
        key = "QWER"[k] if k < 4 else "·"
        rows.append((f"{key} · {'ультимейт ' if sid == ult else ''}{sk['name']} — {sk.get('desc', '')}",
                     GOLD if sid == ult else T.TEXT, 13, False))
    worn = prof.worn(h)
    if worn:
        rows += [None, ("Артефакты: " + ", ".join(A.art_name(xd, a) for a in worn), BLESS, 13, False)]
    w = 440
    lines = []
    for row in rows:
        if row is None:
            lines.append(None)
            continue
        text, col, size, bold = row
        lines += [(ln, col, size, bold) for ln in T.wrap(text, size, w - 28, bold)]
    hgt = 34 + sum(8 if ln is None else ln[2] + 5 for ln in lines)
    bx = anchor_x + 20 if anchor_x + 20 + w < T.SCREEN_W - 10 else anchor_x - 20 - w
    by = max(TOP_H + 8, min(top, strip_y() - 10 - hgt))
    T.frame(surf, (bx, by, w, hgt), 245, accent=tint_of(data, h.cls)["accent"])
    y = by + 12
    for ln in lines:
        if ln is None:
            y += 8
            continue
        T.text(surf, ln[0], (bx + 14, y), ln[2], ln[1], ln[3])
        y += ln[2] + 5
    T.text(surf, hint, (bx + 14, by + hgt - 20), 12, T.TEXT_DIM)


class HallRoom(RoomScene):
    """Зал: герои стоят по таверне (наведение — карточка, клик — лист героя), вести с поручений, продолжить поход."""
    room = "hall"
    art = "tavern"
    dim = 20
    SPOTS = [(0.10, 0.86, False), (0.35, 0.85, True), (0.57, 0.87, True), (0.22, 0.71, False),
             (0.46, 0.69, False), (0.64, 0.71, True), (0.03, 0.70, False), (0.33, 0.65, True),
             (0.53, 0.63, False), (0.76, 0.66, True)]
    SCALE = 0.8

    def room_title(self):
        return self.app.profile.xd["tavern"]["name"]

    def room_act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "hero":
            self.app.switch(E.TavernHeroScene(self.app, self, action[1]))
        elif kind == "recruit":                    # с листа героя: в отряд — а собираются в «Сборах»
            msg = toggle_pick(self.app, action[1])
            self.say(msg or ("В отряде: " + str(len(self.picked)) + " — отряд собирается в «Сборах» (2)"))
        elif kind == "resume":
            E.resume(self.app)
        elif kind == "abandon":
            prof.abandon()
            self.say("Поход брошен. Золото за него не начислено")
        elif kind == "reroll":
            if prof.reroll():
                sel(self.app)["picked"] = []
            else:
                self.say("Не хватает золота")

    def room_key(self, k):
        if k in (pygame.K_SPACE, pygame.K_RETURN) and self.app.profile.run_state:
            E.resume(self.app)

    def draw_room(self, surf):
        prof = self.app.profile
        if prof.run_state:
            draw_resume(self, surf)
            return
        hover = self.draw_heroes(surf)
        if prof.news:
            r = pygame.Rect(18, TOP_H + 12, 470, 34 + 21 * min(3, len(prof.news)))
            T.frame(surf, r, 225)
            T.text(surf, "Вести с поручений", (r.x + 14, r.y + 8), 15, GLORY, True)
            y = r.y + 30
            for n in prof.news[:3]:
                line, col = E.news_line(prof.xd, n)
                T.text(surf, fit(line, 13, r.w - 28), (r.x + 14, y), 13, col, True)
                y += 21
            self.hit(r, ("room", "yard"), ["Вести с поручений", "клик — Двор, доска поручений"])
        cost = prof.xd["tavern"]["reroll_cost"]
        self.btn(surf, pygame.Rect(T.SCREEN_W - 230, TOP_H + 12, 210, 38), f"Новые лица · {cost}", "reroll",
                 prof.glory >= cost, tip=["Все новички в зале сменятся", "ветераны, общежитие и поручения — остаются"])
        hint = "Наведите на героя — подробности, клик — лист героя. Собрать отряд — «Сборы» (2)"
        T.text(surf, hint, (T.SCREEN_W // 2, strip_y() - 26), 15, T.TEXT, center=True, shadow=True)
        if hover:
            h, img, x, ground = hover
            hero_info(self, surf, h, x + img.get_width() * 3 // 4 if x < T.SCREEN_W // 2 else x + img.get_width() // 4,
                      ground - img.get_height(), "клик — лист героя")

    def draw_heroes(self, surf):
        prof = self.app.profile
        data = prof.data
        img_h = T.SCREEN_W * 2 // 3
        top = (T.SCREEN_H - img_h) // 2
        px = T.SCREEN_W / 192
        placed = []
        for i, h in enumerate(prof.hall()[:len(self.SPOTS)]):
            sx, gy, flip = self.SPOTS[i]
            depth = 0.62 + 0.26 * (gy - 0.62) / 0.24
            img = hero_sprite(data, h.cls, px * self.SCALE * depth)
            if flip:
                img = pygame.transform.flip(img, True, False)
            x = int(sx * T.SCREEN_W - img.get_width() / 2)
            placed.append((gy, h, img, x, min(strip_y() - 6, int(top + gy * img_h))))
        placed.sort(key=lambda p: p[0])
        hover = None
        for gy, h, img, x, ground in placed:
            w = img.get_width()
            if pygame.Rect(x + w // 5, ground - img.get_height(), w * 3 // 5, img.get_height()).collidepoint(self.mouse):
                hover = (h, img, x, ground)
        for gy, h, img, x, ground in placed:
            on = h.uid in self.picked
            hot = hover is not None and hover[0] is h
            w = img.get_width()
            sh = pygame.Surface((int(w * 0.7), max(8, w // 10)), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (*GOLD, 150) if on else (0, 0, 0, 120), sh.get_rect())
            surf.blit(sh, (x + w * 0.15, ground - sh.get_height() * 0.6))
            if hot:
                glow_outline(surf, img, (x, ground - img.get_height()))
            dimg = img
            if not prof.ready(h):
                dimg = img.copy()
                dimg.fill((130, 120, 125, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(dimg, (x, ground - img.get_height()))
            self.hit(pygame.Rect(x + w // 5, ground - img.get_height(), w * 3 // 5, img.get_height()), ("hero", h.uid))
            tag = hero_tag(prof, h)
            label = h.name + (f"  ·  {tag[0]}" if tag else "")
            tw = T.font(13, True).size(label)[0] + 16
            tr = pygame.Rect(x + w // 2 - tw // 2, ground - img.get_height() * 5 // 6 - 26, tw, 21)
            pygame.draw.rect(surf, (16, 12, 9), tr, border_radius=6)
            pygame.draw.rect(surf, tag[1] if tag else T.AMBER_DIM, tr, 1, border_radius=6)
            T.text(surf, label, tr.center, 13, tag[1] if tag else T.TEXT, True, center=True)
        return hover


def draw_resume(scene, surf):
    """Карточка «Отряд в походе»: продолжить или бросить."""
    prof = scene.app.profile
    st = prof.run_state
    r = pygame.Rect(T.SCREEN_W // 2 - 420, TOP_H + 60, 840, 430)
    T.frame(surf, r, 240)
    acts = X.chapter_view(prof.xd, st.get("chapter", "swamp"))["acts"]
    act = acts[min(st.get("act", 0), len(acts) - 1)]["name"]
    if st.get("endless", st.get("solo")):
        act = f"Акт {st.get('act', 0) + 1} · {act}"
    T.text(surf, "Отряд в походе", (r.centerx, r.y + 26), 30, T.TEXT, True, center=True)
    T.text(surf, act, (r.centerx, r.y + 66), 18, GLORY, True, center=True)
    heroes = st.get("heroes", [])
    step = min(220, (r.w - 80) // max(1, len(heroes)))
    x = r.centerx - step * len(heroes) // 2
    for h in heroes:
        img = hero_fit(prof.data, h["cls"], 150)
        surf.blit(img, (x + step // 2 - img.get_width() // 2, r.y + 250 - img.get_height()))
        T.text(surf, h["name"], (x + step // 2, r.y + 262), 17, T.TEXT, True, center=True)
        T.text(surf, f"ур. {h['level']}", (x + step // 2, r.y + 284), 14, T.TEXT_DIM, center=True)
        x += step
    scene.btn(surf, pygame.Rect(r.centerx - 290, r.bottom - 84, 300, 52), "Продолжить поход (Пробел)", "resume", True,
              primary=True)
    scene.btn(surf, pygame.Rect(r.centerx + 30, r.bottom - 84, 260, 52), "Бросить поход", "abandon", True,
              tip="Поход закончится без золота, герои не вернутся")


# ---------- Главы ----------

class ChapterRoom(RoomScene):
    """Выбор главы: крупные карточки с кратким описанием механик, ступень и формат."""
    room = "chapters"
    title = "Главы"
    art = "room_muster"
    dim = 140

    def room_act(self, action, button=1):
        prof = self.app.profile
        s = sel(self.app)
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "chapter":
            if prof.chapter_open(action[1]):
                s["chapter"] = action[1]
                s["tier"] = min(s["tier"], prof.tier_open_of(action[1]))
                s["picked"] = s["picked"][:prof.squad_cfg(action[1])["squad_start"]]
            else:
                self.say("Глава откроется победой в предыдущей")
        elif kind == "tier":
            if 0 <= action[1] <= prof.tier_open_of(s["chapter"]):
                s["tier"] = action[1]
            else:
                self.say("Ступень откроется победой на предыдущей")
        elif kind == "party_mode":
            prof.solo = action[1]
            prof.mode = "solo" if prof.solo else "expedition"
            s["picked"] = s["picked"][:prof.squad_cfg(s["chapter"])["squad_start"]]
            from game.app import remember_mode
            if getattr(self.app, "_base_path", None):
                remember_mode(prof.mode, self.app._base_path)
            prof.save()
        elif kind == "autocast":
            from ui import settings
            settings.put("autocast_start", action[1])
        elif kind == "next":
            go(self.app, "muster")
        elif kind in ("resume", "abandon"):
            HallRoom.room_act(self, action, button)

    def room_key(self, k):
        if self.app.profile.run_state:
            if k in (pygame.K_SPACE, pygame.K_RETURN):
                E.resume(self.app)
            return
        if k in (pygame.K_SPACE, pygame.K_RETURN):
            go(self.app, "muster")
        elif k == pygame.K_LEFT:
            self.room_act(("tier", max(0, sel(self.app)["tier"] - 1)))
        elif k == pygame.K_RIGHT:
            self.room_act(("tier", sel(self.app)["tier"] + 1))

    def draw_room(self, surf):
        prof = self.app.profile
        if prof.run_state:
            draw_resume(self, surf)
            return
        xd = prof.xd
        s = sel(self.app)
        panel = pygame.Rect(16, TOP_H + 8, T.SCREEN_W - 32, strip_y() - TOP_H - 16)
        T.frame(surf, panel, 230)
        T.text(surf, "Куда идём", (panel.x + 14, panel.y + 10), 20, GOLD, True)
        T.text(surf, "Выберите главу. Под карточкой — только то, что важно знать до похода.",
               (panel.x + 14, panel.y + 36), 13, T.TEXT_DIM)

        cards_h = panel.h - 152
        gap = 10
        cw = (panel.w - 28 - gap * 2) // 3
        ch = (cards_h - gap * 2) // 3
        for i, (cid, name, ok) in enumerate(prof.chapters()):
            meta = xd["chapters"][cid]
            col = tuple(meta.get("color", GLORY))
            r = pygame.Rect(panel.x + 14 + (i % 3) * (cw + gap),
                            panel.y + 58 + (i // 3) * (ch + gap), cw, ch)
            on = cid == s["chapter"]
            hot = ok and r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (58, 42, 27) if on or hot else (32, 24, 17), r, border_radius=8)
            pygame.draw.rect(surf, col if on else (92, 68, 44) if ok else (65, 55, 50), r,
                             3 if on else 1, border_radius=8)
            thumb = IL.get(meta.get("art", "act_0"), "act", (146, 96))
            if not ok:
                thumb = pygame.transform.grayscale(thumb)
            surf.blit(thumb, (r.x + 8, r.y + 8))
            tx = r.x + 164
            tw = r.right - tx - 8
            T.text(surf, fit(name, 18, tw), (tx, r.y + 8), 18, col if ok else T.TEXT_DIM, True)
            lines = T.wrap(meta.get("desc", ""), 12, tw)[:2]
            for j, line in enumerate(lines):
                T.text(surf, line, (tx, r.y + 32 + j * 15), 12, T.TEXT if ok else T.TEXT_DIM)
            mech = meta.get("mechanics") or []
            if mech:
                T.text(surf, fit("• " + mech[0], 11, tw), (tx, r.y + 64), 11, (220, 200, 160) if ok else T.TEXT_DIM)
                if len(mech) > 1:
                    T.text(surf, fit("• " + mech[1], 11, tw), (tx, r.y + 79), 11, (220, 200, 160) if ok else T.TEXT_DIM)
            if not ok:
                T.text(surf, "закрыто", (r.centerx, r.y + 112), 14, CURSE, True, center=True, shadow=True)
            self.hit(r, ("chapter", cid), [(name, col), meta.get("desc", "")] +
                     [(m, (220, 200, 160)) for m in mech[:3]] +
                     ["клик — выбрать" if ok else "откроется победой в предыдущей главе"])

        bar = pygame.Rect(panel.x + 14, panel.bottom - 92, panel.w - 28, 34)
        T.text(surf, "Ступень", (bar.x, bar.y + 7), 14, T.TEXT_DIM, True)
        x = bar.x + 70
        tiers = xd["config"]["tiers"]
        for i, tt in enumerate(tiers):
            ok = i <= prof.tier_open_of(s["chapter"])
            col = E.tier_color(i, len(tiers))
            r = pygame.Rect(x, bar.y, 28, 30)
            on = i == s["tier"]
            pygame.draw.rect(surf, T.mix(T.PANEL, col, 0.4 if on else 0.12), r, border_radius=6)
            pygame.draw.rect(surf, col if ok else T.PANEL_EDGE, r, 2 if on else 1, border_radius=6)
            T.text(surf, str(i + 1), r.center, 15, col if ok else (80, 70, 60), True, center=True)
            self.hit(r, ("tier", i), [(tt["name"], col), tt["desc"]] +
                     ([] if ok else [("Закрыто — победите на предыдущей ступени", CURSE)]))
            x += 32
        T.text(surf, fit(tiers[s["tier"]]["name"], 13, 220), (x + 8, bar.y + 8), 13,
               E.tier_color(s["tier"], len(tiers)), True)

        row2 = pygame.Rect(panel.x + 14, panel.bottom - 46, panel.w - 28, 34)
        T.text(surf, "Формат", (row2.x, row2.y + 7), 14, T.TEXT_DIM, True)
        xx = self.seg(surf, row2.x + 62, row2.y, ((False, "Отряд"), (True, "Бесконечный")),
                      bool(prof.solo), "party_mode", h=32)
        from ui import settings
        T.text(surf, "Автокаст", (xx + 10, row2.y + 7), 14, T.TEXT_DIM, True)
        self.seg(surf, xx + 88, row2.y, tuple((m, label) for m, label, _ in E.AUTOCAST_MODES),
                 settings.SETTINGS.get("autocast_start", "default"), "autocast", h=32)
        self.btn(surf, pygame.Rect(panel.right - 248, row2.y, 234, 32), "Собрать отряд  (Пробел)",
                 "next", True, primary=True)


# ---------- Сборы ----------

class MusterRoom(RoomScene):
    """Сборы: глава и ступень, формат и автокаст; крупные карточки героев с ячейками артефактов; «В поход»."""
    room = "muster"
    title = "Сборы"
    art = "room_muster"
    dim = 150
    CARD_W, CARD_H = 196, 382

    def __init__(self, app):
        super().__init__(app)
        self.scroll = 0

    def heroes(self):
        return self.app.profile.recruitable()

    def room_act(self, action, button=1):
        prof = self.app.profile
        s = sel(self.app)
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "recruit" and button == 3:
            self.app.switch(E.TavernHeroScene(self.app, self, action[1]))
        elif kind == "endless_skill":
            h = next((x for x in self.heroes() if x.uid == action[1]), None)
            if h is not None:
                choices = story_meta.one_skill_choices(prof.data, h.cls, h.level, h)
                if choices:
                    cur = h.endless_skill if h.endless_skill in choices else story_meta.default_one_skill(
                        prof.data, h.cls, h.level, h)
                    i = choices.index(cur) if cur in choices else -1
                    h.endless_skill = choices[(i + 1) % len(choices)]
                    prof.save()
        elif kind == "recruit":
            msg = toggle_pick(self.app, action[1])
            if msg:
                self.say(msg)
        elif kind == "slot":
            h = next((x for x in self.heroes() if x.uid == action[1]), None)
            if h:
                self.overlay = ChestOverlay(self, h)
        elif kind == "chapter":
            if prof.chapter_open(action[1]):
                s["chapter"] = action[1]
                s["tier"] = min(s["tier"], prof.tier_open_of(action[1]))
                s["picked"] = s["picked"][:prof.squad_cfg(action[1])["squad_start"]]
            else:
                self.say("Глава откроется победой в предыдущей")
        elif kind == "tier":
            if 0 <= action[1] <= prof.tier_open_of(s["chapter"]):
                s["tier"] = action[1]
            else:
                self.say("Ступень откроется победой на предыдущей")
        elif kind == "party_mode":
            prof.solo = action[1]
            prof.mode = "solo" if prof.solo else "expedition"
            s["picked"] = s["picked"][:prof.squad_cfg(s["chapter"])["squad_start"]]
            from game.app import remember_mode
            if getattr(self.app, "_base_path", None):
                remember_mode(prof.mode, self.app._base_path)
            prof.save()
        elif kind == "autocast":
            from ui import settings
            settings.put("autocast_start", action[1])
        elif kind == "chapters":
            go(self.app, "chapters")
        elif kind == "scroll":
            self.wheel(-action[1])
        elif kind == "go":
            self.start()
        elif kind in ("resume", "abandon"):
            HallRoom.room_act(self, action, button)

    def start(self):
        prof = self.app.profile
        s = sel(self.app)
        cfg = prof.squad_cfg(s["chapter"])
        if not cfg["squad_min"] <= len(s["picked"]) <= cfg["squad_start"]:
            self.say(f"Выберите {cfg['squad_start']} героев для этой главы")
            return
        if self.hire_total() > prof.glory:
            self.say("Не хватает золота на найм — выберите новичков попроще")
            return
        picked = list(s["picked"])
        s["picked"] = []
        E.start_run(self.app, picked, s["tier"], s["chapter"])

    def hire_total(self):
        prof = self.app.profile
        return sum(prof.hire_cost(h) for h in self.heroes() if h.uid in self.picked)

    def wheel(self, dy):
        n = len(self.heroes())
        self.scroll = max(0, min(max(0, n - self.visible()), self.scroll - dy))
        self.scroll_pos["muster"] = self.scroll

    def visible(self):
        return (T.SCREEN_W - 32 + 10) // (self.CARD_W + 10)

    def room_key(self, k):
        prof = self.app.profile
        if prof.run_state:
            if k in (pygame.K_SPACE, pygame.K_RETURN):
                E.resume(self.app)
            return
        if k in (pygame.K_SPACE, pygame.K_RETURN):
            self.start()
        elif k == pygame.K_LEFT:
            self.act(("tier", max(0, self.tier - 1)))
        elif k == pygame.K_RIGHT:
            self.act(("tier", self.tier + 1))

    def draw_room(self, surf):
        prof = self.app.profile
        if prof.run_state:
            draw_resume(self, surf)
            return
        self.draw_summary(surf)
        self.draw_cards(surf)
        y = strip_y() - 66
        names = [h.name for h in self.heroes() if h.uid in self.picked]
        cfg = prof.squad_cfg(sel(self.app)["chapter"])
        need = f"{cfg['squad_start']} героев для этой главы"
        msg = ("В отряде: " + ", ".join(names)) if names else f"Выберите {need}: клик по карточке. ПКМ — лист героя."
        T.text(surf, msg, (24, y + 6), 17, GOLD if names else T.TEXT, True, shadow=True)
        hire = self.hire_total()
        if hire:
            T.text(surf, f"Найм новичков: {hire} золота", (24, y + 32), 14, GLORY if hire <= prof.glory else CURSE)
        ok = cfg["squad_min"] <= len(self.picked) <= cfg["squad_start"] and hire <= prof.glory
        self.btn(surf, pygame.Rect(T.SCREEN_W - 300, y, 280, 54), "В поход  (Пробел)", "go", ok, primary=True)

    def draw_summary(self, surf):
        prof = self.app.profile
        xd = prof.xd
        s = sel(self.app)
        meta = xd["chapters"][s["chapter"]]
        panel = pygame.Rect(16, TOP_H + 8, T.SCREEN_W - 32, 92)
        T.frame(surf, panel, 232)
        col = tuple(meta.get("color", GLORY))
        T.text(surf, meta["name"], (panel.x + 14, panel.y + 8), 22, col, True)
        desc = fit(meta.get("desc", ""), 13, panel.w - 260)
        T.text(surf, desc, (panel.x + 14, panel.y + 36), 13, T.TEXT_DIM)
        mech = (meta.get("mechanics") or [""])[0]
        T.text(surf, fit("• " + mech, 12, panel.w - 260), (panel.x + 14, panel.y + 56), 12, (220, 200, 160))
        if prof.solo:
            T.text(surf, "Бесконечный забег: у каждого героя 1 способность, акты не кончаются",
                   (panel.x + 14, panel.y + 73), 11, (150, 220, 170))
        t = xd["config"]["tiers"][s["tier"]]
        T.text(surf, f"Ступень {s['tier'] + 1} · {t['name']}", (panel.right - 226, panel.y + 10), 15,
               E.tier_color(s["tier"], len(xd["config"]["tiers"])), True)
        self.btn(surf, pygame.Rect(panel.right - 226, panel.y + 40, 210, 34), "Сменить главу", "chapters", True)

    def draw_cards(self, surf):
        heroes = self.heroes()
        y = TOP_H + 112
        n = self.visible()
        self.scroll_pos["muster"] = self.scroll_pos.get("muster", self.scroll)
        shown_n = min(n, len(heroes))
        total = shown_n * (self.CARD_W + 10) - 10
        x = (T.SCREEN_W - total) // 2
        first = self.scroll_list(surf, "muster", pygame.Rect(x, y, total, self.CARD_H - 2), len(heroes), n,
                                 horizontal=True)
        self.scroll = first
        prev = None
        for h in heroes[first:first + n]:
            r = pygame.Rect(x, y, self.CARD_W, self.CARD_H)
            self.hero_card(surf, r, h)
            if h.dorm:                                # жильцы общежития — отдельно от гостей зала
                band = pygame.Rect(r.x + 8, r.y - 3, r.w - 16, 6)
                pygame.draw.rect(surf, (150, 220, 170), band, border_radius=3)
            if prev is not None and prev.dorm and not h.dorm:
                pygame.draw.line(surf, (150, 220, 170), (r.x - 5, r.y + 10), (r.x - 5, r.bottom - 10), 2)
            prev = h
            x += self.CARD_W + 10

    def hero_card(self, surf, r, h):
        prof = self.app.profile
        data, xd = prof.data, prof.xd
        on = h.uid in self.picked
        ready = prof.ready(h)
        tn = tint_of(data, h.cls)
        hot = r.collidepoint(self.mouse)
        T.frame(surf, r, 240, accent=GOLD if on else tn["dim"], corner=tn["accent"],
                fill=T.mix(T.PANEL, GOLD, 0.12) if on else None)
        if on:
            pygame.draw.rect(surf, GOLD, r, 3, border_radius=8)
        elif hot:
            pygame.draw.rect(surf, T.mix(tn["accent"], (0, 0, 0), 0.2), r, 2, border_radius=8)
        T.text(surf, fit(f"{h.name} {title_of(xd, h)}".strip(), 18, r.w - 20), (r.x + 12, r.y + 10), 18, T.TEXT, True)
        rk = xd["tavern"]["ranks"][str(h.rank)]["name"]
        T.text(surf, f"{data.classes[h.cls]['name']} · {rk}", (r.x + 12, r.y + 34), 13, tn["accent"], True)
        img = hero_fit(data, h.cls, 132)
        if not ready:
            img = img.copy()
            img.fill((120, 110, 115, 255), special_flags=pygame.BLEND_RGBA_MULT)
        sh = pygame.Surface((img.get_width() * 2 // 3, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (*GOLD, 150) if on else (0, 0, 0, 120), sh.get_rect())
        surf.blit(sh, (r.centerx - sh.get_width() // 2, r.y + 184))
        surf.blit(img, (r.centerx - img.get_width() // 2, r.y + 190 - img.get_height()))
        tag = hero_tag(prof, h)
        if on:
            tag = ("в отряде" + (f" · найм {prof.hire_cost(h)}" if prof.hire_cost(h) else ""), GOLD)
        if tag:
            T.text(surf, fit(tag[0], 13, r.w - 16), (r.centerx, r.y + 200), 13, tag[1], True, center=True)
        if prof.solo:                               # бесконечный забег: ровно одна способность
            choices = story_meta.one_skill_choices(data, h.cls, h.level, h)
            sid = h.endless_skill if h.endless_skill in choices else story_meta.default_one_skill(
                data, h.cls, h.level, h)
            sk = data.skills.get(sid, {})
            T.text(surf, "Способность", (r.x + 12, r.y + 220), 12, T.TEXT_DIM, True)
            T.text(surf, fit(sk.get("name", "—"), 14, r.w - 24), (r.x + 12, r.y + 237), 14, GOLD, True)
            T.text(surf, "клик — сменить", (r.x + 12, r.y + 255), 11, T.TEXT_DIM)
        else:
            ult = story_meta.ult_of(data, h.cls, h.skills)
            yy = r.y + 222
            for k, sid in enumerate(h.skills[:4]):
                sk = data.skills[sid]
                T.text(surf, fit(f"{'QWER'[k]}  {sk['name']}", 13, r.w - 20), (r.x + 12, yy), 13,
                       GOLD if sid == ult else T.TEXT_DIM)
                yy += 17
        self.hit(r, ("recruit", h.uid), [(h.name, tn["accent"]),
                                         "клик — " + ("убрать из отряда" if on else "взять в поход"), "ПКМ — лист героя"])
        if prof.solo:                               # клик по строке способности — следующая
            self.hit(pygame.Rect(r.x + 8, r.y + 214, r.w - 16, 54), ("endless_skill", h.uid),
                     ["Одна способность на весь забег", "клик — следующая способность"])
        slots = prof.art_slots(h)
        worn = prof.worn(h)
        sw = 34
        sx = r.centerx - (5 * (sw + 4) - 4) // 2
        sy = r.bottom - sw - 10
        T.text(surf, "Артефакты", (r.x + 12, sy - 18), 12, T.TEXT_DIM, True)
        for i in range(5):
            sr = pygame.Rect(sx + i * (sw + 4), sy, sw, sw)
            if i >= slots:
                pygame.draw.rect(surf, (22, 17, 13), sr, border_radius=6)
                pygame.draw.rect(surf, (54, 44, 36), sr, 1, border_radius=6)
                self.hit(sr, None, [f"Ячейка {i + 1}", f"откроется с рангом {i + 1} (победы в походах)"])
                continue
            if i < len(worn):
                WS.draw_art_icon(surf, sr, xd, worn[i])
                self.hit(sr, ("slot", h.uid), WS.art_tip(prof, worn[i]) + [("клик — сундук", T.TEXT_DIM)])
            else:
                hot_s = sr.collidepoint(self.mouse)
                pygame.draw.rect(surf, (54, 40, 26) if hot_s else (34, 26, 18), sr, border_radius=6)
                pygame.draw.rect(surf, T.AMBER_DIM, sr, 1, border_radius=6)
                T.text(surf, "+", sr.center, 20, T.AMBER_DIM, True, center=True)
                self.hit(sr, ("slot", h.uid), ["Пустая ячейка", "клик — надеть артефакт из сундука"])
        return hot


# ---------- сундук (хранилище артефактов) ----------

class ChestOverlay(Overlay):
    """Сундук: артефакты хранилища. С героем — клик надевает/снимает; без героя — смотреть, самоцветы, материалы."""

    def __init__(self, scene, hero=None):
        super().__init__(scene)
        self.hero = hero
        self.tab = "arts"
        self.scroll = 0

    def arts(self):
        prof = self.app.profile
        return sorted(prof.stash.values(), key=lambda a: (-A.RARITY_ORDER.index(a["rarity"]), a["set"], a["kind"]))

    def act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        h = self.hero
        if kind == "tab":
            self.tab = action[1]
            self.scroll = 0
        elif kind == "art" and h is not None:
            if action[1] in h.arts:
                prof.unequip(h, action[1])
            elif not prof.equip(h, action[1]):
                self.scene.say("Нет свободной ячейки (их число — ранг героя) или артефакт в походе")
        elif kind == "off" and h is not None:
            prof.unequip(h, action[1])
        elif kind == "gem_view":
            prof = self.app.profile
            g = next((x for x in prof.gems + prof.rough if x["uid"] == action[1]), None)
            if g:
                self.scene.overlay = GemViewer(self.scene, g, back=self)

    def wheel(self, dy):
        self.scroll = max(0, self.scroll - dy)

    def draw(self, surf):
        prof = self.app.profile
        xd = prof.xd
        h = self.hero
        r = self.frame(surf, "Сундук" + (f" — артефакты для {h.name}" if h else ""))
        y0 = r.y + 56
        if h:
            img = hero_fit(prof.data, h.cls, 88)
            surf.blit(img, (r.x + 18, y0 + 92 - img.get_height()))
            x = r.x + 30 + img.get_width()
            worn = prof.worn(h)
            for i in range(5):
                sr = pygame.Rect(x + i * 80, y0 + 10, 72, 72)
                if i >= prof.art_slots(h):
                    pygame.draw.rect(surf, (22, 17, 13), sr, border_radius=8)
                    T.text(surf, f"ранг {i + 1}", sr.center, 12, (90, 80, 70), center=True)
                elif i < len(worn):
                    WS.draw_art_icon(surf, sr, xd, worn[i])
                    self.scene.hit(sr, ("off", worn[i]["uid"]), WS.art_tip(prof, worn[i]) + [("клик — снять", T.TEXT_DIM)])
                else:
                    pygame.draw.rect(surf, (34, 26, 18), sr, border_radius=8)
                    pygame.draw.rect(surf, T.AMBER_DIM, sr, 1, border_radius=8)
                    T.text(surf, "пусто", sr.center, 12, T.TEXT_DIM, center=True)
            bx = x + 5 * 80 + 16
            k = A.power_score(xd, worn) if worn else 1.0
            T.text(surf, f"Сила артефактов ×{k:.2f}", (bx, y0 + 6), 17, BLESS if worn else T.TEXT_DIM, True)
            by = y0 + 32
            for sid, n_ in A.set_counts(xd, worn).items():
                s = xd["artifacts"]["sets"][sid]
                for need, b in sorted(s["bonus"].items()):
                    col = BLESS if n_ >= int(need) else T.TEXT_DIM
                    T.text(surf, fit(f"«{s['name']}» {n_}/{need}: {b['text']}", 13, r.right - bx - 20), (bx, by), 13, col)
                    by += 17
            y0 += 104
        else:
            self.scene.seg(surf, r.x + 18, y0, (("arts", f"Артефакты · {len(prof.stash)}"),
                                                ("gems", f"Огранённые · {len(prof.gems)}"),
                                                ("rough", f"Необработанные · {len(prof.rough)}"), ("mats", "Материалы")),
                           self.tab, "tab", h=34)
            y0 += 48
        if self.tab == "gems" and not h:
            self.draw_gems(surf, r, y0)
        elif self.tab == "rough" and not h:
            draw_stone_grid(self.scene, surf, pygame.Rect(r.x + 18, y0, r.w - 36, r.bottom - 14 - y0), "chest_rough",
                            [("rough", x) for x in self.app.profile.rough], lambda kind, x: ("gem_view", x["uid"]),
                            "Необработанных камней нет: рынок (7) и вылазки.")
        elif self.tab == "mats" and not h:
            self.draw_mats(surf, r, y0)
        else:
            self.draw_arts(surf, r, y0)

    def draw_arts(self, surf, r, y0):
        prof = self.app.profile
        xd = prof.xd
        h = self.hero
        arts = self.arts()
        with self.scene.grid(surf, "chest_arts", pygame.Rect(r.x + 18, y0, r.w - 36, r.bottom - 14 - y0), len(arts),
                             236, 92) as cells:
            for i, tr in cells:
                self.draw_art_card(surf, arts[i], tr)
        if not arts:
            T.text(surf, "Сундук пуст. Артефакты куются в Мастерской (3).", (r.x + 18, y0 + 10), 16, T.TEXT_DIM)

    def draw_art_card(self, surf, art, tr):
        prof = self.app.profile
        xd = prof.xd
        h = self.hero
        tw = tr.w
        if True:
            owner = prof.art_owner(art["uid"])
            mine = h is not None and art["uid"] in h.arts
            locked = prof.art_locked(art["uid"])
            col = WS.rar_color(xd, art["rarity"])
            hot = tr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (58, 42, 28) if hot else (32, 24, 17), tr, border_radius=8)
            pygame.draw.rect(surf, GOLD if mine else col if not owner else (80, 64, 50), tr, 2 if mine else 1,
                             border_radius=8)
            WS.draw_art_icon(surf, pygame.Rect(tr.x + 6, tr.y + 6, 76, 76), xd, art, dim=bool(owner and not mine) or locked)
            T.text(surf, xd["artifacts"]["kinds"][art["kind"]]["name"], (tr.x + 90, tr.y + 8), 16, T.TEXT, True)
            T.text(surf, fit(xd["artifacts"]["sets"][art["set"]]["name"], 13, tw - 96), (tr.x + 90, tr.y + 30), 13, col)
            T.text(surf, f"{art['q'] * 100:.0f}%" + (f" · +{art['level']}" if art["level"] else ""), (tr.x + 90, tr.y + 48),
                   13, T.TEXT_DIM)
            if owner:
                T.text(surf, fit("на " + owner.name, 12, tw - 96), (tr.x + 90, tr.y + 66), 12, GOLD if mine else T.TEXT_DIM)
            act = ("art", art["uid"]) if h is not None and not locked else None
            tip = WS.art_tip(prof, art) + ([("клик — " + ("снять" if mine else f"надеть на {h.name}"), T.TEXT_DIM)]
                                           if act else [])
            self.scene.hit(tr, act, tip)

    def draw_gems(self, surf, r, y0):
        prof = self.app.profile
        a = prof.xd["artifacts"]
        with self.scene.grid(surf, "chest_gems", pygame.Rect(r.x + 18, y0, r.w - 36, r.bottom - 14 - y0),
                             len(prof.gems), 170, 170) as cells:
            for i, tr in cells:
                self.draw_gem_card(surf, prof.gems[i], tr, i)
        if not prof.gems:
            T.text(surf, "Огранённых самоцветов нет — ювелир гранит их из сырья.", (r.x + 18, y0 + 10), 16, T.TEXT_DIM)

    def draw_gem_card(self, surf, g, tr, i):
        prof = self.app.profile
        a = prof.xd["artifacts"]
        if True:
            gd = a["gems"][g["id"]]
            hot = tr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (44, 32, 24) if hot else (26, 20, 16), tr, border_radius=10)
            pygame.draw.rect(surf, tuple(gd["color"]), tr, 2 if hot else 1, border_radius=10)
            JV.draw_gem(surf, g, tuple(gd["color"]), (tr.centerx, tr.y + 64), 118, self.scene.clock + i * 0.7,
                        xd=prof.xd)
            T.text(surf, gd["name"], (tr.centerx, tr.y + 128), 15, tuple(gd["color"]), True, center=True)
            T.text(surf, f"{g.get('size', 0):.2f} кар. · {GM.grade(prof.xd, g.get('cl', 0.6)).lower()}",
                   (tr.centerx, tr.y + 148), 12, T.TEXT_DIM, center=True)
            self.scene.hit(tr, ("gem_view", g["uid"]), [gd["name"]] + GM.describe(prof.xd, g) +
                           [(GM.stat_text(prof.xd, g), BLESS), "клик — рассмотреть; вставить — у ювелира"])

    def draw_mats(self, surf, r, y0):
        prof = self.app.profile
        xd = prof.xd
        x, y = r.x + 18, y0
        for k, m in xd.get("materials", {}).items():
            tr = pygame.Rect(x, y, 280, 96)
            pygame.draw.rect(surf, (32, 24, 17), tr, border_radius=8)
            pygame.draw.rect(surf, tuple(m["color"]), tr, 1, border_radius=8)
            surf.blit(res_icon(xd, k, 64), (tr.x + 14, tr.y + 16))
            T.text(surf, m["name"], (tr.x + 92, tr.y + 14), 17, tuple(m["color"]), True)
            T.text(surf, str(prof.mats.get(k, 0)), (tr.x + 92, tr.y + 40), 26, T.TEXT, True)
            T.text(surf, "редкий" if m.get("rare") else "общий", (tr.right - 14 - T.font(12).size("редкий")[0],
                                                                  tr.bottom - 22), 12, T.TEXT_DIM)
            self.scene.hit(tr, None, [m["name"], m.get("desc", "общий материал: бои и поручения")])
            x += 292
            if x + 280 > r.right - 18:
                x, y = r.x + 18, y + 106


class GemViewer(Overlay):
    """Витрина огранённого камня: крупно; мышь (зажать и тянуть) — вращать как угодно, колесо — приблизить."""

    def __init__(self, scene, gem, back=None):
        super().__init__(scene)
        self.gem = gem
        self.back = back
        self.insp = JV.Inspector()

    def pointer(self, ev):
        return self.insp.pointer(ev, self.view_rect())

    def view_rect(self):
        r = self.rect
        return pygame.Rect(r.x + 20, r.y + 56, r.w - 40, r.h - 160)

    def update(self, dt):
        self.insp.update(dt)

    @property
    def rect(self):
        return pygame.Rect(T.SCREEN_W // 2 - 360, TOP_H + 30, 720, strip_y() - TOP_H - 60)

    def act(self, action, button=1):
        if action == "close" and self.back is not None:
            self.scene.overlay = self.back

    def wheel(self, dy):
        self.insp.wheel(dy)

    def draw(self, surf):
        prof = self.app.profile
        gd = prof.xd["artifacts"]["gems"][self.gem["id"]]
        col = tuple(gd["color"])
        rough = "q" not in self.gem
        r = self.frame(surf, gd["name"] + (" — необработанный" if rough else ""))
        faces = JV.stone_faces(self.gem)
        self.insp.draw(surf, self.view_rect(), faces, JV.gem_color(self.gem, col), self.scene.clock,
                       mm=JV.mm_per_unit(self.gem, faces, prof.xd), incl=None if rough else self.gem.get("incl"),
                       star=0.0 if rough else self.gem.get("star", 0.0), axis=self.gem.get("axis"),
                       cfield=JV.gem_cfield(self.gem, faces if rough else None))
        lines = GM.describe(prof.xd, self.gem, rough=rough)
        T.text(surf, fit(" · ".join(lines), 16, r.w - 40), (r.centerx, r.bottom - 94), 16, col, True, center=True)
        if rough:
            T.text(surf, f"цена ≈ {prof.market_price('rough', self.gem)} · огранить — у ювелира: разметка покажет "
                         "примеси внутри", (r.centerx, r.bottom - 66), 14, T.TEXT, center=True)
        else:
            T.text(surf, fit(GM.stat_text(prof.xd, self.gem) + f" · цена ≈ {prof.market_price('cut', self.gem)}"
                             " · вставить — у ювелира", 14, r.w - 40), (r.centerx, r.bottom - 66), 14, T.TEXT,
                   center=True)
        T.text(surf, "зажмите мышь и тяните — вращать как угодно · колесо — приблизить · Esc — закрыть",
               (r.centerx, r.bottom - 36), 12, T.TEXT_DIM, center=True)


def draw_stone_grid(scene, surf, area, key, items, action_of, empty, price=None, button=None):
    """Сетка камней (огранённых и необработанных) с прокруткой: живой камень, название, размер, качество, цена.
    items — [(вид: cut | rough, камень)]; button(вид, камень) → (подпись, действие, можно) — кнопка под карточкой."""
    prof = scene.app.profile
    a = prof.xd["artifacts"]
    ch = 226 if button else 186
    with scene.grid(surf, key, area, len(items), 176, ch) as cells:
        for i, tr in cells:
            _stone_card(scene, surf, prof, a, items[i], tr, i, action_of, price, button)
    if not items:
        T.text(surf, empty, (area.x, area.y + 10), 16, T.TEXT_DIM)


def _stone_card(scene, surf, prof, a, item, tr, i, action_of, price, button):
    kind, g = item
    cw = tr.w
    if True:
        gd = a["gems"][g["id"]]
        col = tuple(gd["color"])
        hot = tr.collidepoint(scene.mouse)
        pygame.draw.rect(surf, (44, 32, 24) if hot else (26, 20, 16), tr, border_radius=10)
        pygame.draw.rect(surf, col, tr, 2 if hot else 1, border_radius=10)
        if kind == "rough":
            JV.draw_rough(surf, g, col, (tr.centerx, tr.y + 62), 104, scene.clock + i * 0.7, xd=prof.xd)
            sub = f"{g.get('size', 1.0):.2f} кар. · сырой · {GM.color_word(prof.xd, g.get('col', 0.5))}"
        else:
            JV.draw_gem(surf, g, col, (tr.centerx, tr.y + 62), 100, scene.clock + i * 0.7, xd=prof.xd)
            sub = f"{g.get('size', 1.0):.2f} кар. · {GM.grade(prof.xd, g.get('cl', 0.6)).lower()}"
        T.text(surf, gd["name"], (tr.centerx, tr.y + 130), 16, col, True, center=True)
        T.text(surf, fit(sub, 12, cw - 12), (tr.centerx, tr.y + 152), 12, T.TEXT_DIM, center=True)
        if price:
            p_ = price(kind, g)
            coin(surf, (tr.centerx - 24, tr.y + 176), 8)
            T.text(surf, str(p_), (tr.centerx - 12, tr.y + 167), 16, GOLD, True)
        scene.hit(tr, action_of(kind, g), [gd["name"] + (" (необработанный)" if kind == "rough" else "")] +
                  GM.describe(prof.xd, g, rough=kind == "rough") +
                  ([] if kind == "rough" else [(GM.stat_text(prof.xd, g), BLESS)]) + ["клик — рассмотреть"])
        if button:
            label, act, ok = button(kind, g)
            scene.btn(surf, pygame.Rect(tr.x + 12, tr.bottom - 40, tr.w - 24, 32), label, act, ok, primary=True)


class TradeMixin:
    """Вкладки «Купить / Продать» у бродячего мастера: хотелки визита, терпение и торг (просить выше цены)."""
    who = "smith"
    tmode = "buy"
    ask_i = 0

    def trade_tabs(self, surf, r):
        self.scene.seg(surf, r.right - 270, r.y + 12, (("buy", "Купить"), ("sell", "Продать")), self.tmode, "tmode",
                       h=34)

    def trade_act(self, kind, action):
        """True — действие торга обработано."""
        from sim import forge as FG
        prof = self.app.profile
        if kind == "tmode":
            self.tmode = action[1]
        elif kind == "ask":
            self.ask_i = action[1]
        elif kind == "tsell":
            ask = FG.TRADE["asks"][self.ask_i]
            res, price = prof.trade_sell(self.who, action[1], action[2], ask)
            self.scene.say({"sold": f"Продано за {price}", "refused": "«Нет уж, за такие деньги — не возьму»",
                            "angry": "Торговец обиделся — до следующего визита ничего не купит"}.get(res, "Нельзя"))
        else:
            return False
        return True

    def want_name(self, wid):
        from sim import forge as FG
        prof = self.app.profile
        if self.who == "jeweler":
            return prof.xd["artifacts"]["gems"][wid]["name"]
        return FG.ALLOYS[wid]["name"] if wid in FG.ALLOYS else res_name(prof.xd, wid)

    def draw_trade_head(self, surf, r):
        """Хотелки, терпение, запрос (×1.00 … ×1.50) с шансом согласия. Возвращает y под шапкой."""
        from sim import forge as FG
        prof = self.app.profile
        w = prof.market.get(self.who) or {}
        y = r.y + 60
        wants = ", ".join(f"{self.want_name(x['id'])} ×{x['k']:.2f}" for x in w.get("wants", []))
        T.text(surf, "Сейчас берёт дороже: " + (wants or "ничего особенного"), (r.x + 20, y), 16, GLORY, True)
        pat = w.get("patience", 1.0)
        T.text(surf, "Терпение:", (r.x + 20, y + 32), 14, T.TEXT_DIM)
        bar = pygame.Rect(r.x + 100, y + 36, 180, 10)
        pygame.draw.rect(surf, (40, 30, 24), bar, border_radius=5)
        pygame.draw.rect(surf, BLESS if pat > 0.5 else GOLD if pat > 0.2 else CURSE,
                         (bar.x, bar.y, int(bar.w * pat), bar.h), border_radius=5)
        if w.get("angry"):
            T.text(surf, "обиделся — до следующего визита не покупает", (bar.right + 14, y + 30), 14, CURSE, True)
        x = r.x + 330
        T.text(surf, "Запрос:", (x, y + 32), 14, T.TEXT_DIM)
        opts = []
        for i, k in enumerate(FG.TRADE["asks"]):
            ch = FG.haggle_chance(k, pat)
            opts.append((i, f"×{k:.2f}" + ("" if i == 0 else f" · {ch * 100:.0f}%")))
        self.scene.seg(surf, x + 64, y + 24, opts, self.ask_i, "ask", h=30)
        T.text(surf, "выше запрос — дороже, но торговец может отказать; отказ убавляет терпение",
               (r.x + 20, y + 62), 12, T.TEXT_DIM)
        return y + 90

    def sell_button(self, kind, key):
        from sim import forge as FG
        prof = self.app.profile
        w = prof.market.get(self.who) or {}
        p_ = prof.trade_price(self.who, kind, key, FG.TRADE["asks"][self.ask_i])
        return f"Продать · {p_}", ("tsell", kind, key), not w.get("angry")


class WandererOverlay(TradeMixin, Overlay):
    """Бродячий кузнец на рынке: слитки сплавов, книги и приборы; покупает металлы (торг)."""
    who = "smith"

    @property
    def title(self):
        return (self.app.profile.market.get("smith") or {}).get("name", "Бродячий кузнец")

    def act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if self.trade_act(kind, action):
            return
        if kind == "buy_ingot":
            self.scene.say("Куплено — слиток в кузне" if prof.buy_ingot(action[1]) else "Не хватает золота")
        elif kind == "buy_piece":
            self.scene.say("Куплено — в кузне" if prof.buy_piece(action[1]) else "Не хватает золота")
        elif kind == "buy_tool":
            self.scene.say("Куплено" if prof.buy_tool(action[1]) else "Не хватает золота")
        elif kind == "buy_forge":
            self.scene.say("Куплено — в кузне" if prof.buy_smith(action[1]) else "Не хватает золота")

    def draw_sell(self, surf, r):
        """Продать кузнецу: слитки, примитивы, руды пачкой — карточки с ценой по запросу."""
        from sim import forge as FG
        prof = self.app.profile
        xd = prof.xd
        y = self.draw_trade_head(surf, r)
        goods = prof.trade_goods("smith")
        area = pygame.Rect(r.x + 20, y, r.w - 40, r.bottom - 14 - y)
        with self.scene.grid(surf, "smith_sell", area, len(goods), 220, 132, gap=10) as cells:
            for i, cr in cells:
                kind, key, it, want = goods[i]
                if kind == "mat":
                    name, sub, col = res_name(xd, key), f"пачка {FG.MAT_LOT} ед. · есть {it['n']}", (200, 190, 170)
                    ic = res_icon(xd, key, 40)
                else:
                    a = FG.ALLOYS[it["alloy"]]
                    col = a["color"]
                    if kind == "ingot":
                        name, ic = f"Слиток · {a['name']}", forge_icon(f"ingot_{it['alloy']}", 40)
                    else:
                        name = f"{FG.PRIMS[it['kind']]['name']} · {a['name']}"
                        ic = forge_icon(f"prim_{it['kind']}", 40, tuple(col))
                    sub = f"{it['mass']} г · качество {it.get('q', 0.8) * 100:.0f}%"
                hot = cr.collidepoint(self.scene.mouse)
                pygame.draw.rect(surf, (44, 32, 24) if hot else (28, 21, 16), cr, border_radius=10)
                pygame.draw.rect(surf, GOLD if want > 1 else col, cr, 2 if want > 1 else 1, border_radius=10)
                if ic is not None:
                    surf.blit(ic, (cr.x + 30 - ic.get_width() // 2, cr.y + 32 - ic.get_height() // 2))
                T.text(surf, fit(name, 14, cr.w - 70), (cr.x + 60, cr.y + 12), 14, T.TEXT, True)
                T.text(surf, fit(sub, 12, cr.w - 70), (cr.x + 60, cr.y + 34), 12, T.TEXT_DIM)
                if want > 1:
                    T.text(surf, f"хочет — ×{want:.2f}", (cr.x + 60, cr.y + 54), 12, GOLD, True)
                label, act, ok = self.sell_button(kind, key)
                self.scene.btn(surf, pygame.Rect(cr.x + 12, cr.bottom - 44, cr.w - 24, 34), label, act, ok,
                               primary=True)
        if not goods:
            T.text(surf, "Продавать нечего: слитки, примитивы или руда (от 10 ед.).", (area.x, area.y + 8), 15,
                   T.TEXT_DIM)

    def draw(self, surf):
        prof = self.app.profile
        r = self.frame(surf)
        self.trade_tabs(surf, r)
        if self.tmode == "sell":
            return self.draw_sell(surf, r)
        w = prof.market.get("smith") or {}
        from sim import forge as FG
        T.text(surf, "Слитки сплавов", (r.x + 20, r.y + 60), 18, GLORY, True)
        x = r.x + 20
        known = FG.known_alloys(prof.f_tools())
        for ing in w.get("ingots", []):
            a = FG.ALLOYS[ing["alloy"]]
            cr = pygame.Rect(x, r.y + 90, 190, 200)
            pygame.draw.rect(surf, (30, 22, 16), cr, border_radius=10)
            pygame.draw.rect(surf, a["color"], cr, 1, border_radius=10)
            ic = forge_icon(f"ingot_{ing['alloy']}", 64)
            if ic is not None:
                surf.blit(ic, (cr.centerx - ic.get_width() // 2, cr.y + 14))
            T.text(surf, fit(a["name"], 15, cr.w - 16), (cr.centerx, cr.y + 90), 15, a["color"], True, center=True)
            T.text(surf, f"{ing['mass']} г · качество {ing['q'] * 100:.0f}%", (cr.centerx, cr.y + 112), 12,
                   T.TEXT_DIM, center=True)
            if ing["alloy"] not in known:
                T.text(surf, "редкость: сами пока не плавите", (cr.centerx, cr.y + 130), 11, GOLD, center=True)
            self.scene.btn(surf, pygame.Rect(cr.x + 12, cr.bottom - 42, cr.w - 24, 32), f"Купить · {ing['price']}",
                           ("buy_ingot", ing["uid"]), prof.glory >= ing["price"], primary=True)
            x += 200
        if not w.get("ingots"):
            T.text(surf, "Слитки разобраны.", (r.x + 20, r.y + 96), 14, T.TEXT_DIM)
        npc = JV.spr("npc_smith", None, 200)                         # лист NS: бродячий кузнец
        if npc is not None:
            surf.blit(npc, (r.right - npc.get_width() - 40, r.y + 300 - npc.get_height()))
        offer = w.get("forge", [])
        x0 = r.x + 20
        T.text(surf, "Книги, приборы, жидкости, формы", (x0, r.y + 320), 18, GLORY, True)
        y = r.y + 350
        for tid in offer:
            name, price, desc = (FG.TOOLS.get(tid) or FG.BOOKS.get(tid))[:2] + ((FG.TOOLS.get(tid) or FG.BOOKS.get(tid))[-1],)
            tr = pygame.Rect(x0, y, r.right - 20 - x0, 56)
            pygame.draw.rect(surf, (30, 22, 16), tr, border_radius=8)
            pygame.draw.rect(surf, (120, 90, 50), tr, 1, border_radius=8)
            ic = forge_icon("book" if tid in FG.BOOKS else f"tool_{tid}", 44)   # лист KI; нет — без значка
            tx = tr.x + 14
            if ic is not None:
                surf.blit(ic, (tr.x + 30 - ic.get_width() // 2, tr.centery - ic.get_height() // 2))
                tx = tr.x + 58
            T.text(surf, fit(name, 15, tr.right - 200 - tx), (tx, tr.y + 8), 15, T.TEXT, True)
            T.text(surf, fit(desc, 12, tr.right - 200 - tx), (tx, tr.y + 32), 12, T.TEXT_DIM)
            self.scene.btn(surf, pygame.Rect(tr.right - 186, tr.y + 10, 172, 36), f"Купить · {price}",
                           ("buy_forge", tid), prof.glory >= price, primary=True)
            y += 64
        if not offer:
            T.text(surf, "Сегодня без книг и приборов.", (x0, y + 4), 14, T.TEXT_DIM)


class JewelerOverlay(TradeMixin, Overlay):
    """Бродячий ювелир: книги огранок (новая огранка навсегда) и отборные необработанные камни; покупает
    ваши камни — сырые и огранённые (торг)."""
    who = "jeweler"

    @property
    def title(self):
        return (self.app.profile.market.get("jeweler") or {}).get("name", "Бродячий ювелир")

    def act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if self.trade_act(kind, action):
            return
        if kind == "own_view":
            g = next((x for x in prof.rough + prof.gems if x["uid"] == action[1]), None)
            if g:
                self.scene.overlay = GemViewer(self.scene, g, back=self)
        elif kind == "book":
            self.scene.say("Новая огранка выучена" if prof.buy_book(action[1]) else "Не хватает золота")
        elif kind == "jrough":
            self.scene.say("Куплено — камень в сундуке" if prof.buy_jeweler_rough(action[1]) else "Не хватает золота")
        elif kind == "loupe":
            self.scene.say("Куплено — на станке огранки" if prof.buy_loupe(action[1]) else "Не хватает золота")
        elif kind == "gem_view":
            j = prof.market.get("jeweler") or {}
            g = next((x for x in j.get("rough", []) if x["uid"] == action[1]), None)
            if g:
                self.scene.overlay = GemViewer(self.scene, g, back=self)

    def draw_sell(self, surf, r):
        prof = self.app.profile
        y = self.draw_trade_head(surf, r)
        goods = [(k, it) for k, key, it, want in prof.trade_goods("jeweler")]
        draw_stone_grid(self.scene, surf, pygame.Rect(r.x + 20, y, r.w - 40, r.bottom - 14 - y), "jeweler_sell",
                        goods, lambda kind, g: ("own_view", g["uid"]), "Камней нет — продавать нечего.",
                        button=lambda kind, g: self.sell_button(kind, g["uid"]))      # цена — на кнопке

    def draw(self, surf):
        prof = self.app.profile
        r = self.frame(surf)
        self.trade_tabs(surf, r)
        if self.tmode == "sell":
            return self.draw_sell(surf, r)
        j = prof.market.get("jeweler") or {}
        npc = JV.spr("npc_jeweler", None, 150)                       # лист JT: бродячий ювелир
        if npc is not None:
            surf.blit(npc, (r.right - npc.get_width() - 24, r.bottom - npc.get_height() - 16))
        T.text(surf, "Книги огранок", (r.x + 20, r.y + 60), 18, GLORY, True)
        T.text(surf, f"известно огранок: {len(prof.cuts)} из {len(GM.CUTS)}", (r.x + 200, r.y + 64), 13, T.TEXT_DIM)
        y = r.y + 92
        for cid in j.get("books", []):
            c = GM.CUT_BY_ID[cid]
            br = pygame.Rect(r.x + 20, y, r.w // 2 - 30, 92)
            pygame.draw.rect(surf, (34, 25, 18), br, border_radius=8)
            pygame.draw.rect(surf, (150, 110, 60), br, 1, border_radius=8)
            from game import workshop_games as WG
            JV.stone(surf, JV.ideal(WG.CUTS.index(c)), JV.turntable(self.scene.clock), (br.x + 48, br.centery), 0.34,
                     (150, 200, 255), self.scene.clock)
            low, top = WG.cut_counts(c)
            bk = JV.spr("book_cut", 28, 28)
            if bk is not None:
                surf.blit(bk, (br.x + 70, br.y + 6))
            T.text(surf, f"«{c['name']}»", (br.x + 100, br.y + 10), 17, GOLD if c.get("rare") else T.TEXT, True)
            if c.get("rare"):                                       # авторская огранка — редкий свиток
                pygame.draw.rect(surf, GOLD, br, 2, border_radius=8)
                T.text(surf, "авторский свиток", (br.x + 110 + T.font(17, True).size(f"«{c['name']}»")[0],
                                                  br.y + 13), 12, GOLD, True)
            T.text(surf, fit(c.get("desc", ""), 12, br.w - 300), (br.x + 100, br.y + 36), 12, T.TEXT_DIM)
            T.text(surf, f"граней {low + top} · предел {c['cap'] * 100:.0f}% · ценность ×{c['value']:.2f}",
                   (br.x + 100, br.y + 58), 12, BLESS)
            self.scene.btn(surf, pygame.Rect(br.right - 190, br.y + 26, 176, 40), f"Купить · {c['book']}",
                           ("book", cid), prof.glory >= c["book"], primary=True)
            y += 100
        if not j.get("books"):
            T.text(surf, "Книг больше нет.", (r.x + 20, y + 4), 14, T.TEXT_DIM)
            y += 30
        y += 16
        T.text(surf, "Лупа и диски для станка", (r.x + 20, y), 18, GLORY, True)
        own = prof.lenses()
        T.text(surf, "у вас: " + (" + ".join(f"×{GM.LOUPE_BY_ID[t][2]}" for t in own) if own else "нет"),
               (r.x + 200, y + 4), 13, T.TEXT_DIM)
        y += 30
        for tid in j.get("tools", []):
            name, price, desc = GM.tool_info(tid)
            br = pygame.Rect(r.x + 20, y, r.w // 2 - 30, 64)
            pygame.draw.rect(surf, (34, 25, 18), br, border_radius=8)
            pygame.draw.rect(surf, (150, 110, 60), br, 1, border_radius=8)
            ic = JV.disc_icon(tid, 44)
            tx = br.x + 14 + (52 if ic is not None else 0)
            if ic is not None:
                surf.blit(ic, (br.x + 10, br.y + 10))
            T.text(surf, name, (tx, br.y + 10), 16, T.TEXT, True)
            T.text(surf, desc, (tx, br.y + 36), 12, T.TEXT_DIM)
            self.scene.btn(surf, pygame.Rect(br.right - 190, br.y + 12, 176, 40), f"Купить · {price}",
                           ("loupe", tid), prof.glory >= price, primary=True)
            y += 72
        if not j.get("tools"):
            T.text(surf, "Сегодня без стёкол.", (r.x + 20, y), 14, T.TEXT_DIM)
        x0 = r.x + r.w // 2 + 10
        T.text(surf, "Отборные камни", (x0, r.y + 60), 18, GLORY, True)
        stock = [("rough", x) for x in j.get("rough", [])]
        draw_stone_grid(self.scene, surf, pygame.Rect(x0, r.y + 92, r.right - x0 - 20, r.bottom - r.y - 110),
                        "jeweler_stock", stock, lambda kind, g: ("gem_view", g["uid"]), "Камни разобраны.",
                        price=prof.market_price,
                        button=lambda kind, g: ("Купить", ("jrough", g["uid"]), prof.glory >= prof.market_price(kind, g)))


class MarketRoom(RoomScene):
    """Рынок: торговцы самоцветами (товар — после каждого похода). Слева — что продают, справа — ваши камни
    (продать за половину цены). Клик по камню — рассмотреть."""
    room = "market"
    title = "Рынок"
    sub = "Самоцветы — редкость: товар обновляется после каждого похода"
    art = "room_market"
    dim = 150

    def room_act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "buy":
            if prof.buy(action[1], action[2]):
                self.say("Куплено — камень в сундуке")
            else:
                self.say("Не хватает золота")
        elif kind == "sell":
            item = next((x for x in (prof.rough if action[1] == "rough" else prof.gems) if x["uid"] == action[2]), None)
            if item and prof.sell(action[1], action[2]):
                self.say(f"Продано за {prof.sell_price(action[1], item)}")
        elif kind == "wanderer":
            self.overlay = WandererOverlay(self)
        elif kind == "jeweler":
            self.overlay = JewelerOverlay(self)
        elif kind == "gem_view":
            g = next((x for x in prof.gems + prof.rough + prof.market.get("rough", []) + prof.market.get("cut", [])
                      if x["uid"] == action[1]), None)
            if g:
                self.overlay = GemViewer(self, g)

    def draw_room(self, surf):
        prof = self.app.profile
        half = (T.SCREEN_W - 48) // 2
        left = pygame.Rect(16, TOP_H + 10, half, strip_y() - TOP_H - 20)
        right = pygame.Rect(32 + half, TOP_H + 10, half, strip_y() - TOP_H - 20)
        for r, title in ((left, "Лавка самоцветов"), (right, "Ваши камни — продать за половину цены")):
            T.frame(surf, r, 236)
            T.text(surf, title, (r.x + 16, r.y + 12), 20, GLORY, True)
        stock = [("rough", x) for x in prof.market.get("rough", [])] + [("cut", x) for x in prof.market.get("cut", [])]
        draw_stone_grid(self, surf, pygame.Rect(left.x + 16, left.y + 50, left.w - 32, left.h - 64), "market_stock",
                        stock, lambda kind, g: ("gem_view", g["uid"]), "Прилавок пуст — загляните после похода.",
                        price=prof.market_price,
                        button=lambda kind, g: ("Купить", ("buy", kind, g["uid"]),
                                                prof.glory >= prof.market_price(kind, g)))
        w = prof.market.get("smith")
        if w:                                          # бродячий кузнец — иногда заходит
            self.btn(surf, pygame.Rect(left.right - 300, left.y + 8, 284, 36), "Бродячий кузнец: " + w["name"].split()[-1],
                     "wanderer", True, primary=True, tip=[w["name"], "редкие металлы, инструменты и уроки"])
        j = prof.market.get("jeweler")
        if j:                                          # бродячий ювелир — книги огранок
            self.btn(surf, pygame.Rect(left.right - 300 - (296 if w else 0), left.y + 8, 284, 36),
                     "Бродячий ювелир: " + j["name"].split()[-1], "jeweler", True, primary=True,
                     tip=[j["name"], "книги огранок и отборные камни"])
        own = [("rough", x) for x in prof.rough] + [("cut", x) for x in prof.gems]
        draw_stone_grid(self, surf, pygame.Rect(right.x + 16, right.y + 50, right.w - 32, right.h - 64), "market_own",
                        own, lambda kind, g: ("gem_view", g["uid"]), "Своих камней нет.",
                        price=prof.sell_price,
                        button=lambda kind, g: ("Продать", ("sell", kind, g["uid"]), True))


# ---------- Мастерская ----------

STATIONS = (("ws_forge", 0.13), ("ws_jewel", 0.35), ("ws_leather", 0.65), ("ws_alchemy", 0.87))


class WorkshopRoom(RoomScene):
    """Мастерская: станции мастеров стоят в комнате (клик — работа с мини-игрой), сундук — хранилище."""
    room = "workshop"
    title = "Мастерская"
    art = "room_workshop"
    dim = 95
    mats = True

    def __init__(self, app, ws=None):
        super().__init__(app)
        if ws:
            self.overlay = (ForgeOverlay if ws == "ws_forge" else StationOverlay)(self, ws)

    def room_act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "station":                          # мастерская — отдельный экран со своими вкладками
            self.app.switch(StationScene(self.app, action[1]))
        elif kind == "chest":
            self.overlay = ChestOverlay(self)

    def room_key(self, k):
        if k == pygame.K_c:
            self.overlay = ChestOverlay(self)

    def draw_room(self, surf):
        prof = self.app.profile
        xd = prof.xd
        ground = strip_y() - 116
        for ws, fx in STATIONS:
            lv = prof.building_level(ws)
            b = xd["buildings"][ws]
            img = obj_img(f"obj_{ws}", 230)
            if not lv:
                img = img.copy()
                img.fill((110, 100, 96, 255), special_flags=pygame.BLEND_RGBA_MULT)
            x = int(fx * T.SCREEN_W - img.get_width() / 2)
            pos = (x, ground - img.get_height())
            rect = pygame.Rect(pos, img.get_size())
            hot = rect.collidepoint(self.mouse)
            sh = pygame.Surface((img.get_width(), 18), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 120), sh.get_rect())
            surf.blit(sh, (x, ground - 10))
            if hot:
                glow_outline(surf, img, pos)
            surf.blit(img, pos)
            sub = (f"ур. {lv} · {b['levels'][lv - 1]['text']}" if lv else "не построено — Стройка (5)"
                   if prof.master_free(ws) else f"мастер в плену: «{prof.master_chapter(ws)}»")
            plate(surf, (int(fx * T.SCREEN_W), ground + 8), b["name"], sub, GLORY if lv else T.TEXT_DIM, w=250)
            self.hit(rect.union(pygame.Rect(int(fx * T.SCREEN_W) - 125, ground + 8, 250, 50)), ("station", ws),
                     [(b["name"], GLORY), b["desc"], "клик — к мастеру"])
        img = obj_img("obj_chest", 92)
        cx = T.SCREEN_W // 2
        pos = (cx - img.get_width() // 2, strip_y() - 30 - img.get_height())
        rect = pygame.Rect(pos, img.get_size())
        if rect.collidepoint(self.mouse):
            glow_outline(surf, img, pos)
        surf.blit(img, pos)
        T.text(surf, f"Сундук · {len(prof.stash)}", (cx, strip_y() - 26), 14, T.TEXT, True, center=True, shadow=True)
        self.hit(rect, "chest", ["Сундук", "Хранилище артефактов, самоцветов и материалов (C)"])


class StationOverlay(Overlay):
    """Работа у станции мастера: ковка (сет × вид), огранка и вставка самоцветов, улучшение и зачарование."""

    def __init__(self, scene, ws):
        super().__init__(scene)
        self.ws = ws
        xd = self.app.profile.xd
        kinds = [k for k, v in xd["artifacts"]["kinds"].items() if v["workshop"] == ws]
        self.kind = kinds[0] if kinds else None
        self.set_sel = next(iter(xd["artifacts"]["sets"]))
        self.mode = "craft"
        self.art_sel = None
        self.result = None
        self.scroll = 0

    @property
    def title(self):
        return self.app.profile.xd["buildings"][self.ws]["name"]

    @property
    def rect(self):
        if self.level():
            return Overlay.rect.fget(self)
        return pygame.Rect(T.SCREEN_W // 2 - 380, TOP_H + 120, 760, 300)

    def level(self):
        return self.app.profile.building_level(self.ws)

    def modes(self):
        """Вкладки станции (для клавиш 1–9 и Tab на отдельном экране)."""
        if self.ws == "ws_jewel":
            return [("craft", "Оправа"), ("cut", "Огранка"), ("socket", "Вставка"), ("show", "Витрина")]
        return []

    def play(self, title, done, diff=1, color=None, seed=None):
        """Мини-игра мастерской; diff — сложность (0–3, по редкости вещи); seed — заготовка (свой камень)."""
        app = self.app
        scene = self.scene
        seed = seed if seed is not None else int(scene.clock * 1000) + len(app.profile.stash)
        game = G.GAMES[self.ws if self.mode != "cut" else "ws_jewel"](seed, diff=diff)
        if color is not None:
            game.color = color
        self.last_game = game
        app.switch(WS.MiniGameScene(app, game, title, done, lambda: app.switch(scene)))

    def act(self, action, button=1):
        prof = self.app.profile
        xd = prof.xd
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "mode":
            self.mode = action[1]
            self.result = None
        elif kind == "set":
            self.set_sel = action[1]
        elif kind == "kind":
            self.kind = action[1]
        elif kind == "pick_art":
            self.art_sel = action[1]
        elif kind == "craft_whole":
            self.craft_whole()
        elif kind == "alloy_pick":                  # металл изделия: клик — только этот, ещё клик — любой годный
            self.alloy_sel = None if getattr(self, "alloy_sel", None) == action[1] else action[1]
        elif kind == "build":
            go(self.app, "build")
        elif kind == "craft":
            if not prof.can_craft(self.ws, self.set_sel):
                self.scene.say("Не хватает материалов или золота, или мастерская мала для этой редкости")
                return
            ws, k, sid = self.ws, self.kind, self.set_sel
            if ws == "ws_jewel":                 # кольца и амулеты — оправа из кузни: проволока и лист
                from sim import forge as FG
                prims = prof.pick_prims(k, getattr(self, "alloy_sel", None), sid)
                if prims is None:
                    self.scene.say(self.need_text(k, sid))
                    return
                from game import forge_games as FGM
                game = FGM.ItemGame(k, prims, prof.f_tools(), prof.forge_level(), int(self.scene.clock * 1000))
                uids = [p["uid"] for p in prims]

                def jdone(q):
                    r_ = game.result
                    if not r_:
                        return
                    art = prof.make_item(k, sid, uids, r_["heat"], seed=int(self.scene.clock * 1000))
                    metal = ", ".join(FG.ALLOYS[a_]["name"] for a_ in (art or {}).get("alloys", []))
                    self.result = ([(A.art_name(xd, art), WS.rar_color(xd, art["rarity"])),
                                    (f"Оправа: {metal} — вставьте огранённые камни", GLORY)]
                                   + [(ln, T.TEXT) for ln in A.art_lines(xd, art)], art) if art else None
                app, scene = self.app, self.scene
                self.last_game = game
                app.switch(WS.MiniGameScene(app, game, f"Оправа: {xd['artifacts']['kinds'][k]['name']}", jdone,
                                            lambda: app.switch(scene)))
                return

            def done(q):
                art = prof.craft(ws, k, sid, q, seed=int(self.scene.clock * 1000))
                self.result = ([(A.art_name(xd, art), WS.rar_color(xd, art["rarity"])),
                                (f"{A.quality_word(art['q'])} — качество {art['q'] * 100:.0f}%", GLORY)]
                               + [(ln, T.TEXT) for ln in A.art_lines(xd, art)], art) if art else None
            self.play(f"Ковка: {xd['artifacts']['kinds'][k]['name']} «{xd['artifacts']['sets'][sid]['name']}»", done,
                      A.RARITY_ORDER.index(xd["artifacts"]["sets"][sid]["rarity"]),
                      WS.rar_color(xd, xd["artifacts"]["sets"][sid]["rarity"]))
        elif kind == "cut":
            rough = next((r for r in prof.rough if r["uid"] == action[1]), None)
            if rough is None or not prof.can_pay({"glory": xd["artifacts"]["gem_cost"]["gold"]}):
                self.scene.say("Нужен необработанный камень (рынок, вылазки) и немного золота")
                return
            gid, ruid = rough["id"], rough["uid"]
            gd = xd["artifacts"]["gems"][gid]

            def done(q):
                game = self.last_game
                if game.split is not None:           # раскол по трещине — остался меньший кусок
                    r2 = prof.split_rough(ruid, 0.4, drop=game.split, seed=int(self.scene.clock * 1000))
                    self.result = ([(f"{gd['name']} раскололся по трещине", CURSE),
                                    (f"остался кусок {r2['size']:.2f} кар. — его можно огранить снова", T.TEXT)],
                                   None) if r2 else None
                    return
                if game.phase != "cut":              # огранку не начали — камень остаётся необработанным
                    self.result = None
                    return
                g = prof.cut_gem(ruid, q, shape=game.shape(), cut=game.cut["id"] if game.cut else None,
                                 ct=game.final_ct(), incl=game.final_incl(), star=game.final_star(),
                                 cf=game.cf, cz=game.final_colors(), axis=game.caxis)
                self.result = ([(f"{gd['name']} · {g['size']:.2f} кар.: {A.quality_word(g['q'])} ({g['q'] * 100:.0f}%)",
                                 tuple(gd["color"])),
                                (" · ".join(GM.describe(xd, g)[1:]), T.TEXT),
                                (GM.stat_text(xd, g) + f" · цена ≈ {prof.market_price('cut', g)}", BLESS)], None) \
                    if g else None
            game = G.JewelCut(rough["seed"], diff=1, rough=GM.ensure_rough(xd, rough),
                              known=None if prof.sandbox else prof.cuts, xd=xd, lenses=prof.lenses(),
                              disks=prof.disks(), autofocus="loupe_af" in prof.jtools)
            game.color = GM.tint(tuple(gd["color"]), rough.get("col", 0.5))
            self.last_game = game
            app, scene = self.app, self.scene
            app.switch(WS.MiniGameScene(app, game, f"Огранка: {gd['name']} · {rough['size']:.2f} кар.", done,
                                        lambda: app.switch(scene)))
        elif kind == "sc_slot":                     # витрина: выбрать место
            self.sc_sel = action[1]
        elif kind == "sc_gem":
            sl = prof.showcase_slots()
            i = getattr(self, "sc_sel", None)
            if i is None or sl[i]:                  # место не выбрано — первое свободное
                i = next((k for k, x in enumerate(sl) if x is None), i if i is not None else 0)
            if prof.show_gem(i, action[1]):
                self.sc_sel = i
                self.scene.say("Камень выставлен на витрину")
        elif kind == "sc_take":
            if prof.unshow(action[1]):
                self.scene.say("Камень снят — он в сундуке")
        elif kind == "sc_sale":
            prof.toggle_sale(action[1])
        elif kind == "unsocket":
            g = prof.unsocket(self.art_sel, action[1])
            self.scene.say(f"Камень вынут — {xd['artifacts']['gems'][g['id']]['name']} в сундуке" if g else
                           "Не хватает золота")
        elif kind == "socket":
            if self.art_sel and prof.socket(self.art_sel, action[1]):
                self.scene.say("Самоцвет вставлен")
            else:
                self.scene.say("Сначала выберите артефакт со свободным гнездом")
        elif kind == "upgrade":
            if self.art_sel and prof.upgrade_art(self.art_sel):
                self.scene.say(f"Улучшено: +{prof.stash[self.art_sel]['level']}")
            else:
                self.scene.say("Не хватает материалов, золота или достигнут потолок мастерской")
        elif kind == "enchant":
            art = prof.stash.get(self.art_sel)
            if not art or not prof.can_pay(A.enchant_cost(xd, art)) or prof.art_locked(art["uid"]):
                self.scene.say("Не хватает материалов или золота")
                return
            uid = art["uid"]

            def done(q):
                ex = prof.enchant(uid, q, seed=int(self.scene.clock * 1000))
                a2 = prof.stash[uid]
                self.result = ([(A.art_name(xd, a2), WS.rar_color(xd, a2["rarity"])),
                                (f"Новое свойство · качество {ex['q'] * 100:.0f}%", GLORY)]
                               + [(ln, T.TEXT) for ln in A.art_lines(xd, a2) if ln.startswith("Свойство")], a2) \
                    if ex else None
            self.play("Зачарование", done, A.RARITY_ORDER.index(art["rarity"]))

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.mode == "craft" and self.ws != "ws_alchemy" and self.level():
            self.act("craft")
            return True
        return False

    def wheel(self, dy):
        self.scroll = max(0, self.scroll - dy)

    def draw(self, surf):
        prof = self.app.profile
        xd = prof.xd
        r = self.frame(surf)
        b = xd["buildings"][self.ws]
        lv = self.level()
        if lv:
            T.text(surf, fit(f"ур. {lv} · " + b["desc"], 14, r.right - 400 - self.head_x),
                   (self.head_x, r.y + 20), 14, T.TEXT_DIM)
        if not lv and not prof.master_free(self.ws):
            m = prof.master_of(self.ws)
            T.text(surf, f"Мастера нет: {m['name']} в плену.", (r.centerx, r.y + 110), 24, CURSE, True, center=True)
            T.text(surf, f"Победите босса главы «{prof.master_chapter(self.ws)}» — мастер вернётся с отрядом и откроет "
                         "мастерскую.", (r.centerx, r.y + 148), 16, T.TEXT, center=True)
            return
        if not lv:
            T.text(surf, f"«{b['name']}» ещё не построена.", (r.centerx, r.y + 110), 24, CURSE, True, center=True)
            T.text(surf, "Постройте её в Стройке — уровень мастерской открывает редкость вещей.",
                   (r.centerx, r.y + 148), 16, T.TEXT, center=True)
            self.scene.btn(surf, pygame.Rect(r.centerx - 130, r.bottom - 76, 260, 52), "В Стройку (5)", "build", True,
                           primary=True)
            return
        if self.ws == "ws_jewel":
            self.scene.seg(surf, r.right - 500, r.y + 12, [(m, f"{i + 1} {lab}") for i, (m, lab) in
                                                            enumerate(self.modes())], self.mode, "mode", h=34)
        if self.ws == "ws_alchemy":
            self.draw_alchemy(surf, r)
        elif self.mode == "cut":
            self.draw_cut(surf, r)
        elif self.mode == "socket":
            self.draw_socket(surf, r)
        elif self.mode == "show":
            self.draw_showcase(surf, r)
        else:
            self.draw_craft(surf, r)
        if self.result:
            self.draw_result(surf, r)

    def draw_result(self, surf, r):
        lines, art = self.result
        h = 22 * len(lines) + 24
        box = pygame.Rect(r.right - 470, r.bottom - h - 16, 454, h)
        T.frame(surf, box, 248, accent=GOLD, corner=GOLD)
        x = box.x + 12
        if art:
            WS.draw_art_icon(surf, pygame.Rect(box.x + 10, box.y + 10, 64, 64), self.app.profile.xd, art)
            x += 74
        y = box.y + 12
        for text, col in lines:
            T.text(surf, fit(text, 14, box.right - x - 10), (x, y), 14, col, True)
            y += 22

    def draw_craft(self, surf, r):
        prof = self.app.profile
        xd = prof.xd
        a = xd["artifacts"]
        lv = building_value(prof, self.ws)
        kinds = [k for k, v in a["kinds"].items() if v["workshop"] == self.ws]
        y = r.y + 58
        for sid, s in a["sets"].items():
            rk = a["rarities"][s["rarity"]]["rank"]
            ok = lv >= rk
            sr = pygame.Rect(r.x + 16, y, 470, 64)
            on = sid == self.set_sel
            col = WS.rar_color(xd, s["rarity"])
            hot = sr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (64, 46, 30) if on else (44, 32, 22) if hot else (30, 22, 16), sr, border_radius=8)
            pygame.draw.rect(surf, col if on else (80, 60, 40), sr, 2 if on else 1, border_radius=8)
            T.text(surf, s["name"], (sr.x + 12, sr.y + 8), 18, col if ok else T.TEXT_DIM, True)
            mat = s["mat"]
            sub = a["rarities"][s["rarity"]]["name"] + ("" if ok else f" · нужен ур. {rk}")
            T.text(surf, sub, (sr.x + 12, sr.y + 36), 13, T.TEXT_DIM if ok else CURSE)
            if mat:
                sx = sr.x + 12 + T.font(13).size(sub)[0] + 12
                surf.blit(res_icon(xd, mat, 20), (sx, sr.y + 34))
                T.text(surf, xd["materials"][mat]["name"], (sx + 24, sr.y + 36), 13, T.TEXT_DIM)
            for i, k in enumerate(kinds):
                WS.draw_art_icon(surf, pygame.Rect(sr.right - 56 - i * 54, sr.y + 6, 52, 52), xd,
                                 {"kind": k, "rarity": s["rarity"], "level": 0}, dim=not ok)
            self.scene.hit(sr, ("set", sid), [(s["name"], col)] + [(f"{n} вещи: {b['text']}", BLESS)
                                                                   for n, b in sorted(s["bonus"].items())])
            y += 70
        s = a["sets"][self.set_sel]
        x0 = r.x + 510
        col = WS.rar_color(xd, s["rarity"])
        T.text(surf, f"«{s['name']}»", (x0, r.y + 58), 26, col, True)
        y = r.y + 96
        for n, b in sorted(s["bonus"].items()):
            T.text(surf, fit(f"{n} вещи: {b['text']}", 15, r.right - x0 - 20), (x0, y), 15, BLESS)
            y += 22
        y += 8
        for i, k in enumerate(kinds):
            kr = pygame.Rect(x0 + i * 350, y, 340, 168)
            on = k == self.kind
            hot = kr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (64, 46, 30) if on else (44, 32, 22) if hot else (30, 22, 16), kr, border_radius=10)
            pygame.draw.rect(surf, GOLD if on else (80, 60, 40), kr, 2 if on else 1, border_radius=10)
            demo = A.make(xd, "demo", k, self.set_sel, 1.0)
            WS.draw_art_icon(surf, pygame.Rect(kr.x + 12, kr.y + 12, 112, 112), xd, demo)
            T.text(surf, a["kinds"][k]["name"], (kr.x + 138, kr.y + 14), 22, T.TEXT, True)
            ly = kr.y + 48
            for ln in A.art_lines(xd, demo):
                T.text(surf, fit(ln, 14, kr.right - kr.x - 150), (kr.x + 138, ly), 14, T.TEXT_DIM)
                ly += 20
            T.text(surf, "при качестве 100%", (kr.x + 14, kr.bottom - 28), 12, T.TEXT_DIM)
            self.scene.hit(kr, ("kind", k), [(a["kinds"][k]["name"], T.TEXT), "клик — выбрать"])
        y += 186
        if self.ws in ("ws_forge", "ws_jewel") and self.kind:          # из чего: примитивы и металл сета
            y = self.draw_need(surf, x0, y - 6, r.right - 16)
        cost = A.craft_cost(xd, self.ws, self.set_sel)
        T.text(surf, "Цена:", (x0, y + 4), 16, T.TEXT_DIM, True)
        cost_icons(self.scene, surf, prof, cost, x0 + 58, y)
        if self.ws in ("ws_forge", "ws_jewel") and self.kind:      # сборка (≤100%) или цельная ковка (≤130%)
            from sim import forge as FG
            mass = FG.item_mass(self.kind)
            ing = prof.whole_ingot(self.kind, self.set_sel, getattr(self, "alloy_sel", None))
            from sim import forge_card as FC
            card = FC.CARDS[FC.card_for(self.kind, prof.f_tools())]
            stages = " → ".join(FC.OPS[st["op"]][0].lower() for st in card["stages"])
            T.text(surf, fit(f"{card['name']}: {stages} · слиток {mass} г · до {card['cap'] * 100:.0f}%" +
                             ("" if card["cap"] > 1 else " (техкарта мастера — книга: до 130%)"), 14, r.right - x0 - 20),
                   (x0, y + 36), 14, T.TEXT_DIM)
            bx = x0
            if self.ws == "ws_jewel":                          # ювелир: оправу можно и собрать из примитивов
                self.scene.btn(surf, pygame.Rect(x0, y + 66, 300, 56), "Собрать  (Enter)", "craft",
                               prof.can_craft(self.ws, self.set_sel), primary=True)
                bx = x0 + 312
            self.scene.btn(surf, pygame.Rect(bx, y + 66, 300, 56),
                           "Ковать по техкарте" + ("  (Enter)" if self.ws == "ws_forge" else ""), "craft_whole",
                           ing is not None and prof.can_craft(self.ws, self.set_sel), primary=True,
                           tip=[(card["name"], GLORY), f"слиток годного сплава от {mass} г — ковка по этапам: {stages}",
                                f"затем закалка; качество до {card['cap'] * 100:.0f}%" +
                                (", от 115% — свойство" if card["cap"] > 1 else ""),
                                (f"слиток: {FG.ALLOYS[ing['alloy']]['name']}, {ing['mass']} г" if ing else
                                 "нет подходящего слитка — тигель", BLESS if ing else CURSE)])
        else:
            T.text(surf, "Качество — по мини-игре (70–130%); от 115% — дополнительное свойство.", (x0, y + 36), 14,
                   T.TEXT_DIM)
            self.scene.btn(surf, pygame.Rect(x0, y + 66, 300, 56), "Ковать  (Enter)", "craft",
                           prof.can_craft(self.ws, self.set_sel), primary=True)

    def run_game(self, game, title, done):
        """Мини-игра; done может поставить следующую (self.next_game = (игра, заголовок, done)) — цепочка."""
        app, scene = self.app, self.scene
        self.last_game = game
        self.next_game = None

        def back():
            nxt, self.next_game = self.next_game, None
            if nxt:
                self.run_game(*nxt)
            else:
                app.switch(scene)
        app.switch(WS.MiniGameScene(app, game, title, done, back))

    def craft_whole(self):
        """Вещь по техкарте: ковка из слитка по этапам → закалка → вещь (потолок — у техкарты: 100% или 130%)."""
        from game import forge_games as FGM
        from sim import forge as FG
        prof = self.app.profile
        xd = prof.xd
        k, sid = self.kind, self.set_sel
        ing = prof.whole_ingot(k, sid, getattr(self, "alloy_sel", None))
        if ing is None:
            metals = " / ".join(FG.ALLOYS[m]["name"] for m in prof.set_alloys(k, sid))
            self.scene.say(f"Нужен слиток от {FG.item_mass(k)} г: {metals} — тигель")
            return
        if not prof.can_craft(self.ws, sid):
            self.scene.say("Не хватает золота или редкого материала сета")
            return
        seed = int(self.scene.clock * 1000) + prof.art_n
        mass, iu, aid = FG.item_mass(k), ing["uid"], ing["alloy"]
        name = xd["artifacts"]["kinds"][k]["name"]
        from game.forge_card_game import CardGame
        from sim import forge_card as FC
        game = CardGame(aid, k, prof.f_tools(), prof.forge_level(), seed, mass=mass)

        def forged(q):
            r = game.result
            if not r:
                return
            temper = FGM.TemperGame(k, [{"alloy": aid, "mass": mass, "q": 0.9}], prof.f_tools(),
                                    prof.forge_level(), seed)

            def tempered(q2):
                rr = temper.result
                if not rr:
                    return
                card = FC.CARDS[r["card"]]
                art = prof.make_item_whole(k, sid, iu, r["score"], rr["heat"], rr["quench_hard"], rr["temper_acc"],
                                           seed, cap=card["cap"], card=r["card"])
                self.result = ([(A.art_name(xd, art), WS.rar_color(xd, art["rarity"])),
                                (f"{card['name']}: {A.quality_word(art['q'])} — {art['q'] * 100:.0f}%" +
                                 (" · трещина при закалке" if rr["crack"] else ""), GLORY)]
                               + [(ln, T.TEXT) for ln in A.art_lines(xd, art)], art) if art else None
            self.next_game = (temper, f"Закалка: {name}", tempered)
        self.run_game(game, f"Ковка по техкарте: {name}", forged)

    def need_text(self, kind, sid):
        from sim import forge as FG
        prof = self.app.profile
        need = " + ".join(f"{FG.PRIMS[p]['name'].lower()} ×{n}" for p, n in FG.RECIPES[kind].items())
        al = getattr(self, "alloy_sel", None)
        metals = [al] if al else prof.set_alloys(kind, sid)
        return f"Нужно: {need} — металл: " + " / ".join(FG.ALLOYS[m]["name"] for m in metals)

    def draw_need(self, surf, x0, y, right):
        """Что нужно для изделия: примитивы по рецепту (сколько есть) и металлы сета с их эффектами."""
        from sim import forge as FG
        prof = self.app.profile
        xd = prof.xd
        allowed = prof.set_alloys(self.kind, self.set_sel)
        sel = getattr(self, "alloy_sel", None)
        if sel not in allowed:
            self.alloy_sel = sel = None
        use = [sel] if sel else allowed
        tr = T.text(surf, f"Нужно для «{xd['artifacts']['kinds'][self.kind]['name']}»:", (x0, y + 4), 16, T.TEXT,
                    True)
        x = tr.right + 12
        if self.ws == "ws_forge":                              # кузня: вещь — из слитка по техкарте
            need = FG.item_mass(self.kind)
            ing = prof.whole_ingot(self.kind, self.set_sel, sel)
            lab = f"слиток от {need} г · " + (f"есть: {FG.ALLOYS[ing['alloy']]['name']} {ing['mass']} г" if ing
                                              else "нет — тигель")
            cr = pygame.Rect(x, y, T.font(14, True).size(lab)[0] + 24, 30)
            pygame.draw.rect(surf, (34, 26, 19), cr, border_radius=8)
            pygame.draw.rect(surf, BLESS if ing else CURSE, cr, 1, border_radius=8)
            T.text(surf, lab, (cr.x + 12, cr.y + 6), 14, BLESS if ing else CURSE, True)
        for pk, n in (FG.RECIPES[self.kind].items() if self.ws != "ws_forge" else ()):
            have = sum(1 for p in prof.forge["prims"] if p["kind"] == pk and p["alloy"] in use)
            lab = f"{FG.PRIMS[pk]['name']} ×{n} · есть {have}"
            ic = forge_icon(f"prim_{pk}", 22)
            pad = 36 if ic is not None else 12
            w = T.font(14, True).size(lab)[0] + pad + 12
            cr = pygame.Rect(x, y, w, 30)
            pygame.draw.rect(surf, (34, 26, 19), cr, border_radius=8)
            pygame.draw.rect(surf, BLESS if have >= n else CURSE, cr, 1, border_radius=8)
            if ic is not None:
                surf.blit(ic, (cr.x + 8, cr.centery - ic.get_height() // 2))
            T.text(surf, lab, (cr.x + pad, cr.y + 6), 14, BLESS if have >= n else CURSE, True)
            x += w + 8
        y += 40
        T.text(surf, f"Металл сета «{xd['artifacts']['sets'][self.set_sel]['name']}» — у каждого свой эффект "
                     "(клик — только этот металл):", (x0, y), 13, T.TEXT_DIM)
        y += 22
        n_ = max(1, len(allowed))
        cw = min(250, (right - x0 - 8 * (n_ - 1)) // n_)
        for i, aid in enumerate(allowed):
            a = FG.ALLOYS[aid]
            cr = pygame.Rect(x0 + i * (cw + 8), y, cw, 60)
            on = aid == sel
            hot = cr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (64, 46, 30) if on else (44, 32, 22) if hot else (30, 22, 16), cr, border_radius=8)
            pygame.draw.rect(surf, GOLD if on else a["color"], cr, 2 if on else 1, border_radius=8)
            ic = forge_icon(f"ingot_{aid}", 34)
            if ic is not None:
                surf.blit(ic, (cr.x + 8, cr.centery - ic.get_height() // 2))
            else:
                pygame.draw.polygon(surf, a["color"], [(cr.x + 8, cr.y + 40), (cr.x + 14, cr.y + 22),
                                                       (cr.x + 38, cr.y + 22), (cr.x + 44, cr.y + 40)])
            eff = A.metal_affix_text(xd, {"alloy": aid, "id": FG.ALLOY_AFFIX[aid][0], "k": FG.ALLOY_AFFIX[aid][1]},
                                     False)
            cnt = sum(1 for p in prof.forge["prims"] if p["alloy"] == aid)
            T.text(surf, fit(a["name"], 14, cw - 58), (cr.x + 52, cr.y + 6), 14, T.TEXT, True)
            T.text(surf, fit(eff, 12, cw - 58), (cr.x + 52, cr.y + 25), 12, BLESS)
            T.text(surf, f"заготовок: {cnt}", (cr.x + 52, cr.y + 42), 11, T.TEXT_DIM)
            self.scene.hit(cr, ("alloy_pick", aid),
                           [(a["name"], a["color"]), (eff + " (при качестве 100%)", BLESS),
                            f"твёрдость {a['hard'] * 100:.0f}% · вязкость {a['tough'] * 100:.0f}%",
                            "клик — ковать только из него; ещё клик — из любого годного"])
        return y + 70

    def art_list(self, surf, x, y, w, bottom, pred):
        prof = self.app.profile
        xd = prof.xd
        arts = [a for a in sorted(prof.stash.values(), key=lambda a: (-A.RARITY_ORDER.index(a["rarity"]), a["set"]))
                if pred(a)]
        with self.scene.grid(surf, "station_arts", pygame.Rect(x, y, w, bottom - y), len(arts), w, 64, gap=6) as cells:
            for i, tr in cells:
                self.art_row(surf, arts[i], tr)
        if not arts:
            T.text(surf, "Нет подходящих артефактов.", (x, y + 6), 15, T.TEXT_DIM)

    def art_row(self, surf, art, tr):
        prof = self.app.profile
        xd = prof.xd
        w = tr.w
        if True:
            on = art["uid"] == self.art_sel
            locked = prof.art_locked(art["uid"])
            hot = tr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (64, 46, 30) if on else (44, 32, 22) if hot else (30, 22, 16), tr, border_radius=8)
            pygame.draw.rect(surf, GOLD if on else (80, 60, 40), tr, 2 if on else 1, border_radius=8)
            WS.draw_art_icon(surf, pygame.Rect(tr.x + 6, tr.y + 6, 52, 52), xd, art, dim=locked)
            T.text(surf, fit(A.art_name(xd, art), 16, w - 76), (tr.x + 68, tr.y + 10), 16,
                   WS.rar_color(xd, art["rarity"]), True)
            free = A.sockets(xd, art) - len(art["gems"])
            T.text(surf, f"{art['q'] * 100:.0f}%" + (f" · гнёзд {free}" if free else "")
                   + (" · в походе" if locked else ""), (tr.x + 68, tr.y + 36), 13, T.TEXT_DIM)
            self.scene.hit(tr, ("pick_art", art["uid"]) if not locked else None, WS.art_tip(prof, art))

    def draw_alchemy(self, surf, r):
        prof = self.app.profile
        xd = prof.xd
        T.text(surf, "Артефакты сундука", (r.x + 18, r.y + 58), 17, GLORY, True)
        self.art_list(surf, r.x + 16, r.y + 86, 470, r.bottom - 10, lambda a: True)
        art = prof.stash.get(self.art_sel)
        x0 = r.x + 510
        if not art:
            T.text(surf, "Выберите артефакт слева.", (x0, r.y + 64), 17, T.TEXT_DIM)
            return
        WS.draw_art_icon(surf, pygame.Rect(x0, r.y + 58, 120, 120), xd, art)
        T.text(surf, A.art_name(xd, art), (x0 + 136, r.y + 64), 24, WS.rar_color(xd, art["rarity"]), True)
        T.text(surf, f"{A.quality_word(art['q'])} · {art['q'] * 100:.0f}%", (x0 + 136, r.y + 98), 15, T.TEXT_DIM)
        y = r.y + 124
        for ln in A.art_lines(xd, art):
            T.text(surf, ln, (x0 + 136, y), 14, T.TEXT)
            y += 19
        y = max(y, r.y + 196) + 10
        cap = min(prof.upgrade_cap(), xd["artifacts"]["max_level"])
        T.text(surf, f"Улучшение: +{art['level']} из +{cap}", (x0, y), 18, GLORY, True)
        T.text(surf, "потолок — уровень Алхимии", (x0 + 230, y + 4), 13, T.TEXT_DIM)
        y += 30
        if art["level"] < cap:
            cost = A.upgrade_cost(xd, art)
            cost_icons(self.scene, surf, prof, cost, x0, y)
            nxt = dict(art, level=art["level"] + 1)
            T.text(surf, "→ " + "; ".join(A.art_lines(xd, nxt)[:2]), (x0, y + 32), 14, BLESS)
            self.scene.btn(surf, pygame.Rect(x0, y + 58, 280, 48), f"Улучшить до +{art['level'] + 1}", "upgrade",
                           prof.can_pay(cost), primary=True)
        else:
            T.text(surf, "Потолок улучшения", (x0, y), 15, T.TEXT_DIM)
        y += 124
        T.text(surf, "Зачарование — новое свойство, мини-игра задаёт его силу", (x0, y), 18, GLORY, True)
        cost = A.enchant_cost(xd, art)
        cost_icons(self.scene, surf, prof, cost, x0, y + 30)
        self.scene.btn(surf, pygame.Rect(x0, y + 62, 280, 48), "Перезачаровать" if art.get("extra") else "Зачаровать",
                       "enchant", prof.can_pay(cost), tip="Старое свойство заменится" if art.get("extra") else None)

    def draw_cut(self, surf, r):
        """Огранка: свои необработанные камни — каждый свой (форма заготовки задана), клик — на станок."""
        prof = self.app.profile
        xd = prof.xd
        a = xd["artifacts"]
        cost = {"glory": a["gem_cost"]["gold"]}
        T.text(surf, f"Необработанные камни: {len(prof.rough)} — редкость: рынок и вылазки. Цена работы:",
               (r.x + 18, r.y + 64), 17, GLORY, True)
        cost_icons(self.scene, surf, prof, cost, r.x + 640, r.y + 60)
        known = ", ".join(GM.cut_name(c) for c in prof.cuts) or "—"
        T.text(surf, fit(f"Огранки: {known}. Новые — книги бродячего ювелира на Рынке (7).", 13, r.w - 760),
               (r.x + 740, r.y + 66), 13, T.TEXT_DIM)
        y0 = r.y + 100
        with self.scene.grid(surf, "cut_rough", pygame.Rect(r.x + 18, y0, r.w - 36, r.bottom - 14 - y0),
                             len(prof.rough), 210, 280, gap=12) as cells:
            for i, tr in cells:
                self.rough_card(surf, prof.rough[i], tr, i, cost)
        if not prof.rough:
            T.text(surf, "Необработанных камней нет. Купите на Рынке (7) или найдите в вылазке.", (r.x + 18, y0 + 10),
                   16, T.TEXT_DIM)

    def rough_card(self, surf, rough, tr, i, cost):
        prof = self.app.profile
        xd = prof.xd
        a = xd["artifacts"]
        if True:
            g = a["gems"][rough["id"]]
            col = tuple(g["color"])
            hot = tr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (44, 32, 24) if hot else (30, 22, 16), tr, border_radius=10)
            pygame.draw.rect(surf, col, tr, 2 if hot else 1, border_radius=10)
            JV.draw_rough(surf, rough, col, (tr.centerx, tr.y + 76), 128, self.scene.clock + i, xd=xd)
            T.text(surf, g["name"], (tr.centerx, tr.y + 158), 20, col, True, center=True)
            T.text(surf, f"{rough['size']:.2f} кар. · цена ≈ {prof.market_price('rough', rough)}",
                   (tr.centerx, tr.y + 184), 13, T.TEXT_DIM, center=True)
            T.text(surf, fit(GM.describe(xd, rough, rough=True)[1], 12, tr.w - 12), (tr.centerx, tr.y + 204), 12,
                   T.TEXT_DIM, center=True)
            self.scene.hit(tr, None, [g["name"]] + GM.describe(xd, rough, rough=True))
            self.scene.btn(surf, pygame.Rect(tr.x + 16, tr.bottom - 58, tr.w - 32, 44), "Огранить",
                           ("cut", rough["uid"]), prof.can_pay(cost), primary=True)

    def draw_socket(self, surf, r):
        prof = self.app.profile
        xd = prof.xd
        a = xd["artifacts"]
        T.text(surf, "Артефакт с гнёздами", (r.x + 18, r.y + 58), 17, GLORY, True)
        self.art_list(surf, r.x + 16, r.y + 86, 470, r.bottom - 10,
                      lambda art: A.sockets(xd, art) > 0)
        x0 = r.x + 510
        art = prof.stash.get(self.art_sel)
        top = r.y + 88
        if art and art.get("gems"):                       # вставленные камни: крупно, с характеристиками; вынуть
            T.text(surf, "В гнёздах — вынуть за работу ювелира:", (x0, r.y + 58), 15, T.TEXT, True)
            avail = r.right - 16 - x0
            gap = 12
            cols = 1 if avail < 2 * 340 + gap or len(art["gems"]) == 1 else 2
            cw, ch = min(600, (avail - gap * (cols - 1)) // cols), 178
            for k, g in enumerate(art["gems"]):
                gd = a["gems"][g["id"]]
                cr = pygame.Rect(x0 + (k % cols) * (cw + gap), r.y + 84 + (k // cols) * (ch + gap), cw, ch)
                pygame.draw.rect(surf, (32, 24, 17), cr, border_radius=10)
                pygame.draw.rect(surf, tuple(gd["color"]), cr, 1, border_radius=10)
                JV.draw_gem(surf, dict(g, uid=f"{art['uid']}:{k}"), tuple(gd["color"]), (cr.x + 82, cr.centery), 150,
                            self.scene.clock + k)                # витрина во всю карточку (не в масштабе карат)
                tx = cr.x + 166
                tw = cr.right - tx - 12
                T.text(surf, gd["name"], (tx, cr.y + 10), 18, tuple(gd["color"]), True)
                lines = [ln for d in GM.describe(xd, g) for ln in T.wrap(d, 13, tw)]
                for j, ln in enumerate(lines[:4]):
                    T.text(surf, ln, (tx, cr.y + 36 + j * 17), 13, T.TEXT_DIM)
                sy = cr.y + 40 + min(4, len(lines)) * 17
                for j, ln in enumerate(T.wrap(GM.stat_text(xd, g), 14, tw, True)[:2]):
                    T.text(surf, ln, (tx, sy + j * 18), 14, BLESS, True)
                cost = GM.unsocket_cost(xd, g)
                self.scene.btn(surf, pygame.Rect(tx, cr.bottom - 38, min(240, tw), 30), f"Вынуть · {cost}",
                               ("unsocket", k), prof.glory >= cost and not prof.art_locked(art["uid"]),
                               tip=GM.describe(xd, g))
            rows = (len(art["gems"]) + cols - 1) // cols
            top = r.y + 84 + rows * (ch + gap) + 34
        T.text(surf, f"Огранённые камни: {len(prof.gems)} — клик вставляет в выбранный артефакт",
               (x0, top - 30 if top > r.y + 88 else r.y + 58), 15, T.TEXT, True)
        with self.scene.grid(surf, "socket_gems", pygame.Rect(x0, top, r.right - 16 - x0, r.bottom - 10 - top),
                             len(prof.gems), 128, 130, gap=8) as cells:
            for i, tr in cells:
                self.socket_card(surf, prof.gems[i], tr)
        if not prof.gems:
            T.text(surf, "Камней нет — сначала огранка.", (x0, r.y + 92), 15, T.TEXT_DIM)

    # ---------- витрина ----------

    def draw_showcase(self, surf, r):
        """Витрина: 6 мест под огранённые камни. Клик по месту — выбрать, по камню из сундука — выставить;
        с ценником гости таверны покупают камень после похода."""
        prof = self.app.profile
        xd = prof.xd
        a = xd["artifacts"]
        slots = prof.showcase_slots()
        n = len(slots)
        sel = getattr(self, "sc_sel", None)
        T.text(surf, "Витрина — камни на виду у гостей таверны. С ценником камень могут купить после похода "
                     "(дороже, чем на рынке).", (r.x + 18, r.y + 60), 14, T.TEXT_DIM)
        gap = 12
        cw = (r.w - 36 - gap * (n - 1)) // n
        ch = 296
        for i, s_ in enumerate(slots):
            cr = pygame.Rect(r.x + 18 + i * (cw + gap), r.y + 88, cw, ch)
            hot = cr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (24, 16, 22) if not hot else (34, 24, 30), cr, border_radius=12)
            pygame.draw.rect(surf, GOLD if i == sel else (110, 80, 60), cr, 2 if i == sel else 1, border_radius=12)
            self.scene.hit(cr, ("sc_slot", i), [f"Место {i + 1}", "клик — выбрать, затем камень из сундука"])
            if not s_:
                T.text(surf, "пусто", (cr.centerx, cr.y + 100), 15, (130, 110, 100), center=True)
                T.text(surf, f"место {i + 1}", (cr.centerx, cr.y + 122), 12, T.TEXT_DIM, center=True)
                continue
            g = s_["gem"]
            gd = a["gems"][g["id"]]
            JV.draw_gem(surf, g, tuple(gd["color"]), (cr.centerx, cr.y + 82), min(cw - 20, 150),
                        self.scene.clock * 0.6 + i)
            T.text(surf, fit(gd["name"], 15, cw - 12), (cr.centerx, cr.y + 162), 15, tuple(gd["color"]), True,
                   center=True)
            T.text(surf, fit(f"{GM.cut_name(g.get('cut'))} · {g.get('size', 0):.2f} кар.", 12, cw - 12),
                   (cr.centerx, cr.y + 182), 12, T.TEXT_DIM, center=True)
            self.scene.hit(cr.inflate(0, -80), ("sc_slot", i), [gd["name"]] + GM.describe(xd, g) +
                           [(GM.stat_text(xd, g), BLESS)])
            price = GM.showcase_price(xd, g)
            self.scene.btn(surf, pygame.Rect(cr.x + 8, cr.bottom - 74, cw - 16, 30),
                           f"Ценник · {price}" if s_.get("sale") else "Без ценника", ("sc_sale", i), True,
                           primary=bool(s_.get("sale")),
                           tip=["С ценником гости могут купить камень после похода" if not s_.get("sale") else
                                f"Гость заплатит {price} (рынок — {prof.sell_price('cut', g)})", "клик — переключить"])
            self.scene.btn(surf, pygame.Rect(cr.x + 8, cr.bottom - 38, cw - 16, 30), "Снять", ("sc_take", i), True)
        y0 = r.y + 88 + ch + 22
        T.text(surf, f"Огранённые камни в сундуке: {len(prof.gems)} — клик выставляет на " +
               (f"место {sel + 1}" if sel is not None else "первое свободное место"), (r.x + 18, y0), 15, T.TEXT, True)
        log = prof.showcase.get("log", [])
        if log:
            T.text(surf, fit("Недавно купили: " + ", ".join(log[:3]), 13, r.w - 520), (r.x + 500, y0 + 2), 13, GLORY)
        top = y0 + 28
        with self.scene.grid(surf, "show_gems", pygame.Rect(r.x + 18, top, r.w - 36, r.bottom - 10 - top),
                             len(prof.gems), 128, 130, gap=8) as cells:
            for i, tr in cells:
                g = prof.gems[i]
                gd = a["gems"][g["id"]]
                hot = tr.collidepoint(self.scene.mouse)
                pygame.draw.rect(surf, (54, 40, 26) if hot else (32, 24, 17), tr, border_radius=8)
                pygame.draw.rect(surf, tuple(gd["color"]), tr, 1, border_radius=8)
                JV.draw_gem(surf, g, tuple(gd["color"]), (tr.centerx, tr.y + 46), 80, self.scene.clock)
                T.text(surf, fit(gd["name"], 14, tr.w - 8), (tr.centerx, tr.y + 88), 14, tuple(gd["color"]), True,
                       center=True)
                T.text(surf, fit(GM.cut_name(g.get("cut")), 11, tr.w - 8), (tr.centerx, tr.y + 108), 11,
                       T.TEXT_DIM, center=True)
                self.scene.hit(tr, ("sc_gem", g["uid"]), [gd["name"]] + GM.describe(xd, g) + ["клик — на витрину"])
        if not prof.gems:
            T.text(surf, "Огранённых камней нет — сначала огранка.", (r.x + 18, top + 6), 14, T.TEXT_DIM)

    def socket_card(self, surf, g, tr):
        prof = self.app.profile
        xd = prof.xd
        a = xd["artifacts"]
        if True:
            gd = a["gems"][g["id"]]
            hot = tr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (54, 40, 26) if hot else (32, 24, 17), tr, border_radius=8)
            pygame.draw.rect(surf, tuple(gd["color"]), tr, 1, border_radius=8)
            JV.draw_gem(surf, g, tuple(gd["color"]), (tr.centerx, tr.y + 46), 80, self.scene.clock, xd=xd)
            T.text(surf, gd["name"], (tr.centerx, tr.y + 86), 15, tuple(gd["color"]), True, center=True)
            T.text(surf, f"×{GM.power(xd, g):.2f} · {g.get('size', 0):.2f} кар.", (tr.centerx, tr.y + 106), 12,
                   T.TEXT_DIM, center=True)
            self.scene.hit(tr, ("socket", g["uid"]), [gd["name"]] + GM.describe(xd, g) +
                           [(GM.stat_text(xd, g), BLESS), "клик — вставить"])



# ---------- Горн мастера: ковка по этапам ----------

def draw_metal_piece(surf, xd, p, x, y, cell):
    from game import smith_games as SG
    SG.draw_piece(surf, xd, p, x, y, cell)


SMITH_MODES = (("smelt", "1 Плавка"), ("stack", "2 Пакет"), ("weld", "3 Сварка"), ("cut", "4 Разделка"),
               ("craft", "5 Ковка"), ("orders", "Заказы"))


class SmithOverlay(StationOverlay):
    """Горн мастера: плавка → пакет → сварка и складывание → разделка → ковка. Полуфабрикаты — в сундуке кузни."""

    def __init__(self, scene, ws="ws_forge"):
        super().__init__(scene, ws)
        self.mode = "smelt"
        self.b_sel = None
        self.cut_kind = "bracers"
        self.frame_sel = "mid"

    def tools(self):
        return tuple(self.app.profile.smith.get("tools", []))


    def act(self, action, button=1):
        from game import smith_games as SG
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        kind = action[0] if isinstance(action, tuple) else action
        seed = int(self.scene.clock * 1000) + prof.art_n
        if kind == "mode":
            self.mode = action[1]
            self.result = None
        elif kind == "smelt":
            if not prof.can_pay({"ore": SM.cfg(xd)["smelt"]["ore"]}):
                self.scene.say("Нужна руда")
                return
            game = SG.SmeltGame(seed, xd, self.tools())

            def done(q):
                r = game.result
                out = prof.smelt(r["carbon"], r["heat_ok"], r["slag"], seed) if r else None
                self.result = ([(f"Выплавлено кусков: {len(out)} — {SM.cfg(xd)['metals'][out[0]['metal']]['name']}",
                                 GLORY), (f"чистота {out[0]['purity'] * 100:.0f}%", T.TEXT)], None) if out else None
            self.run_game(game, "Плавка руды", done)
        elif kind == "stack":
            if not prof.smith["pieces"]:
                self.scene.say("Нет кусков металла — сначала плавка")
                return
            game = SG.StackGame(seed, xd, self.tools(), prof.smith["pieces"], SM.frame_size(xd, self.frame_sel))

            def done(q):
                r = game.result
                b = prof.stack(r["grid"], r["used"]) if r else None
                if b:
                    self.b_sel = b["uid"]
                    self.mode = "weld"
                    pr = SM.billet_props(xd, b)
                    self.result = ([("Пакет собран — дальше сварка", GLORY),
                                    (f"{b['mass']} г · {pr['layers']} слоёв · узор {pr['pattern'] * 100:.0f}%",
                                     T.TEXT)], None)
            self.run_game(game, "Пакет", done)
        elif kind == "b_pick":
            self.b_sel = action[1]
        elif kind == "weld":
            b = next((x for x in prof.smith["billets"] if x["uid"] == self.b_sel), None)
            if b is None:
                self.scene.say("Выберите пакет")
                return
            game = SG.WeldGame(seed, xd, self.tools(), b, prof.fold_max())

            def done(q):
                if game.result:
                    prof.store_billet(game.result)
                    pr = SM.billet_props(xd, game.result)
                    self.mode = "cut"
                    self.result = ([("Пакет сварен — дальше разделка", GLORY),
                                    (f"{pr['layers']} слоёв · тв. {pr['hard'] * 100:.0f}% · вяз. {pr['tough'] * 100:.0f}%",
                                     T.TEXT)], None)
            self.run_game(game, "Сварка и складывание", done)
        elif kind == "frame":
            self.frame_sel = action[1]
        elif kind == "cut_kind":
            self.cut_kind = action[1]
        elif kind == "cut":
            b = next((x for x in prof.smith["billets"] if x["uid"] == self.b_sel and x.get("welded")), None)
            if b is None:
                self.scene.say("Выберите сваренный пакет")
                return
            game = SG.CutGame(seed, xd, self.tools(), b)

            def done(q):
                r = game.result
                if r and r["cuts"]:
                    parts = prof.cut_parts(b["uid"], r["cuts"], r["cold"], r.get("wide", False))
                    self.mode = "craft"
                    self.result = ([("Части готовы — дальше ковка", GLORY),
                                    (", ".join(f"{p['mass']} г" for p in parts), T.TEXT)], None)
            self.run_game(game, "Разделка", done)
        elif kind == "craft":
            parts = SM.match_parts(xd, self.kind, prof.smith["parts"])
            if parts is None:
                need = " + ".join(f"{m} г" for m in SM.parts_for(xd, self.kind))
                self.scene.say(f"Нужны части: {need} (разделка)")
                return
            if not prof.can_craft(self.ws, self.set_sel):
                self.scene.say("Не хватает материалов или золота, или мастерская мала для этой редкости")
                return
            game = SG.ShapeGame(seed, xd, self.tools(), parts, self.kind)
            kind_, sid = self.kind, self.set_sel

            def done(q):
                r = game.result
                art = prof.forge_item(kind_, sid, [p["uid"] for p in parts], r["scores"], r["quench"], seed) if r else None
                self.result = ([(A.art_name(xd, art), WS.rar_color(xd, art["rarity"])),
                                (f"{A.quality_word(art['q'])} — качество {art['q'] * 100:.0f}%", GLORY)]
                               + [(ln, T.TEXT) for ln in A.art_lines(xd, art)], art) if art else None
            self.run_game(game, f"Ковка: {xd['artifacts']['kinds'][kind_]['name']}", done)
        elif kind == "fulfil":
            if prof.fulfil(action[1], action[2]):
                self.scene.say("Заказ сдан!")
            else:
                self.scene.say("Вещь не подходит")
        else:
            super().act(action, button)

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.level():
            self.act({"smelt": "smelt", "stack": "stack", "weld": "weld", "cut": "cut", "craft": "craft"}.get(
                self.mode, "none"))
            return True
        return False

    def draw(self, surf):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        r = self.frame(surf)
        if not self.level():
            return StationOverlay.draw(self, surf)
        self.scene.seg(surf, r.x + 200, r.y + 12, SMITH_MODES, self.mode, "mode", h=34)
        tools = [SM.cfg(xd)["tools"][t]["name"] for t in prof.smith.get("tools", []) if t in SM.cfg(xd)["tools"]]
        T.text(surf, fit("Инструменты: " + (", ".join(tools) if tools else "простые (новые — у бродячих кузнецов на рынке)"),
                         12, r.w - 40), (r.x + 20, r.y + 52), 12, T.TEXT_DIM)
        body = pygame.Rect(r.x + 16, r.y + 74, r.w - 32, r.h - 90)
        getattr(self, "draw_" + self.mode)(surf, body)
        if self.result:
            self.draw_result(surf, r)

    def big_btn(self, surf, x, y, label, action, ok):
        self.scene.btn(surf, pygame.Rect(x, y, 300, 56), label, action, ok, primary=True)

    def draw_smelt(self, surf, r):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        c = SM.cfg(xd)["smelt"]
        T.text(surf, "Плавка руды в тигле", (r.x, r.y), 20, GLORY, True)
        tips = ("Руда плавится в куски металла разной формы.", "Мало угля — железо: мягкое, вязкое (держит удар).",
                "Больше угля — сталь: твёрдая, но хрупкая.", "Слишком много — чугун: хрупкий и грязный.",
                "Держите жар в окне и снимайте шлак — металл чище.")
        for i, ln in enumerate(tips):
            T.text(surf, ln, (r.x, r.y + 34 + i * 22), 15, T.TEXT)
        T.text(surf, "Цена:", (r.x, r.y + 160), 16, T.TEXT_DIM, True)
        cost_icons(self.scene, surf, prof, {"ore": c["ore"]}, r.x + 58, r.y + 156)
        self.big_btn(surf, r.x, r.y + 196, "Плавить  (Enter)", "smelt", prof.can_pay({"ore": c["ore"]}))
        self.draw_pieces(surf, pygame.Rect(r.x + 560, r.y, r.w - 560, r.h))

    def draw_pieces(self, surf, r):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        pcs = prof.smith["pieces"]
        T.text(surf, f"Куски металла: {len(pcs)}", (r.x, r.y), 17, GLORY, True)
        with self.scene.grid(surf, "smith_pieces", pygame.Rect(r.x, r.y + 30, r.w, r.h - 30), len(pcs), 120, 84,
                             gap=8, stretch=False) as cells:
            for i, cr in cells:
                self.piece_card(surf, pcs[i], cr)
        if not pcs:
            T.text(surf, "Пусто — плавьте руду или купите у бродячего кузнеца.", (r.x, r.y + 34), 14, T.TEXT_DIM)

    def piece_card(self, surf, p, cr):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        if True:
            pygame.draw.rect(surf, (30, 22, 16), cr, border_radius=8)
            pygame.draw.rect(surf, (80, 60, 40), cr, 1, border_radius=8)
            draw_metal_piece(surf, xd, p, cr.x + 8, cr.y + 8, 12)
            m = SM.cfg(xd)["metals"][p["metal"]]
            T.text(surf, fit(m["name"], 13, 110), (cr.x + 6, cr.bottom - 36), 13, T.TEXT, True)
            T.text(surf, f"{SM.piece_mass(xd, p)} г · {p['purity'] * 100:.0f}%", (cr.x + 6, cr.bottom - 18), 12,
                   T.TEXT_DIM)
            self.scene.hit(cr, None, [m["name"], m["desc"], f"твёрдость {m['hard'] * 100:.0f}%, вязкость "
                                                            f"{m['tough'] * 100:.0f}%, чистота {p['purity'] * 100:.0f}%"])

    def draw_stack(self, surf, r):
        from sim import smithing as SM
        prof = self.app.profile
        fr = SM.cfg(prof.xd)["frames"]
        T.text(surf, "Пакет: куски на рамке как в тетрисе", (r.x, r.y), 20, GLORY, True)
        g = SM.cfg(prof.xd)["cell_g"]
        items = [(k, f"{v['name']} {v['size'][0] * v['size'][1] * g} г") for k, v in fr.items()]
        self.scene.seg(surf, r.x, r.y + 196, tuple(items[:3]), self.frame_sel, "frame", h=32)
        self.scene.seg(surf, r.x, r.y + 232, tuple(items[3:]), self.frame_sel, "frame", h=32)
        w, h = SM.frame_size(prof.xd, self.frame_sel)
        tips = (f"Рамка {w}×{h} клеток (по {SM.cfg(prof.xd)['cell_g']} г): строки — будущие слои.",
                "Чередуйте твёрдые и мягкие слои — получится дамаск.", "Пустые клетки не страшны: слиток просто легче.",
                "Куски можно поворачивать.")
        for i, ln in enumerate(tips):
            T.text(surf, ln, (r.x, r.y + 34 + i * 22), 15, T.TEXT)
        T.text(surf, "Заготовка (больше рамка — тяжелее пакет, больше частей):", (r.x, r.y + 172), 14, T.TEXT_DIM)
        self.big_btn(surf, r.x, r.y + 286, "Собрать пакет  (Enter)", "stack", bool(prof.smith["pieces"]))
        self.draw_pieces(surf, pygame.Rect(r.x + 560, r.y, r.w - 560, r.h))

    def billet_list(self, surf, r, pred, key):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        bs = [b for b in prof.smith["billets"] if pred(b)]
        with self.scene.grid(surf, key, r, len(bs), r.w, 70, gap=8) as cells:
            for i, br in cells:
                self.billet_row(surf, bs[i], br)
        if not bs:
            T.text(surf, "Нет подходящих пакетов.", (r.x, r.y + 6), 14, T.TEXT_DIM)
        return bs

    def billet_row(self, surf, b, br):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        if True:
            pr = SM.billet_props(xd, b)
            on = b["uid"] == self.b_sel
            hot = br.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (64, 46, 30) if on else (44, 32, 22) if hot else (30, 22, 16), br, border_radius=8)
            pygame.draw.rect(surf, GOLD if on else (80, 60, 40), br, 2 if on else 1, border_radius=8)
            from game import metal_view as MV, smith_games as SG
            surf.blit(MV.bar(xd, b["grid"], b.get("folds", 0), b.get("twist", 0), 60, 46, 20), (br.x + 10, br.y + 12))
            T.text(surf, f"{b['mass']} г · {pr['layers']} слоёв" + (" · сварен" if b.get("welded") else ""),
                   (br.x + 80, br.y + 10), 15, T.TEXT, True)
            SG.mini_props(surf, br.x + 80, br.y + 54, 160, pr)
            T.text(surf, f"тв. {pr['hard'] * 100:.0f}% · вяз. {pr['tough'] * 100:.0f}% · узор {pr['pattern'] * 100:.0f}% · "
                         f"сварка {b['weld'] * 100:.0f}%", (br.x + 80, br.y + 38), 12,
                   T.TEXT_DIM)
            self.scene.hit(br, ("b_pick", b["uid"]))

    def draw_weld(self, surf, r):
        prof = self.app.profile
        T.text(surf, "Сварка и складывание", (r.x, r.y), 20, GLORY, True)
        tips = ("Пакет греют до сварочного жара и проковывают —", "слои срастаются. Складывание удваивает слои:",
                "дамаск тоньше и вязче, металл чище, но −5% массы.", f"Сложить можно до {prof.fold_max()} раз.")
        for i, ln in enumerate(tips):
            T.text(surf, ln, (r.x, r.y + 34 + i * 22), 15, T.TEXT)
        bs = self.billet_list(surf, pygame.Rect(r.x + 560, r.y, r.w - 560, r.h), lambda b: True, "smith_billets")
        if self.b_sel not in [b["uid"] for b in bs] and bs:
            self.b_sel = bs[0]["uid"]
        self.big_btn(surf, r.x, r.y + 140, "В горн  (Enter)", "weld", bool(bs))

    def draw_cut(self, surf, r):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        T.text(surf, "Разделка на части", (r.x, r.y), 20, GLORY, True)
        tips = ["Брусок режется на куски любой массы — на глаз.", "Enter — закончить: остаток станет последней частью.",
                "Под вещи нужны части:"] + [f"  {xd['artifacts']['kinds'][k]['name']}: " + " + ".join(
                    f"{m} г" for m in v["parts"]) for k, v in SM.cfg(xd)["recipes"].items()]
        for i, ln in enumerate(tips):
            T.text(surf, ln, (r.x, r.y + 32 + i * 20), 14, T.TEXT if i < 2 else T.TEXT_DIM)
        bs = self.billet_list(surf, pygame.Rect(r.x + 560, r.y, r.w - 560, r.h // 2 - 10), lambda b: b.get("welded"),
                              "smith_cutb")
        if self.b_sel not in [b["uid"] for b in bs] and bs:
            self.b_sel = bs[0]["uid"]
        self.big_btn(surf, r.x, r.y + 150, "Разделить  (Enter)", "cut", bool(bs))
        self.parts_list(surf, pygame.Rect(r.x + 560, r.y + r.h // 2 + 4, r.w - 560, r.h // 2 - 4))

    def parts_list(self, surf, r):
        """Готовые части: масса и свойства металла."""
        from game import smith_games as SG
        prof = self.app.profile
        parts = prof.smith["parts"]
        T.text(surf, f"Части: {len(parts)}", (r.x, r.y), 16, GLORY, True)
        with self.scene.grid(surf, "smith_parts", pygame.Rect(r.x, r.y + 24, r.w, r.h - 24), len(parts), 142, 58,
                             gap=8) as cells:
            for i, cr in cells:
                self.part_card(surf, parts[i], cr)
        if not parts:
            T.text(surf, "Пока нет — разделите сваренный брусок.", (r.x, r.y + 28), 13, T.TEXT_DIM)

    def part_card(self, surf, p, cr):
        from game import smith_games as SG
        prof = self.app.profile
        if True:
            pygame.draw.rect(surf, (30, 22, 16), cr, border_radius=8)
            pygame.draw.rect(surf, (80, 60, 40), cr, 1, border_radius=8)
            lk = p.get("look") or {"rows": [["iron"]]}
            from game import metal_view as MV
            surf.blit(MV.bar(prof.xd, lk["rows"], lk.get("folds", 0), lk.get("twist", 0), 50, 18, 20), (cr.x + 8, cr.y + 8))
            T.text(surf, f"{p['mass']} г", (cr.x + 66, cr.y + 6), 16, T.TEXT, True)
            SG.mini_props(surf, cr.x + 8, cr.y + 36, cr.w - 16, p["props"])
            pr = p["props"]
            self.scene.hit(cr, None, [f"Часть {p['mass']} г", f"твёрдость {pr['hard'] * 100:.0f}% (урон)",
                                      f"вязкость {pr['tough'] * 100:.0f}% (здоровье)", f"{pr['layers']} слоёв"])

    def draw_orders(self, surf, r):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        T.text(surf, "Заказы кузни — обновляются после каждого похода", (r.x, r.y), 20, GLORY, True)
        y = r.y + 36
        for o in prof.smith.get("orders", []):
            orr = pygame.Rect(r.x, y, r.w, 120)
            pygame.draw.rect(surf, (30, 22, 16), orr, border_radius=8)
            pygame.draw.rect(surf, (120, 90, 50), orr, 1, border_radius=8)
            T.text(surf, o["text"], (orr.x + 14, orr.y + 10), 17, T.TEXT, True)
            names = {"hard": "твёрдость", "tough": "вязкость", "layers": "слоёв", "pattern": "узор"}
            req = ", ".join(f"{names[k]} ≥ {v * 100:.0f}%" if k != "layers" else f"{names[k]} ≥ {v}"
                            for k, v in o["req"].items())
            T.text(surf, f"{xd['artifacts']['kinds'][o['kind']]['name']} · качество ≥ {o['q'] * 100:.0f}% · {req}",
                   (orr.x + 14, orr.y + 38), 14, T.TEXT_DIM)
            coin(surf, (orr.x + 24, orr.y + 72), 9)
            T.text(surf, f"{o['gold']}" + (" + " + ", ".join(f"{res_name(xd, k)} {v}" for k, v in o["mats"].items())
                                           if o.get("mats") else ""), (orr.x + 40, orr.y + 62), 16, GOLD, True)
            fits = [a for a in prof.stash.values() if SM.order_ok(xd, o, a) and not prof.art_locked(a["uid"])]
            x = orr.x + 380
            for a in fits[:4]:
                self.scene.btn(surf, pygame.Rect(x, orr.y + 66, 190, 40), fit("Сдать: " + A.art_name(xd, a), 14, 180),
                               ("fulfil", o["id"], a["uid"]), True, primary=True)
                x += 198
            if not fits:
                T.text(surf, "подходящих вещей нет", (orr.x + 380, orr.y + 76), 14, T.TEXT_DIM)
            y += 130

    def draw_craft(self, surf, r):
        from sim import smithing as SM
        prof = self.app.profile
        xd = prof.xd
        rr = pygame.Rect(r.x - 16, r.y - 74, r.w + 32, r.h + 90)
        StationOverlay.draw_craft(self, surf, rr)
        need = SM.parts_for(xd, self.kind)
        have = SM.match_parts(xd, self.kind, prof.smith["parts"])
        col = (150, 230, 150) if have else (240, 160, 110)
        T.text(surf, "Части: " + " + ".join(f"{m} г" for m in need) + (" — есть" if have else " — нет (разделка)"),
               (rr.x + 510, rr.bottom - 40), 15, col, True)

def building_value(prof, bid):
    return X.building_value(prof.xd, prof.buildings, bid) or 0


# ---------- Двор: доска поручений и общежитие ----------

class YardRoom(RoomScene):
    """Двор: внизу — доска поручений и вход в общежитие (у входа — ветераны, что уйдут после похода); листая
    вверх — этажи общежития, где живут выкупленные ветераны."""
    room = "yard"
    title = "Двор"
    art = "room_yard"
    dim = 70
    FLOOR_H, GROUND_H, ROOF_H = 240, 220, 150
    FLOORS = 6                                      # по комнате на этаж (мест в общежитии — до 6)
    ROOMS_ART = ("room_dorm", "room_dorm_2", "room_dorm_3", "room_dorm_4", "room_dorm_5", "room_dorm_6")
    SKY_K, ROOFS_K, TREES_K = 0.5, 0.65, 0.82        # параллакс задника: небо, крыши, кроны (дом и двор — 1.0)

    def __init__(self, app):
        super().__init__(app)
        self.cam = 0.0
        self.target = 0.0

    @property
    def sub(self):
        prof = self.app.profile
        return "колесо или ↑ ↓ — этажи общежития" if self.cam < 40 else \
            f"Общежитие: {len(prof.dorm_heroes())}/{prof.dorm_slots()} мест"

    def max_cam(self):
        roof = sprite_w("dorm_roof", self.BX1 - self.BX0 + 60)
        world = self.GROUND_H + self.FLOORS * self.FLOOR_H + (roof.get_height() if roof else self.ROOF_H) + 40
        return max(0, world - (self.ground() - TOP_H))

    def ground(self):
        return strip_y() - 60

    def sy(self, wy):
        """Экранная y по высоте мира (0 — земля двора, вверх — этажи)."""
        return int(self.ground() - wy + self.cam)

    def wheel(self, dy):
        self.target = max(0.0, min(self.max_cam(), self.target + dy * 110))

    def update(self, dt):
        super().update(dt)
        self.cam += (self.target - self.cam) * min(1.0, dt * 10)

    def room_key(self, k):
        if k in (pygame.K_UP, pygame.K_w, pygame.K_PAGEUP):
            self.wheel(2)
        elif k in (pygame.K_DOWN, pygame.K_s, pygame.K_PAGEDOWN):
            self.wheel(-2)

    def room_act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "board":
            self.overlay = BoardOverlay(self)
        elif kind in ("vet", "lodger"):
            h = next((x for x in prof.roster if x.uid == action[1]), None)
            if h:
                self.overlay = HeroPopup(self, h)
        elif kind == "floor":
            self.target = max(0.0, min(self.max_cam(), action[1]))

    def draw_backdrop(self, surf):
        if self.draw_layers(surf):
            return
        surf.fill((14, 16, 26))
        for i in range(0, T.SCREEN_H, 4):                 # ночное небо над двором
            k = i / T.SCREEN_H
            pygame.draw.line(surf, T.mix((8, 10, 24), (46, 38, 50), k), (0, i), (T.SCREEN_W, i), 4)
        rng = random.Random(7)
        for _ in range(90):
            x, y = rng.randrange(T.SCREEN_W), rng.randrange(T.SCREEN_H) + int(self.cam * 0.15) - 200
            if TOP_H < y < self.sy(0):
                pygame.draw.circle(surf, (200, 200, 220), (x, y), 1)
        moon = (230, 150 + int(self.cam * 0.2))
        light(surf, moon, 120, (120, 120, 150), 0.35)
        pygame.draw.circle(surf, (230, 228, 200), moon, 26)
        art = room_art(self.art, None)
        if art:
            img = IL.get(art, "tavern", (T.SCREEN_W, T.SCREEN_W * 2 // 3), hd=True)
            surf.blit(img, (0, self.ground() + 60 - img.get_height() + int(self.cam * 0.55)))
            return
        hy = self.sy(0) - int(self.cam * 0.35)            # дальние крыши — медленнее
        for k, (x, w, h) in enumerate(((0, 220, 120), (200, 180, 160), (360, 260, 110), (600, 200, 150),
                                       (780, 240, 130), (1000, 300, 170))):
            pygame.draw.rect(surf, (20, 18, 26), (x, hy - h, w, h + 400))
            pygame.draw.polygon(surf, (24, 20, 30), [(x - 10, hy - h), (x + w // 2, hy - h - 60), (x + w + 10, hy - h)])
            if k % 2 == 0:
                pygame.draw.rect(surf, (180, 140, 70), (x + w // 3, hy - h + 30, 12, 16))
        gy = self.sy(0)
        pygame.draw.rect(surf, (44, 38, 34), (0, gy - 8, T.SCREEN_W, T.SCREEN_H))
        for row in range(6):                              # булыжник двора
            for c in range(-1, T.SCREEN_W // 46 + 2):
                pygame.draw.ellipse(surf, (60, 52, 46), (c * 46 + (row % 2) * 23, gy + row * 14, 38, 11))
        for x in range(0, self.BX0 - 20, 34):             # забор
            pygame.draw.rect(surf, (56, 40, 28), (x, gy - 96, 22, 96))
            pygame.draw.polygon(surf, (56, 40, 28), [(x, gy - 96), (x + 11, gy - 108), (x + 22, gy - 96)])
        pygame.draw.rect(surf, (46, 32, 22), (0, gy - 70, self.BX0 - 20, 8))
        sh = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        sh.fill((6, 8, 12, self.dim))
        surf.blit(sh, (0, 0))

    def draw_layers(self, surf):
        """Задник слоями (лист 35 и лист L): небо из трёх частей, дальние крыши, кроны, передний план двора.
        Небо и дальние слои едут медленнее дома (параллакс). False — слоёв нет, рисуем по-старому."""
        if not room_art("yard_sky_mid", None) or not sprite_exists("layer_yard"):
            return False
        W = T.SCREEN_W
        seg = W * 2 // 3
        base = self.ground() + 60 + int(self.cam * self.SKY_K)
        need = int(self.max_cam() * self.SKY_K) + T.SCREEN_H + seg
        parts = ["yard_sky_low"] + ["yard_sky_mid"] * max(1, need // seg) + ["yard_sky_high"]
        col = self.sky_column(W, seg, parts)
        surf.blit(col, (0, base - col.get_height()))
        for name, k, lift in (("layer_roofs", self.ROOFS_K, 150), ("layer_trees", self.TREES_K, 60)):
            img = sprite_w(name, W)
            if img is not None:
                surf.blit(img, (0, self.ground() - lift - img.get_height() + int(self.cam * k)))
        img = sprite_w("layer_yard", W)
        surf.blit(img, (0, self.sy(0) + 60 - img.get_height()))
        sh = pygame.Surface((W, T.SCREEN_H), pygame.SRCALPHA)
        sh.fill((6, 8, 12, self.dim // 2))
        surf.blit(sh, (0, 0))
        return True

    _SKY = {}

    def sky_column(self, W, seg, parts):
        """Небо одним столбом: части друг над другом, стыки сглажены (без резкой ступеньки цвета)."""
        key = (W, seg, tuple(parts))
        if key in self._SKY:
            return self._SKY[key]
        n = len(parts)
        col = pygame.Surface((W, seg * n))
        for k, iid in enumerate(parts):
            iid = room_art(iid, None) or room_art("yard_sky_mid", None)
            col.blit(IL.get(iid, "tavern", (W, seg), hd=True), (0, seg * (n - 1 - k)))
        band = 90
        for k in range(1, n):
            y = seg * k
            strip = col.subsurface((0, y - band, W, band * 2)).copy()
            smooth = pygame.transform.smoothscale(pygame.transform.smoothscale(strip, (W // 8, 3)), (W, band * 2))
            mask = pygame.Surface((W, band * 2), pygame.SRCALPHA)
            for i in range(band * 2):
                a = int(255 * max(0.0, 1 - abs(i - band) / band))
                pygame.draw.line(mask, (255, 255, 255, a), (0, i), (W, i))
            layer = pygame.Surface((W, band * 2), pygame.SRCALPHA)
            layer.blit(smooth, (0, 0))
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            col.blit(layer, (0, y - band))
        self._SKY[key] = col
        return col

    def draw_room(self, surf):
        self.draw_building(surf)
        self.draw_board(surf)
        self.draw_outside(surf)
        self.draw_floors_nav(surf)

    # --- общежитие ---
    BX0, BX1 = 560, 1220

    def draw_building(self, surf):
        """Общежитие из модулей (лист D): основание со входом, этажи (свой вид у каждого), крыша. Комната видна
        сквозь проём фасада; без спрайтов — простые стены."""
        prof = self.app.profile
        x0, x1 = self.BX0, self.BX1
        w = x1 - x0
        top_w = self.GROUND_H + self.FLOORS * self.FLOOR_H
        modular = sprite_exists("dorm_base") and sprite_exists("dorm_floor_1")
        wall = pygame.Rect(x0, self.sy(top_w), w, self.sy(0) - self.sy(top_w))    # стена — за модулями, без щелей
        pygame.draw.rect(surf, (52, 38, 26) if not modular else (58, 36, 22), wall)
        # крыша
        roof_y = self.sy(top_w)
        roof = sprite_w("dorm_roof", w + 60)
        if roof is not None:                          # крыша — по ширине дома, пропорции сохраняются
            surf.blit(roof, (x0 - 30, roof_y - roof.get_height() + 6))
        else:
            pts = [(x0 - 30, roof_y), ((x0 + x1) // 2, roof_y - self.ROOF_H + 40), (x1 + 30, roof_y)]
            pygame.draw.polygon(surf, (70, 40, 32), pts)
            pygame.draw.polygon(surf, (40, 24, 20), pts, 3)
        # этажи: по комнате на этаж
        lodgers = prof.dorm_heroes()
        slots = prof.dorm_slots()
        for f in range(self.FLOORS):
            wy0 = self.GROUND_H + f * self.FLOOR_H
            fr = pygame.Rect(x0, self.sy(wy0 + self.FLOOR_H), w, self.FLOOR_H)
            if fr.y > strip_y() or fr.bottom < TOP_H:
                continue
            T.text(surf, f"{f + 1} этаж", (x0 - 14 - T.font(14, True).size(f"{f + 1} этаж")[0], fr.y + 12), 14,
                   T.TEXT_DIM, True, shadow=True)
            frame = sprite_fit(f"dorm_floor_{f % 6 + 1}", w, self.FLOOR_H) if modular else None
            rr = (pygame.Rect(fr.x + int(w * 0.08), fr.y + int(self.FLOOR_H * 0.12), int(w * 0.84),
                              int(self.FLOOR_H * 0.80)) if frame is not None else fr.inflate(-20, -16))
            h = lodgers[f] if f < len(lodgers) else None
            self.draw_room_cell(surf, rr, f, h, f < slots, frame=(frame, fr))
            if frame is None:
                pygame.draw.line(surf, (34, 24, 16), (x0, fr.y), (x1, fr.y), 6)
        # основание: вход
        gr = pygame.Rect(x0, self.sy(self.GROUND_H), w, self.GROUND_H)
        base = sprite_fit("dorm_base", w, self.GROUND_H) if modular else None
        if base is not None:
            surf.blit(base, gr)
            door_top = gr.y + 40
        else:
            door = pygame.Rect((x0 + x1) // 2 - 50, self.sy(0) - 150, 100, 150)
            pygame.draw.rect(surf, (36, 24, 16), door, border_top_left_radius=40, border_top_right_radius=40)
            pygame.draw.rect(surf, (90, 62, 36), door.inflate(-10, -10), border_top_left_radius=36,
                             border_top_right_radius=36)
            pygame.draw.circle(surf, (230, 190, 80), (door.right - 22, door.centery + 10), 4)
            pygame.draw.line(surf, (34, 24, 16), (x0, gr.y), (x1, gr.y), 6)
            door_top = door.y
        sign = pygame.Rect(0, 0, 250, 40)
        sign.midbottom = ((x0 + x1) // 2, door_top - 8)
        T.frame(surf, sign, 240)
        T.text(surf, f"Общежитие · {len(prof.dorm_heroes())}/{prof.dorm_slots()}", sign.center, 16, GLORY, True,
               center=True)

    def draw_room_cell(self, surf, rr, i, h, open_, frame=(None, None)):
        prof = self.app.profile
        data = prof.data
        frame_img, fr = frame
        clip = surf.get_clip()
        surf.set_clip(rr.clip(clip))
        self._cell_content(surf, rr, i, h, open_)
        surf.set_clip(clip)
        if frame_img is not None:                    # фасад этажа с проёмом — поверх комнаты
            surf.blit(frame_img, fr)
        if not open_:
            T.text(surf, "закрыто", (rr.centerx, rr.centery - 12), 18, T.TEXT_DIM, True, center=True, shadow=True)
            T.text(surf, "расширьте общежитие в Стройке", (rr.centerx, rr.centery + 12), 13, T.TEXT_DIM, center=True,
                   shadow=True)
            self.hit(rr, ("room", "build"), ["Комната закрыта", "Больше мест — постройка «Общежитие» в Стройке"])
            return
        if h is None:
            T.text(surf, "свободная комната", (rr.centerx, rr.y + 28), 15, T.TEXT, True, center=True, shadow=True)
            self.hit(rr, None, ["Свободная комната", "Поселить ветерана — клик по нему у входа во двор"])
            return
        sub = f"{data.classes[h.cls]['name']} · побед {h.vet.get('wins', 0)}" + (" · на поручении" if h.task else "")
        plate(surf, (rr.centerx - 60, rr.bottom - 58), fit(f"{h.name} {title_of(prof.xd, h)}".strip(), 17, 220), sub,
              w=240)
        self.hit(rr, ("lodger", h.uid), [h.name, "клик — летопись или отпустить"])

    def _cell_content(self, surf, rr, i, h, open_):
        """Внутри проёма: комната (иллюстрация — своя на этаж) и жилец; закрытая — заколочена."""
        prof = self.app.profile
        data = prof.data
        if not open_:
            pygame.draw.rect(surf, (40, 30, 22), rr)
            for k in range(0, rr.w + rr.h, 40):
                pygame.draw.line(surf, (70, 52, 34), (rr.x + k, rr.y), (rr.x + k - rr.h, rr.bottom), 10)
            pygame.draw.rect(surf, (24, 18, 12), rr, 3)
            return
        arts = [a for a in self.ROOMS_ART if room_art(a, None)]
        art = arts[i % len(arts)] if arts else None
        if art:                                      # иллюстрация комнаты (листы 33–35), обрезка по ширине
            img = IL.get(art, "tavern", (rr.w, rr.w * 2 // 3), hd=True)
            surf.blit(img, (rr.x, rr.bottom - img.get_height() + (img.get_height() - rr.h) // 3))
            sh = pygame.Surface(rr.size, pygame.SRCALPHA)
            sh.fill((0, 0, 0, 70))
            surf.blit(sh, rr)
        else:
            pygame.draw.rect(surf, (86, 60, 38), rr)
            for y in range(rr.y + 14, rr.bottom - 26, 16):
                pygame.draw.line(surf, (74, 52, 32), (rr.x, y), (rr.right, y))
            pygame.draw.rect(surf, (58, 40, 26), (rr.x, rr.bottom - 26, rr.w, 26))
        if not art:                                  # заглушка: окно с луной, лампа, кровать
            win = pygame.Rect(rr.x + 24, rr.y + 26, 64, 70)
            pygame.draw.rect(surf, (28, 34, 60), win)
            pygame.draw.circle(surf, (230, 230, 200), (win.right - 16, win.y + 18), 7)
            pygame.draw.rect(surf, (50, 34, 22), win, 4)
            pygame.draw.line(surf, (50, 34, 22), (win.centerx, win.y), (win.centerx, win.bottom), 3)
            lamp = (rr.right - 40, rr.y + 40)
            light(surf, lamp, 110, (255, 180, 90), 0.35)
            pygame.draw.circle(surf, (255, 210, 120), lamp, 6)
            bed = obj_img("obj_bed", 64)
            surf.blit(bed, (rr.x + 14, rr.bottom - 22 - bed.get_height()))
        if h is None:
            return
        img = hero_fit(data, h.cls, 130)
        pos = (rr.right - 110 - img.get_width() // 2, rr.bottom - 14 - img.get_height())
        if rr.collidepoint(self.mouse):
            glow_outline(surf, img, pos)
        surf.blit(img, pos)

    def draw_outside(self, surf):
        """У входа: ветераны, что уйдут после похода, если не поселить."""
        prof = self.app.profile
        data = prof.data
        cands = [h for h in prof.roster if h.vet and not h.dorm and not h.task]
        x = self.BX0 + 40
        gy = self.sy(0)
        for h in cands[:6]:
            img = hero_fit(data, h.cls, 120)
            if x + img.get_width() > (self.BX0 + self.BX1) // 2 - 60 and x < (self.BX0 + self.BX1) // 2 + 60:
                x = (self.BX0 + self.BX1) // 2 + 60
            pos = (x, gy - img.get_height())
            rect = pygame.Rect(pos, img.get_size())
            if rect.collidepoint(self.mouse):
                glow_outline(surf, img, pos)
            surf.blit(img, pos)
            cost = prof.dorm_cost(h)
            T.text(surf, h.name, (rect.centerx, rect.y - 36), 14, T.TEXT, True, center=True, shadow=True)
            T.text(surf, f"поселить · {cost}", (rect.centerx, rect.y - 18), 12, GOLD, True, center=True, shadow=True)
            self.hit(rect, ("vet", h.uid), [h.name, "Ветеран уйдёт из таверны после следующего похода",
                                            f"клик — поселить в общежитие ({cost} золота)"])
            x += img.get_width() + 16

    def draw_board(self, surf):
        prof = self.app.profile
        img = pygame.transform.flip(obj_img("obj_board", 300), True, False)     # зеркально: фонарь — к дому
        x = 110
        pos = (x, self.sy(0) - img.get_height())
        rect = pygame.Rect(pos, img.get_size())
        if rect.collidepoint(self.mouse):
            glow_outline(surf, img, pos)
        surf.blit(img, pos)
        # заказы и идущие поручения — листки на доске
        area = pygame.Rect(rect.x + rect.w * 0.14, rect.y + rect.h * 0.3, rect.w * 0.72, rect.h * 0.4)
        has_art = os.path.exists(os.path.join(ROOT, "assets", "sprites", "obj_board.png"))
        notes = [] if has_art else [("offer", o) for o in prof.offers] + [("task", t) for t in prof.tasks()]
        for i, (kind, _) in enumerate(notes[:8]):
            nx = area.x + (i % 4) * area.w // 4 + 6
            ny = area.y + (i // 4) * area.h // 2 + 4
            nr = pygame.Rect(nx, ny, area.w // 4 - 12, area.h // 2 - 10)
            pygame.draw.rect(surf, (232, 220, 190) if kind == "offer" else (200, 220, 240), nr)
            for ly in range(nr.y + 8, nr.bottom - 4, 6):
                pygame.draw.line(surf, (150, 140, 120), (nr.x + 4, ly), (nr.right - 4, ly))
            pygame.draw.circle(surf, (200, 50, 40) if kind == "task" else (90, 70, 50), (nr.centerx, nr.y + 3), 3)
        busy = len(prof.tasks())
        plate(surf, (rect.centerx, self.sy(0) + 6), "Доска поручений",
              f"заказов {len(prof.offers)} · идёт {busy}/{prof.board_slots()}" + (" · есть вести" if prof.news else ""),
              GLORY, w=280)
        self.hit(rect.union(pygame.Rect(rect.centerx - 140, self.sy(0) + 6, 280, 50)), "board",
                 ["Доска поручений", "Свободные герои уходят на задания на несколько походов", "клик — открыть"])

    def draw_floors_nav(self, surf):
        """Справа — этажи: клик переносит взгляд."""
        x = T.SCREEN_W - 46
        marks = [("Двор", 0.0)] + [(f"{f + 1} эт.", min(self.max_cam(), self.GROUND_H + f * self.FLOOR_H - 120))
                                    for f in range(self.FLOORS)]
        y = strip_y() - 40
        for label, cam in marks:
            r = pygame.Rect(x - 20, y - 26, 58, 30)
            on = abs(self.cam - cam) < 80
            pygame.draw.rect(surf, (82, 58, 34) if on else (30, 22, 15), r, border_radius=6)
            pygame.draw.rect(surf, T.AMBER if on else (92, 68, 42), r, 1, border_radius=6)
            T.text(surf, label, r.center, 13, T.AMBER if on else T.TEXT_DIM, True, center=True)
            self.hit(r, ("floor", cam), ["Перейти: " + label])
            y -= 38


class HeroPopup(Overlay):
    """Герой во дворе: поселить в общежитие / отпустить / летопись."""

    def __init__(self, scene, hero):
        super().__init__(scene)
        self.hero = hero

    @property
    def rect(self):
        return pygame.Rect(T.SCREEN_W // 2 - 300, TOP_H + 110, 600, 340)

    def act(self, action, button=1):
        prof = self.app.profile
        h = self.hero
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "keep":
            if prof.keep_in_dorm(h):
                self.scene.say(f"{h.name} поселился в общежитии")
                self.scene.overlay = None
            else:
                self.scene.say("Нет свободных мест или не хватает золота")
        elif kind == "release":
            prof.release(h)
            self.scene.say(f"{h.name} уйдёт из таверны после следующего похода")
            self.scene.overlay = None
        elif kind == "book":
            open_book(self.app, ("live", h.uid), back=lambda: go(self.app, "yard"))

    def draw(self, surf):
        prof = self.app.profile
        xd, data = prof.xd, prof.data
        h = self.hero
        r = self.frame(surf, f"{h.name} {title_of(xd, h)}".strip())
        img = hero_fit(data, h.cls, 170)
        surf.blit(img, (r.x + 30, r.y + 220 - img.get_height()))
        x = r.x + 60 + img.get_width()
        rk = xd["tavern"]["ranks"][str(h.rank)]["name"]
        T.text(surf, f"{data.classes[h.cls]['name']} · {rk} · ур. {h.level}", (x, r.y + 64), 16, GLORY, True)
        T.text(surf, f"Побед: {h.vet.get('wins', 0)} · записей в летописи: {len(h.chronicle)}", (x, r.y + 92), 14,
               T.TEXT_DIM)
        if h.dorm:
            T.text(surf, "Живёт в общежитии: не уйдёт из таверны.", (x, r.y + 124), 15, BLESS)
        else:
            T.text(surf, "Уйдёт из таверны после следующего похода.", (x, r.y + 124), 15, (220, 170, 120))
            free = len(prof.dorm_heroes()) < prof.dorm_slots()
            T.text(surf, "мест нет — расширьте общежитие" if not free else
                   f"свободно мест: {prof.dorm_slots() - len(prof.dorm_heroes())}", (x, r.y + 148), 13, T.TEXT_DIM)
        by = r.bottom - 74
        if h.dorm:
            self.scene.btn(surf, pygame.Rect(r.x + 30, by, 250, 50), "Отпустить", "release", True,
                           tip="Уйдёт из таверны после следующего похода")
        else:
            cost = prof.dorm_cost(h)
            ok = len(prof.dorm_heroes()) < prof.dorm_slots() and prof.glory >= cost
            self.scene.btn(surf, pygame.Rect(r.x + 30, by, 250, 50), f"Поселить · {cost}", "keep", ok, primary=True)
        self.scene.btn(surf, pygame.Rect(r.right - 280, by, 250, 50), "Летопись", "book", True)


class BoardOverlay(Overlay):
    """Доска поручений: заказы, идущие поручения, кого отправить, вести."""
    title = "Доска поручений"

    def __init__(self, scene):
        super().__init__(scene)
        self.sel = None
        self.team = []

    def offer(self):
        return next((o for o in self.app.profile.offers if o["key"] == self.sel), None)

    def free_heroes(self):
        prof = self.app.profile
        return [h for h in prof.recruitable(solo=True) if prof.ready(h)]

    def act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "offer":
            self.sel = None if self.sel == action[1] else action[1]
            self.team = []
        elif kind == "send_hero":
            o = self.offer()
            need = prof.xd["contracts"]["templates"][o["id"]]["heroes"] if o else 0
            uid = action[1]
            if uid in self.team:
                self.team.remove(uid)
            elif len(self.team) < need:
                self.team.append(uid)
            elif need == 1:
                self.team = [uid]
        elif kind == "send":
            o = self.offer()
            if o and prof.send(o, self.team):
                self.scene.say(f"Ушли на поручение «{prof.xd['contracts']['templates'][o['id']]['name']}»")
                sel(self.app)["picked"] = [u for u in sel(self.app)["picked"] if u not in self.team]
                self.sel, self.team = None, []
            else:
                self.scene.say("Доска заполнена или героев не столько, сколько нужно")

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.sel:
            self.act("send")
            return True
        return False

    def draw(self, surf):
        prof = self.app.profile
        data, xd = prof.data, prof.xd
        cfg = xd["contracts"]
        r = self.frame(surf)
        T.text(surf, "Свободные герои уходят на задания на несколько походов и в поход не идут. Провал — рана; "
                     "на опасных — гибель.", (r.x + 240, r.y + 20), 14, T.TEXT_DIM)
        y = r.y + 56
        full = len(prof.tasks()) >= prof.board_slots()
        for o in prof.offers:
            t = cfg["templates"][o["id"]]
            orr = pygame.Rect(r.x + 16, y, 600, 100)
            on = o["key"] == self.sel
            risk, rcol = E.RISK[t["risk"]]
            hot = orr.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (64, 46, 30) if on else (44, 32, 22) if hot else (30, 22, 16), orr, border_radius=8)
            pygame.draw.rect(surf, GOLD if on else rcol, orr, 2 if on else 1, border_radius=8)
            T.text(surf, t["name"], (orr.x + 14, orr.y + 8), 19, T.TEXT, True)
            T.text(surf, risk, (orr.right - 14 - T.font(14, True).size(risk)[0], orr.y + 11), 14, rcol, True)
            T.text(surf, fit(f"{t['desc']} · походов: {t['runs']} · героев: {t['heroes']} · подходят: "
                             f"{E.fit_text(data, t.get('fit', {}))}", 14, orr.w - 28), (orr.x + 14, orr.y + 38), 14,
                   T.TEXT_DIM)
            rw = t["reward"]
            xx = orr.x + 14
            T.text(surf, "Награда:", (xx, orr.y + 68), 14, BLESS, True)
            xx += 74
            if rw.get("gold"):
                coin(surf, (xx + 9, orr.y + 77), 8)
                xx = T.text(surf, f"{rw['gold'][0]}–{rw['gold'][1]}", (xx + 22, orr.y + 68), 14, T.TEXT, True).right + 12
            for m, v in (rw.get("mats") or {}).items():
                surf.blit(res_icon(xd, m, 22), (xx, orr.y + 66))
                xx = T.text(surf, f"{v[0]}–{v[1]}", (xx + 25, orr.y + 68), 14, T.TEXT, True).right + 12
            for tk, v in (rw.get("trophy") or {}).items():
                surf.blit(res_icon(xd, tk, 22), (xx, orr.y + 66))
                xx = T.text(surf, str(v), (xx + 25, orr.y + 68), 14, T.TEXT, True).right + 12
            if rw.get("recruit"):
                T.text(surf, f"новобранец ранга {rw['recruit']}", (xx, orr.y + 68), 14, T.TEXT, True)
            self.scene.hit(orr, ("offer", o["key"]), [(t["name"], rcol), t["desc"], "клик — выбрать, затем героев справа"])
            y += 108
        if not prof.offers:
            T.text(surf, "Новые заказы появятся после похода.", (r.x + 18, y + 8), 16, T.TEXT_DIM)
        if prof.news:
            y = max(y + 6, r.bottom - 30 - 22 * min(4, len(prof.news)))
            T.text(surf, "Вести с поручений", (r.x + 18, y), 16, GLORY, True)
            y += 24
            for n in prof.news[:4]:
                line, col = E.news_line(xd, n)
                T.text(surf, fit(line, 14, 600), (r.x + 18, y), 14, col, True)
                y += 21
        x0 = r.x + 640
        tasks = prof.tasks()
        T.text(surf, f"Идут поручения: {len(tasks)}/{prof.board_slots()}", (x0, r.y + 58), 18, (150, 200, 240), True)
        y = r.y + 86
        for key, heroes in tasks.items():
            task = heroes[0].task
            t = cfg["templates"][task["id"]]
            tr = pygame.Rect(x0, y, r.right - x0 - 16, 64)
            pygame.draw.rect(surf, (30, 22, 16), tr, border_radius=8)
            pygame.draw.rect(surf, E.RISK[t["risk"]][1], tr, 1, border_radius=8)
            xx = tr.x + 8
            for h in heroes:
                img = hero_fit(data, h.cls, 56)
                surf.blit(img, (xx, tr.bottom - img.get_height() - 4))
                xx += img.get_width() - 4
            T.text(surf, t["name"], (tr.x + 120, tr.y + 8), 17, T.TEXT, True)
            T.text(surf, fit(f"{', '.join(h.name for h in heroes)} · осталось походов: {task['left']} · "
                             f"шанс {task['chance'] * 100:.0f}%", 14, tr.w - 130), (tr.x + 120, tr.y + 36), 14,
                   T.TEXT_DIM)
            y += 70
        if not tasks:
            T.text(surf, "Никто не на задании.", (x0, y + 4), 15, T.TEXT_DIM)
            y += 30
        o = self.offer()
        y = max(y + 10, r.y + 250)
        if not o:
            T.text(surf, "Выберите заказ слева.", (x0, y), 16, T.TEXT_DIM)
            return
        t = cfg["templates"][o["id"]]
        T.text(surf, f"«{t['name']}»: кого отправить ({len(self.team)}/{t['heroes']})", (x0, y), 18, GOLD, True)
        y += 30
        free = self.free_heroes()
        with self.scene.grid(surf, "board_heroes", pygame.Rect(x0, y, r.right - 16 - x0, r.bottom - 110 - y),
                             len(free), 104, 114, gap=8) as cells:
            for i, cell in cells:
                self.hero_cell(surf, free[i], cell, o)
        team = [h for h in free if h.uid in self.team]
        by = r.bottom - 70
        if team:
            p = prof.contract_chance(o["id"], team)
            T.text(surf, f"Шанс успеха: {p * 100:.0f}% · частично: {cfg['chance']['partial'] * 100:.0f}%",
                   (x0, by - 30), 17, BLESS if p >= 0.7 else (240, 180, 80), True)
        if full:
            T.text(surf, "Доска заполнена — больше мест: «Доска поручений» в Стройке", (x0, by - 30), 14, CURSE)
        self.scene.btn(surf, pygame.Rect(r.right - 316, by, 300, 54), "Отправить  (Enter)", "send",
                       len(team) == t["heroes"] and not full, primary=True)

    def hero_cell(self, surf, h, cell, o):
        prof = self.app.profile
        data = prof.data
        if True:
            img = hero_fit(data, h.cls, 84)
            on = h.uid in self.team
            hot = cell.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, T.mix(T.PANEL_DARK, GOLD, 0.25) if on else (44, 32, 22) if hot else (30, 22, 16), cell,
                             border_radius=8)
            pygame.draw.rect(surf, GOLD if on else (80, 60, 40), cell, 2 if on else 1, border_radius=8)
            surf.blit(img, (cell.centerx - img.get_width() // 2, cell.y + 4))
            T.text(surf, fit(h.name, 13, 98), (cell.centerx, cell.bottom - 20), 13, T.TEXT, True, center=True)
            p = prof.contract_chance(o["id"], [h])
            self.scene.hit(cell, ("send_hero", h.uid), [h.name, f"{data.classes[h.cls]['name']} · ранг {h.rank}",
                                                        f"шанс в одиночку {p * 100:.0f}%"])


# ---------- Горн мастера v2: тигель → примитивы → изделие (sim/forge.py, game/forge_games.py) ----------

FORGE_MODES = (("crucible", "1 Тигель"), ("hammer", "2 Ковка"), ("item", "3 Изделие"), ("store", "Склад"),
               ("damascus", "Дамаск"), ("orders", "Заказы"))


class ForgeOverlay(SmithOverlay):
    """Кузня: тигель (сплав по весам и жару) → слиток → примитивы (ковка руками или литьё в форму) → изделие
    с закалкой и отпуском. Дамаск (пакет и сварка) — ветка по книге."""

    def __init__(self, scene, ws="ws_forge"):
        super().__init__(scene, ws)
        self.mode = "crucible"
        self.ing_sel = None
        self.sub = "stack"

    def modes(self):
        return [m for m in FORGE_MODES if m[0] != "damascus"]           # дамаск — пока убран

    def act(self, action, button=1):
        from game import forge_games as FGM
        from sim import forge as FG
        prof = self.app.profile
        xd = prof.xd
        kind = action[0] if isinstance(action, tuple) else action
        seed = int(self.scene.clock * 1000) + prof.art_n
        if kind == "mode":
            self.mode = action[1]
            self.result = None
        elif kind == "alloy":
            aid = action[1]
            if not FG.can_melt(aid, prof.forge_level()):
                self.scene.say("Горн не даёт такого жара — улучшите Горн мастера в Стройке")
                return
            game = FGM.CrucibleGame(aid, prof.mats, prof.f_tools(), prof.forge_level(), seed)

            def done(q):
                r = game.result
                out = prof.crucible(r["alloy"], r["charge"], r["purity"], r["heat"], r["mold"], r["pour"],
                                    casts=r.get("casts"), spilt=r.get("spilt", 0)) if r else None
                if isinstance(out, dict) and "casts" in out:     # разливка в формы: литые примитивы + слиток
                    c_, ing = out["casts"], out["ingot"]
                    lines = [(f"Отлито: {len(c_)} из {len(r['casts'])} форм", GLORY)]
                    for p_ in c_:
                        lines.append((f"{FG.PRIMS[p_['kind']]['name']} · {p_['len']} мм · качество {p_['q'] * 100:.0f}%",
                                      T.TEXT))
                    if r.get("spilt"):
                        lines.append((f"пролито {r['spilt']} г", CURSE))
                    if ing:
                        self.ing_sel = ing["uid"]
                        lines.append((f"остаток — слиток {ing['mass']} г", T.TEXT))
                    self.result = (lines, None)
                elif isinstance(out, list):
                    self.result = ([(f"Отлито: {FG.PRIMS[out[0]['kind']]['name'].lower()} ×{len(out)}", GLORY),
                                    (f"качество {out[0]['q'] * 100:.0f}% (литьё)", T.TEXT)], None)
                elif out:
                    self.ing_sel = out["uid"]
                    self.result = ([(f"Слиток {FG.ALLOYS[out['alloy']]['name']} · {out['mass']} г", GLORY),
                                    (f"качество {out['q'] * 100:.0f}% · чистота {out['purity'] * 100:.0f}%", T.TEXT)],
                                   None)
            self.run_game(game, f"Тигель: {FG.ALLOYS[aid]['name']}", done)
        elif kind == "ingot":
            self.ing_sel = action[1]
        elif kind == "prim":
            ing = next((i for i in prof.forge["ingots"] if i["uid"] == self.ing_sel), None)
            pk = action[1]
            if ing is None:
                self.scene.say("Выберите слиток")
                return
            if ing["mass"] < FG.PRIMS[pk]["mass"]:
                self.scene.say("Слиток мал для этого примитива")
                return
            from game.forge_card_game import CardGame
            game = CardGame(ing["alloy"], pk, prof.f_tools(), prof.forge_level(), seed)
            iu = ing["uid"]

            def done(q):
                if game.result:
                    p = prof.forge_prim(iu, pk, game.result["score"], game.result.get("len"))
                    self.result = ([(f"{FG.PRIMS[pk]['name']} готов", GLORY),
                                    (f"качество {p['q'] * 100:.0f}% · длина {p['len']} мм "
                                     f"(нужно {FG.PRIMS[pk]['len']})", T.TEXT)], None) if p else None
            self.run_game(game, f"Ковка: {FG.PRIMS[pk]['name'].lower()}", done)
        elif kind == "craft":                       # вещи кузни — только по техкарте из слитка
            self.craft_whole()
        elif kind == "sub":
            self.sub = action[1]
        elif kind == "to_ingot":
            ing = prof.damascus_ingot(action[1])
            self.scene.say("Пакет стал слитком дамаска — в ковку" if ing else "Нужен сваренный пакет")
        else:
            super().act(action, button)

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.mode == "item":
            self.act("craft")
            return True
        return False

    def draw(self, surf):
        prof = self.app.profile
        if not self.level():
            return StationOverlay.draw(self, surf)
        r = self.frame(surf)
        modes = [(m, f"{i + 1} {lab.split(' ', 1)[-1]}") for i, (m, lab) in enumerate(self.modes())]
        self.scene.seg(surf, r.x + 260, r.y + 12, modes, self.mode, "mode", h=34)
        body = pygame.Rect(r.x + 18, r.y + 60, r.w - 36, r.h - 74)
        getattr(self, "draw_" + self.mode, self.draw_crucible)(surf, body)
        if self.result:
            self.draw_result(surf, r)

    def tool_line(self, surf, x, y, kinds):
        from sim import forge as FG
        prof = self.app.profile
        own = [FG.TOOLS[t][0] for t in FG.TOOLS if FG.TOOLS[t][2] in kinds and prof.f_has(t)]
        s_ = ("есть: " + ", ".join(own)) if own else "приборов нет — бродячий кузнец (Рынок)"
        w = self.rect.right - 30 - x
        tr = T.text(surf, fit(s_, 13, w), (x, y), 13, T.TEXT_DIM)
        if own:
            self.scene.hit(tr, None, ["Есть в кузне:"] + own)

    def draw_crucible(self, surf, r):
        from sim import forge as FG
        prof = self.app.profile
        tools = prof.f_tools()
        lv = prof.forge_level()
        T.text(surf, f"Сплавы · горн даёт до {FG.max_temp(lv)} °C", (r.x, r.y), 18, GLORY, True)
        self.tool_line(surf, r.x + 330, r.y + 4, ("forge", "mold", "gauge"))
        alloys = [a for a in FG.ALLOYS if not FG.ALLOYS[a].get("nocrucible")]
        with self.scene.grid(surf, "forge_alloys", pygame.Rect(r.x, r.y + 34, r.w, r.h - 34), len(alloys), 300, 112,
                             gap=10) as cells:
            for i, cr in cells:
                aid = alloys[i]
                a = FG.ALLOYS[aid]
                known = aid in FG.known_alloys(tools)
                melt_ok = FG.can_melt(aid, lv)
                hot = cr.collidepoint(self.scene.mouse)
                pygame.draw.rect(surf, (52, 38, 26) if hot and known else (30, 22, 16), cr, border_radius=10)
                pygame.draw.rect(surf, a["color"] if known else (70, 60, 50), cr, 2 if hot else 1, border_radius=10)
                ic = forge_icon(f"ingot_{aid}", 30)
                if ic is not None:
                    if not known:
                        ic = ic.copy()
                        ic.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    surf.blit(ic, (cr.x + 34 - ic.get_width() // 2, cr.y + 26 - ic.get_height() // 2))
                else:
                    pygame.draw.rect(surf, a["color"] if known else (60, 56, 52), (cr.x + 12, cr.y + 14, 44, 24),
                                     border_radius=4)
                T.text(surf, a["name"], (cr.x + 66, cr.y + 12), 16, T.TEXT if known else T.TEXT_DIM, True)
                if not known:
                    T.text(surf, FG.BOOKS[a["book"]][0], (cr.x + 12, cr.y + 50), 12, T.TEXT_DIM)
                    T.text(surf, "книга — у бродячего кузнеца или в походах", (cr.x + 12, cr.y + 70), 12, T.TEXT_DIM)
                else:
                    need = FG.charge_need(aid, 300)
                    have = all(prof.mats.get(m, 0) >= v for m, v in need.items())
                    T.text(surf, f"{a['melt']} °C · " + ", ".join(f"{res_name(prof.xd, m)} {v}" for m, v in need.items()),
                           (cr.x + 12, cr.y + 50), 12, T.TEXT if have else CURSE)
                    T.text(surf, "на слиток 300 г" + ("" if melt_ok else " · горн слаб"), (cr.x + 12, cr.y + 70), 12,
                           T.TEXT_DIM if melt_ok else CURSE)
                self.scene.hit(cr, ("alloy", aid) if known else None,
                               [a["name"], f"твёрдость {a['hard'] * 100:.0f}% · вязкость {a['tough'] * 100:.0f}%",
                                "закаливается" if a.get("quench") else "не закаливается",
                                "клик — в тигель" if known else "нужна книга"])

    def draw_hammer(self, surf, r):
        from sim import forge as FG
        prof = self.app.profile
        ings = prof.forge["ingots"]
        T.text(surf, "Слитки — выберите и выкуйте примитив", (r.x, r.y), 18, GLORY, True)
        self.tool_line(surf, r.x + 420, r.y + 4, ("hammer", "anvil"))
        half = pygame.Rect(r.x, r.y + 34, r.w // 2 - 10, r.h - 34)
        with self.scene.grid(surf, "forge_ingots", half, len(ings), 200, 70, gap=8) as cells:
            for i, cr in cells:
                ing = ings[i]
                a = FG.ALLOYS[ing["alloy"]]
                on = ing["uid"] == self.ing_sel
                pygame.draw.rect(surf, (64, 46, 30) if on else (30, 22, 16), cr, border_radius=8)
                pygame.draw.rect(surf, GOLD if on else a["color"], cr, 2 if on else 1, border_radius=8)
                ic = forge_icon(f"ingot_{ing['alloy']}", 40)
                if ic is not None:
                    surf.blit(ic, (cr.x + 42 - ic.get_width() // 2, cr.centery - ic.get_height() // 2))
                else:
                    pygame.draw.polygon(surf, a["color"], [(cr.x + 12, cr.y + 48), (cr.x + 22, cr.y + 22),
                                                           (cr.x + 62, cr.y + 22), (cr.x + 72, cr.y + 48)])
                T.text(surf, fit(a["name"], 14, cr.w - 90), (cr.x + 84, cr.y + 10), 14, T.TEXT, True)
                T.text(surf, f"{ing['mass']} г · {ing['q'] * 100:.0f}%", (cr.x + 84, cr.y + 36), 13, T.TEXT_DIM)
                self.scene.hit(cr, ("ingot", ing["uid"]), [a["name"], f"{ing['mass']} г, качество {ing['q'] * 100:.0f}%"])
        if not ings:
            T.text(surf, "Слитков нет — тигель (1).", (half.x, half.y + 6), 15, T.TEXT_DIM)
        x0 = r.x + r.w // 2 + 10
        ing = next((i for i in ings if i["uid"] == self.ing_sel), None)
        T.text(surf, "Примитив:", (x0, r.y + 34), 16, T.TEXT, True)
        for j, (pk, p) in enumerate(FG.PRIMS.items()):
            br = pygame.Rect(x0, r.y + 64 + j * 74, r.right - x0, 66)
            ok = ing is not None and ing["mass"] >= p["mass"]
            hot = br.collidepoint(self.scene.mouse)
            pygame.draw.rect(surf, (52, 38, 26) if hot and ok else (30, 22, 16), br, border_radius=8)
            pygame.draw.rect(surf, (200, 160, 90) if ok else (70, 60, 50), br, 1, border_radius=8)
            T.text(surf, f"{p['name']} — {p['mass']} г", (br.x + 14, br.y + 10), 16, T.TEXT if ok else T.TEXT_DIM, True)
            uses = ", ".join(prof.xd["artifacts"]["kinds"][k]["name"].lower() for k, v in FG.RECIPES.items() if pk in v)
            T.text(surf, f"толщина {p['thick']} мм, длина {p['len']} мм · для: {uses}", (br.x + 14, br.y + 38), 12,
                   T.TEXT_DIM)
            self.scene.hit(br, ("prim", pk) if ok else None, [p["name"], "клик — ковать из выбранного слитка"])

    def draw_item(self, surf, r):
        StationOverlay.draw_craft(self, surf, self.rect)

    def draw_store(self, surf, r):
        from sim import forge as FG
        prof = self.app.profile
        prims = prof.forge["prims"]
        T.text(surf, f"Примитивы: {len(prims)} · слитки: {len(prof.forge['ingots'])}", (r.x, r.y), 18, GLORY, True)
        with self.scene.grid(surf, "forge_prims", pygame.Rect(r.x, r.y + 34, r.w, r.h - 34), len(prims), 190, 64,
                             gap=8) as cells:
            for i, cr in cells:
                p = prims[i]
                a = FG.ALLOYS[p["alloy"]]
                pygame.draw.rect(surf, (30, 22, 16), cr, border_radius=8)
                pygame.draw.rect(surf, a["color"], cr, 1, border_radius=8)
                ic = forge_icon(f"prim_{p['kind']}", 40, tuple(a["color"]))
                if ic is not None:
                    surf.blit(ic, (cr.x + 35 - ic.get_width() // 2, cr.centery - ic.get_height() // 2))
                else:
                    th = max(3, int(FG.PRIMS[p["kind"]]["thick"] * 2))
                    pygame.draw.rect(surf, a["color"], (cr.x + 10, cr.y + 32 - th // 2, 50, th), border_radius=2)
                T.text(surf, f"{FG.PRIMS[p['kind']]['name']}" + (" (литой)" if p.get("cast") else ""),
                       (cr.x + 70, cr.y + 8), 14, T.TEXT, True)
                T.text(surf, fit(f"{a['name']} · {p['q'] * 100:.0f}% · {p.get('len', FG.PRIMS[p['kind']]['len'])} мм",
                                 12, cr.w - 76), (cr.x + 70, cr.y + 34), 12, T.TEXT_DIM)
        if not prims:
            T.text(surf, "Пусто — ковка (2) или литьё в формы.", (r.x, r.y + 40), 15, T.TEXT_DIM)

    def draw_damascus(self, surf, r):
        prof = self.app.profile
        self.scene.seg(surf, r.x, r.y, (("stack", "Пакет"), ("weld", "Сварка")), self.sub, "sub", h=30)
        self.mode = self.sub
        try:
            getattr(self, "draw_" + self.sub)(surf, pygame.Rect(r.x, r.y + 40, r.w, r.h - 40))
        finally:
            self.mode = "damascus"
        welded = [b for b in prof.smith["billets"] if b.get("welded")]
        y = r.bottom - 46
        for b in welded[:3]:
            self.scene.btn(surf, pygame.Rect(r.right - 300, y, 290, 38), f"Пакет {b['mass']} г → слиток дамаска",
                           ("to_ingot", b["uid"]), True, primary=True)
            y -= 44


class MineRoom(RoomScene):
    """Шахта: рабочие добывают руды и самоцветы, пока игра открыта; склад, кирки, вагонетки, глубина."""
    room = "mine"
    title = "Шахта"
    sub = "Добыча идёт, пока игра открыта — забирайте со склада"
    art = "room_mine"
    dim = 150
    mats = True

    def room_act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "collect":
            got, stones = prof.mine_collect()
            n = sum(got.values())
            self.say(f"Забрано: {n} ед." + (f" и самоцветов: {len(stones)}" if stones else "") if n or stones else
                     "Склад пуст")
        elif kind == "up":
            if not prof.mine_upgrade(action[1]):
                self.say("Не хватает золота")

    FLOORS = (0.36, 0.527, 0.699, 0.90)     # полы туннелей на иллюстрации шахты (доли высоты)
    TUNNEL = (0.04, 0.78)                   # туннели по ширине (справа — подъёмник)

    def draw_backdrop(self, surf):
        """Шахта в разрезе (иллюстрация) — во всю комнату, без затемнения сверху."""
        from ui import illustrations as IL
        top, bottom = TOP_H, strip_y()
        self.view = pygame.Rect(0, top, T.SCREEN_W, bottom - top)
        path = os.path.join(IL.DIR, "hd", "room_mine.png")
        if not os.path.exists(path):
            return super().draw_backdrop(surf)
        if getattr(self, "_img_size", None) != self.view.size:
            src = pygame.image.load(path)
            k = max(self.view.w / src.get_width(), self.view.h / src.get_height())
            img = pygame.transform.smoothscale(src, (int(src.get_width() * k) + 1, int(src.get_height() * k) + 1))
            self._img = img
            self._img_size = self.view.size
            self._ox = (self.view.w - img.get_width()) // 2
            self._oy = self.view.bottom - img.get_height()
        surf.blit(self._img, (self._ox, self._oy))

    def at(self, fx, fy):
        img = getattr(self, "_img", None)
        if img is None:
            return (self.view.x + fx * self.view.w, self.view.y + fy * self.view.h)
        return (self._ox + fx * img.get_width(), self._oy + fy * img.get_height())

    def draw_room(self, surf):
        from sim import forge as FG
        prof = self.app.profile
        m = prof.mine
        xd = prof.xd
        levels = FG.MINE["depths"]
        for i, d in enumerate(levels):
            open_ = i <= m["depth"]
            floor = self.at(0, self.FLOORS[i])[1]
            x0 = self.at(self.TUNNEL[0], 0)[0]
            x1 = self.at(self.TUNNEL[1], 0)[0]
            band_h = (self.at(0, self.FLOORS[0])[1] - self.at(0, 0.21)[1])
            band = pygame.Rect(x0, floor - band_h, x1 - x0, band_h)
            if not open_:                                    # не вскрыт — тёмный завал
                sh = pygame.Surface(band.size, pygame.SRCALPHA)
                sh.fill((6, 5, 4, 205))
                surf.blit(sh, band)
                T.text(surf, f"{d['name']} — не вскрыт", (band.centerx, band.centery), 18, T.TEXT_DIM, True,
                       center=True, shadow=True)
                continue
            label = d["name"] + " · " + ", ".join(res_name(xd, k) for k in d["mats"]) + \
                (" · сырые самоцветы" if d.get("rough") else "")
            T.text(surf, label, (band.x + 14, band.y + 10), 14, (240, 225, 200), True, shadow=True)
            n = m["workers"] if i == m["depth"] else max(1, m["workers"] // (m["depth"] + 1))
            from game import metal_view as MV
            cart = MV.prop("mine_cart", None, max(8, int(44 * self.view.h / 560)))
            if cart is not None:                             # вагонетка в конце туннеля — левее панели склада
                cx_ = min(band.right, T.SCREEN_W - 16 - 420) - cart.get_width() - 14
                surf.blit(cart, (cx_, floor - cart.get_height()))
            for w in range(n):                               # горняки с кирками (лист MH; нет — простые фигурки)
                px = band.x + 80 + w * (band.w - 160) / max(1, 7) + 6 * math.sin(self.clock * 1.7 + w)
                py = floor - 4
                self.draw_miner(surf, px, py, self.clock * 5 + w * 1.3, flip=w % 2 == 1)
        self.draw_mine_panel(surf)

    def draw_miner(self, surf, x, y, t, flip=False):
        s = (self.view.h / 560)
        frames = mine_frames(max(8, int(62 * s)))
        if frames:                                         # лист MH: замах — середина — удар (общий холст)
            v = math.sin(t)
            img = frames[0] if v > 0.35 else frames[2] if v < -0.35 else frames[1]
            if flip:
                img = pygame.transform.flip(img, True, False)
            surf.blit(img, (x - img.get_width() / 2, y - img.get_height()))
            return
        body = (90, 70, 52)
        pygame.draw.line(surf, body, (x, y - 30 * s), (x, y - 12 * s), max(2, int(6 * s)))
        pygame.draw.line(surf, (60, 48, 38), (x, y - 12 * s), (x - 5 * s, y), max(2, int(4 * s)))
        pygame.draw.line(surf, (60, 48, 38), (x, y - 12 * s), (x + 5 * s, y), max(2, int(4 * s)))
        pygame.draw.circle(surf, (220, 180, 140), (int(x), int(y - 36 * s)), max(3, int(6 * s)))
        pygame.draw.circle(surf, (200, 160, 60), (int(x), int(y - 40 * s)), max(2, int(5 * s)))
        a = math.sin(t) * 0.9 - 0.3
        hx, hy = x + math.cos(a) * 20 * s, y - 28 * s - math.sin(a) * 20 * s
        pygame.draw.line(surf, (120, 90, 60), (x, y - 26 * s), (hx, hy), max(2, int(3 * s)))
        pygame.draw.line(surf, (170, 170, 180), (hx - 7 * s, hy - 4 * s), (hx + 7 * s, hy + 4 * s), max(2, int(3 * s)))

    def draw_mine_panel(self, surf):
        from sim import forge as FG
        prof = self.app.profile
        m = prof.mine
        xd = prof.xd
        top, bottom = TOP_H + 10, strip_y() - 10
        # склад и улучшения — справа, поверх подъёмника
        x0 = T.SCREEN_W - 16 - 420
        panel = pygame.Rect(x0, top, 420, bottom - top)
        T.frame(surf, panel, 220)
        stock = m.get("stock", {})
        cap = FG.mine_cap(m)
        tot = sum(stock.values())
        T.text(surf, f"Склад {tot} / {cap}", (panel.x + 16, panel.y + 12), 20, GLORY, True)
        bar = pygame.Rect(panel.x + 16, panel.y + 42, panel.w - 32, 10)
        pygame.draw.rect(surf, (40, 32, 26), bar, border_radius=5)
        pygame.draw.rect(surf, (230, 180, 100), (bar.x, bar.y, int(bar.w * min(1, tot / max(1, cap))), bar.h),
                         border_radius=5)
        T.text(surf, f"добыча {FG.mine_rate(m):.0f} ед./мин · рабочих {m['workers']}", (panel.x + 16, panel.y + 58), 13,
               T.TEXT_DIM)
        y = panel.y + 84
        for k, v in sorted(stock.items(), key=lambda kv: -kv[1]):
            surf.blit(res_icon(xd, k, 20), (panel.x + 16, y))
            T.text(surf, f"{res_name(xd, k)}: {v}", (panel.x + 42, y + 2), 14, T.TEXT)
            y += 24
        if m.get("rough"):
            T.text(surf, f"сырые самоцветы: {m['rough']}", (panel.x + 16, y + 2), 14, BLESS, True)
            y += 24
        self.btn(surf, pygame.Rect(panel.x + 16, y + 6, panel.w - 32, 44), "Забрать со склада", "collect",
                 tot > 0 or m.get("rough", 0) > 0, primary=True)
        y += 64
        names = {"workers": ("Нанять рабочего", f"рабочих {m['workers']}"),
                 "pick": ("Кирки лучше", f"выработка ×{FG.MINE['pick'][m['pick']][0]}"),
                 "store": ("Склад больше", f"вместимость {cap}"),
                 "cart": ("Вагонетки", f"подъём {FG.MINE['cart'][m['cart']][0]} ед./мин"),
                 "depth": ("Вскрыть горизонт", FG.MINE["depths"][m["depth"]]["name"])}
        for what, (label, now) in names.items():
            cost = FG.mine_next_cost(m, what)
            row = pygame.Rect(panel.x + 16, y, panel.w - 32, 52)
            pygame.draw.rect(surf, (32, 24, 18), row, border_radius=8)
            T.text(surf, label, (row.x + 10, row.y + 6), 15, T.TEXT, True)
            T.text(surf, now, (row.x + 10, row.y + 28), 12, T.TEXT_DIM)
            if cost is None:
                T.text(surf, "предел", (row.right - 90, row.y + 18), 13, GLORY, True)
            else:
                self.btn(surf, pygame.Rect(row.right - 150, row.y + 8, 140, 36), f"{cost}", ("up", what),
                         prof.glory >= cost, primary=True)
            y += 58


# ---------- отдельный экран мастерской ----------

STATION_MATS = {"ws_forge": ["ore", "coal", "copper", "tin", "silver", "gold", "meteor", "embersteel", "stardust"],
                "ws_jewel": ["gems", "pearl", "stardust"],
                "ws_alchemy": ["herbs", "pearl", "embersteel", "stardust"],
                "ws_leather": ["leather", "pearl", "embersteel", "stardust"]}
STATION_ART = {"ws_forge": "ws_bench_forge", "ws_jewel": "ws_bench_jewel", "ws_alchemy": "ws_bench_alchemy",
               "ws_leather": "ws_bench_leather"}


class StationScene(RoomScene):
    """Мастерская мастера — отдельный экран: окно во весь экран, свои вкладки (1–9, Tab — дальше, Shift+Tab —
    назад), в шапке — только свои ресурсы. Esc — назад в Мастерскую."""
    room = "workshop"
    mats = True
    dim = 175

    def __init__(self, app, ws):
        super().__init__(app)
        self.ws = ws
        self.overlay = (ForgeOverlay if ws == "ws_forge" else StationOverlay)(self, ws)
        self.overlay.full = True
        self.art = STATION_ART.get(ws, "room_workshop")
        self.title = self.app.profile.xd["buildings"][ws]["name"]

    def mat_keys(self):
        allm = self.app.profile.xd.get("materials", {})
        return [k for k in STATION_MATS.get(self.ws, list(allm)) if k in allm]

    def draw_backdrop(self, surf):
        from ui import illustrations as IL
        if os.path.exists(os.path.join(IL.DIR, "hd", f"{self.art}.png")):
            self.backdrop(surf, self.art, "tavern", dim=self.dim)
        else:
            self.backdrop(surf, room_art("room_workshop"), "tavern", dim=self.dim)

    def draw(self, surf):
        self.hits = []
        surf.fill(T.BG)
        self.draw_backdrop(surf)
        self.overlay.draw(surf)
        self.draw_top(surf)
        self.draw_tip(surf)
        self.draw_toast(surf, T.SCREEN_H - 30)

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind in ("close", "room"):
            go(self.app, "workshop")
        elif kind == "menu":
            self.app.to_title()
        else:
            self.overlay.act(action, button)

    def key(self, k):
        if k == pygame.K_ESCAPE:
            go(self.app, "workshop")
            return
        modes = self.overlay.modes() if hasattr(self.overlay, "modes") else []
        if modes and pygame.K_1 <= k <= pygame.K_9 and k - pygame.K_1 < len(modes):
            self.overlay.act(("mode", modes[k - pygame.K_1][0]))
            return
        if modes and k == pygame.K_TAB:
            back = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) if pygame.get_init() else False
            i = next((j for j, (m, _) in enumerate(modes) if m == self.overlay.mode), 0)
            self.overlay.act(("mode", modes[(i + (-1 if back else 1)) % len(modes)][0]))
            return
        self.overlay.key(k)


# ---------- Стройка ----------

BUILD_GROUPS = (("Таверна", ("u:hall", "u:renown", "u:guests", "u:provisions")),
                ("Мастерская", ("ws_forge", "ws_jewel", "ws_leather", "ws_alchemy")),
                ("Двор", ("board", "dorm")),
                ("Поход", ("smithy", "yard", "library", "altar", "infirmary")))


class BuildRoom(RoomScene):
    """Стройка: улучшения зала и постройки (за золото и трофеи глав), сгруппированы по комнатам."""
    room = "build"
    title = "Стройка"
    sub = "Золото — за бои, акты и поручения; трофеи глав — за боссов"
    art = "room_build"
    dim = 165

    def room_act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "buy":
            if not prof.buy_upgrade(action[1]):
                self.say("Не хватает золота")
        elif kind == "build":
            if not prof.build(action[1]):
                self.say("Не хватает золота или трофеев глав")

    def items(self):
        prof = self.app.profile
        xd = prof.xd
        out = []
        for group, ids in BUILD_GROUPS:
            for bid in ids:
                if bid.startswith("u:"):
                    uid = bid[2:]
                    if uid not in xd["tavern"]["upgrades"]:
                        continue
                    up = xd["tavern"]["upgrades"][uid]
                    lv, top = prof.level(uid), len(up["costs"])
                    cost = prof.upgrade_cost(uid)
                    out.append((group, up["name"], up["desc"], lv, top, value_text(prof, uid, lv),
                                value_text(prof, uid, lv + 1) if cost is not None else None,
                                {"glory": cost} if cost is not None else None, ("buy", uid)))
                elif bid in xd.get("buildings", {}):
                    b = xd["buildings"][bid]
                    lv, top = prof.building_level(bid), len(b["levels"])
                    if not prof.master_free(bid):         # мастерская — после спасения мастера
                        out.append((group, b["name"], b["desc"], 0, top, "мастер в плену",
                                    f"спасите: босс главы «{prof.master_chapter(bid)}»", None, ("locked", bid)))
                        continue
                    out.append((group, b["name"], b["desc"], lv, top, b["levels"][lv - 1]["text"] if lv else "не построено",
                                b["levels"][lv]["text"] if lv < top else None, prof.building_cost(bid), ("build", bid)))
        return out

    def draw_room(self, surf):
        prof = self.app.profile
        items = self.items()
        cols = 4
        cw = (T.SCREEN_W - 32 - 12 * (cols - 1)) // cols
        rows = (len(items) + cols - 1) // cols
        ch = min(160, (strip_y() - TOP_H - 20 - 10 * (rows - 1)) // rows)
        for i, (group, name, desc, lv, top, now, nxt, cost, action) in enumerate(items):
            r = pygame.Rect(16 + (i % cols) * (cw + 12), TOP_H + 12 + (i // cols) * (ch + 10), cw, ch)
            done = nxt is None
            T.frame(surf, r, 236, accent=GLORY if lv else T.PANEL_EDGE)
            nx = T.text(surf, fit(name, 18, cw - 120), (r.x + 14, r.y + 10), 18, T.TEXT, True).right
            for k in range(top):
                pygame.draw.circle(surf, GLORY if k < lv else (70, 62, 54), (nx + 14 + k * 14, r.y + 21), 5)
            T.text(surf, group, (r.right - 12 - T.font(12).size(group)[0], r.y + 12), 12, T.TEXT_DIM)
            T.text(surf, fit(desc, 13, cw - 28), (r.x + 14, r.y + 36), 13, T.TEXT_DIM)
            T.text(surf, fit("Сейчас: " + now, 14, cw - 28), (r.x + 14, r.y + 58), 14, T.TEXT)
            if done:
                T.text(surf, "построено полностью", (r.x + 14, r.bottom - 30), 14, GLORY, True)
                continue
            if action[0] == "locked":
                T.text(surf, fit(nxt, 14, cw - 28), (r.x + 14, r.y + 78), 14, CURSE, True)
                T.text(surf, "мастерская откроется с мастером", (r.x + 14, r.bottom - 34), 13, T.TEXT_DIM)
                self.hit(r, None, [(name, GLORY), desc, now, nxt])
                continue
            T.text(surf, fit("Дальше: " + nxt, 14, cw - 28), (r.x + 14, r.y + 78), 14, BLESS)
            cost_icons(self, surf, prof, cost, r.x + 14, r.bottom - 40, size=22)
            ok = prof.can_pay(cost)
            self.btn(surf, pygame.Rect(r.right - 118, r.bottom - 46, 106, 36),
                     "Построить" if action[0] == "build" else "Купить", action, ok, primary=True)
            self.hit(r, None, [(name, GLORY), desc, "Сейчас: " + now, "Дальше: " + nxt])


def value_text(prof, uid, lv):
    up = prof.xd["tavern"]["upgrades"][uid]
    v = up["values"][min(lv, len(up["values"]) - 1)]
    if uid == "hall":
        return f"героев в зале: {v}"
    if uid == "renown":
        return f"ветераны {v['2']}%, герои {v['3']}%"
    if uid == "provisions":
        return f"+{v} золота в начале похода"
    if uid == "guests":
        classes = []
        for k in range(1, lv + 1):
            classes += up["values"][min(k, len(up["values"]) - 1)]
        return ", ".join(prof.data.classes[c]["name"] for c in classes if c in prof.data.classes) or "8 основных классов"
    return str(v)


# ---------- Зал славы: кладбище и летопись ----------

class FameRoom(RoomScene):
    """Зал славы: два прохода — на кладбище павших и к летописи героев."""
    room = "fame"
    title = "Зал славы"
    art = "room_fame"
    dim = 40

    def room_act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "cemetery":
            self.app.switch(CemeteryScene(self.app))
        elif kind == "book":
            open_book(self.app, None)

    def room_key(self, k):
        if k in (pygame.K_LEFT, pygame.K_a):
            self.act("cemetery")
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.act("book")

    ARCHES = ((0.16, 0.36), (0.61, 0.83))           # проходы на иллюстрации room_fame: доли ширины

    def draw_room(self, surf):
        prof = self.app.profile
        pages = book_pages(prof)
        if room_art(self.art, None):                  # арки нарисованы на иллюстрации — они и есть проходы
            img_h = T.SCREEN_W * 2 // 3
            top = (T.SCREEN_H - img_h) // 2
            for (x0, x1), (act, title, sub) in zip(self.ARCHES, (
                    ("cemetery", "Кладбище", f"павших героев: {len(prof.fallen)} · ← клавиша"),
                    ("book", "Летопись", f"героев в книге: {len(pages)} · клавиша →"))):
                r = pygame.Rect(int(x0 * T.SCREEN_W), top + int(0.12 * img_h), int((x1 - x0) * T.SCREEN_W),
                                int(0.47 * img_h))
                hot = r.collidepoint(self.mouse)
                if hot:
                    light(surf, r.center, r.w * 3 // 4, (255, 200, 120), 0.3)
                    pygame.draw.rect(surf, GOLD, r.inflate(10, 10), 2, border_top_left_radius=r.w // 2,
                                     border_top_right_radius=r.w // 2)
                plate(surf, (r.centerx, r.bottom + 16), title, sub, GLORY if hot else T.TEXT, w=300)
                self.hit(r.union(pygame.Rect(r.centerx - 150, r.bottom + 16, 300, 50)), act, [title, "клик — пройти"])
            return
        for i, (act, title, sub, art, mood) in enumerate((
                ("cemetery", "Кладбище", f"павших героев: {len(prof.fallen)}", room_art("room_cemetery", "defeat"), "act"),
                ("book", "Летопись", f"героев в книге: {len(pages)}", room_art("room_library", "tavern"), "tavern"))):
            r = pygame.Rect(T.SCREEN_W // 2 - 560 + i * 600, TOP_H + 40, 520, strip_y() - TOP_H - 70)
            hot = r.collidepoint(self.mouse)
            T.frame(surf, r, 240, accent=GOLD if hot else T.AMBER_DIM)
            arch = pygame.Rect(r.x + 30, r.y + 30, r.w - 60, r.h - 150)
            img = IL.get(art, mood, arch.size, hd=True)
            mask = pygame.Surface(arch.size, pygame.SRCALPHA)     # проём арки: полукруг сверху
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, arch.w // 2, arch.w, arch.h - arch.w // 2))
            pygame.draw.ellipse(mask, (255, 255, 255, 255), (0, 0, arch.w, arch.w))
            pic = pygame.Surface(arch.size, pygame.SRCALPHA)
            pic.blit(img, (0, 0))
            pic.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            if not hot:
                pic.fill((170, 160, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(pic, arch)
            pygame.draw.arc(surf, GOLD if hot else (110, 84, 52), (arch.x, arch.y, arch.w, arch.w), 0, math.pi, 4)
            T.text(surf, title, (r.centerx, r.bottom - 106), 30, GLORY if hot else T.TEXT, True, center=True, shadow=True)
            T.text(surf, sub, (r.centerx, r.bottom - 66), 16, T.TEXT_DIM, center=True)
            T.text(surf, "← клавиша" if i == 0 else "клавиша →", (r.centerx, r.bottom - 40), 13, T.TEXT_DIM,
                   center=True)
            self.hit(r, act, [title, "клик — пройти"])


class CemeteryScene(RoomScene):
    """Кладбище: идти вперёд-назад (← → или A D, колесо, клик по могиле); могилы павших — в шахматном порядке;
    у ближайшей — кто здесь лежит. L или клик — летопись павшего."""
    room = "fame"
    title = "Кладбище"
    art = "room_cemetery"
    dim = 120
    STEP = 190

    def __init__(self, app):
        super().__init__(app)
        self.graves = list(app.profile.fallen)
        self.cam = 180.0
        self.target = None
        self.walk = 0.0

    @property
    def sub(self):
        return "← → или A D — идти, колесо — быстрее; L — летопись павшего" if self.graves else ""

    def escape(self):
        go(self.app, "fame")

    def gx(self, i):
        return 260 + i * self.STEP

    def wheel(self, dy):
        self.target = self.clamp(self.cam - dy * self.STEP)

    def clamp(self, x):
        return max(120.0, min(self.gx(max(0, len(self.graves) - 1)) + 160.0, x))

    def update(self, dt):
        super().update(dt)
        keys = pygame.key.get_pressed() if pygame.display.get_init() else None
        d = 0
        if keys:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                d -= 1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                d += 1
        if d:
            self.target = None
            self.cam = self.clamp(self.cam + d * 380 * dt)
            self.walk += dt
        elif self.target is not None:
            step = (self.target - self.cam) * min(1.0, dt * 6)
            self.cam += step
            self.walk += dt if abs(step) > 0.5 else 0
            if abs(self.target - self.cam) < 1:
                self.target = None

    def nearest(self):
        if not self.graves:
            return None
        i = min(range(len(self.graves)), key=lambda k: abs(self.gx(k) - self.cam))
        return i if abs(self.gx(i) - self.cam) < 130 else None

    def room_key(self, k):
        i = self.nearest()
        if k in (pygame.K_l, pygame.K_RETURN, pygame.K_SPACE) and i is not None:
            self.open(i)

    def open(self, i):
        f = self.graves[i]
        open_book(self.app, ("fallen", f.get("name"), i), back=lambda: self.app.switch(self))

    def room_act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "grave":
            i = action[1]
            if self.nearest() == i:
                self.open(i)
            else:
                self.target = self.clamp(float(self.gx(i)))

    def draw_backdrop(self, surf):
        img = IL.get(room_art(self.art, "defeat"), "act", (int(T.SCREEN_W * 1.25), int(T.SCREEN_W * 1.25 * 2 / 3)),
                     hd=True)
        x = -int((self.cam * 0.12) % max(1, img.get_width() - T.SCREEN_W))
        surf.blit(img, (x, (T.SCREEN_H - img.get_height()) // 2))
        sh = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        sh.fill((8, 10, 16, self.dim))
        surf.blit(sh, (0, 0))

    def draw_room(self, surf):
        back_y, front_y = strip_y() - 210, strip_y() - 70
        if not room_art(self.art, None):             # заглушка: земля и дорожка (на иллюстрации — свои)
            ground = pygame.Surface((T.SCREEN_W, strip_y() - back_y + 30), pygame.SRCALPHA)
            ground.fill((22, 20, 18, 150))
            surf.blit(ground, (0, back_y - 30))
            path = pygame.Rect(0, (back_y + front_y) // 2 - 22, T.SCREEN_W, 44)
            pygame.draw.rect(surf, (52, 44, 36), path)
            for k in range(-1, T.SCREEN_W // 60 + 2):           # камни дорожки, плывут с шагом
                x = k * 60 - int(self.cam) % 60
                pygame.draw.ellipse(surf, (70, 60, 50), (x, path.y + 10 + (k % 2) * 12, 34, 12))
        if not self.graves:
            T.text(surf, "Здесь пока пусто — никто из героев не пал.", (T.SCREEN_W // 2, TOP_H + 120), 22, T.TEXT_DIM,
                   True, center=True, shadow=True)
        near = self.nearest()
        for row in (0, 1):                           # задний ряд, путник, передний ряд
            if row == 1:
                self.draw_walker(surf, (back_y + front_y) // 2 + 14)
            self.draw_graves(surf, row, near, back_y, front_y)
        if near is not None:
            self.draw_epitaph(surf, self.graves[near])
        if self.graves:
            k = len(self.graves)
            pos = (self.cam - 120) / max(1, self.gx(k - 1) + 40)
            bar = pygame.Rect(T.SCREEN_W // 2 - 200, strip_y() - 18, 400, 6)
            pygame.draw.rect(surf, (40, 34, 30), bar, border_radius=3)
            pygame.draw.circle(surf, T.AMBER, (int(bar.x + bar.w * max(0, min(1, pos))), bar.centery), 6)

    def draw_graves(self, surf, row, near, back_y, front_y):
        for i in range(row, len(self.graves), 2):
            f = self.graves[i]
            sx = int(self.gx(i) - self.cam + T.SCREEN_W // 2)
            if sx < -150 or sx > T.SCREEN_W + 150:
                continue
            front = i % 2 == 1
            gy = front_y if front else back_y
            img = obj_img(f"grave_{1 + i % 3}", 150 if front else 116)
            pos = (sx - img.get_width() // 2, gy - img.get_height())
            if i == near:
                glow_outline(surf, img, pos, (200, 220, 255))
            surf.blit(img, pos)
            nick = f" «{f['titles'][-1]}»" if f.get("titles") else ""
            T.text(surf, f['name'] + nick, (sx, gy + 6), 15 if front else 13, T.TEXT if i == near else T.TEXT_DIM, True,
                   center=True, shadow=True)
            self.hit(pygame.Rect(pos, img.get_size()), ("grave", i), [f["name"] + nick, "клик — подойти / летопись"])

    def draw_walker(self, surf, cy):
        """Путник с фонарём — в центре экрана, между рядами могил."""
        cx = T.SCREEN_W // 2 - 96                 # стоит слева от ближайшей могилы, смотрит на неё
        bob = int(math.sin(self.walk * 9) * 3)
        light(surf, (cx + 21, cy - 46 + bob), 230, (255, 180, 100), 0.42)
        pygame.draw.polygon(surf, (30, 26, 34), [(cx - 16, cy + bob), (cx + 16, cy + bob), (cx + 8, cy - 58 + bob),
                                                (cx - 8, cy - 58 + bob)])
        pygame.draw.circle(surf, (30, 26, 34), (cx, cy - 64 + bob), 12)
        pygame.draw.line(surf, (60, 50, 40), (cx + 12, cy - 40 + bob), (cx + 20, cy - 52 + bob), 3)
        pygame.draw.rect(surf, (255, 200, 110), (cx + 16, cy - 52 + bob, 10, 13))

    def draw_epitaph(self, surf, f):
        prof = self.app.profile
        xd, data = prof.xd, prof.data
        r = pygame.Rect(T.SCREEN_W // 2 - 340, TOP_H + 16, 680, 150)
        T.frame(surf, r, 238, accent=(170, 180, 210))
        img = pygame.transform.grayscale(hero_fit(data, f["cls"], 120))
        surf.blit(img, (r.x + 16, r.bottom - 12 - img.get_height()))
        x = r.x + 30 + img.get_width()
        nick = f" «{f['titles'][-1]}»" if f.get("titles") else ""
        T.text(surf, f["name"] + nick, (x, r.y + 12), 24, T.TEXT, True)
        T.text(surf, f"{data.classes[f['cls']]['name']} · ур. {f['level']}" + (" · в одиночку" if f.get("solo") else ""),
               (x, r.y + 46), 15, GLORY, True)
        where = "Поручение" if f.get("chapter") == "tavern" else \
            f"{xd['chapters'].get(f.get('chapter'), {}).get('name', f.get('chapter'))}, акт {f.get('act')}"
        T.text(surf, fit(f"{where} · {f.get('reason', '')}", 15, r.right - x - 16), (x, r.y + 72), 15, T.TEXT_DIM)
        feats = f.get("feats") or {}
        bits = [f"{feats[k]} {label}" for k, label in FEATS if feats.get(k)]
        if f.get("wins"):
            bits.insert(0, f"побед до того: {f['wins']}")
        T.text(surf, fit(" · ".join(bits), 14, r.right - x - 16), (x, r.y + 98), 14, T.TEXT_DIM)
        T.text(surf, "L или клик — летопись", (x, r.y + 122), 13, (170, 180, 210))


def book_pages(prof):
    """Страницы летописи: живые герои таверны с записями, затем павшие (новые — первыми)."""
    pages = [("live", h) for h in prof.roster if h.chronicle]
    pages += [("fallen", f) for f in reversed(prof.fallen)]
    return pages


def open_book(app, at=None, back=None):
    """Книга летописи; at — ("live", uid) или ("fallen", имя, индекс в списке павших)."""
    prof = app.profile
    pages = book_pages(prof)
    idx = 0
    if at:
        for i, (kind, x) in enumerate(pages):
            if at[0] == "live" and kind == "live" and x.uid == at[1]:
                idx = i
            if at[0] == "fallen" and kind == "fallen" and len(at) > 2 and x is prof.fallen[at[2]]:
                idx = i
    app.switch(BookScene(app, idx, back))


class BookScene(RoomScene):
    """Летопись — книга: на развороте один герой (слева — кто он, справа — его записи). ← → — листать."""
    room = "fame"
    title = "Летопись"
    sub = "← → — листать страницы, Esc — назад"
    art = "room_library"
    dim = 170

    def __init__(self, app, idx=0, back=None):
        super().__init__(app)
        self.pages = book_pages(app.profile)
        self.idx = max(0, min(idx, len(self.pages) - 1))
        self.back = back
        self.turn = 0.0

    def escape(self):
        if self.back:
            self.back()
        else:
            go(self.app, "fame")

    def flip(self, d):
        n = self.idx + d
        if 0 <= n < len(self.pages):
            self.idx = n
            self.turn = 0.25 * d

    def wheel(self, dy):
        self.flip(-1 if dy > 0 else 1)

    def update(self, dt):
        super().update(dt)
        if self.turn:
            self.turn = max(0.0, self.turn - dt) if self.turn > 0 else min(0.0, self.turn + dt)

    def room_key(self, k):
        if k in (pygame.K_LEFT, pygame.K_a, pygame.K_PAGEUP):
            self.flip(-1)
        elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_PAGEDOWN):
            self.flip(1)

    def room_act(self, action, button=1):
        if action == "prev":
            self.flip(-1)
        elif action == "next":
            self.flip(1)

    def draw_backdrop(self, surf):
        self.backdrop(surf, room_art(self.art), "tavern", dim=self.dim)

    def draw_room(self, surf):
        book = pygame.Rect(60, TOP_H + 14, T.SCREEN_W - 120, strip_y() - TOP_H - 30)
        pygame.draw.rect(surf, (70, 30, 24), book.inflate(16, 16), border_radius=14)
        pygame.draw.rect(surf, (40, 16, 12), book.inflate(16, 16), 3, border_radius=14)
        half = book.w // 2
        off = int(self.turn * 120)
        for side in (0, 1):
            pg = pygame.Rect(book.x + side * half + 4, book.y + 4, half - 8, book.h - 8)
            pygame.draw.rect(surf, (226, 210, 176), pg, border_radius=6)
            for k in range(6):
                shade = (210 - k * 6, 194 - k * 6, 160 - k * 6)
                x = pg.right - 1 - k if side == 0 else pg.x + k
                pygame.draw.line(surf, shade, (x, pg.y + 4), (x, pg.bottom - 4))
        pygame.draw.line(surf, (120, 90, 60), (book.centerx, book.y + 4), (book.centerx, book.bottom - 4), 3)
        if not self.pages:
            T.text(surf, "Летопись пуста: у героев ещё нет записей.", book.center, 20, (70, 50, 36), True, center=True)
            return
        kind, x = self.pages[self.idx]
        ink, ink_dim = (58, 38, 24), (110, 84, 60)
        left = pygame.Rect(book.x + 34 + off, book.y + 26, half - 70, book.h - 60)
        right = pygame.Rect(book.centerx + 30 + off, book.y + 26, half - 64, book.h - 60)
        self.draw_left(surf, left, kind, x, ink, ink_dim)
        self.draw_right(surf, right, kind, x, ink, ink_dim)
        T.text(surf, f"{self.idx + 1}", (book.x + 40, book.bottom - 28), 14, ink_dim, True)
        T.text(surf, f"{self.idx + 1} / {len(self.pages)}", (book.right - 80, book.bottom - 28), 14, ink_dim, True)
        if self.idx > 0:
            self.btn(surf, pygame.Rect(book.x - 52, book.centery - 40, 40, 80), "<", "prev")
        if self.idx < len(self.pages) - 1:
            self.btn(surf, pygame.Rect(book.right + 12, book.centery - 40, 40, 80), ">", "next")

    def draw_left(self, surf, r, kind, x, ink, ink_dim):
        prof = self.app.profile
        xd, data = prof.xd, prof.data
        titles = (xd.get("chronicle") or {}).get("titles", {})
        if kind == "live":
            h = x
            name, cls, level = h.name, h.cls, h.level
            nicks = [titles[t]["name"] for t in h.titles if t in titles]
            feats = h.feats
            status = ("Живёт в общежитии" if h.dorm else "В таверне") + (f" · ветеран, побед {h.vet.get('wins', 0)}"
                                                                         if h.vet else "")
            rank = xd["tavern"]["ranks"][str(h.rank)]["name"]
        else:
            name, cls, level = x["name"], x["cls"], x["level"]
            nicks = list(x.get("titles") or [])
            feats = x.get("feats") or {}
            where = "на поручении" if x.get("chapter") == "tavern" else \
                xd["chapters"].get(x.get("chapter"), {}).get("name", x.get("chapter"))
            status = f"Пал: {where} — {x.get('reason', '')}"
            rank = "павший"
        img = hero_fit(data, cls, 250)
        if kind == "fallen":
            img = pygame.transform.grayscale(img)
        T.text(surf, name + (f" «{nicks[-1]}»" if nicks else ""), (r.centerx, r.y + 4), 28, ink, True, center=True)
        T.text(surf, f"{data.classes[cls]['name']} · {rank} · ур. {level}", (r.centerx, r.y + 42), 16, ink_dim, True,
               center=True)
        surf.blit(img, (r.centerx - img.get_width() // 2, r.y + 330 - img.get_height()))
        pygame.draw.line(surf, ink_dim, (r.x + 40, r.y + 340), (r.right - 40, r.y + 340))
        y = r.y + 354
        for ln in T.wrap(status, 17, r.w - 20, True):
            T.text(surf, ln, (r.centerx, y), 17, (130, 40, 30) if kind == "fallen" else ink, True, center=True)
            y += 23
        y += 10
        if nicks:
            T.text(surf, "Прозвища: " + ", ".join(nicks), (r.centerx, y), 16, ink, True, center=True)
            y += 28
        bits = [f"{feats[k]} {label}" for k, label in FEATS if feats.get(k)]
        for ln in T.wrap(" · ".join(bits) or "подвигов пока нет", 16, r.w - 20):
            T.text(surf, ln, (r.centerx, y), 16, ink_dim, center=True)
            y += 22

    def draw_right(self, surf, r, kind, x, ink, ink_dim):
        prof = self.app.profile
        xd = prof.xd
        chron = x.chronicle if kind == "live" else (x.get("chronicle") or [])
        T.text(surf, "Летопись", (r.x, r.y + 4), 22, ink, True)
        y = r.y + 40
        colors = {"death": (130, 40, 30), "fall": (140, 70, 40), "title": (130, 90, 20), "boss": (90, 50, 110),
                  "win": (40, 100, 50), "task": (50, 80, 120)}
        lines = []
        for e in chron:
            ch = xd["chapters"].get(e.get("chapter"), {}).get("name", "") if e.get("chapter") != "tavern" else "таверна"
            head = f"Поход {e.get('run', 1)}" + (f", {ch}" if ch else "")
            for ln in T.wrap(f"{head}: {e['text']}", 16, r.w - 10):
                lines.append((ln, colors.get(e.get("kind"), ink)))
        cap = max(1, (r.bottom - y) // 23)
        if len(lines) > cap:
            skipped = len(lines) - cap + 1
            T.text(surf, f"… ранее ещё {skipped} строк", (r.x, y), 13, ink_dim)
            y += 19
            lines = lines[-(cap - 1):]
        for ln, col in lines:
            T.text(surf, ln, (r.x, y), 16, col)
            y += 23
        if not chron:
            T.text(surf, "Записей нет.", (r.x, y), 14, ink_dim)


ROOM_CLASSES = {"hall": HallRoom, "chapters": ChapterRoom, "muster": MusterRoom, "workshop": WorkshopRoom, "yard": YardRoom,
                "build": BuildRoom, "fame": FameRoom, "market": MarketRoom, "mine": MineRoom}
