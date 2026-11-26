"""Экраны «Спуска»: бой (поле нынешней игры + живая рука карт), награда, прозрение, карта этажа, торговец,
колода, итог.

Управление в бою: тянуть карту на цель (ЛКМ — основное за энергию, ПКМ — простое бесплатно; от карты тянется
стрелка) или кликнуть карту и затем цель. ПКМ/Esc — отмена. Space или кнопка — конец хода. 1–9 — карта,
Shift+1–9 — её простое действие.
"""
import math
import os
import random

import pygame

from sim.combat import ENEMY
from sim.grid import cheb
from ui import audio
from ui import projection as P
from ui import theme as T
from ui.battle_view import FR, BattleView, Fx
from ui.field_life import FieldLife
from ui.vfx_textures import make_textures

from . import cardface as CF
from . import gfx as G
from . import model as M
from . import skin as SK
from .battle import BallistaShot
from .hints import Hints, Plain
from .idols import MEANING_ICON, SPEC, IdolCast
from .terrain import Ground
from .relic_choice import RelicChoice
from .hand import HandView


CW, CH = CF.DW, CF.DH
HOLD_T = 0.35                    # удержание карты без движения — подробный вид
TYPE_COL = {"attack": (190, 80, 60), "skill": (70, 120, 190), "power": (150, 90, 200)}
INTENT_COL = {"melee": (255, 110, 90), "zone": (255, 80, 60), "shot": (255, 170, 80), "block": (130, 170, 255),
              "aim": (255, 220, 110), "heal": (130, 230, 140), "roar": (220, 140, 255), "charge": (255, 90, 60),
              "pull": (120, 200, 255), "guard": (130, 170, 255), "rally": (255, 150, 90), "veil": (190, 190, 220),
              "curse": (200, 150, 255), "hex": (200, 150, 255), "drown": (120, 160, 255), "summon": (200, 230, 140)}


def wrap(s, size, w):
    return T.wrap(s, size, w)


def draw_card(surf, r, card, mouse=None, main_ok=True, alt_ok=True, hot=False, chosen=None):
    """Карта в прямоугольник r: лицо из deck/cardface.py (основное сверху, простое снизу вверх ногами)."""
    CF.blit_card(surf, r, card, main_ok, alt_ok, hot)


_dims = {}


def dim(surf, alpha):
    """Затемнить весь экран (в родном разрешении — одной готовой поверхностью)."""
    tgt = surf.native if G.is_canvas(surf) else surf
    key = tgt.get_size()                                  # одна тёмная поверхность — меняется только прозрачность
    d = _dims.get(key)
    if d is None:
        d = pygame.Surface(tgt.get_size())
        d.fill((8, 6, 4))
        _dims.clear()
        _dims[key] = d
    d.set_alpha(alpha)
    tgt.blit(d, (0, 0))


def shift_held():
    return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)


def title_text(surf, s, pos, size, color):
    """Заголовок капителями Alegreya SC (на холсте — в родном разрешении)."""
    if G.is_canvas(surf):
        img = CF.title_font(max(6, round(size * surf.S))).render(s, True, color)
        x, y = surf.pt(pos)
        surf.native.blit(img, (round(x), round(y)))
    else:
        surf.blit(CF.title_font(size).render(s, True, color), pos)


class Inspector:
    """Подробный вид карты в духе CZN: крупная карта (наклон за мышью) и справа — стопка тёмных плашек ключевых
    слов, простого применения, роста и дара. Два режима: удержание (ЛКМ без движения — пока держишь) и чтение
    (Shift закрепляет: мышь свободна, наведение на выделенное слово на карте — подсказка, плашка подсвечена)."""

    CW = 360                                  # ширина крупной карты (логические единицы)
    PW = 310                                  # ширина плашек

    def __init__(self, card, anchor_x=None, state=None, pinned=False):
        self.card = card
        self.anchor_x = anchor_x
        self.state = state or (True, True, False, None, frozenset())   # main_ok, alt_ok, hot, heat, lit
        self.pinned = pinned
        self.mouse = None                     # мышь в режиме чтения (фон её не видит)
        self.rects = []                       # [(rect, название плашки)]
        self.card_rect = pygame.Rect(0, 0, 0, 0)
        self.made_rects = []                  # [(rect, карта)] — карты, которые эта создаёт (слева)
        self.stack = []                       # путь просмотра: прежние карты (назад — ПКМ / Backspace)
        self.back_rect = None

    PV = 210                                  # ширина карточки «Создаёт» слева

    def made(self):
        """Карты, которые создаёт открытая карта (как в CZN — видны слева, можно открыть)."""
        from . import model as M
        out = []
        for cid in M.created_ids(self.card.d):
            d = M.card_def(cid)
            if d is not None:
                out.append(M.Card(cid, {cid: d}))
        return out

    def open_card(self, card):
        """Перейти к созданной карте (прежняя — в путь, назад — ПКМ или Backspace)."""
        self.stack.append((self.card, self.state, self.anchor_x))
        self.card = card
        self.state = (True, True, False, None, frozenset())
        self.anchor_x = None

    def wheel(self, dy):
        """Колесо в режиме чтения: уровень (цена в жаре) открытой карты Пиромантки."""
        return CF.wheel_level(self.card, dy)

    def back(self):
        if not self.stack:
            return False
        self.card, self.state, self.anchor_x = self.stack.pop()
        return True

    def click(self, pos, button=1):
        """Клик в режиме чтения: по созданной карте — открыть её; ПКМ или «назад» — вернуться. True — обработан."""
        if button == 3:
            return self.back()
        if self.back_rect is not None and self.back_rect.collidepoint(pos):
            return self.back()
        lv = CF.level_at(self.card, self.card_rect, pos)
        if lv is not None:                                          # кружок уровня — сменить цену
            CF.set_level(self.card, lv)
            return True
        for r, c in self.made_rects:
            if r.collidepoint(pos):
                self.open_card(c)
                return True
        return False

    def panels(self):
        from . import model as M
        c = self.card
        d = c.d
        out = [(name, expl, CF.GOLD) for name, expl in M.keywords(c)]
        cat = {"basic": "Базовая", "neutral": "Нейтральная", "hero": "Классовая",
               "token": "Служебная"}.get(c.category, c.category)
        out.insert(0, ("Редкость", f"{c.rarity_name} · {cat}",
                       M.CARD_RARITY_COLOR.get(c.rarity, M.CARD_RARITY_COLOR[1])))
        if c.spirit_rank_name:
            out.append((f"Слияние · ранг {c.spirit_rank_name}", M.TAG_INFO["Слияние"], CF.GOLD))
        retained = M.retain_phrase(d)
        if retained:
            out.append(("При сохранении", retained, (150, 230, 160)))
        if d["alt"]["target"] != "none":
            out.append(("Простое — бесплатно", M.phrase(d["alt"]) + " Не считается сыгранной картой.",
                        (150, 230, 160)))
        g = c.growth_next()
        if g:
            opts = ", ".join(label for label, _ in c.options())
            if c.insight_ready():
                state = "Прозрение готово — выберите ветку после боя."
            else:
                state = (f"Шанс {int(M.INSIGHT_CHANCE * 100)}% за основное применение; "
                         f"гарантия через {max(0, M.INSIGHT_PITY - c.insight_misses)} применений.")
            out.append(("Рост карты", state + (f" Варианты: {opts}." if opts else ""), (255, 214, 120)))
        if c.divine:
            gd = c.divine
            out.append((f"Дар: {gd['name']}", f"{gd['title'].capitalize()}. {gd['about']}",
                        tuple(gd.get("color", (200, 180, 255)))))
        return out

    def panel_h(self, text):
        th = CF.title_font(20).get_height()
        return 12 + th + 4 + CF.rich(CF._MEASURE, text, pygame.Rect(0, 0, self.PW - 30, 10), 15, (0, 0, 0),
                                     left=True) + 12

    def columns(self):
        """Плашки по колонкам: [[(название, текст, цвет)], ...] — сколько влезает по высоте."""
        cols, cur, y = [], [], 0
        for p in self.panels():
            h = self.panel_h(p[1]) + 8
            if cur and y + h > T.SCREEN_H - 60:
                cols.append(cur)
                cur, y = [], 0
            cur.append(p)
            y += h
        if cur:
            cols.append(cur)
        return cols

    def layout(self, ncols=1, left=0):
        w = self.CW
        h = round(w * CF.FH / CF.FW)
        cx = self.anchor_x if self.anchor_x is not None else T.SCREEN_W // 2 - self.PW // 2 * ncols + left // 2
        cx = max(w // 2 + 16 + left, min(T.SCREEN_W - w // 2 - (self.PW + 10) * ncols - 22, cx))
        r = pygame.Rect(0, 0, w, h)
        r.midtop = (cx, 28)
        return r

    def contains(self, pos):
        return self.card_rect.collidepoint(pos) or any(r.collidepoint(pos) for r, _ in self.rects) or \
            any(r.collidepoint(pos) for r, _ in self.made_rects) or \
            (self.back_rect is not None and self.back_rect.collidepoint(pos))

    def _panel(self, surf, x, y, title, text, col, hot=False):
        """Плашка: тёмный сланец, цветная полоска слева, заголовок капителями, текст PT Serif."""
        w = self.PW
        th = CF.title_font(20).get_height()
        body_h = CF.rich(CF._MEASURE, text, pygame.Rect(0, 0, w - 30, 10), 15, (0, 0, 0), left=True)
        h = 12 + th + 4 + body_h + 12
        r = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, (14, 13, 18), r, border_radius=6)
        pygame.draw.rect(surf, T.mix(col, (0, 0, 0), 0.25) if hot else (92, 80, 64), r, 2 if hot else 1,
                         border_radius=6)
        pygame.draw.rect(surf, col, (r.x, r.y + 6, 4, r.h - 12))
        title_text(surf, title, (r.x + 16, r.y + 8), 20, col)
        CF.rich(surf, text, pygame.Rect(r.x + 16, r.y + 12 + th, w - 30, body_h), 15, (226, 220, 208), left=True)
        return r

    def word_at(self, mouse):
        """Выделенное слово карты под мышью: (экранный rect, слово, стиль) или None."""
        from . import cardart
        if not cardart.available() or not self.card_rect.collidepoint(mouse):
            return None
        r = self.card_rect
        k = r.w / CF.FW
        for b, word, st in cardart.word_boxes(self.card, *self.state):
            sr = pygame.Rect(round(r.x + b.x * k), round(r.y + b.y * k), max(1, round(b.w * k)),
                             max(1, round(b.h * k)))
            if sr.inflate(4, 4).collidepoint(mouse):
                return sr, word, st
        return None

    def draw(self, surf, mouse):
        from . import model as M
        dim(surf, 150)
        cols = self.columns()
        made = self.made()
        r = self.layout(len(cols), left=(self.PV + 24) if made else 0)
        self.card_rect = r
        tilt = None                                                     # крупный вид — ровный (поворот — в руке)
        main_ok, alt_ok, hot, heat, lit = self.state
        sh = pygame.Rect(r.x + 10, r.y + 14, r.w, r.h)                  # тень под картой
        pygame.draw.rect(surf, (0, 0, 0), sh, border_radius=18)
        CF.blit_card(surf, r, self.card, main_ok, alt_ok, False, heat=heat, lit=lit, tilt=tilt)
        hover = self.word_at(mouse) if self.pinned else None
        info = M.lookup(hover[1], hover[2]) if hover else None
        # плашки — справа (или слева, если справа нет места)
        self.rects = []
        for i, column in enumerate(cols):                               # колонки плашек — справа от карты
            x = r.right + 18 + i * (self.PW + 10)
            y = r.y
            for title, text, col in column:
                pr = self._panel(surf, x, y, title, text, col, hot=bool(info and info[0] == title))
                self.rects.append((pr, title))
                y = pr.bottom + 8
        if hover is not None:                                           # слово под мышью
            hr = hover[0]
            pygame.draw.line(surf, (255, 240, 180), (hr.x, hr.bottom), (hr.right, hr.bottom), 2)
            if info:
                tx = min(mouse[0] + 18, T.SCREEN_W - self.PW - 8)
                ty = min(mouse[1] + 20, T.SCREEN_H - 120)
                self._panel(surf, tx, ty, info[0], info[1], (255, 240, 180), hot=True)
        self.draw_made(surf, made, r, mouse)
        if self.stack:                                                  # открыта созданная карта — путь назад
            prev = self.stack[-1][0]
            label = f"← Назад: {prev.name}"
            bw = max(160, T.font(15, True).size(label)[0] + 30)
            self.back_rect = pygame.Rect(r.centerx - bw // 2, r.bottom + 30, bw, 34)
            hot = self.back_rect.collidepoint(mouse)
            pygame.draw.rect(surf, (40, 32, 24) if not hot else (70, 54, 34), self.back_rect, border_radius=8)
            pygame.draw.rect(surf, (230, 200, 140) if hot else (140, 118, 90), self.back_rect, 2, border_radius=8)
            T.text(surf, label, self.back_rect.center, 15, (250, 236, 210), True, center=True)
        else:
            self.back_rect = None
        hint = ("наведите на выделенное слово — описание · клик по карте слева — открыть" +
                (" · ПКМ или Backspace — назад" if self.stack else "") + " · Shift, Esc или клик мимо — закрыть"
                if self.pinned and made else
                "наведите на выделенное слово — описание · ПКМ или Backspace — назад · Shift, Esc — закрыть"
                if self.stack else
                "наведите на выделенное слово — описание · Shift, Esc или клик мимо — закрыть" if self.pinned else
                "отпустите — закрыть · Shift — закрепить и читать слова")
        if self.card.levels:
            hint = "колесо или клик по кружку — уровень (цена в жаре) · " + hint
        T.text(surf, hint, (r.centerx, r.bottom + 14), 13, (210, 200, 180), center=True, shadow=True)

    def draw_made(self, surf, made, r, mouse):
        """Слева от карты — карты, которые она создаёт: подпись «Создаёт», клик — открыть."""
        self.made_rects = []
        if not made:
            return
        gap = 24
        y = r.y + 42
        available = T.SCREEN_H - y - 24 - gap * (len(made) - 1)
        h = min(round(self.PV * CF.FH / CF.FW), available // len(made))
        w = round(h * CF.FW / CF.FH)
        x = r.x - 24 - (self.PV + w) // 2
        title_text(surf, "Создаёт", (x + 4, y - 32), 18, (150, 220, 255))
        for c in made:
            cr = pygame.Rect(x, y, w, h)
            hot = cr.collidepoint(mouse)
            sh = cr.move(6, 8)
            pygame.draw.rect(surf, (0, 0, 0), sh, border_radius=12)
            CF.blit_card(surf, cr.inflate(16, 22) if hot else cr, c, True, True, hot)
            if hot:
                pygame.draw.rect(surf, (150, 220, 255), cr.inflate(22, 28), 3, border_radius=14)
            self.made_rects.append((cr, c))
            y = cr.bottom + gap


def reading_event(screen, ev, card_under):
    """Shift над картой — закрепить чтение (Inspector); Shift/Esc/клик мимо — закрыть. True — событие съедено."""
    r = getattr(screen, "reading", None)
    if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
        if r is not None:
            screen.reading = None
        else:
            c = card_under()
            if c is not None:
                screen.reading = Inspector(c, pinned=True)
                screen.reading.mouse = screen.mouse
        return True
    if r is None:
        return False
    if ev.type == pygame.MOUSEWHEEL:
        r.wheel(ev.y)
    elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_BACKSPACE:
        r.back()
    elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
        screen.reading = None
    elif ev.type == pygame.MOUSEBUTTONDOWN and r.click(ev.pos, ev.button):
        pass
    elif ev.type == pygame.MOUSEBUTTONDOWN and not r.contains(ev.pos):
        screen.reading = None
    elif ev.type == pygame.MOUSEMOTION:
        r.mouse = ev.pos                                 # фон (карты позади) мышь не видит
    return True


def card_detail(surf, card, heat=None, mouse=None):
    """Режим чтения карты (как по Shift) — для экранов вне боя и тестов."""
    Inspector(card, state=(True, True, False, heat, frozenset()), pinned=True).draw(
        surf, mouse or (T.SCREEN_W // 2, T.SCREEN_H // 2))


def _changes(a, b):
    """Что меняет прозрение: стороны карты, текст которых стал другим — [(сторона, новый текст)]."""
    from . import model as M
    out = []
    la, lb = a.levels, b.levels
    if lb:
        for i, L in enumerate(lb):
            old = M.phrase(la[i]["main"]) if i < len(la) else ""
            new = M.phrase(L["main"])
            if new != old or (i < len(la) and la[i]["heat"] != L["heat"]):
                out.append((f"жар {L['heat']}", new))
    elif M.phrase(a.d["main"], a.d.get("exhaust")) != M.phrase(b.d["main"], b.d.get("exhaust")):
        out.append(("основное", M.phrase(b.d["main"], b.d.get("exhaust"))))
    if not lb and a.d.get("cost") != b.d.get("cost"):
        out.append(("цена", f"{{{b.d.get('cost')}}} энерг."))
    if M.phrase(a.d["alt"]) != M.phrase(b.d["alt"]):
        out.append(("простое", M.phrase(b.d["alt"])))
    if M.card_extras(a.d) != M.card_extras(b.d):
        out.append(("свойство", M.card_extras(b.d)))
    return out


def model_res():
    """Качество моделек «Спуска»: 32 или 64 (настройка sprite_res, общая с экспедицией; 16 там — как 32)."""
    from ui import settings
    return 64 if settings.SETTINGS.get("sprite_res", 32) >= 64 else 32


def sk_wrap(sk, text, size, width):
    """Перенос строк по ширине шрифта скина (тем же, каким текст будет нарисован)."""
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and sk.size(t, size)[0] > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


_ITEM_IMG = {}


def item_icon(surf, r, center, size, alpha=255):
    """Свой значок предмета (assets/ui/items/<id>.png, лист DC7) — чётко, в родном разрешении. False — его нет."""
    iid = r.get("id")
    if iid not in _ITEM_IMG:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "ui", "items",
                         f"{iid}.png")
        try:
            _ITEM_IMG[iid] = pygame.image.load(p).convert_alpha() if os.path.exists(p) else None
        except pygame.error:
            _ITEM_IMG[iid] = None
    img = _ITEM_IMG[iid]
    if img is None:
        return False
    if hasattr(surf, "blit_hd"):
        surf.blit_hd(img, center, 0.0, size / img.get_width(), alpha=alpha)
    else:
        sm = pygame.transform.smoothscale(img, (size, size))
        if alpha < 255:
            sm.set_alpha(alpha)
        surf.blit(sm, (center[0] - size // 2, center[1] - size // 2))
    return True


def draw_item_icon(surf, item, center, size):
    if item_icon(surf, item, center, size):
        return
    img = CF.art(item.get("icon", ""), size)
    if img is not None:
        surf.blit(img, img.get_rect(center=center))
    else:
        T.text(surf, item["name"][:1], center, size // 2, T.AMBER, True, center=True)


class Bag:
    """Сумка предметов (deck/items.py): полоска значков — рамка по редкости, счётчик, подсказка; окно со всеми
    предметами — I или клик по значкам (в бою, на карте этажа, у торговца)."""

    def __init__(self):
        self.open = False
        self.rects = []

    def event(self, ev):
        """True — событие съедено сумкой."""
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_i:
                self.open = not self.open
                return True
            if self.open and ev.key == pygame.K_ESCAPE:
                self.open = False
                return True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            if self.open:
                self.open = False
                return True
            if ev.button == 1 and any(r.collidepoint(ev.pos) for r, _ in self.rects):
                self.open = True
                return True
        return self.open and ev.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)

    @staticmethod
    def counter(run, r, battle):
        from .items import counter_of
        return counter_of(run, r, battle)

    def bar(self, surf, run, pos, mouse, battle=None, right=False):
        """Значки предметов в ряд от pos (right — ряд кончается в pos); под мышью — подсказка."""
        from .items import RARITY_COLOR, RARITY_NAME
        sk = SK.use(getattr(run, "hero_id", "merc"))
        items = list(getattr(run, "relics", []))
        per_row = 14
        x0, y = pos
        if right:
            x0 -= 34 * min(per_row, max(1, len(items)))
        self.rects = []
        tip = None
        for i, r in enumerate(items):
            x = x0 + 34 * (i % per_row)
            yy = y + 34 * (i // per_row)
            rect = pygame.Rect(x, yy, 30, 30)
            col = RARITY_COLOR.get(r.get("rarity"), (210, 170, 100))
            spent = r.get("mods", {}).get("revive") and getattr(run, "relic_state", {}).get("revived")
            sk.badge(surf, rect.center, 13, "", tuple(int(c * 0.55) for c in col) if spent else col)
            img = None if item_icon(surf, r, rect.center, 26, 90 if spent else 255) else CF.art(r.get("icon", ""), 22)
            if img is not None:
                if spent:
                    img = img.copy()
                    img.set_alpha(90)
                surf.blit(img, (x + 4, yy + 4))
            elif not _ITEM_IMG.get(r.get("id")):
                sk.text(surf, r["name"][0], rect.center, 15, sk.p["title"], center=True, title=True)
            n = self.counter(run, r, battle)
            if n:
                sk.text(surf, str(n), (rect.right - 1, rect.bottom - 7), 12, (255, 240, 200), center=True, title=True)
            self.rects.append((rect, r))
            if rect.collidepoint(mouse) and not self.open:
                tip = (r, rect)
        if tip:
            r, rect = tip
            n = self.counter(run, r, battle)
            from .items import about
            lines = sk_wrap(sk, about(r, run), 13, 290)
            extra = f"Счёт: {n or 0} из {r['count']}" if r.get("count") else ""
            box = pygame.Rect(min(rect.x, T.SCREEN_W - 340), rect.bottom + 8, 320,
                              52 + 18 * len(lines) + (18 if extra else 0))
            sk.panel(surf, box, 246, cut=8)
            sk.text(surf, r["name"], (box.x + 14, box.y + 8), 15, RARITY_COLOR.get(r.get("rarity"), sk.p["title"]),
                    title=True)
            sk.text(surf, RARITY_NAME.get(r.get("rarity"), "") + " · I — сумка", (box.x + 14, box.y + 28), 11,
                    sk.p["dim"], outline=False)
            for i, ln in enumerate(lines):
                sk.text(surf, ln, (box.x + 14, box.y + 46 + i * 18), 13, sk.p["text"], outline=False)
            if extra:
                sk.text(surf, extra, (box.x + 14, box.y + 46 + len(lines) * 18), 12, (255, 220, 150), outline=False)

    def draw(self, surf, run, battle=None):
        """Окно сумки: все предметы с описанием, редкостью и счётчиками."""
        if not self.open:
            return
        from .items import RARITY_COLOR, RARITY_NAME
        sk = SK.use(getattr(run, "hero_id", "merc"))
        dim(surf, 150)
        items = list(getattr(run, "relics", []))
        cols = 2
        cw, ch = 520, 92
        rows = max(1, (len(items) + cols - 1) // cols)
        visible = min(rows, 6)
        r = pygame.Rect(0, 0, cols * cw + 60, 110 + visible * ch)
        r.center = (T.SCREEN_W // 2, T.SCREEN_H // 2 - 20)
        sk.panel(surf, r, 250, accent=True)
        sk.text(surf, f"Сумка · предметов: {len(items)}", (r.centerx, r.y + 28), 24, sk.p["title"], center=True,
                title=True)
        sk.text(surf, "Предметы срабатывают сами, когда выполнено их условие. Закрыть — I, Esc или клик",
                (r.centerx, r.y + 56), 13, sk.p["dim"], center=True, outline=False)
        if not items:
            sk.text(surf, "Пока пусто: предметы дают сундуки, элита, страж лестницы и торговец.",
                    (r.centerx, r.y + 110), 15, sk.p["text"], center=True, outline=False)
            return
        for i, it in enumerate(items[:visible * cols]):
            x = r.x + 30 + (i % cols) * cw
            y = r.y + 84 + (i // cols) * ch
            col = RARITY_COLOR.get(it.get("rarity"), (210, 170, 100))
            sk.badge(surf, (x + 22, y + 24), 20, "", col)
            img = None if item_icon(surf, it, (x + 22, y + 24), 36) else CF.art(it.get("icon", ""), 30)
            if img is not None:
                surf.blit(img, (x + 7, y + 9))
            sk.text(surf, it["name"], (x + 52, y + 2), 17, col, title=True)
            tag = RARITY_NAME.get(it.get("rarity"), "")
            n = self.counter(run, it, battle)
            if it.get("count"):
                tag += f" · счёт {n or 0} из {it['count']}"
            if it.get("mods", {}).get("revive") and getattr(run, "relic_state", {}).get("revived"):
                tag += " · уже сработал"
            sk.text(surf, tag, (x + 52 + sk.size(it["name"], 17, True)[0] + 10, y + 6), 12, sk.p["dim"], outline=False)
            from .items import about
            for k, ln in enumerate(sk_wrap(sk, about(it, run), 13, cw - 80)[:3]):
                sk.text(surf, ln, (x + 52, y + 26 + k * 17), 13, sk.p["text"], outline=False)
        if len(items) > visible * cols:
            sk.text(surf, f"…и ещё {len(items) - visible * cols}", (r.centerx, r.bottom - 22), 13, sk.p["dim"],
                    center=True, outline=False)


def relic_bar(surf, run, pos, mouse):
    """Совместимость: значки предметов без окна сумки."""
    Bag().bar(surf, run, pos, mouse)


def button(surf, r, label, mouse, on=True, primary=False):
    hot = on and r.collidepoint(mouse)
    T.frame(surf, r, 245, accent=T.SELECT if hot else (T.AMBER if primary else T.PANEL_EDGE),
            fill=(60, 44, 26) if hot else (40, 30, 22))
    T.text(surf, label, r.center, 17, T.TEXT if on else T.TEXT_DIM, True, center=True)
    return hot


class BattleScreen:
    """Бой: поле, рука, намерения, журнал."""

    def __init__(self, game, battle):
        self.game = game
        self.b = battle
        self.combat = battle.c
        self.view = BattleView(game.gd)
        self.view.simple = True
        self.view.num_boost, self.view.num_dy = 6, -34    # цифры урона крупнее и всплывают от фигурки, не под табличкой
        self.view.reset(self.combat)
        self.fit_board()
        self._light_props()
        self.life = FieldLife(random.randrange(1 << 30))  # своё зерно: случайность забега не трогаем
        from .terrain import theme_of
        if theme_of(self.combat) == "swamp":              # трава, живность, облака болота — только на болоте
            self.life.setup(self.view, self.combat)
        self.view.life = self.life
        self.view.crisp = True                           # подсказки и кольца у ног — чётким слоем (deck/hints.py)
        self.hints = Hints()
        self.ground = Ground()                           # земля: HD-пиксель с рельефом (deck/terrain.py)
        self.ground.prepare(self.combat, self.view.painter)
        self.view.height_at = self.ground.height_at      # декор, трава, вороны — на буграх
        self.phase = "battle"
        self.selected = battle.hero
        self.selected_units = [battle.hero]
        self.targeting = None
        self.hover_cell = None
        self.dragging = False
        self.picked = None
        self.mouse = (0, 0)
        self.paused = False
        self.slowmo = False
        self.pick = None
        self.job = None
        self.wait = 0.0
        self.chain_show = None             # карта, которую Цепочка играет сама: крупный показ
        self.chain_t = 0.0
        self.chain_dur = 0.0
        self.chain_pick = None             # (карта, режим): Цепочка ждёт выбора цели игроком
        self.chain_send = None
        self.chain_send_ready = False
        self.relic_choice = None
        self.relic_choice_offset = 0
        self.relic_choice_hits = []
        self.sel = None                    # (карта, режим): выбрана кликом или тянется
        self.hand_picks = []
        self.press = None                  # (карта, кнопка, точка) — нажали на карту, ещё не ясно: клик или тяга
        self.press_t = 0.0                 # сколько держат нажатой без движения
        self.inspect = None                # Inspector: удержание или закреплённое чтение (Shift)
        self.discard_pick = []             # Адажио: выбранные в руке карты для сброса
        self.pick = None                   # подошли на клетку, а рядом несколько врагов: (карта, сторона, клетка, враги)
        self.shot_pick = None               # цель залпа выбрана, ждём выбор орудия
        self.prayer = None                 # Жрец: свиток на статуе, ждём цель — (карта, статуя, варианты)
        self.drag = False                  # карту тянут мышью
        self.end_rect = pygame.Rect(T.SCREEN_W - 200, T.SCREEN_H - 70, 180, 50)
        self.hand_area = pygame.Rect(150, T.SCREEN_H - CH - 26, T.SCREEN_W - 150 - 230, CH + 26)
        self.deck_pile_rect = None
        self.discard_pile_rect = None
        self.hv = HandView((CW, CH), (60, T.SCREEN_H - 30), (T.SCREEN_W - 240, T.SCREEN_H - 40))
        self.hv.face = self.card_face
        self.hv.face_tilt = lambda c, st, tilt, zoom=1.0: CF.face(c, *st, tilt=tilt, width=self.face_w(zoom))
        self._S = 1.0                      # масштаб окна (холста) — лица карт рисуются под него
        self.hv.glow = lambda c, st: bool(st[4]) and st[0]   # условие выполнено и основное играется
        self.hv.back = CF.back(battle.run.hero_id) if hasattr(battle.run, "hero_id") else None
        self.zone_t = 0.0
        self.toast = None
        self.intro_t = 0.0                 # заставка до готовой земли
        self._intro_frames = 0
        self.shown_t = None                # когда бой проявился
        self.help_open = False             # справка по управлению (? / H / F1)
        self.bag = Bag()                   # сумка предметов (I или клик по значкам)
        from ui import settings
        self.ui_hidden = bool(settings.SETTINGS.get("descent_hide_ui", False))   # Tab: только карты, энергия, намерения
        self.log_open = False              # журнал в панели героя (L)
        self._state_tips = []

    def _light_props(self):
        """Декор вокруг доски без старой пиксельной карты земли (её здесь не рисуют — земля своя, deck/terrain):
        только расстановка по рельефу клеток — вход в бой без лишней секунды."""
        pr = self.view.painter
        cache = {}
        tmc = {}
        raw = pr._terrain_map

        def terrain_map(combat):                          # рельеф клеток — заново, только если он поменялся
            key = tuple(c.base_terrain if c.terrain == "ice_floor" and c.base_terrain else c.terrain
                        for c in combat.grid.cells.values())
            if tmc.get("key") != key:
                tmc["key"], tmc["val"] = key, raw(combat)
            return tmc["val"]
        pr._terrain_map = terrain_map

        def props(combat):
            tm, names = pr._terrain_map(combat)
            key = tm.tobytes()
            if key not in cache:
                cache.clear()
                cache[key] = pr._place_props(combat, tm, names, pr.style(combat), pr.palette(combat))
            return cache[key]
        pr.props = props

    def fit_board(self):
        """Доска — над рукой и в обход панели героя справа: карты в покое не закрывают поле."""
        P.fit(16, 92, T.SCREEN_W - 16, T.SCREEN_H - CH - 18, avoid=[(T.SCREEN_W - 262, 14, 248, 250)])
        self.view._ground = None
        self.view._cpu_tex = None

    # ---------- такт ----------

    @property
    def busy(self):
        return self.job is not None or self.b.pending_discard > 0

    def run_job(self, gen):
        self.job = gen
        self.wait = 0.0

    ANIM = 0.85                                        # всё, что показывает бой, — чуть медленнее (плавнее)

    def update(self, dt):
        self.intro_t += dt
        if not self.ready():                           # заставка: земля ещё строится — бой стоит
            return
        if not self.b.pending_discard and self.discard_pick:
            self.discard_pick = []
        real = dt
        dt = dt * self.ANIM
        if self.chain_show is not None:
            self.chain_t += real
            if self.chain_t >= self.chain_dur:
                self.chain_show = None
        over = {}
        for u in self.combat.units:                 # шаги фигурок: бой реального времени здесь не идёт
            if u.move_t < 1.0:
                nt = u.move_t + dt / max(0.01, u.move_dur)
                if nt >= 1.0:                       # остаток кадра — следующему шагу (без запинки)
                    over[u.id] = (nt - 1.0) * u.move_dur
                u.move_t = min(1.0, nt)
        moving = any(u.move_t < 1.0 for u in self.combat.units if u.alive)
        if self.job is not None and not moving and self.chain_pick is None and self.relic_choice is None:
            self.wait -= dt
            if self.wait <= 0:
                try:
                    if self.chain_send_ready:
                        act = self.job.send(self.chain_send)
                        self.chain_send_ready = False
                    else:
                        act = next(self.job)
                    if isinstance(act, RelicChoice):
                        if act.options:
                            self.relic_choice = act
                            self.relic_choice_offset = 0
                            self.relic_choice_hits = []
                        self.wait = 0.0
                    elif act and act[0] == "chain_card":      # Цепочка: сначала показать карту, потом эффект
                        self.chain_show, self.chain_t, self.chain_dur = act[2], 0.0, max(0.35, act[1])
                        self.wait = max(0.45, act[1]) + 0.06
                    elif act and act[0] == "chain_choice":  # не-атака: игрок сам выбирает цель
                        self.chain_pick = (act[1], act[2])
                        self.chain_show = None
                        self.sel = (act[1], act[2])
                        self.wait = 0.0
                    elif act and act[0] == "impact":        # эффект выпущен — ждём попадания, потом урон
                        self.wait = min(1.4, self.pump()) + 0.02
                    elif act and act[0] == "move":          # шаг пути — сразу следующий, с остатком кадра
                        u = act[2]
                        u.move_t = min(0.9, over.get(u.id, 0.0) / max(0.01, u.move_dur))
                        self.wait = 0.0
                    else:
                        self.wait = (act[1] if act else 0.0) + 0.06
                except StopIteration:
                    self.job = None
                    self.chain_pick = None
                    self.chain_send_ready = False
        if self.b.zone_fx:
            self.zone_t = 0.6
            self._zone_cells = self.b.zone_fx[0]
            self.b.zone_fx = None
        self.zone_t = max(0.0, self.zone_t - dt)
        self.pump()
        self.ambient(dt)
        self.life.update(real, self.view, self.combat)
        self.view.update(dt, dt)
        dt = real
        if self.press and not self.drag and self.press[1] == 1 and self.inspect is None:   # держат без движения
            self.press_t += dt
            if self.press_t >= HOLD_T:
                card = self.press[0]
                sp = self.hv.sprites.get(card.uid)
                self.inspect = Inspector(card, sp.x if sp else None, self.state_of(card))
        if self.inspect is not None:
            root = self.inspect.stack[0][0] if self.inspect.stack else self.inspect.card
            if root not in self.b.hand:                       # сыграли или сбросили — чтение закрыть
                self.inspect = None
            elif not self.inspect.stack:                      # открыта созданная карта — её состояние своё
                self.inspect.state = self.state_of(self.inspect.card)
        hv = self.hv                                  # рука: состав, раскладка, пружины
        hv.sync(self.b.hand)
        far = (-9999, -9999)                          # открыт крупный вид — рука не следит за мышью
        hand_mouse = far if self.inspect is not None else self.mouse
        hv.hover = None if (self.drag or self.busy or self.inspect is not None) else hv.hit(self.mouse)
        lift = self.sel and self.sel[0].d[self.sel[1]]["target"] != "self" and \
            (not self.drag or self.mouse[1] < self.hand_area.y)
        if self.drag and self.sel:                    # прицельная карта над рукой — встаёт, тянется стрелка
            hv.drag = None if lift else self.sel[0].uid
        hv.lifted = self.sel[0].uid if self.sel and (lift or not self.drag) else None
        aiming = (self.sel and self.sel[0].d[self.sel[1]]["target"] != "self") or self.prayer or self.pick
        hv.sink = bool(aiming) and self.mouse[1] < self.hand_area.y + 40 and hv.hover is None
        hv.layout(self.b.hand, self.hand_area, hand_mouse)
        hv.update(dt, hand_mouse)
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt)
            if self.toast[1] <= 0:
                self.toast = None
        if self.b.result and self.job is None:
            self.game.battle_over(self.b)

    # ---------- эффекты механик (vfx_skills.md, «Спуск») ----------

    ALT_FX = {"block": "shield_small", "push": "wind_gust", "mark": "reveal_fx", "card": "refresh_fx",
              "poison": "venom_coat", "buff": "buff_good"}

    def pump(self):
        """Разобрать события боя: свои эффекты механик — здесь, остальное — полю. Возвращает время до попадания."""
        rest = []
        for e in self.combat.events:                      # эффекты механик и простых действий — свои
            if e.get("t") == "deck_fx":
                self.deck_fx(e)
            else:
                self.life.on_event(e, self.view)
                rest.append(e)
        self.combat.events.clear()
        return self.view.consume(rest) or 0.0

    STATUS_FX = {"fire": "status_fire", "poison": "status_poison", "ice": "status_ice", "water": "status_water",
                 "weak": "curse_hit", "vulnerable": "curse_hit", "hex": "curse_hit", "rally": "buff_good",
                 "veil": "reveal_fx", "bleed": "slash_hit", "counter": "parry_stance"}
    STATUS_WORD = {"fire": ("Горит!", (255, 150, 70)), "poison": ("Отравлен", (150, 230, 90)),
                   "ice": ("Мороз", (170, 220, 255)), "water": ("Мокрый", (120, 180, 255)),
                   "weak": ("Слабость", (200, 160, 255)), "vulnerable": ("Уязвимость", (255, 140, 200)),
                   "hex": ("Сглаз", (200, 150, 255)), "rally": ("Сила!", (255, 170, 90)),
                   "veil": ("Туман", (200, 200, 230)), "bleed": ("Кровь!", (235, 70, 70)),
                   "counter": ("Контратака", (255, 210, 150))}

    def shake(self, amount, stop=0.0):
        sc = self.view.vfx.screen
        sc.shake = max(sc.shake, amount)
        if stop:
            sc.hitstop = max(sc.hitstop, stop)

    def deck_fx(self, e):
        v = self.view
        vx = v.vfx
        k = e["kind"]
        u = e.get("unit")
        if k == "alt":                                     # простое действие — скромно
            what = e["what"]
            fx, fy = v.feet_pos(u)
            if what == "step":
                vx.emit("dust", fx, fy, count=10)
            elif what == "heat":
                hx, hy = v.unit_pos(u)
                vx.emit("sparks_up", hx, hy, count=10)
                vx.emit("embers", hx, hy - 6, count=6)
            elif what == "strike":
                pass                                       # выпад фигурки — событие удара
            else:
                tgt = e.get("target") if what in ("push", "mark", "poison") and e.get("target") else u
                vx.play(self.ALT_FX.get(what, "buff_good"), v._ctx(u, tgt))
        elif k == "momentum_step":                         # Разгон: послеобраз и пыль из-под ног
            v.add_ghost(u, 0.3 + 0.05 * e["n"], (255, 170, 90))
            fx, fy = v.feet_pos(u)
            vx.emit("dust", fx, fy, count=4 + 2 * e["n"])
            if e["n"] >= 3:
                vx.emit("speed_lines", fx, fy - 20, count=4)
        elif k == "momentum_hit":                          # удар с разгона: кольцо, искры, стоп-кадр
            n = e["n"]
            x, y = v.unit_pos(u)
            gx, gy = v.feet_pos(u)
            vx.emit("shock_ring_big" if n >= 4 else "shock_ring", gx, gy, count=1)
            vx.emit("hit_sparks", x, y, count=8 + 4 * n)
            self.shake(3 + 2 * n, 0.04 + 0.02 * n)
        elif k == "heat_gain":
            x, y = v.unit_pos(u)
            vx.emit("sparks_up", x, y, count=6 + 3 * max(0, e.get("n", 1)))
        elif k == "heat_cool":
            x, y = v.unit_pos(u)
            vx.emit("steam", x, y, count=10)
        elif k == "overheat":                              # перегрев — взрыв на ней
            vx.play("fire_explosion", v._ctx(u, u))
            self.shake(10, 0.08)
        elif k == "roar":                                  # рёв — ударная волна от врага
            gx, gy = v.feet_pos(u)
            v.fx.append(Fx("ring", 0.7, x=gx, y=gy, r0=10, r1=60 * e.get("r", 3), color=(220, 140, 255)))
            self.shake(5)
        elif k == "portal":                                # призыв — портал на месте появления
            vx.play("portal_fx", v._ctx(center=e["cell"]))
        elif k == "shake":
            self.shake(e.get("n", 8), 0.06)
        elif k == "tier":                                  # Жрец: действие высокой ступени — подпись и тряска
            from .idols import TIER_COLOR
            q = e.get("q", 2)
            v.float_text(u, e["name"], TIER_COLOR.get(q, (255, 255, 255)), 14 + 3 * q, ttl=1.4 + 0.2 * q, dy=-40)
            gx, gy = v.feet_pos(u)
            v.fx.append(Fx("ring", 0.5 + 0.15 * q, x=gx, y=gy, r0=12, r1=40 * q, color=TIER_COLOR.get(q, (255, 255, 255))))
            if q >= 3:
                self.shake(4 * (q - 1), 0.05 * (q - 1))
            if q >= 4:
                v.fx.append(Fx("banner", 1.6, s=e["name"], color=TIER_COLOR[4]))
        elif k == "phase":                                 # босс меняет фазу — баннер и тряска
            v.fx.append(Fx("banner", 2.2, s=f"{u.name}: «{e['name']}»", color=(255, 190, 110)))
            self.shake(12, 0.1)
        elif k == "relic":                                 # реликвия сработала
            v.float_text(u, e["name"], (170, 220, 255), 14, ttl=1.2, dy=-28)
        elif k == "curse":                                 # «Тина» и утащенные карты
            if e.get("n"):
                x, y = v.unit_pos(u)
                vx.emit("poison_bubbles", x, y, count=10)
        elif k == "echo":                                  # Отклик: карта в руке вспыхивает и срабатывает
            sp = self.hv.sprites.get(e["uid"])
            if sp is not None:
                sp.s = 1.45
                sp.vy -= 500
            vx.play("buff_good", v._ctx(u, u))
        elif k == "dot":                                   # тик горения / яда — вспышка на фигурке
            x, y = v.unit_pos(u)
            if e["el"] == "burn":
                vx.play("hit_fire", v._ctx(target=u))
                vx.emit("fire_burst", x, y, count=6 + 2 * min(6, e.get("n", 1)))
                vx.emit("embers", x, y - 10, count=8)
            elif e["el"] == "bleed":
                vx.emit("red_splash", x, y, count=6 + min(10, e.get("n", 1)))
            else:
                vx.play("hit_poison", v._ctx(target=u))
                vx.emit("poison_bubbles", x, y, count=6 + min(8, e.get("n", 1)))
                vx.emit("toxic_puff", x, y - 6, count=3)
        elif k == "status":                                # наложили состояние — короткий эффект и слово
            el = e["el"]
            if el in self.STATUS_FX:
                vx.play(self.STATUS_FX[el], v._ctx(target=u))
            word = self.STATUS_WORD.get(el)
            if word:
                v.float_text(u, word[0], word[1], 13, ttl=0.9, dy=-14)
        elif k == "power":                                 # Сила сыграна / сработала — фиолетовое кольцо и имя
            gx, gy = v.feet_pos(u)
            v.fx.append(Fx("ring", 0.6, x=gx, y=gy, r0=10, r1=70, color=(200, 150, 255)))
            v.float_text(u, e["name"], (215, 175, 255), 14, ttl=1.1, dy=-34)
        elif k == "exhaust":                                # Изгнание — карта рассыпается дымом
            x, y = v.unit_pos(u)
            vx.emit("smoke_puffs", x, y - 20, count=6)
        elif k == "created":                                # Создать карту — искорки над героем
            x, y = v.unit_pos(u)
            vx.emit("sparkle_trail", x, y - 24, count=8)
        elif k == "counter":                                # Контратака — стойка и ответ
            vx.play("parry_stance", v._ctx(u, e.get("target") or u))
        elif k == "react":                                 # реакции стихий — заметно
            x, y = v.unit_pos(u)
            what = e["what"]
            if what == "steam":
                vx.emit("steam", x, y, count=22)
                vx.emit("steam_fb", x, y - 8, count=4)
                v.float_text(u, "Пар!", (225, 225, 230), 15, ttl=1.0, dy=-16)
            elif what == "shock":
                vx.play("hit_storm", v._ctx(target=u))
                vx.emit("hit_sparks", x, y, count=18)
                v.float_text(u, "Разряд ×2!", (255, 240, 120), 16, ttl=1.1, dy=-16)
                self.shake(6, 0.06)
            elif what == "ice":
                vx.play("ice_burst", v._ctx(target=u))
                vx.emit("ice_shards", x, y, count=14)
                v.float_text(u, "Лёд!", (170, 230, 255), 16, ttl=1.1, dy=-16)
                self.shake(4, 0.04)
            elif what == "flare":
                vx.play("fire_explosion", v._ctx(target=u))
                v.float_text(u, "Вспышка!", (255, 180, 90), 16, ttl=1.0, dy=-16)
                self.shake(6, 0.05)

    def ambient(self, dt):
        """Постоянное: аура состояний по числу стаков; угли вокруг Пиромантки по жару, у порога — пламя."""
        b = self.b
        v = self.view
        for u in self.combat.units:
            if not u.alive or u.obj:
                continue
            ds = u.ds
            if ds.get("burn", 0) >= 2:
                for _ in range(v._rate(("d_burn", u.id), 0.8 * min(6, ds["burn"]), dt)):
                    v.vfx.emit("fire_tongues", *v.feet_pos(u), count=1)
            if ds.get("poison", 0) >= 2:
                for _ in range(v._rate(("d_pois", u.id), 0.5 * min(6, ds["poison"]), dt)):
                    v.vfx.emit("toxic_puff", *v.unit_pos(u), count=1)
            if ds.get("frost", 0) >= 3:
                for _ in range(v._rate(("d_frost", u.id), 0.4 * min(9, ds["frost"]), dt)):
                    v.vfx.emit("ice_bits", *v.unit_pos(u), count=1)
            if ds.get("weak") or ds.get("vulnerable"):
                for _ in range(v._rate(("d_curse", u.id), 1.5, dt)):
                    v.vfx.emit("curse_smoke", *v.feet_pos(u), count=1)
        h = b.hero
        if not h.alive or b.mech != "heat":
            return
        heat = h.ds["heat"]
        over = b.hero_def.get("overheat", 8)
        self._ember = getattr(self, "_ember", 0.0) + dt * (1.5 + 2.2 * heat)
        if self._ember >= 1:
            n = int(self._ember)
            self._ember -= n
            fx, fy = self.view.feet_pos(h)
            self.view.vfx.emit("heat_embers", fx, fy - 10, count=n)
        if heat >= over - 1:
            self._tongue = getattr(self, "_tongue", 0.0) + dt * (3 if heat <= over else 7)
            if self._tongue >= 1:
                self._tongue -= 1
                fx, fy = self.view.feet_pos(h)
                self.view.vfx.emit("fire_tongues", fx, fy, count=1)

    # ---------- ввод ----------

    def cell_at(self, pos):
        wx, wy = self.view.uncam(pos)
        return P.screen_to_cell(wx, wy, self.combat.grid.w, self.combat.grid.h)

    def pick_target_unit(self, pos, units, reach=0):
        unit = self.view.pick_unit(pos, lambda v: v in units, reach=reach)
        if unit is not None:
            return unit
        cell = self.cell_at(pos)
        return next((u for u in units if u.cell == cell), None)

    def target_at(self, pos, sel=None):
        """Цель под курсором для выбранной карты: юнит (по фигурке или клетке) или клетка."""
        sel = sel or self.sel
        if not sel:
            return None
        card, mode = sel
        use = card.d[mode]
        ts = self.b.targets(card, mode)
        if use["target"] in M.HAND_TARGETS:
            uid = self.hv.hit(pos, exclude=card.uid)
            return next((c for c in ts if c.uid == uid), None)
        if pos[1] >= self.hand_area.y + 30:
            return None
        hero = self.b.hero
        if use.get("allow_stay") and hero.cell in ts and self.pick_target_unit(pos, [hero]) is hero:
            return hero.cell
        if self.shot_pick and self.shot_pick[:2] == sel:
            victim = self.shot_pick[2]
            if victim not in ts:
                return None
            shooters = self.b.ballista_shooters(victim, use.get("range", 6))
            shooter = self.pick_target_unit(pos, shooters, reach=10)
            return BallistaShot(shooter, victim) if shooter is not None else None
        if card.d[mode]["target"] == "statue":            # свиток Жреца: статуя под курсором (фигурка или клетка)
            if self.prayer is not None:
                return self.prayer_target(pos)
            st = self.view.pick_unit(pos, lambda v: v in ts, reach=10)
            if st is None:
                cell = self.cell_at(pos)
                st = next((x for x in ts if x.cell == cell), None)
            return st
        if card.d[mode]["target"] == "reach":             # подход: важна клетка под курсором, а не фигурка —
            cell = self.cell_at(pos)                      # иначе за врага и между врагами не встать
            if cell is None:
                return self.view.pick_unit(pos, lambda v: v in ts, reach=0) if pos[1] < self.hand_area.y else None
            spots = self.b.reach_spots(card, mode)
            if cell in spots:
                foes = spots[cell]
                return (cell, foes[0] if len(foes) == 1 else None)
            return next((t for t in ts if hasattr(t, "cell") and t.cell == cell), None)
        u = self.view.pick_unit(pos, lambda v: v in ts)
        if u is not None:
            return u
        cell = self.cell_at(pos)
        if cell is None:
            return None
        if card.d[mode]["target"] == "reach":             # подойти: клетка рядом с врагом — (клетка, враг)
            spots = self.b.reach_spots(card, mode)
            if cell in spots:
                foes = spots[cell]
                return (cell, foes[0] if len(foes) == 1 else None)
        for t in ts:
            if (t.cell if hasattr(t, "cell") else t) == cell:
                return t
        return None

    def select(self, card, mode):
        if self.busy or self.b.result:
            return
        ts = self.b.targets(card, mode)
        if not ts:
            self.toast = (self.unplayable_reason(card, mode), 1.2)
            return
        self.shot_pick = None
        self.hand_picks.clear()
        if card.d[mode]["target"] == "self" and ts == [self.b.hero]:
            self.fire(card, mode, self.b.hero)
            return
        self.sel = (card, mode)

    def unplayable_reason(self, card, mode):
        b = self.b
        if b.attacks_locked(card):
            return "Глухая оборона закрывает карты атаки"
        if mode == "main" and not b.can_afford(card):
            return "Не хватает ресурса для розыгрыша"
        target = card.d[mode].get("target")
        if target == "ballista_place" and b.ballista_locked(card):
            return "Установка этой карты уже на поле"
        if target == "ballista_fire":
            if not b.ballistas:
                return "Сначала поставьте баллисту"
            if not any(unit.charge for unit in b.ballistas):
                return "Сначала зарядите баллисту"
            return "На линиях баллисты сейчас нет цели"
        if target == "copy_hand":
            return "В руке нужна другая карта, которую можно скопировать"
        if target in ("hand_retain", "hand_other"):
            return "В руке недостаточно подходящих карт"
        return "Нет доступной цели"

    def choose_hand_target(self, card, mode, target):
        if target in self.hand_picks:
            self.hand_picks.remove(target)
            return
        self.hand_picks.append(target)
        if len(self.hand_picks) == card.d[mode].get("count", 1):
            chosen = tuple(self.hand_picks) if len(self.hand_picks) > 1 else target
            self.hand_picks.clear()
            if self.chain_pick is not None:
                self.chain_choose(chosen)
            else:
                self.fire(card, mode, chosen)

    def chain_choose(self, target):
        """Игрок выбрал цель для не-атаки, которую разыграла Цепочка."""
        if self.chain_pick is None:
            return
        self.hand_picks.clear()
        self.chain_pick = None
        self.chain_send = target
        self.chain_send_ready = True
        self.sel = None
        self.wait = 0.0

    def fire(self, card, mode, target):
        """Сыграть: карта летит к цели и гаснет, бой отыгрывает её."""
        self.sel = None
        self.hand_picks.clear()
        self.drag = False
        self.hv.drag = None
        v = self.view
        aim = (target.statue if isinstance(target, IdolCast) else target.ballista if isinstance(target, BallistaShot)
               else target[1] if self.b.is_spot(target) else target)
        if isinstance(aim, tuple) and aim and isinstance(aim[0], M.Card):
            aim = aim[-1]
        if isinstance(aim, M.Card):
            sprite = self.hv.sprites.get(aim.uid)
            pos = self.hv.rect_of(sprite).center if sprite is not None else self.mouse
        else:
            x, y = v.cam(v.feet_pos(aim)) if hasattr(aim, "cell") else v.cam(T.cell_feet(aim))
            pos = (x, y - 40)
        self.hv.played(card, pos)
        self.pick = None
        self.shot_pick = None
        self.prayer = None
        self.run_job(self.b.play(card, mode, target))

    def ready(self):
        """Бой показан: земля построена (или рисуем на обычной поверхности — тесты, снимки)."""
        return self.ground.img is not None or not getattr(self, "_canvas_seen", False)

    def open_pile(self, key):
        """Открыть стопку боя: deck / used / discard / exhaust."""
        from .piles import PileScreen
        self.game.scene = PileScreen(self.game, self, key)

    def handle(self, ev):
        if not self.ready():
            if hasattr(ev, "pos"):
                self.mouse = ev.pos
            return
        if self.relic_choice is not None:
            self.handle_relic_choice(ev)
            return
        if self.b.pending_discard:                            # Адажио: выбор карт для сброса
            if ev.type == pygame.MOUSEMOTION:
                self.mouse = ev.pos
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                uid = self.hv.hit(ev.pos)
                card = next((c for c in self.b.hand if c.uid == uid), None)
                if card is not None:
                    if card in self.discard_pick:
                        self.discard_pick.remove(card)
                    elif len(self.discard_pick) < self.b.pending_discard:
                        self.discard_pick.append(card)
                    need = min(self.b.pending_discard, len(self.b.hand))
                    if len(self.discard_pick) >= need:
                        self.resolve_player_discard(tuple(self.discard_pick))
                        self.discard_pick = []
            return
        if self.chain_pick is not None:                       # Цепочка ждёт выбора цели для не-атаки
            if ev.type == pygame.MOUSEMOTION:
                self.mouse = ev.pos
                self.hover_cell = self.cell_at(ev.pos)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                card, mode = self.chain_pick
                target = self.target_at(ev.pos, (card, mode))
                if target is not None:
                    if card.d[mode]["target"] in M.HAND_TARGETS:
                        self.choose_hand_target(card, mode, target)
                    else:
                        self.chain_choose(target)
                elif ev.pos[1] < self.hand_area.y:
                    self.toast = (f"«{card.name}»: выберите подсвеченную цель", 1.2)
            return
        if self.ui_event(ev):
            return
        if ((ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3) or
                (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE)) and (
                self.shot_pick or (self.sel and self.sel[0].d[self.sel[1]]["target"] in M.HAND_TARGETS)):
            self.sel = self.press = self.shot_pick = None
            self.hand_picks.clear()
            self.drag = False
            self.hv.drag = None
            return
        if ev.type == pygame.MOUSEMOTION and self.inspect is not None and self.inspect.pinned:
            self.inspect.mouse = ev.pos                      # читают карту — мышь только для чтения,
            return                                           # рука и поле её не видят
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            self.hover_cell = self.cell_at(ev.pos)
            if self.press and not self.drag and math.dist(ev.pos, self.press[2]) > 10 and not self.busy:
                self.inspect = None                          # повели — это перетаскивание, а не осмотр
                card, button, _ = self.press                 # тянут карту — играется сторона, что сверху;
                self.drag = True                             # цель проверяется только при отпускании
                self.sel = (card, self.hv.mode(card.uid))
                self.hv.start_drag(card.uid, ev.pos)
        elif ev.type == pygame.MOUSEWHEEL and self.inspect is not None:
            self.inspect.wheel(ev.y)                          # читают карту — уровень открытой карты
            return
        elif ev.type == pygame.MOUSEWHEEL:
            card = (self.sel[0] if self.drag and self.sel else                     # тянут — её; иначе та,
                    next((c for c in self.b.hand if c.uid == self.hv.hit(self.mouse)), None)   # что под мышью
                    or (self.sel[0] if self.sel else None))
            if card is not None and card.levels:                  # уровень карты: колесо вверх — сильнее
                card.manual = True
                card.lvl = max(0, min(len(card.levels) - 1, card.lvl + (1 if ev.y > 0 else -1)))
                if self.sel and self.sel[0] is card:
                    self.hand_picks.clear()
                    self.sel = (card, self.sel[1])
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and self.inspect is not None and self.inspect.pinned:
            if self.inspect.click(ev.pos, ev.button):        # созданная карта — открыть; ПКМ — назад
                return
            if not self.inspect.contains(ev.pos):            # клик мимо — закрыть чтение
                self.inspect = None
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and (self.drag or self.press):
            card = self.sel[0] if self.drag and self.sel else self.press[0] if self.press else None
            if card is None or card.d["alt"].get("target") == "none":    # нечего поворачивать (свиток) — отмена
                self.drag = False
                self.hv.drag = None
                self.press = None
                self.sel = None
                self.prayer = None
                return
            self.hv.flip(card.uid)                           # тянут — повернуть её же
            if self.drag:
                self.sel = (card, self.hv.mode(card.uid))
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            self.mouse = ev.pos
            if not self.ui_hidden and ev.button == 1:
                if self.deck_pile_rect is not None and self.deck_pile_rect.collidepoint(ev.pos):
                    self.open_pile("deck")
                    return
                if self.discard_pile_rect is not None and self.discard_pile_rect.collidepoint(ev.pos):
                    self.open_pile("discard")
                    return
            if self.end_rect.collidepoint(ev.pos) and ev.button == 1:
                self.end_turn()
                return
            uid = self.hv.hit(ev.pos)
            card = next((c for c in self.b.hand if c.uid == uid), None)
            if self.sel and not self.busy and self.sel[0].d[self.sel[1]]["target"] in M.HAND_TARGETS:
                target = self.target_at(ev.pos)
                if target is not None:
                    self.choose_hand_target(*self.sel, target)
                    return
            if card is not None and ev.button == 3:          # ПКМ — повернуть карту
                if card.d["alt"].get("target") == "none":    # простого нет (свиток Жреца) — не переворачивать
                    self.toast = ("У этой карты нет простого применения", 1.2)
                    return
                self.hv.flip(card.uid)
                if self.sel and self.sel[0] is card:
                    self.sel = (card, self.hv.mode(card.uid)) if self.b.targets(card, self.hv.mode(card.uid)) else None
                return
            if card is not None and not self.busy:
                self.press = (card, ev.button, ev.pos)
                self.press_t = 0.0
                return
            if ev.button == 3:
                self.sel = None
                self.prayer = None
                return
            if self.prayer and not self.busy:                    # Жрец: цель для свитка на статуе
                t = self.prayer_target(ev.pos)
                if t is not None:
                    self.fire(self.prayer[0], "main", t)
                elif ev.pos[1] < self.hand_area.y:
                    self.prayer = None
                    self.sel = None
                return
            if self.b.idols is not None and not self.sel and not self.busy:     # Жрец: клик по клетке — идти
                cell = self.cell_at(ev.pos)
                if cell in self.b.walk_cells():
                    self.run_job(self.b.hero_walk(cell))
                    return
            if self.pick and not self.busy:                     # кого бить с выбранной клетки
                card, mode, cell, foes = self.pick
                f = self.view.pick_unit(ev.pos, lambda v: v in foes)
                if f is None:
                    f = next((x for x in foes if x.cell == self.cell_at(ev.pos)), None)
                self.pick = None
                if f is not None:
                    self.fire(card, mode, (cell, f))
                return
            if self.sel and not self.busy:
                t = self.target_at(ev.pos)
                if t is None and not self.shot_pick and ev.pos[1] < self.hand_area.y:
                    t = self.b.auto_target(*self.sel)
                if t is not None and not self.ask_pick(*self.sel, t):
                    self.fire(*self.sel, t)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.mouse = ev.pos
            if self.inspect is not None and not self.inspect.pinned:      # отпустили после осмотра — закрыть
                self.inspect = None
                self.press = None
                return
            if self.drag and self.sel:                       # отпустили тянутую карту — только тут она играется
                card, mode = self.sel
                if card.d[mode]["target"] in M.HAND_TARGETS and self.b.targets(card, mode):
                    target = self.target_at(ev.pos)
                    self.drag = False
                    self.hv.drag = None
                    if target is not None:
                        self.choose_hand_target(card, mode, target)
                    self.press = None
                    return
                if not self.b.targets(card, mode):
                    self.toast = (self.unplayable_reason(card, mode), 1.4)
                elif card.d[mode]["target"] == "self" and self.b.targets(card, mode) == [self.b.hero]:
                    if ev.pos[1] < self.hand_area.y:
                        self.fire(card, mode, self.b.hero)
                else:
                    t = self.target_at(ev.pos)
                    if t is None and ev.pos[1] < self.hand_area.y:      # атаку просто разыграли — ближайшему
                        t = self.b.auto_target(card, mode)
                    if self.ask_pick(card, mode, t):
                        self.drag = False
                        self.hv.drag = None
                        return
                    if t is not None:
                        self.fire(card, mode, t)
                self.drag = False
                self.hv.drag = None
                if self.sel and self.sel[0] is card:
                    self.sel = None
                    self.shot_pick = None
            elif self.press:                                 # клик: выбрать карту, цель — следующим кликом
                card, button, _ = self.press
                if self.sel and self.sel[0] is card:
                    self.sel = None
                else:
                    self.select(card, self.hv.mode(card.uid))
            self.press = None
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):          # Shift — закрепить чтение / закрыть
                if self.inspect is not None and self.inspect.pinned:
                    self.inspect = None
                elif self.inspect is not None:
                    self.inspect.pinned = True
                    self.inspect.mouse = self.mouse
                    self.press = None
                elif not self.drag:
                    uid = self.hv.hit(self.mouse)
                    card = next((c for c in self.b.hand if c.uid == uid), None)
                    if card is not None:
                        sp = self.hv.sprites.get(uid)
                        self.inspect = Inspector(card, sp.x if sp else None, self.state_of(card), pinned=True)
                        self.inspect.mouse = self.mouse
                return
            if ev.key == pygame.K_BACKSPACE and self.inspect is not None and self.inspect.back():
                return
            if ev.key == pygame.K_ESCAPE and self.inspect is not None:
                self.inspect = None
                return
            if ev.key == pygame.K_ESCAPE:
                self.sel = None
                self.pick = None
                self.prayer = None
            elif ev.key in (pygame.K_SPACE, pygame.K_e):
                self.end_turn()
            elif pygame.K_1 <= ev.key <= pygame.K_9:
                i = ev.key - pygame.K_1
                if i < len(self.b.hand):
                    c = self.b.hand[i]
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:       # Shift+цифра — повернуть
                        self.hv.flip(c.uid)
                    else:
                        self.select(c, self.hv.mode(c.uid))

    def prayer_target(self, pos):
        """Свиток лежит на статуе: цель под курсором среди вариантов бога (враг — по фигурке, клетка — по земле)."""
        card, st, opts = self.prayer
        units = [o for o in opts if hasattr(o, "cell")]
        if units:
            u = self.view.pick_unit(pos, lambda v: v in units, reach=8)
            if u is not None:
                return IdolCast(st, u)
        cell = self.cell_at(pos)
        if cell is None:
            return None
        if cell in opts:
            return IdolCast(st, cell)
        u = next((o for o in units if o.cell == cell), None)
        return IdolCast(st, u) if u is not None else None

    def ask_prayer(self, card, st):
        """Свиток положили на статую: без выбора — играется сразу; иначе ждём цель (подсветка — её досягаемость)."""
        opts = self.b.idols.choices(st, card.d["meaning"])
        if opts is None:
            self.fire(card, "main", IdolCast(st, None))
            return True
        if not opts:
            self.toast = (f"{st.god['name']}: некуда — нет цели в досягаемости", 1.6)
            return True
        self.prayer = (card, st, opts)
        self.sel = (card, "main")
        return True

    def ask_pick(self, card, mode, t):
        """Подошли на клетку, а рядом несколько врагов — спросить, кого бить. True — ждём клика."""
        if isinstance(t, IdolCast):                           # Жрец: цель свитка выбрана — играть
            self.fire(card, "main", t)
            return True
        if card.d[mode]["target"] == "statue" and t is not None and getattr(t, "statue", None):
            return self.ask_prayer(card, t)
        if card.d[mode]["target"] == "ballista_fire" and t is not None and not isinstance(t, BallistaShot):
            shooters = self.b.ballista_shooters(t, card.d[mode].get("range", 6))
            if len(shooters) == 1:
                self.fire(card, mode, BallistaShot(shooters[0], t))
            elif shooters:
                self.shot_pick = (card, mode, t)
                self.sel = (card, mode)
            return bool(shooters)
        if isinstance(t, tuple) and len(t) == 2 and isinstance(t[0], tuple) and t[1] is None:
            self.pick = (card, mode, t[0], self.b.reach_spots(card, mode)[t[0]])
            self.sel = (card, mode)
            self.toast = ("Рядом несколько врагов — кликните, кого бить", 2.0)
            return True
        return False

    def aim(self):
        """Цель под мышью — или, если тянут атаку над полем мимо врагов, та, кого она ударит сама.
        Возвращает (цель, сама ли)."""
        if not self.sel:
            return None, False
        t = self.target_at(self.mouse)
        if t is not None:
            return t, False
        card, mode = self.sel
        if self.drag and self.mouse[1] < self.hand_area.y:
            t = self.b.auto_target(card, mode)
            return t, t is not None
        return None, False

    def end_turn(self):
        if self.busy or self.b.result:
            return
        self.sel = None
        self.hand_picks.clear()
        self.shot_pick = None
        self.run_job(self.b.end_turn())

    # ---------- земля ----------

    def ground_hook(self, ov):
        """На пиксельной земле — только то, что лежит на ней: тени облаков, круги на воде, капканы."""
        self.life.draw_ground(ov)
        for p in self.b.traps:                           # капканы Охотницы
            r = FR(p)
            pygame.draw.circle(ov, (40, 30, 20, 220), r.center, r.w // 3)
            pygame.draw.circle(ov, (230, 200, 130, 255), r.center, r.w // 3, 3)
            for a in range(0, 360, 45):
                v = pygame.math.Vector2(1, 0).rotate(a)
                pygame.draw.line(ov, (230, 200, 130, 255), (r.centerx + v.x * r.w // 6, r.centery + v.y * r.w // 6),
                                 (r.centerx + v.x * r.w // 3, r.centery + v.y * r.w // 3), 2)

    def feet(self, u):
        """Где стоит фигурка — в клетках земли (с учётом шага)."""
        return self.view.ground_pos(u)

    def collect_idols(self, h, pulse):
        """Жрец: шаги, статуи (кольцо цвета бога), досягаемость при свитке, варианты цели, топь, тучи, нити."""
        b = self.b
        idols = b.idols
        for m in idols.mud:                                    # топь Велеса
            h.zone([m], (110, 90, 50), 90, 160, 1.5, glow=False)
        for cell, _t in idols.clouds:                          # грозовые тучи
            h.blob(P.cell_ground(cell), 0.55, 0.3, (20, 30, 60), 150)
            h.ring(P.cell_ground(cell), 0.42, (150, 190, 255), int(150 + 80 * pulse), 2, squash=0.55)
        seen = set()
        for f in b.foes():                                     # нити Мокоши
            mate = getattr(f, "bound_to", None)
            if f.ds.get("bound") and mate is not None and mate.alive and (mate.id, f.id) not in seen:
                seen.add((f.id, mate.id))
                h.line(self.feet(f), self.feet(mate), (210, 170, 240), 200, 2, dash=0.18)
        for st in idols.statues:
            col = tuple(st.god["color"])
            h.ring(self.feet(st), 0.4, col, 230, 2.2, squash=0.55)
            if st.rod:
                h.ring(self.feet(st), 2.4, (170, 210, 255), int(60 + 60 * pulse), 1.4, glow=False, squash=1.0)
        if self.prayer is not None:                            # цель свитка: досягаемость статуи и варианты
            card, st, opts = self.prayer
            col = tuple(st.god["color"])
            h.zone(idols.reach(st), col, 26, 140, 1.5, glow=False)
            for o in opts:
                if hasattr(o, "cell"):
                    h.ring(self.feet(o), 0.48, col, int(160 + 80 * pulse), 2.4, squash=0.55)
                else:
                    h.cell(o, col, 40, 170, 0.12, 1.5)
            t = self.prayer_target(self.mouse)
            if t is not None and t.tgt is not None:
                c0 = self.feet(t.tgt) if hasattr(t.tgt, "cell") else P.cell_ground(t.tgt)
                h.line(self.feet(st), c0, col, 230, 2.5)
            return
        if self.sel and self.sel[0].d[self.sel[1]].get("target") == "statue":   # свиток в руке: статуи и досягаемость
            card = self.sel[0]
            ts = b.targets(card, "main")
            hov = self.target_at(self.mouse)
            for st in ts:
                h.ring(self.feet(st), 0.55, (255, 240, 200), int(140 + 100 * pulse), 2.4, squash=0.55)
            if hov is not None and getattr(hov, "statue", None):
                h.zone(idols.reach(hov), tuple(hov.god["color"]), 30, 170, 1.5, glow=False)
            return
        if not self.busy and b.walk_left > 0:                  # шаги Жреца
            h.zone(list(b.walk_cells()), (150, 230, 170), 22, 120, 1.2, glow=False)

    def collect_hints(self, h):
        """Подсказки на поле — чётким слоем (deck/hints.py): зоны врагов, дальность и цели карты, путь, кольца."""
        b = self.b
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 180)
        hero = b.hero
        if self.relic_choice is not None:
            pointed = next((value for r, value in self.relic_choice_hits if r.collidepoint(self.mouse)), None)
            hot_cell = self.relic_choice_cell(pointed)
            for _, value in self.relic_choice.options:
                cell = self.relic_choice_cell(value)
                if cell is not None:
                    h.cell(cell, T.SELECT, fill=65 if cell == hot_cell else 30, width=2.5, glow=True)
        c = lambda p: P.cell_ground(p)                    # noqa: E731 — центр клетки
        self.life.collect(h)                              # тени облаков и птиц, круги на воде
        if b.idols is not None:
            self.collect_idols(h, pulse)
        SURF = {"poison": (120, 220, 80), "fire": (255, 130, 50), "oil": (150, 110, 50), "fog": (190, 200, 210),
                "briar": (110, 160, 70), "cracks": (210, 170, 120)}
        for pos, cell in self.combat.grid.cells.items():  # покрытия поля (docs/descent_field.md)
            col = SURF.get(cell.hazard)
            if col is None:
                continue
            h.zone([pos], col, int((50 if cell.hazard in ("poison", "fire") else 38) + 25 * pulse), 0, glow=False)
            if cell.hazard in ("poison", "fire"):
                for i in range(3):                        # пузыри / угли
                    q = (pos[0] + 0.2 + 0.3 * ((pos[0] * 7 + i * 5) % 3), pos[1] + 0.25 + 0.25 * i)
                    h.ring(q, 0.05 + 0.02 * math.sin(pygame.time.get_ticks() / 300 + i), col, 200, 1.2, glow=False)
            elif cell.hazard == "cracks":                 # трещина: кольца по заряду
                for i in range(b.cracks_at(pos)):
                    h.ring((pos[0] + 0.5, pos[1] + 0.5), 0.12 + 0.07 * i, col, 210, 1.4, glow=False)
        if b.env_now:                                     # природа: что случится в ход врагов
            e = b.env_now
            col = (150, 200, 255) if e["kind"] == "gust" else (255, 110, 40)
            h.zone(e["cells"], col, int(40 + 40 * pulse), 230, 2.0)
        if b.garden is not None:                          # фейные кольца эльфа — мягкая зелёная зона
            for ring in b.garden.rings:
                h.zone(list(ring["cells"]), (130, 225, 150), int(22 + 18 * pulse), 140, 1.2, glow=False)
        for p, _n in b.traps.items():                    # капканы Охотницы: кольцо с зубьями
            cc = c(p)
            h.ring(cc, 0.26, (235, 205, 140), 240, 2.0, glow=False, fill=90, squash=0.9)
            for a in range(0, 360, 45):
                va = math.radians(a)
                h.line((cc[0] + math.cos(va) * 0.13, cc[1] + math.sin(va) * 0.12),
                       (cc[0] + math.cos(va) * 0.26, cc[1] + math.sin(va) * 0.234), (235, 205, 140), 230, 1.5, glow=False)
        for u in self.combat.units:                       # мягкая тень и кольцо: свои — голубые, враги — красные
            if not u.alive:
                continue
            fp = self.feet(u)
            rr = 0.42 if u.boss else 0.34
            h.blob((fp[0], fp[1] + 0.02), rr * 1.05, rr * 0.5, (0, 0, 0), 150)
            if u.obj:
                continue
            col = (120, 196, 255) if u.team != ENEMY else (255, 96, 76)
            if u.boss or u.elite:
                h.ring(fp, rr + 0.08, (240, 200, 80) if u.boss else (210, 215, 225), 210, 1.4, glow=False, squash=0.5)
            h.ring(fp, rr, col, 220, 1.8, glow=False, squash=0.5)
        hov = self.view.pick_unit(self.mouse) if not self.sel and self.mouse[1] < self.hand_area.y else None
        if hov is not None and hov.alive:                 # под курсором — белое кольцо
            h.ring(self.feet(hov), 0.46 + 0.03 * math.sin(pygame.time.get_ticks() / 120), (255, 255, 255), 230, 2.2,
                   squash=0.55)
        for u in b.foes():                                # намерения: зоны и линии
            it = u.intent or {}
            k = it.get("kind")
            if k == "zone":
                h.zone(b.zone_hit_cells(it), (255, 70, 50), int(45 + 45 * pulse), 235, 2.5)
            elif k == "charge":                           # линия рывка — отмечена заранее
                h.zone(it.get("cells", []), (255, 110, 60), int(40 + 40 * pulse), 230, 2.5)
            elif k == "pull":                             # досягаемость утягивания
                h.zone(b.fire_zone(u, it), (90, 170, 255), int(18 + 16 * pulse), 150, 1.5, glow=False)
                if b.in_fire_zone(u, it):
                    h.line(self.feet(u), self.feet(hero), (120, 200, 255), 230, 3)
            elif k == "shot":                             # зона обстрела: стрелок стоит и бьёт сюда
                h.zone(b.fire_zone(u, it), (255, 160, 70), int(22 + 18 * pulse), 170, 1.5, glow=False)
                if b.in_fire_zone(u, it):
                    h.line(self.feet(u), self.feet(hero), (255, 170, 80), 230, 3)
        if b.mech == "momentum" and hero.ds["momentum"] and hero.alive:     # разгон — свечение под героем
            k = hero.ds["momentum"] / max(1, b.hero_def.get("momentum_max", 5))
            h.ring(self.feet(hero), 0.42 + 0.2 * k, (255, 180, 90), int(120 + 100 * k * pulse), 2.2, squash=0.55)
        for u in b.foes():                                # прицел стрелка — красная нить к герою
            if u.ds["aim"] > 1 and hero.alive:
                h.line(self.feet(u), self.feet(hero), (255, 50, 50), int(110 + 140 * pulse), 3)
                h.ring(self.feet(hero), 0.3, (255, 70, 70), 220, 2)
        if self.zone_t > 0:
            h.zone(getattr(self, "_zone_cells", []), (255, 200, 120), int(200 * self.zone_t / 0.6), 0)
        if hov is not None and hov.team == ENEMY and hov.alive:     # куда дойдёт враг
            h.zone(b.paths(hov, hov.speed), (255, 130, 100), 34, 150, 1.5, glow=False)
        if self.sel:
            card, mode = self.sel
            u = card.d[mode]
            if u["target"] in M.HAND_TARGETS:
                return
            h.zone(b.range_cells(card, mode), (255, 205, 120), 30, 170, 1.5, glow=False)   # дальность — всегда
            for t in b.targets(card, mode):
                h.cell(t.cell if hasattr(t, "cell") else t, (255, 230, 120), 50, 210, 0.1, 2)
            if u["target"] == "reach":                    # куда можно встать рядом с врагом
                for q in b.reach_spots(card, mode):
                    h.ring(c(q), 0.12, (120, 220, 255), 230, 2, fill=120, glow=False)
            if u["target"] == "ballista_fire":
                victim = self.shot_pick[2] if self.shot_pick else None
                shooters = (b.ballista_shooters(victim, u.get("range", 6)) if victim is not None
                            else [unit for unit in b.ballistas if unit.charge])
                for shooter in shooters:
                    h.ring(self.feet(shooter), 0.49, (255, 215, 132), 230, 2.5, squash=0.55)
                    if victim is not None:
                        h.line(self.feet(shooter), self.feet(victim), (255, 206, 115), 130, 2, glow=False)
            if self.pick:                                  # рядом несколько — кого бить?
                pp = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 140)
                h.cell(self.pick[2], (120, 220, 255), 60, 240, 0.04, 3, glow=True)
                for f in self.pick[3]:
                    h.ring(self.feet(f), 0.5, (255, 120, 80), int(120 + 120 * pp), 3)
            t, auto = self.aim()
            shot_origin = t.ballista if isinstance(t, BallistaShot) else None
            if shot_origin is not None:
                t = t.victim
            spot = isinstance(t, tuple) and len(t) == 2 and isinstance(t[0], tuple)
            if spot:                                       # встать сюда: клетка и тот, кого ударит
                if t[1] is not None:
                    h.ring(self.feet(t[1]), 0.48, (255, 230, 120), 240, 3)
                t = t[0]
            if t is not None:
                p = t.cell if hasattr(t, "cell") else t
                h.cell(p, (255, 250, 210), 40, 250, 0.0, 3, glow=True)
                if auto:                                   # отпустят где угодно — ударит сюда
                    pp = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 140)
                    h.ring(self.feet(t) if hasattr(t, "cell") else c(p), 0.55, (255, 120, 80), int(120 + 120 * pp), 3)
                if u["target"] == "area":                  # область удара вокруг выбранной клетки
                    h.zone([q for q in b.c.grid.in_radius(p, u.get("radius", 1)) if b.c.grid.get(q) is not None],
                           (255, 140, 60), 70, 230, 2.5)
                elif u["target"] == "ballista_place":
                    for ray, victim in b.ballista_lines(origin=p):
                        color = (255, 206, 115) if victim is not None else (165, 184, 200)
                        h.zone(ray, color, 28, 145, 1.2, glow=False)
                elif u["target"] == "ballista_fire":
                    shooters = [shot_origin] if shot_origin else b.ballista_shooters(t, u.get("range", 6))
                    for shooter in shooters:
                        h.line(self.feet(shooter), self.feet(t), (255, 206, 115), 245, 3.5)
                path = None
                if u["target"] == "cell_step":
                    path = b.paths(hero, u.get("step", 1)).get(p)
                elif u["target"] == "cell_dash":
                    path = b.dash_paths(u.get("dash", 1)).get(p)
                elif u["target"] == "reach":
                    reach = b.paths(hero, u.get("reach", 1))
                    if spot:
                        path = reach.get(p)
                    else:
                        near = [q for q in reach if cheb(q, p) <= 1]
                        if near:
                            path = reach[min(near, key=lambda q: len(reach[q]))]
                if path:
                    h.path([self.feet(hero)] + [c(q) for q in path], (170, 255, 190), 235, 3)
        elif self.hover_cell and self.combat.grid.in_bounds(self.hover_cell) and self.mouse[1] < self.hand_area.y:
            h.cell(self.hover_cell, (255, 255, 255), 26, 170, 0.0, 1.5)     # клетка под курсором

    # ---------- отрисовка ----------

    def refresh_damage_previews(self):
        """Обновить зелёные числа на картах в руке под текущие баффы героя."""
        for c in getattr(self.game.run, "deck", []):
            c.preview = None
            c.preview_cost = None
        for c in self.b.hand:
            c.preview = {"main": self.b.damage_preview(c, "main"),
                         "alt": self.b.damage_preview(c, "alt")}
            c.preview_cost = self.b.effective_cost(c)

    def draw(self, surf):
        self.refresh_damage_previews()
        v = self.view
        if v._cpu_tex is None:
            v._cpu_tex = make_textures()
        self.hints.clear()
        self.collect_hints(self.hints)
        if G.is_canvas(surf):
            # поле с фигурками — пиксельный кадр 1280×800 (растянут) → подсказки чётко в родном разрешении →
            # фигурки ещё раз поверх подсказок → частицы и интерфейс — в родном разрешении
            if getattr(self, "_units", None) is None:
                self._units = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
                self._world = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
            self._canvas_seen = True
            if self._S != surf.S:                          # окно сменило размер — лица карт под новый
                self._S = surf.S
                self.hv.cache.clear()
                self.hv.zoom = max(1.4, 330 / (CW * surf.S))    # под мышью — не меньше ~330 пикселей в ширину
            v.painter.props(self.combat)                   # декор вокруг доски (и место травы) — по рельефу
            # заставка — один кадр на экране, затем земля строится сразу (параллельно, ~1.5 с), пока видно
            # название боя; бой появляется уже с готовой землёй
            first = self._intro_frames == 0 and not getattr(self.game, "sync_ground", False)
            self._intro_frames += 1
            if not first and self.ground.img is None:
                self.warm()                                # заодно — всё, что иначе грузилось бы посреди боя
            ground = None if first else self.ground.surface(surf, self.combat, v.painter, self.life.decal_list(),
                                                            wait=True)
            if ground is None:
                self.draw_intro(surf)
                return
            if self.shown_t is None:
                self.shown_t = self.intro_t
            surf.native.blit(ground, (0, 0))
            self.hints.draw(surf)
            surf.pixel = True                              # фигурки, трава, декор — прямо в родное разрешение,
            try:                                           # пиксели арта — ближайшие (без слоя и растяжения кадра)
                v._draw_world(surf, self)
            finally:
                surf.pixel = False
            v.vfx.draw_cpu(surf.native, v._cpu_tex, v._cpu_cache, props=v.props, scale=surf.S,
                           offset=(surf.ox, surf.oy))
        else:                                              # обычная поверхность (тесты, снимки) — всё в один кадр
            surf.fill(T.BG)
            v.draw_world(surf, self)
            self.hints.draw(Plain(surf))
            for img, r in v.unit_blits:
                surf.blit(img, r)
            v.vfx.draw_cpu(surf, v._cpu_tex, v._cpu_cache, props=v.props)
        v.icon_tips = []                                   # полоски HP и цифры урона — на чётком слое
        v._fc = self.forecast()
        for u in self.combat.units:                       # HP и состояния — видны и при скрытом интерфейсе
            if u.alive:
                self.draw_unit_hud(surf, u, v._fc)
        self.draw_intents(surf)
        self.draw_idol_intents(surf)
        v._draw_fx(surf)                                   # цифры урона — поверх табличек намерений
        if not self.ui_hidden:
            self.draw_top(surf)
            self.draw_side(surf)
        self.draw_hand(surf)
        if self.b.pending_discard:
            self.draw_discard_choice(surf)
        self.draw_chain_show(surf)
        self.draw_eye(surf)
        if not self.ui_hidden:
            self.draw_tip(surf)
        if self.toast and not self.ui_hidden:
            T.text(surf, self.toast[0], (T.SCREEN_W // 2 - 140, T.SCREEN_H - 230), 18, (255, 200, 120), True,
                   center=True, shadow=True)
        if self.inspect is not None:                      # осмотр карты (удержание) или чтение (Shift)
            self.inspect.draw(surf, self.inspect.mouse or self.mouse)
        self.draw_help(surf)
        self.bag.draw(surf, self.game.run, self.b)
        if self.relic_choice is not None:
            self.draw_relic_choice(surf)

    def complete_relic_choice(self, value):
        self.relic_choice = None
        self.chain_send = value
        self.chain_send_ready = True

    def resolve_player_discard(self, cards):
        current = self.job

        def job():
            yield from self.b.resolve_discard_gen(cards)
            if current is not None:
                yield from current

        self.run_job(job())

    def handle_relic_choice(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:
            limit = max(0, len(self.relic_choice.options) - 6)
            self.relic_choice_offset = max(0, min(limit, self.relic_choice_offset - ev.y))
            self.relic_choice_hits = []
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.complete_relic_choice(None)
            elif pygame.K_1 <= ev.key <= pygame.K_6:
                index = self.relic_choice_offset + ev.key - pygame.K_1
                if index < len(self.relic_choice.options):
                    self.complete_relic_choice(self.relic_choice.options[index][1])
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for rect, value in self.relic_choice_hits:
                if rect.collidepoint(ev.pos):
                    self.complete_relic_choice(value)
                    return
            clicked = self.cell_at(ev.pos)
            if clicked is not None:
                for _, value in self.relic_choice.options:
                    if self.relic_choice_cell(value) == clicked:
                        self.complete_relic_choice(value)
                        return

    def relic_choice_cell(self, value):
        p = getattr(value, "cell", value)
        if isinstance(p, tuple) and len(p) == 2 and all(type(x) is int for x in p) and self.b.c.grid.get(p):
            return p
        return None

    def draw_relic_choice(self, surf):
        choice = self.relic_choice
        visible = choice.options[self.relic_choice_offset:self.relic_choice_offset + 6]
        panel = pygame.Rect(T.SCREEN_W - 486, 128, 440, 138 + 44 * len(visible))
        T.frame(surf, panel, 248, accent=T.AMBER)
        for i, line in enumerate(T.wrap(choice.prompt, 17, panel.w - 30)):
            T.text(surf, line, (panel.x + 16, panel.y + 14 + 20 * i), 17, T.AMBER, True)
        self.relic_choice_hits = []
        if len(choice.options) > 6:
            first = self.relic_choice_offset + 1
            T.text(surf, f"{first}–{first + len(visible) - 1} из {len(choice.options)} · колесо",
                   (panel.x + 16, panel.bottom - 70), 12, T.TEXT_DIM)
        for i, (label, value) in enumerate(visible):
            rect = pygame.Rect(panel.x + 14, panel.y + 74 + 44 * i, panel.w - 28, 38)
            button(surf, rect, f"{i + 1}. {label}", self.mouse)
            self.relic_choice_hits.append((rect, value))
        decline = pygame.Rect(panel.x + 14, panel.bottom - 50, panel.w - 28, 38)
        button(surf, decline, "Пропустить (Esc)", self.mouse)
        self.relic_choice_hits.append((decline, None))
        if self.shown_t is not None and G.is_canvas(surf):  # бой проявляется из темноты заставки
            k = (self.intro_t - self.shown_t) / 0.5
            if k < 1:
                dim(surf, int(255 * (1 - k) ** 1.5))

    def warm(self):
        """Во время заставки: лица карт колоды, картинки и значки интерфейса, шрифты, спрайты — заранее,
        чтобы в бою ничего не грузилось с диска и не собиралось в первый раз (это и давало подлагивания)."""
        seen = set()
        for c in list(self.b.draw_pile) + list(self.b.hand) + list(getattr(self.game.run, "deck", [])):
            if id(c) in seen:
                continue
            seen.add(id(c))
            for st in ((True, True, False, None, False), (False, True, False, None, False),
                       (True, True, False, None, True)):
                try:
                    CF.face(c, *st, width=self.face_w())
                except Exception:                          # лицо карты — не повод не начать бой
                    break
        sk = self.skin
        for name in ("corner", "edge", "fill", "portrait", "orb", "button", "ribbon", "divider", "medallion",
                     "badge", "pip_on", "pip_off"):
            sk.art(name)
        for key in list(self.INTENT_ICON.values()) + [s[1] for s in self.STATES] + ["s_shield"]:
            sk.icon(key, 24)
        for size in (11, 12, 13, 14, 15, 16, 18):
            T.font(size)
            T.font(size, True)
        for u in self.combat.units:
            for flip in (False, True):
                self.view.sprite_of(u, flip)

    def draw_intro(self, surf):
        """Заставка боя, пока строится земля: тьма, название боя, этаж."""
        sk = self.skin
        surf.native.fill((8, 7, 6))
        b = self.b
        last = getattr(self.game.run, "last_floor", False)
        tag = ("босс главы" if last else "страж лестницы") if b.fight.get("boss") else             "элита" if b.fight.get("elite") else "бой"
        k = min(1.0, self.intro_t / 0.4)
        col = tuple(int(c * k) for c in sk.p["title"])
        sk.text(surf, b.fight["name"], (T.SCREEN_W // 2, T.SCREEN_H // 2 - 18), 40, col, center=True, title=True)
        sk.text(surf, f"Этаж {self.game.run.depth} · {tag}", (T.SCREEN_W // 2, T.SCREEN_H // 2 + 26), 17,
                tuple(int(c * k) for c in sk.p["dim"]), center=True)
        for i in range(3):                                 # три огонька — идёт
            a = 0.5 + 0.5 * math.sin(self.intro_t * 5 - i * 0.9)
            pygame.draw.circle(surf, tuple(int(c * a * k) for c in sk.p["accent"]),
                               (T.SCREEN_W // 2 - 16 + i * 16, T.SCREEN_H // 2 + 62), 3)

    def forecast(self):
        """Прогноз урона выбранной карты по врагу под курсором: {индекс юнита: (урон, добьёт)}."""
        if not self.sel:
            return None
        card, mode = self.sel
        t = self.target_at(self.mouse)
        shot_origin = t.ballista if isinstance(t, BallistaShot) else None
        if shot_origin is not None:
            t = t.victim
        if t is None or not hasattr(t, "cell") or t is self.b.hero:
            return None
        dmg = 0
        for op in card.d[mode].get("do", []):
            if op["op"] == "damage":
                dmg += self.b.hit_value(self.b.hero, t, op["n"])
            elif op["op"] == "body_slam":
                dmg += self.b.hit_value(self.b.hero, t, self.b.hero.shield + op.get("n", 0))
            elif op["op"] == "ballista_fire":
                shooters = self.b.ballista_shooters(t, card.d[mode].get("range", 6))
                if shot_origin is not None or len(shooters) == 1:
                    dmg += self.b.ballista_damage(op, t, ballista=shot_origin or shooters[0])
        if not dmg:
            return None
        return {self.combat.units.index(t): (dmg, dmg >= t.hp + t.shield)}

    # ---------- интерфейс (deck/skin.py: свой у героя, чётко в родном разрешении) ----------

    @property
    def skin(self):
        return SK.use(getattr(self.b.run, "hero_id", "merc"))

    INTENT_ICON = {"melee": "i_melee", "shot": "i_shot", "zone": "i_zone", "block": "i_block", "aim": "i_aim",
                   "heal": "i_heal", "roar": "i_roar", "charge": "i_charge", "pull": "i_pull", "guard": "i_guard",
                   "rally": "i_rally", "veil": "i_veil", "curse": "i_curse", "hex": "i_hex", "drown": "i_drown",
                   "summon": "i_summon"}
    # состояния значками: ключ, значок, цвет, слово для словаря
    STATES = [("momentum", "s_momentum", (255, 180, 90), "Разгон"), ("strength", "s_strength", (255, 150, 90), "Мощь"),
              ("weak", "s_weak", (200, 160, 255), "Слабость"), ("vulnerable", "s_vulnerable", (255, 140, 200), "Уязвимость"),
              ("burn", "s_burn", (255, 130, 60), "Горение"), ("poison", "s_poison", (150, 230, 90), "Яд"),
              ("wet", "s_wet", (120, 180, 255), "Мокрый"), ("thorns", "s_thorns", (170, 220, 120), "Шипы"),
              ("rage", "s_rage", (255, 90, 70), "Раж"), ("frost", "s_frost", (170, 220, 255), "Мороз"),
              ("stun", "s_stun", (255, 230, 120), "Оглушение"), ("focus", "s_focus", (255, 220, 120), "Фокус"),
              ("aim", "s_mark", (255, 120, 90), "Прицел"), ("veil", "s_veil", (190, 190, 225), "Туман"),
              ("mark", "s_mark", (255, 215, 110), "Метка"),
              ("bleed", "s_bleed", (235, 70, 70), "Кровотечение"), ("counter", "s_counter", (255, 210, 150), "Контратака"),
              ("hunt", "s_mark", (255, 170, 90), "Преследование")]

    def intent_value(self, u, it):
        """Число на табличке медальона: урон, защита, сила…"""
        k = it.get("kind")
        if k in ("melee", "zone", "pull"):
            return self.b.intent_damage(u) or None
        if k == "shot":
            return self.b.intent_damage(u) if self.b.in_fire_zone(u, it) else "—"
        if k == "charge":
            return self.b.hit_value(u, self.b.hero, it.get("dmg", 0))
        if k == "aim":
            return f"×{it.get('mult', 2)}"
        if k in ("block", "heal", "guard"):
            return it.get("n", 0)
        if k == "rally":
            return f"+{it.get('n', 1)}"
        if k in ("roar",):
            return it.get("weak", 1)
        if k in ("curse", "hex", "drown"):
            return it.get("n", 1)
        return None

    def draw_intents(self, surf):
        """Намерения — медальоны над головами: значок, число; название — над медальоном при наведении."""
        v = self.view
        sk = self.skin
        e = self.b.env_now
        if e:                                                  # природа: подпись над героем
            fx, fy = v.cam(v.feet_pos(self.b.hero))
            arrow = {(1, 0): " →", (-1, 0): " ←", (0, 1): " ↓", (0, -1): " ↑"}.get(e.get("dir"), "")
            col = (170, 215, 255) if e["kind"] == "gust" else (255, 160, 90)
            sk.text(surf, e["name"] + arrow, (fx, fy - v.unit_h(self.b.hero) - 40), 15, col, center=True, title=True)
        hov = v.pick_unit(self.mouse) if self.mouse[1] < self.hand_area.y else None
        t = self.hv.t
        for u in self.b.foes():
            it = u.intent
            fx, fy = v.cam(v.feet_pos(u))
            bar_y = fy - v.unit_h(u) - 2 - 4.5                 # верх полоски HP (draw_unit_hud)
            states = [s for s in self.state_badges(u) if s[3] != "Защита"]
            top = bar_y - (44 if states else 26)                # медальон с табличкой — над значками состояний
            if it:
                k = it["kind"]
                col = INTENT_COL.get(k, T.TEXT)
                bob = 1.5 * math.sin(t * 2 + u.id)
                sk.medallion(surf, (fx, top + bob), 15, self.INTENT_ICON.get(k, "i_melee"), col,
                             self.intent_value(u, it), t)
                if u is hov:
                    sk.text(surf, it["name"], (fx, top - 30), 15, col, center=True, title=True)
            if u is self.b.prey:                               # Метка добычи
                sk.badge(surf, (fx - 30, top + 4), 11, "s_mark", (255, 215, 110), "+3")

    def draw_unit_hud(self, surf, u, fc=None):
        """Над фигуркой: полоска здоровья (гладкая, с делениями), щит значком, состояния значками, прогноз."""
        v = self.view
        sk = self.skin
        fx, fy = v.cam(v.feet_pos(u))
        top = fy - v.unit_h(u)
        if getattr(u, "statue", None):                  # статуя Жреца: медальон намерения, без полоски
            return
        if u.obj:
            if u.hp >= u.max_hp and u.team == 0:
                return
            r = pygame.Rect(0, 0, 40, 6)
            r.center = (fx, top + 10)
            self.hp_bar(surf, r, u.hp, u.max_hp, col=(200, 180, 150))
            if u in self.b.ballistas:
                col = (236, 205, 130) if u.charge else (150, 149, 140)
                sk.badge(surf, (fx, top - 8), 10, "s_ballista", col, f"{u.charge}/{u.charge_max}")
            return
        bw = 62 if u.boss else 52
        r = pygame.Rect(0, 0, bw, 9)
        r.center = (fx, top - 2)
        hero = u.team != ENEMY
        k = max(0.0, u.hp / max(1, u.max_hp))
        col = (90, 180, 255) if hero else T.mix((235, 70, 55), (130, 215, 90), k)
        f = (fc or {}).get(self.combat.units.index(u)) if fc else None
        self.hp_bar(surf, r, u.hp, u.max_hp, u.shield, col=col, ticks=True,
                    lost=(f[0] if f else 0), kill=bool(f and f[1]), t=self.hv.t)
        if u.shield:
            sk.badge(surf, (r.x - 9, r.centery), 9, "s_shield", (150, 190, 255), u.shield)
        states = [s for s in self.state_badges(u) if s[3] != "Защита"]
        x = fx - (len(states[:5]) - 1) * 10
        for icon, scol, n, _w in states[:5]:
            sk.badge(surf, (x, r.y - 12), 8, icon, scol, n)
            x += 20
        if f:                                                  # прогноз — справа от полоски, не под намерением
            s = "добьёт" if f[1] else f"−{f[0]}"
            sk.text(surf, s, (r.right + 6 + sk.size(s, 14, True)[0] / 2, r.centery), 14,
                    (255, 120, 90) if f[1] else (255, 230, 150), center=True, title=True)

    def draw_idol_intents(self, surf):
        """Жрец: над статуей — медальон её свитка-намерения (смысл, число); при наведении — название."""
        b = self.b
        if b.idols is None:
            return
        v = self.view
        sk = self.skin
        hov = v.pick_unit(self.mouse) if self.mouse[1] < self.hand_area.y else None
        for st in b.idols.statues:
            m, name, n = b.idols.intent_of(st)
            fx, fy = v.cam(v.feet_pos(st))
            top = fy - v.unit_h(st) - 30
            col = tuple(st.god["color"])
            sk.medallion(surf, (fx, top + 1.5 * math.sin(self.hv.t * 2 + st.id)), 14, MEANING_ICON[m], col,
                         n if n else None, self.hv.t)
            lv = b.idols.level(st)
            if lv:                                             # уровень бога — значком у медальона
                sk.badge(surf, (fx + 20, top - 12), 8, "", col)
                sk.text(surf, str(lv), (fx + 20, top - 12), 11, (255, 250, 235), center=True, title=True)
            if st is hov:
                sk.text(surf, f"{st.god['name']}: {name}", (fx, top - 28), 15, col, center=True, title=True)

    def draw_top(self, surf):
        """Слева сверху — плашка этажа: название боя, ход, золото; реликвии рядом."""
        b = self.b
        sk = self.skin
        last = getattr(self.game.run, "last_floor", False)
        tag = (" · босс главы" if last else " · страж лестницы") if b.fight.get("boss") else \
            " · элита" if b.fight.get("elite") else ""
        title = f"{b.fight['name']}{tag}"
        w = max(sk.size(title, 21, True)[0], 200) + 36
        r = pygame.Rect(12, 10, w, 60)
        sk.panel(surf, r, 228, accent=True)
        sk.text(surf, title, (r.x + 18, r.y + 7), 21, sk.p["title"], title=True)
        sk.text(surf, f"Этаж {self.game.run.depth} · ход {b.turn}", (r.x + 18, r.y + 35), 14, sk.p["dim"])
        gx = r.x + 18 + sk.size(f"Этаж {self.game.run.depth} · ход {b.turn}", 14)[0] + 18
        pygame.draw.circle(surf, (120, 84, 20), (gx + 6, r.y + 45), 7)
        pygame.draw.circle(surf, (250, 206, 92), (gx + 6, r.y + 45), 6)
        pygame.draw.circle(surf, (255, 240, 170), (gx + 4, r.y + 43), 2)
        sk.text(surf, str(self.game.run.gold), (gx + 17, r.y + 35), 14, (250, 214, 120))
        self.bag.bar(surf, self.game.run, (r.x + 6, r.bottom + 8), self.mouse, battle=self.b)   # предметы
        hr = self.help_rect
        hot = hr.collidepoint(self.mouse) or self.help_open
        sk.badge(surf, hr.center, 15, "", sk.p["accent"] if hot else (150, 130, 110))
        sk.text(surf, "?", hr.center, 20, sk.p["title"] if hot else sk.p["dim"], center=True, title=True)

    @property
    def help_rect(self):
        return pygame.Rect(T.SCREEN_W - 302, 20, 30, 30)

    @property
    def eye_rect(self):
        return pygame.Rect(T.SCREEN_W - 340, 20, 30, 30)

    def draw_eye(self, surf):
        """Значок-глаз рядом с «?»: скрыть интерфейс боя (Tab). Скрыт — глаз закрыт."""
        sk = self.skin
        r = self.eye_rect
        hot = r.collidepoint(self.mouse)
        col = sk.p["accent"] if hot else (150, 130, 110)
        sk.badge(surf, r.center, 15, "", col)
        cx, cy = r.center
        ink = sk.p["title"] if hot else sk.p["dim"]
        pts_top = [(cx - 9 + i, cy - round(5 * math.sin(math.pi * i / 18))) for i in range(19)]
        pygame.draw.lines(surf, ink, False, pts_top, 2)
        if self.ui_hidden:                                    # закрытый глаз — ресницы вниз
            for dx in (-5, 0, 5):
                pygame.draw.line(surf, ink, (cx + dx, cy + 1), (cx + dx * 1.3, cy + 5), 2)
        else:
            pts_bot = [(cx - 9 + i, cy + round(5 * math.sin(math.pi * i / 18))) for i in range(19)]
            pygame.draw.lines(surf, ink, False, pts_bot, 2)
            pygame.draw.circle(surf, ink, (cx, cy), 3)
        if hot:
            sk.text(surf, "Показать интерфейс (Tab)" if self.ui_hidden else "Скрыть интерфейс (Tab)",
                    (r.centerx, r.bottom + 12), 13, sk.p["text"], center=True)

    def toggle_ui(self):
        from ui import settings
        self.ui_hidden = not self.ui_hidden
        settings.SETTINGS["descent_hide_ui"] = self.ui_hidden
        if getattr(self.game, "save_settings", True):
            settings.save()

    @property
    def log_rect(self):
        return pygame.Rect(T.SCREEN_W - 262 + 12, 14 + 132, 224, 20)

    def state_badges(self, u):
        """[(значок, цвет, число, слово)] — состояния фигурки."""
        ds = u.ds
        out = []
        for key, icon, col, word in self.STATES:
            n = ds.get(key, 0)
            if key == "aim":
                n = n if n > 1 else 0
            if n:
                out.append((icon, col, n if not isinstance(n, bool) else "", word))
        if u.shield:
            out.insert(0, ("s_shield", (150, 190, 255), u.shield, "Защита"))
        if u is self.b.hero and self.b.stance:
            name, _, color = M.FIELD_STANCES[self.b.stance]
            out.insert(0, (f"s_stance_{self.b.stance}", color, "", name))
        return out

    def draw_side(self, surf):
        """Панель героя: портрет, имя, здоровье, состояния значками; журнал — свёрнут (L)."""
        b = self.b
        sk = self.skin
        h = b.hero
        r = pygame.Rect(T.SCREEN_W - 262, 14, 248, 156 + (118 if self.log_open else 0))
        sk.panel(surf, r, 236, accent=True)
        pc = (r.x + 40, r.y + 42)
        port = sk.art("portrait")
        native, S, pt = SK.ctx(surf)
        if port is not None:
            img = SK._remember(("portrait", sk.id, round(60 * S)),
                               lambda: pygame.transform.smoothscale(port, (round(60 * S), round(60 * S))))
            x, y = pt(pc)
            native.blit(img, (round(x - img.get_width() / 2), round(y - img.get_height() / 2)))
        else:
            sk.badge(surf, pc, 22, "", sk.p["accent"])
            sk.text(surf, h.name[:1], pc, 26, sk.p["title"], center=True, title=True)
        sk.text(surf, h.name, (r.x + 72, r.y + 12), 20, sk.p["title"], title=True)
        bar = pygame.Rect(r.x + 72, r.y + 40, r.w - 86, 16)          # здоровье: тёмный жёлоб, красная полоса
        self.hp_bar(surf, bar, h.hp, h.max_hp, h.shield)
        sk.text(surf, f"{max(0, h.hp)} / {h.max_hp}", bar.center, 13, (255, 244, 236), center=True)
        if b.idols is not None:                                # Жрец: уровни богов пантеона
            gl = "  ".join(f"{st.god['name']} {b.idols.level(st)}" for st in b.idols.statues)
            sk.text(surf, gl, (r.x + 72, r.y + 62), 11, sk.p["dim"], outline=False)
        x = r.x + 26
        y = r.y + 96
        self._state_tips = []
        states = self.state_badges(h) + [("s_power", (200, 150, 255), "", f"Сила: {c.name}") for c in b.powers]
        if b.double_attacks:
            states.insert(0, ("s_power", (255, 220, 120), b.double_attacks, "Двойной залп"))
        if not states:
            sk.text(surf, "без состояний", (r.x + 18, y - 9), 13, sk.p["dim"], outline=False)
        for icon, col, n, word in states[:8]:
            sk.badge(surf, (x, y), 13, icon, col, n)
            self._state_tips.append((pygame.Rect(x - 15, y - 15, 30, 30), word, n))
            x += 30
        lr = self.log_rect
        hot = lr.collidepoint(self.mouse)
        col = sk.p["accent"] if hot else sk.p["dim"]
        tx, ty = lr.x + 9, lr.y + 9                        # стрелка: вниз — открыт, вправо — свёрнут
        pygame.draw.polygon(surf, col, [(tx - 5, ty - 3), (tx + 5, ty - 3), (tx, ty + 3)] if self.log_open else
                            [(tx - 3, ty - 5), (tx + 3, ty), (tx - 3, ty + 5)])
        sk.text(surf, "Журнал  (L)", (lr.x + 20, lr.y), 13, col, outline=False)
        if self.log_open:
            yy = lr.bottom + 4
            lines = []
            for text, col in b.log[-14:]:
                for ln in wrap(text, 12, r.w - 30):
                    lines.append((ln, col))
            for ln, col in lines[-7:]:
                sk.text(surf, ln, (r.x + 16, yy), 12, col, outline=False)
                yy += 15
        else:                                                   # кладбище: сброс + Used текущего хода
            gy = pygame.Rect(r.x, r.bottom + 8, r.w, 28)
            sk.panel(surf, gy, 220)
            sk.text(surf, f"Сброс {len(b.discard)}  ·  за ход +{len(b.used)}",
                    (gy.centerx, gy.y + 7), 12, (226, 214, 192), center=True,
                    outline=False)

    def hp_bar(self, surf, r, hp, mx, shield=0, col=(206, 52, 44), ticks=False, lost=0, kill=False, t=0.0):
        native, S, pt = SK.ctx(surf)
        nr = pygame.Rect(*[round(v) for v in pt(r.topleft)], round(r.w * S), round(r.h * S))
        k = max(0.0, min(1.0, hp / max(1, mx)))
        key = ("hp", nr.size, round(k * 200), bool(shield), tuple(col), ticks)

        def make():
            out = pygame.Surface(nr.size, pygame.SRCALPHA)
            c = max(2, nr.h // 3)
            out.blit(SK.apply_mask(SK.vgrad(nr.w, nr.h, [(0, (12, 8, 8)), (1, (34, 22, 20))]),
                                   SK.mask(nr.size, SK.chamfer(nr.w, nr.h, c))), (0, 0))
            fw = max(0, round((nr.w - 4) * k))
            if fw > 2:
                g = SK.vgrad(fw, nr.h - 4, [(0, SK.lighter(col, 0.45)), (0.45, col), (1, SK.darker(col, 0.45))])
                out.blit(SK.apply_mask(g, SK.mask((fw, nr.h - 4), SK.chamfer(fw, nr.h - 4, max(1, c - 2)))), (2, 2))
            if ticks:                                          # деления по 10%
                for i in range(1, 10):
                    x = 2 + (nr.w - 4) * i / 10
                    pygame.draw.aaline(out, (12, 8, 6), (x, nr.h * (0.25 if i != 5 else 0.12)), (x, nr.h - 2),
                                       max(1, round(S * 0.6)))
            pts = SK.chamfer(nr.w - 1, nr.h - 1, c)
            for a_, b_ in zip(pts, pts[1:] + pts[:1]):
                pygame.draw.aaline(out, (150, 190, 255) if shield else (90, 66, 50), a_, b_, max(1, round(S)))
            return out
        native.blit(SK._remember(key, make), nr.topleft)
        if shield:                                             # щит — светлая полоса по верху
            sw = round(min(nr.w - 4, (nr.w - 4) * shield / max(1, mx)))
            pygame.draw.rect(native, (236, 242, 255), (nr.x + 2, nr.y + 1, sw, max(1, round(2 * S))))
        if lost or kill:                                       # прогноз удара — мигающий отрезок
            x1 = nr.x + 2 + (nr.w - 4) * k
            x0 = nr.x + 2 if kill else nr.x + 2 + (nr.w - 4) * max(0.0, (hp + shield - lost) / max(1, mx))
            if x1 - x0 >= 1:
                pulse = 0.55 + 0.45 * math.sin(t * 8)
                c2 = T.mix((255, 240, 160), (255, 255, 255), pulse)
                pygame.draw.rect(native, c2, (round(x0), nr.y + 2, max(2, round(x1 - x0)), nr.h - 4))

    def face_w(self, zoom=1.0):
        """Ширина лица карты в пикселях экрана: в покое или под мышью (крупно) — текст пишется в этом размере."""
        return round(CW * self._S * zoom)

    def card_face(self, card, st, zoom=1.0):
        return CF.face(card, *st, width=self.face_w(zoom))

    def state_of(self, c):
        b = self.b
        sel_uid = self.sel[0].uid if self.sel else None
        return (b.can_play(c, "main"), b.can_play(c, "alt"), c.uid in (self.hv.hover, sel_uid),
                b.hero.ds["heat"] if c.levels else None, b.lit(c))

    def hint_text(self):
        """Подсказка по текущему действию — над рукой."""
        b = self.b
        if b.result:
            return None
        if self.chain_pick:
            card, mode = self.chain_pick
            tg = card.d[mode]["target"]
            what = "клетку" if tg in ("cell_step", "cell_dash", "cell_any") else \
                "область" if tg == "area" else "цель"
            return f"Цепочка: выберите {what} для «{card.name}»"
        if self.busy:
            return "Ход врагов…" if b.enemy_phase else None
        if self.prayer:
            card, st, _ = self.prayer
            spec = SPEC[st.statue][card.d["meaning"]]
            return f"{st.god['name']} — {spec[1]}: {spec[2]} · выберите цель · ПКМ — отмена"
        if self.pick:
            return "Рядом несколько врагов — щёлкните, кого ударить"
        if self.shot_pick:
            return "Выберите баллисту для залпа · ПКМ — отмена"
        if self.sel:
            card, mode = self.sel
            tg = card.d[mode]["target"]
            if tg == "statue":
                return "Отпустите свиток на статую — наведите на статую, и видно, что сделает её бог"
            if tg == "reach":
                return "Выберите клетку, куда встать (можно зайти врагу за спину) · ПКМ — повернуть карту"
            if tg == "cell_step":
                if card.d[mode].get("allow_stay"):
                    return "Выберите клетку для шага или щёлкните по герою, чтобы остаться"
                return "Выберите клетку для шага"
            if tg == "copy_hand":
                return "Выберите карту в руке для копирования · ПКМ — отмена"
            if tg in M.HAND_TARGETS:
                need = card.d[mode].get("count", 1)
                return f"Выберите карты в руке ({len(self.hand_picks)}/{need}) · ПКМ — отмена"
            if tg == "ballista_fire":
                return "Выберите цель залпа на подсвеченной линии"
            if tg == "self":
                if self.b.ballistas and M.can_buff_ballista(card.d[mode]):
                    return "Выберите героя или баллисту для усиления"
                return "Отпустите над полем — сыграть" if self.drag else "Щёлкните по полю — сыграть"
            if self.drag:
                return "Отпустите над целью · без цели — ударит ближайшего · ПКМ — повернуть карту"
            return "Выберите цель · ПКМ — повернуть карту"
        if b.idols is not None and b.walk_left > 0:
            return f"Кликните клетку — пройти (шагов: {b.walk_left}) · тяните свиток на статую"
        if not any(b.can_play(c, "main") or b.can_play(c, "alt") for c in b.hand):
            return "Ходов больше нет — Space: конец хода"
        return None

    def draw_hand(self, surf):
        b = self.b
        sk = self.skin
        g = self.combat.grid                               # поднос: плотный к краю земли (за ним — пусто)
        edge = P.project(g.w / 2, g.h + P.MARGIN_B)[1]
        sk.tray(surf, min(edge - 40, T.SCREEN_H - 200), min(edge + 2, T.SCREEN_H))
        ex, ey = 70, T.SCREEN_H - 112                    # энергия (или жар) и стопки
        if b.mech == "heat":
            self.draw_heat(surf, ex, ey)
        elif b.idols is not None:                               # Жрец: шаги этого хода
            sk.orb(surf, (ex, ey), 36, b.walk_left, b.walk_max, self.hv.t, label=str(b.walk_left))
            sk.text(surf, "шаги", (ex, ey + 22), 12, (255, 240, 220), center=True)
        else:
            sk.orb(surf, (ex, ey), 36, b.energy, b.max_energy, self.hv.t)
        if self.ui_hidden:                                    # скрыт интерфейс: только карты и энергия
            self.deck_pile_rect = self.discard_pile_rect = None
            self.hv.draw(surf, self.state_of)
            return
        top = self.draw_mechanic(surf, 14, ey - 168)
        self.draw_turn(surf, 14, (top if top is not None else ey - 118) - 36)
        self.deck_pile_rect = self.pile(surf, (60, T.SCREEN_H - 34), len(b.draw_pile), "колода")
        self.discard_pile_rect = self.pile(surf, (T.SCREEN_W - 240, T.SCREEN_H - 40), len(b.discard),
                                           "сброс", side=-1)
        tip = self.hint_text()
        if tip:
            w = sk.size(tip, 15)[0] + 90
            r = pygame.Rect(0, 0, w, 32)
            r.center = (T.SCREEN_W // 2 - 20, 30)               # сверху по центру: рука и поднятая карта не закрывают
            r.right = min(r.right, self.help_rect.x - 10)
            sk.ribbon(surf, r, "")
            sk.text(surf, tip, r.center, 15, sk.p["text"], center=True)
        self.hv.draw(surf, self.state_of)
        if self.sel and self.sel[0].d[self.sel[1]]["target"] in M.HAND_TARGETS:
            target = self.target_at(self.mouse)
            native = surf.native if G.is_canvas(surf) else surf
            for card in b.targets(*self.sel):
                sprite = self.hv.sprites.get(card.uid)
                if sprite is not None:
                    rect = self.hv.rect_of(sprite).inflate(4, 4)
                    rect = surf.rect(rect) if G.is_canvas(surf) else rect
                    pygame.draw.rect(native, T.SELECT, rect,
                                     width=3 if card is target or card in self.hand_picks else 1, border_radius=8)
        if self.sel and self.sel[0].d[self.sel[1]]["target"] != "self" and self.mouse[1] < self.hand_area.y + 20:
            t, auto = self.aim()                              # без стрелки: цель видна по подсветке на поле
            ok = t is not None
            label = ("основное" if self.sel[1] == "main" else "простое") + (
                ": ближайший" if auto else ": цель" if ok else "")
            sk.text(surf, label, (self.mouse[0] + 18, self.mouse[1] + 12), 14,
                    (255, 225, 110) if ok else sk.p["dim"])
        sk.button(surf, self.end_rect, "Конец хода", self.end_rect.collidepoint(self.mouse),
                  on=not self.busy and not b.result, primary=not self.hint_text() or "Space" in (self.hint_text() or ""),
                  t=self.hv.t, size=19)

    def draw_discard_choice(self, surf):
        """Подсказка и подсветка выбранных карт для сброса (Адажио)."""
        need = min(self.b.pending_discard, len(self.b.hand))
        for c in self.discard_pick:
            sp = self.hv.sprites.get(c.uid)
            if sp is not None:
                pygame.draw.rect(surf, T.SELECT, self.hv.rect_of(sp).inflate(7, 7), 3, border_radius=8)
        text = f"Сбросьте карты: {len(self.discard_pick)}/{need} · клик по карте — выбрать"
        w = T.font(15, True).size(text)[0] + 38
        r = pygame.Rect((T.SCREEN_W - w) // 2, 82, w, 36)
        T.frame(surf, r, 245, accent=T.SELECT)
        T.text(surf, text, r.center, 15, T.TEXT, True, center=True)

    def draw_chain_show(self, surf):
        """Крупный показ карты, которую только что сыграла Цепочка: игрок должен увидеть, кто играет."""
        c = self.chain_show
        if c is None:
            return
        dur = max(0.35, self.chain_dur)
        t = min(max(0.0, self.chain_t), dur)
        k = min(1.0, t / 0.12, max(0.0, (dur - t) / 0.18))
        if k <= 0.01:
            return
        dim(surf, int(110 * k))
        w = round((208 + 8 * min(1.0, t / 0.16)) * (0.96 + 0.04 * k))
        h = round(w * CF.FH / CF.FW)
        cr = pygame.Rect(0, 0, w, h)
        cr.center = (T.SCREEN_W // 2, T.SCREEN_H // 2 - 52)
        pr = pygame.Rect(cr.x - 18, cr.y - 34, cr.w + 36, cr.h + 70)
        T.frame(surf, pr, 238, accent=(130, 255, 165), fill=(18, 14, 11))
        T.text(surf, "ЦЕПОЧКА", (cr.centerx, pr.y + 8), 20, (130, 255, 170), True,
               center=True, shadow=True)
        T.text(surf, "играет сама · бесплатно", (cr.centerx, pr.bottom - 24), 13, (200, 225, 200),
               center=True, shadow=True)
        CF.blit_card(surf, cr, c, main_ok=True, alt_ok=False, hot=True, alpha=int(255 * k),
                     lit=("chain",))

    def draw_heat(self, surf, ex, ey):
        """Жар Пиромантки: раскалённый шар с числом, деления — до перегрева."""
        b = self.b
        hd = b.hero_def
        heat, over = b.hero.ds["heat"], hd.get("overheat", 8)
        k = min(1.0, heat / max(1, over))
        hot = (255, 90, 30) if heat > over else T.mix((150, 70, 30), (255, 170, 60), k)
        cols = (T.mix(hot, (255, 255, 220), 0.6), hot, T.mix(hot, (40, 10, 4), 0.7))
        self.skin.orb(surf, (ex, ey), 38, max(1, heat), over, self.hv.t * (1 + k), label=str(heat), colors=cols,
                      pips=True)
        self.skin.text(surf, "жар", (ex, ey + 22), 12, (255, 230, 200), center=True)

    def draw_turn(self, surf, x, y):
        """Счётчики хода для условий: сколько сыграно, по тегам, сколько клеток пройдено."""
        b = self.b
        sk = self.skin
        tags = {}
        for ts in b.turn_tags:
            for t in ts:
                tags[t] = tags.get(t, 0) + 1
        s = f"Сыграно {b.played}" + "".join(f" · {M.tag_label(t)} {n}" for t, n in tags.items()) + \
            (f" · пройдено {b.walked}" if b.walked else "")
        w = sk.size(s, 13)[0] + 28
        r = pygame.Rect(x, y, w, 28)
        sk.panel(surf, r, 220, cut=7)
        sk.text(surf, s, (r.x + 14, r.y + 6), 13, (190, 225, 255))

    def draw_mechanic(self, surf, x, y):
        """Особенность героя — плашкой над энергией: разгон, пассивка Охотницы, жар и перегрев."""
        b = self.b
        sk = self.skin
        ds = b.hero.ds
        lines = []
        if b.mech == "fae":
            fae = ds.get("fae", 0)
            r = pygame.Rect(x, y, 190, 62)
            sk.panel(surf, r, 228)
            sk.text(surf, "Феи", (r.x + 14, r.y + 5), 15, sk.p["title"], title=True)
            sk.text(surf, f"{fae}/10", (r.right - 14, r.y + 5), 15, sk.p["text"], right=True, title=True)
            sk.pips(surf, r.x + 14, r.y + 30, 10, fae, w=(r.w - 28 - 4 * 9) / 10, h=9, gap=4)
            if b.garden is not None:
                plants = sum(1 for u in b.garden.plants if u.alive)
                beasts = sum(1 for u in b.garden.beasts.values() if u.alive)
                sk.text(surf, f"растения {plants} · звери {beasts} · прививки {len(b.garden.attachments)}",
                        (r.x + 14, r.y + 44), 11, sk.p["dim"])
            return r.y
        if b.mech == "momentum":
            mx = b.hero_def.get("momentum_max", 5)
            r = pygame.Rect(x, y, 160, 50)
            sk.panel(surf, r, 228)
            sk.text(surf, "Разгон" + (" · не гаснет" if ds["keep_mom"] else ""), (r.x + 14, r.y + 5), 15,
                    sk.p["title"], title=True)
            sk.text(surf, f"+{ds['momentum']}", (r.right - 14, r.y + 5), 15, sk.p["text"], right=True, title=True)
            sk.pips(surf, r.x + 14, r.y + 30, mx, ds["momentum"], w=(r.w - 28 - 4 * (mx - 1)) / mx, h=10, gap=4)
            return r.y
        if b.mech == "hunter":
            p = b.hero_def["passives"].get(b.variant, {})
            lines = [(p.get("name", ""), sk.p["title"])]
            if b.variant == "mark" and b.prey is not None:
                lines.append((f"Добыча: {b.prey.name}", (255, 220, 120)))
            if ds["ranged_bonus"]:
                lines.append((f"Азарт: дальние +{ds['ranged_bonus']}", sk.p["text"]))
            if ds["focus"]:
                lines.append(("Следующий выстрел ×2", (255, 220, 120)))
        elif b.mech == "heat":
            hd = b.hero_def
            lines = [("Жар: " + ("ПЕРЕГРЕВ в конце хода!" if ds["heat"] > hd.get("overheat", 8)
                                 else f"перегрев выше {hd.get('overheat', 8)}"),
                      (255, 120, 80) if ds["heat"] > hd.get("overheat", 8) else (255, 190, 130))]
            if ds["heat_regen"]:
                lines.append((f"Сердце феникса: +{ds['heat_regen']} жара за ход", sk.p["text"]))
            lines.append(("колесо над картой — уровень", sk.p["dim"]))
        if not lines:
            return
        lines = [(ln, col) for s, col in lines for ln in wrap(s, 13, 150)]   # узко: правее начинается рука
        w = max(sk.size(s, 13)[0] for s, _ in lines) + 30
        r = pygame.Rect(x, y + 50 - len(lines) * 18 - 12, w, len(lines) * 18 + 12)
        sk.panel(surf, r, 228)
        for i, (s, col) in enumerate(lines):
            sk.text(surf, s, (r.x + 14, r.y + 5 + i * 18), 14 if i == 0 else 13, col, title=i == 0)
        return r.y

    def pile(self, surf, pos, n, label, side=1):
        x, y = pos
        hit = pygame.Rect(x - 26, y - 52, 84, 76)
        bk = self.hv.back
        for k in range(min(3, max(1, n))):
            r = pygame.Rect(x - 16 + k * 2, y - 22 - k * 2, 32, 48)
            if bk is not None and n:                                   # стопка рубашкой вверх
                if G.is_canvas(surf):
                    surf.blit_hd(bk, r.center, 0, r.w / bk.get_width())
                else:
                    surf.blit(pygame.transform.smoothscale(bk, r.size), r)
                continue
            pygame.draw.rect(surf, (52, 38, 26) if n else (30, 24, 20), r, border_radius=4)
            pygame.draw.rect(surf, T.PANEL_EDGE, r, 1, border_radius=4)
        self.skin.badge(surf, (x + 24 * side, y - 6), 11, "", self.skin.p["accent"])
        self.skin.text(surf, str(n), (x + 24 * side, y - 6), 13, (255, 246, 230), center=True, title=True)
        self.skin.text(surf, label, (x + 2, y + 13), 11, self.skin.p["dim"], center=True)
        if hit.collidepoint(self.mouse):
            pygame.draw.rect(surf, T.SELECT, hit, 1, border_radius=6)
        return hit

    def tip_box(self, surf, lines, anchor, width=320):
        """Подсказка в панели героя: [(текст, цвет, заголовок?)] у точки anchor."""
        sk = self.skin
        out = []
        for s, col, head in lines:
            for ln in wrap(s, 15 if head else 13, width):
                out.append((ln, col, head))
        w = max(sk.size(s, 15 if hd else 13, hd)[0] for s, _, hd in out) + 30
        h = sum(22 if hd else 17 for _, _, hd in out) + 18
        x = min(anchor[0] + 18, T.SCREEN_W - w - 8)
        y = max(8, anchor[1] - h - 10)
        box = pygame.Rect(x, y, w, h)
        sk.panel(surf, box, 246, cut=8)
        yy = y + 9
        for s, col, hd in out:
            sk.text(surf, s, (x + 15, yy), 15 if hd else 13, col, title=hd, outline=False)
            yy += 22 if hd else 17

    def draw_tip(self, surf):
        for r, word, n in getattr(self, "_state_tips", []):            # значок состояния героя под мышью
            if r.collidepoint(self.mouse):
                pc = next((c for c in self.b.powers if word == f"Сила: {c.name}"), None)
                info = (word, M.plain(M.power_text(pc.d["main"]["power"]))) if pc is not None else M.lookup(word)
                name, text = info if info else (word, "")
                self.tip_box(surf, [(f"{name} {n}" if n not in ("", True) else name, self.skin.p["title"], True)] +
                             ([(text, self.skin.p["text"], False)] if text else []), self.mouse, 260)
                return
        idols = self.b.idols
        if idols is not None and self.mouse[1] < self.hand_area.y:
            st, card = None, None
            if self.prayer:                                   # свиток лежит на статуе — что сделает
                card, st, _ = self.prayer
            elif self.sel and self.sel[0].d[self.sel[1]].get("target") == "statue":
                t = self.view.pick_unit(self.mouse, lambda v: getattr(v, "statue", None), reach=10)
                if t is None:                                 # или клетка статуи под мышью
                    cell = self.cell_at(self.mouse)
                    t = next((x for x in idols.statues if x.cell == cell), None)
                if t is not None:
                    st, card = t, self.sel[0]
            if st is not None:
                sk = self.skin
                col = tuple(st.god["color"])
                lines = [(t, col if head else sk.p["text"], head) for t, head in idols.cast_lines(st, card)]
                v = self.view
                x, y = v.cam(v.feet_pos(st))
                self.tip_box(surf, lines, (x + 30, y - v.unit_h(st) - 40), 360)
                return
            u = self.view.pick_unit(self.mouse)
            if u is not None and getattr(u, "statue", None) and not self.sel:
                sk = self.skin
                col = tuple(u.god["color"])
                lines = [(t, col if head else sk.p["text"], head) for t, head in idols.describe(u)]
                self.tip_box(surf, lines, self.mouse, 380)
                return
        u = self.view.pick_unit(self.mouse)
        if u in self.b.ballistas and self.mouse[1] < self.hand_area.y and not self.sel:
            sk = self.skin
            lines = [(u.name, (236, 205, 130), True),
                     (f"Прочность {u.hp}/{u.max_hp} · Заряды {u.charge}/{u.charge_max}", sk.p["text"], False),
                     ("В начале хода +1 заряд, картой +2. Для залпа выберите цель на прямой линии.",
                      sk.p["text"], False)]
            buffs = (("Мощь", u.ds["strength"]), ("Дальний урон", u.ds["ranged_bonus"]),
                     ("К следующему залпу", u.ds.get("shot_empower")), ("Удвоенные залпы", u.ds.get("double_attacks")))
            bonus = [f"{name} +{n}" for name, n in buffs if n]
            if u.ds["focus"]:
                bonus.append("Фокус")
            if u.ds.get("double_next"):
                bonus.append("Следующий залп ×2")
            if bonus:
                lines.insert(2, (" · ".join(bonus), sk.p["title"], False))
            self.tip_box(surf, lines, self.mouse, 270)
            return
        if u is None or not u.alive or u.team != ENEMY or self.sel or self.mouse[1] > self.hand_area.y:
            return
        sk = self.skin
        d = u.edef or {}
        it = u.intent or {}
        lines = [(u.name, (255, 160, 130), True),
                 (f"HP {u.hp}/{u.max_hp}" + (f", защита {u.shield}" if u.shield else "") + f", ход {u.speed} кл.",
                  sk.p["text"], False)]
        st = [f"{w.lower()} {n}" if n not in ("", True) else w.lower() for _, _, n, w in self.state_badges(u)
              if w != "Защита"]
        if st:
            lines.append((" · ".join(st), (255, 210, 150), False))
        expl = {"melee": "подойдёт и ударит, если дотянется — отойди дальше его хода или защищайся",
                "shot": "стоит и стреляет по подсвеченной зоне (дальность и обзор) — выйди из неё или "
                        "спрячься за укрытие; вне зоны он только перебегает",
                "zone": "удар по отмеченным клеткам — уйди из зоны",
                "block": "получит защиту", "aim": "займёт позицию и прицелится: следующий выстрел сильнее",
                "heal": "вылечит раненого союзника", "roar": "слабость герою рядом",
                "charge": "рывок по отмеченной линии: кто на ней — получит удар и толчок; уйди с линии",
                "pull": "утянет героя к себе (дальность и обзор, как у стрелка) и ударит",
                "guard": "защита всем своим рядом", "rally": "сила всем своим рядом",
                "veil": "уйдёт в туман: картами издали не достать, только вплотную или по области",
                "curse": "подложит «Тину» в сброс: мусорная карта, отскрести стоит 1 энергию",
                "hex": "сглаз: на следующий ход меньше карт", "drown": "утащит карты из колоды до конца боя",
                "summon": "призовёт подмогу"}.get(it.get("kind"), "")
        if it:
            lines.append((f"{it['name']} — {expl}", INTENT_COL.get(it.get("kind"), sk.p["text"]), False))
        if d.get("about"):
            lines.append((d["about"], sk.p["dim"], False))
        self.tip_box(surf, lines, self.mouse)

    def draw_help(self, surf):
        """Справка по управлению (? или H/F1)."""
        if not self.help_open:
            return
        sk = self.skin
        dim(surf, 120)
        rows = [("Сыграть карту", "тяните карту на цель и отпустите — или щёлкните карту, затем цель"),
                ("Без цели", "атака, отпущенная где угодно, бьёт ближайшего врага"),
                ("Повернуть карту", "ПКМ (и на лету, пока тянете): сверху — простое применение за 0"),
                ("Подробно", "держите карту нажатой; Shift — читать, наводя на слова"),
                ("Уровень карты", "колесо мыши над картой (Пиромантка)"),
                ("Враг", "наведите — намерение, ход и куда дойдёт"),
                ("Конец хода", "Space или кнопка справа внизу"),
                ("Журнал", "L — развернуть в панели героя"),
                ("Предметы", "I или клик по значкам под названием боя — сумка"),
                ("Скрыть интерфейс", "Tab или глаз рядом с «?» — останутся карты, энергия, намерения, HP и состояния"),
                ("Справка", "H, F1 или «?» — закрыть: любой клик, Esc")]
        r = pygame.Rect(0, 0, 720, 70 + len(rows) * 34)
        r.center = (T.SCREEN_W // 2, T.SCREEN_H // 2 - 40)
        sk.panel(surf, r, 250, accent=True)
        sk.text(surf, "Управление", (r.centerx, r.y + 26), 24, sk.p["title"], center=True, title=True)
        y = r.y + 58
        for k, v in rows:
            sk.text(surf, k, (r.x + 28, y), 15, sk.p["accent"], title=True)
            sk.text(surf, v, (r.x + 200, y + 1), 14, sk.p["text"], outline=False)
            y += 34

    def ui_event(self, ev):
        """Справка, сумка и журнал: True — событие съедено."""
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_TAB:
            self.toggle_ui()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.eye_rect.collidepoint(ev.pos):
            self.toggle_ui()
            return True
        if not self.help_open and not self.ui_hidden and self.bag.event(ev):
            return True
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_h, pygame.K_F1):
                self.help_open = not self.help_open
                return True
            if self.help_open and ev.key == pygame.K_ESCAPE:
                self.help_open = False
                return True
            if ev.key == pygame.K_l:
                self.log_open = not self.log_open
                return True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.help_open:
                self.help_open = False
                return True
            if self.help_rect.collidepoint(ev.pos):
                self.help_open = True
                return True
            if self.log_rect.collidepoint(ev.pos):
                self.log_open = not self.log_open
                return True
        return False

class ChoiceScreen:
    """Выбор между боями: награда (карта из 3), прозрение (1 из 2 веток), костёр."""

    def __init__(self, game, title, sub, options, on_pick, skip=None, back=None, *, relics=False):
        self.game = game
        self.title, self.sub = title, sub
        self.options = options               # [(подпись, карта или None, значение)]
        self.on_pick = on_pick
        self.skip = skip
        self.back = back                     # снимок поля под затемнением
        self.mouse = (0, 0)
        self.rects = []
        self.skip_rect = None
        self.relics = relics

    def update(self, dt):
        pass

    def card_under(self):
        return next((c for (r, _), (_, c, _) in zip(self.rects, self.options) if c is not None
                     and r.collidepoint(self.mouse)), None)

    def handle(self, ev):
        if reading_event(self, ev, self.card_under):
            return
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:                    # колесо над картой Пиромантки — её уровень
            CF.wheel_level(self.card_under(), ev.y)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for (r, val), (_, card, _) in zip(self.rects, self.options):
                if card is not None and r.collidepoint(ev.pos) and CF.level_at(card, r, ev.pos) is not None:
                    CF.set_level(card, CF.level_at(card, r, ev.pos))       # кружок уровня — не выбор карты
                    return
            for r, val in self.rects:
                if r.collidepoint(ev.pos):
                    self.on_pick(val)
                    return
            if self.skip_rect and self.skip_rect.collidepoint(ev.pos):
                self.skip()

    def draw(self, surf):
        if self.back is not None:
            if G.is_canvas(surf):                           # кадр боя уже в родном разрешении
                surf.native.blit(self.back, (0, 0))
            else:
                surf.blit(self.back, (0, 0))
            dim(surf, 190)
        else:
            backdrop(surf, 200)
        cx = T.SCREEN_W // 2
        T.text(surf, self.title, (cx, 110), 32, T.AMBER, True, center=True, shadow=True)
        if self.sub:
            T.text(surf, self.sub, (cx, 150), 16, T.TEXT_DIM, center=True)
        n = len(self.options)
        big = any(card is not None for _, card, _ in self.options)
        tall = any("\n" in (label or "") for label, _, _ in self.options)
        w = int(CW * 1.35) if big else 340 if tall or self.relics else 300
        h = int(CH * 1.35) if big else 230 if self.relics else 110 if tall else 90
        gap = 40
        x0 = cx - (n * w + (n - 1) * gap) // 2
        self.rects = []
        for i, (label, card, val) in enumerate(self.options):
            r = pygame.Rect(x0 + i * (w + gap), 220, w, h)
            hot = r.collidepoint(self.mouse)
            if card is not None:
                draw_card(surf, r, card, hot=hot)
                T.text(surf, card.rarity_name, (r.centerx, r.bottom + 35), 12,
                       M.CARD_RARITY_COLOR.get(card.rarity, T.TEXT_DIM), center=True)
                if label:
                    T.text(surf, label, (r.centerx, r.bottom + 16), 16, T.SELECT if hot else T.TEXT, True, center=True)
            elif self.relics:
                from .items import RARITY_COLOR, RARITY_NAME, about
                color = RARITY_COLOR.get(val.get("rarity"), T.AMBER)
                T.frame(surf, r, 245, accent=T.SELECT if hot else color,
                        fill=(60, 44, 26) if hot else (40, 30, 22))
                draw_item_icon(surf, val, (r.centerx, r.y + 49), 72)
                y = r.y + 96
                for line in T.wrap(val["name"], 19, r.w - 28, True):
                    T.text(surf, line, (r.centerx, y), 19, T.TEXT, True, center=True)
                    y += 22
                T.text(surf, RARITY_NAME.get(val.get("rarity"), "").capitalize(),
                       (r.centerx, y), 14, color, center=True)
                for i, line in enumerate(T.wrap(about(val, self.game.run), 15, r.w - 28)):
                    T.text(surf, line, (r.centerx, y + 24 + i * 19), 15, T.TEXT, center=True)
            elif "\n" in label:                              # заголовок и пояснение (дар бога)
                head, rest = label.split("\n", 1)
                hot = r.collidepoint(self.mouse)
                T.frame(surf, r, 245, accent=T.SELECT if hot else T.AMBER, fill=(60, 44, 26) if hot else (40, 30, 22))
                T.text(surf, head, (r.centerx, r.y + 22), 19, T.AMBER, True, center=True)
                for i, ln in enumerate(T.wrap(rest, 15, r.w - 30)[:4]):
                    T.text(surf, ln, (r.centerx, r.y + 50 + i * 20), 15, T.TEXT, center=True)
            else:
                button(surf, r, label, self.mouse, primary=True)
            self.rects.append((r, val))
        if self.skip:
            self.skip_rect = pygame.Rect(cx - 110, 220 + h + 70, 220, 46)
            button(surf, self.skip_rect, "Пропустить", self.mouse)
        if big:
            lv = any(card is not None and card.levels for _, card, _ in self.options)
            T.text(surf, "Shift над картой — читать подробно" + (" · колесо или клик по кружку — уровень карты"
                                                                 if lv else ""),
                   (cx, T.SCREEN_H - 24), 13, T.TEXT_DIM, center=True)
        if getattr(self, "reading", None) is not None:
            self.reading.draw(surf, self.reading.mouse or self.mouse)


class GodBranchScreen:
    """Жрец: бог вырос — выбор ауры. Видно, какой бог (знак, имя, цвет), его уровень, что уже взято, и две ауры
    крупными плашками цвета бога. Клик или 1/2."""

    def __init__(self, game, god, level, options, on_pick, back=None):
        self.game = game
        self.god = god                         # словарь бога (data/deck/gods.json)
        self.level = level
        self.options = options                 # [(значение, заголовок, описание)]
        self.on_pick = on_pick
        self.back = back
        self.mouse = (0, 0)
        self.rects = []
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, val in self.rects:
                if r.collidepoint(ev.pos):
                    self.on_pick(val)
                    return
        elif ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_9:
            i = ev.key - pygame.K_1
            if i < len(self.options):
                self.on_pick(self.options[i][0])

    def taken(self):
        from .idols import BRANCHES
        run = self.game.run
        auras = BRANCHES[self.god["id"]]["a"]
        return [auras[i][0] for k, i in run.god_picks.get(self.god["id"], []) if k == "a" and i < len(auras)]

    def draw(self, surf):
        from . import cardart
        if self.back is not None:
            if G.is_canvas(surf):
                surf.native.blit(self.back, (0, 0))
            else:
                surf.blit(self.back, (0, 0))
            dim(surf, 200)
        else:
            backdrop(surf, 205)
        sk = SK.use("priest")
        g = self.god
        col = tuple(g.get("color", (220, 200, 160)))
        cx = T.SCREEN_W // 2
        # знак бога: сияние его цвета, медальон, вымпел
        pulse = 0.5 + 0.5 * math.sin(self.t * 2.2)
        glow = pygame.Surface((240, 240), pygame.SRCALPHA)
        for k in range(8):                                    # мягкое сияние: круги накладываются с прозрачностью
            ring = pygame.Surface((240, 240), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*col, int(14 + 10 * pulse)), (120, 120), 62 + k * 7)
            glow.blit(ring, (0, 0))
        surf.blit(glow, (cx - 120, 150 - 120))
        sk.badge(surf, (cx, 150), 62, "", col)
        icon = cardart.icon(f"god_{g['id']}", 96)
        if icon is not None:
            surf.blit(icon, (cx - icon.get_width() // 2, 150 - icon.get_height() // 2))
        else:
            sk.text(surf, g["name"][0], (cx, 150), 56, (255, 250, 235), center=True, title=True)
        sk.text(surf, g["name"], (cx, 238), 38, col, center=True, title=True)
        sk.text(surf, g.get("title", "").capitalize(), (cx, 274), 17, sk.p["dim"], center=True)
        lv = f"Уровень {self.level}"                    # лента уровня
        w = sk.size(lv, 20, True)[0] + 60
        rr = pygame.Rect(cx - w // 2, 296, w, 34)
        sk.ribbon(surf, rr, "")
        sk.text(surf, lv, rr.center, 20, (255, 246, 220), center=True, title=True)
        sk.text(surf, f"Бог вырос: числа его действий +{self.level}. Выберите ауру — она действует в каждом бою, "
                      "пока стоит его статуя.", (cx, 350), 15, sk.p["text"], center=True)
        took = self.taken()
        if took:
            sk.text(surf, "Уже есть: " + " · ".join(took), (cx, 374), 14, col, center=True)
        # ауры — крупные плашки цвета бога
        n = len(self.options)
        pw, ph, gap = 430, 190, 50
        x0 = cx - (n * pw + (n - 1) * gap) // 2
        self.rects = []
        for i, (val, head, desc) in enumerate(self.options):
            r = pygame.Rect(x0 + i * (pw + gap), 410, pw, ph)
            hot = r.collidepoint(self.mouse)
            if hot:
                pygame.draw.rect(surf, col, r.inflate(14, 14), 4, border_radius=18)
            sk.panel(surf, r, 246, accent=True)
            band = pygame.Rect(r.x + 10, r.y + 10, r.w - 20, 50)
            bs = pygame.Surface(band.size, pygame.SRCALPHA)
            bs.fill((*col, 70 if hot else 45))
            surf.blit(bs, band.topleft)
            pygame.draw.rect(surf, col, band, 2, border_radius=6)
            name = head.split(":", 1)[-1].strip()
            sk.text(surf, name, band.center, 24, (255, 250, 235), center=True, title=True)
            sk.text(surf, "аура", (band.right - 30, band.y - 2), 11, col, center=True)
            text = desc[:1].upper() + desc[1:] + "."
            for k, ln in enumerate(sk_wrap(sk, text, 17, pw - 50)[:5]):
                sk.text(surf, ln, (r.centerx, r.y + 84 + k * 26), 17, sk.p["text"], center=True)
            key = pygame.Rect(0, 0, 34, 34)
            key.center = (r.centerx, r.bottom - 26)
            sk.badge(surf, key.center, 15, "", col if hot else (130, 120, 110))
            sk.text(surf, str(i + 1), key.center, 17, (255, 250, 235), center=True, title=True)
            self.rects.append((r, val))
        sk.text(surf, "Клик или клавиша с номером — выбрать", (cx, T.SCREEN_H - 30), 13, sk.p["dim"], center=True)


class EndScreen:
    def __init__(self, game, won, text):
        self.game = game
        self.won = won
        self.text = text
        self.mouse = (0, 0)
        self.btn = pygame.Rect(T.SCREEN_W // 2 - 130, 420, 260, 56)

    def update(self, dt):
        pass

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.btn.collidepoint(ev.pos)) or \
                (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_r)):
            self.game.new_run()

    def draw(self, surf):
        surf.fill(T.BG)
        cx = T.SCREEN_W // 2
        name = getattr(getattr(self.game, "run", None), "hero_name", "Герой")
        T.text(surf, "Глава пройдена!" if self.won else f"{name} пал(а)", (cx, 220), 40,
               (150, 230, 140) if self.won else (255, 120, 100), True, center=True, shadow=True)
        for i, line in enumerate(self.text):
            T.text(surf, line, (cx, 290 + i * 26), 17, T.TEXT_DIM, center=True)
        button(surf, self.btn, "Новый забег  (Enter)", self.mouse, primary=True)


# ---------- карта этажа ----------

NODE_COLORS = {"battle": (200, 85, 70), "elite": (230, 150, 40), "boss": (170, 70, 210), "camp": (80, 185, 105),
               "shop": (225, 200, 80), "altar": (150, 170, 255), "chest": (235, 190, 110),
               "workshop": (190, 160, 130)}
NODE_NAMES = {"battle": "Бой", "elite": "Элита", "boss": "Страж лестницы", "camp": "Костёр", "shop": "Торговец",
              "altar": "Алтарь", "chest": "Сундук", "workshop": "Мастерская"}
NODE_GLYPH = {"altar": "thread", "chest": "event", "workshop": "anvil"}       # сундук — медальон находки карты похода
GOLD = (240, 200, 80)


_SHADES = {}


def _shade(size, dim):
    """Затемняющая накладка — одна на размер и прозрачность, а не новый Surface каждый кадр."""
    key = (size, int(dim))
    s = _SHADES.get(key)
    if s is None:
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill((6, 8, 10, int(dim)))
        if len(_SHADES) > 4:
            _SHADES.clear()
        _SHADES[key] = s
    return s


def backdrop(surf, dim=190):
    """Фон: иллюстрация болота (как у карты похода), притушенная."""
    try:
        from ui import illustrations as IL
        if G.is_canvas(surf):                               # фон — сразу в размер окна
            nw, nh = surf.native.get_size()
            img = IL.get("act_0", "act", (nw, nw * 2 // 3), hd=True)
            surf.native.blit(img, (0, (nh - img.get_height()) // 2))
        else:
            img = IL.get("act_0", "act", (T.SCREEN_W, T.SCREEN_W * 2 // 3), hd=True)
            surf.blit(img, (0, (T.SCREEN_H - img.get_height()) // 2))
    except Exception:                                  # нет картинки — просто тёмный фон
        surf.fill(T.BG)
    if G.is_canvas(surf):                                   # притушить — на всё окно (без светлых полос по бокам)
        size = surf.native.get_size()
        surf.native.blit(_shade(size, dim), (0, 0))
        return
    surf.blit(_shade((T.SCREEN_W, T.SCREEN_H), dim), (0, 0))


def run_header(surf, run, title, sub=None):
    T.text(surf, title, (24, 14), 28, T.TEXT, True)
    if sub:
        T.text(surf, sub, (26, 52), 15, T.TEXT_DIM)
    g = f"Золото: {run.gold}"
    T.text(surf, g, (T.SCREEN_W - 26 - T.font(22, True).size(g)[0], 16), 22, GOLD, True)
    hp = f"HP {run.hp}/{run.max_hp}"
    T.text(surf, hp, (T.SCREEN_W - 26 - T.font(18, True).size(hp)[0], 46), 18, (230, 120, 110), True)


class MapScreen:
    """Этаж: ряды узлов слева направо, тропы, медальоны и подписи — как на карте похода."""

    def __init__(self, game):
        self.game = game
        self.bag = Bag()
        self.mouse = (0, 0)
        self.clock = 0.0
        self.pos = {}
        self.deck_rect = pygame.Rect(T.SCREEN_W - 260, T.SCREEN_H - 66, 236, 44)
        self.bag_rect = pygame.Rect(T.SCREEN_W - 520 - 12 - 220, T.SCREEN_H - 66, 220, 44)
        self.res_rect = pygame.Rect(T.SCREEN_W - 520, T.SCREEN_H - 66, 248, 44)
        self.sound_rect = pygame.Rect(24, 76, 214, 28)
        self.atlas_rect = pygame.Rect(248, 76, 166, 28)
        self.toast = None
        fl = game.run.floor
        layers = max(n["layer"] for n in fl.nodes.values()) + 1
        x0, x1, y0, y1 = 110, T.SCREEN_W - 110, 160, 500
        for n in fl.nodes.values():
            self.pos[n["id"]] = (x0 + (x1 - x0) * n["layer"] / max(1, layers - 1),
                                 y0 + (y1 - y0) * (n["idx"] + 0.5) / n["count"])

    def update(self, dt):
        self.clock += dt
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt)
            if self.toast[1] <= 0:
                self.toast = None

    def node_at(self, pos):
        for nid, p in self.pos.items():
            if math.dist(p, pos) <= 28:
                return nid
        return None

    def handle(self, ev):
        if self.bag.event(ev):
            return
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.sound_rect.collidepoint(ev.pos):
                if getattr(self.game, "sound", None) is not None:
                    self.game.sound.toggle()
                return
            if self.atlas_rect.collidepoint(ev.pos):
                self.game.open_atlas()
                return
            if self.deck_rect.collidepoint(ev.pos):
                self.game.show_deck()
                return
            if self.bag_rect.collidepoint(ev.pos):
                self.bag.open = True
                return
            if self.res_rect.collidepoint(ev.pos):
                self.toggle_res()
                return
            nid = self.node_at(ev.pos)
            if nid and nid in self.game.run.floor.available():
                self.game.enter_node(nid)
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_d:
                self.game.show_deck()
            elif ev.key == pygame.K_a:
                self.game.open_atlas()
            elif ev.key == pygame.K_m:
                self.toggle_res()
            elif pygame.K_1 <= ev.key <= pygame.K_9:
                opts = sorted(self.game.run.floor.available(), key=lambda n: self.pos[n][1])
                i = ev.key - pygame.K_1
                if i < len(opts):
                    self.game.enter_node(opts[i])

    def draw(self, surf):
        from ui import map_art as MA
        run = self.game.run
        fl = run.floor
        backdrop(surf)
        hk, dk = run.scale()
        run_header(surf, run, f"Болото · этаж {fl.depth} из 3 — {run.floor_name}" if run.floor_name else
                   f"Подземелье · этаж {fl.depth}",
                   f"Выберите путь: клик или 1–3 · враги этажа: HP ×{hk:.2f}, урон ×{dk:.2f} · D — колода")
        self.bag.bar(surf, run, (T.SCREEN_W - 40, 74), self.mouse, right=True)
        button(surf, self.sound_rect, f"Звук: {audio.volume_text()} · F10", self.mouse)
        button(surf, self.atlas_rect, "Атлас · A", self.mouse)
        board = pygame.Rect(40, 110, T.SCREEN_W - 80, 450)
        T.frame(surf, board, 150, accent=T.AMBER_DIM)
        avail = set(fl.available())
        visited = set(fl.path)
        rad = {nid: (30 if n["type"] == "boss" else 25 if n["type"] == "elite" else 22) for nid, n in fl.nodes.items()}
        for n in fl.nodes.values():
            for nxt in n["next"]:
                if n["id"] in visited and nxt in visited:
                    state = "done"
                elif n["id"] == fl.node and nxt in avail:
                    state = "open"
                else:
                    state = "future"
                MA.draw_trail(surf, self.pos[n["id"]], self.pos[nxt], state, self.clock, rad[n["id"]], rad[nxt])
        hover = self.node_at(self.mouse)
        keys = {nid: i + 1 for i, nid in enumerate(sorted(avail, key=lambda n: self.pos[n][1]))}
        for n in fl.nodes.values():
            nid = n["id"]
            x, y = self.pos[nid]
            state = "here" if nid == fl.node else "open" if nid in avail else "done" if nid in visited else "future"
            col = NODE_COLORS[n["type"]]
            r = MA.draw_node(surf, (x, y), NODE_GLYPH.get(n["type"], n["type"]), col, state, self.clock)
            if nid == hover and state != "future":
                pygame.draw.circle(surf, (255, 240, 200), (int(x), int(y)), r + 5, 2)
            label = n["fight"]["name"] if n.get("fight") and n["type"] != "battle" else NODE_NAMES[n["type"]]
            MA.ribbon(surf, label, (x, y + r + 5), col, n["type"] == "boss", dim=state == "future")
            if state == "open" and nid in keys:
                bx, by = int(x - r - 4), int(y - r - 4)
                pygame.draw.circle(surf, (20, 16, 10), (bx, by), 11)
                pygame.draw.circle(surf, GOLD, (bx, by), 11, 2)
                T.text(surf, str(keys[nid]), (bx, by), 15, GOLD, True, center=True)
        if fl.node:
            x, y = self.pos[fl.node]
        else:
            first = min(avail, key=lambda n: self.pos[n][0])
            x, y = self.pos[first][0] - 40, (160 + 500) / 2
        img = self.game.hero_img()
        bob = int(2 * math.sin(self.clock * 3))
        surf.blit(img, (x - 34 - img.get_width() // 2, y + 10 - img.get_height() + bob))
        self.draw_deck_strip(surf)
        button(surf, self.deck_rect, f"Колода ({len(run.deck)}) · D", self.mouse)
        r = model_res()
        button(surf, self.res_rect, f"Модели: {r}×{r} · M", self.mouse)
        button(surf, self.bag_rect, f"Сумка ({len(run.relics)}) · I", self.mouse)
        if hover and not self.bag.open:
            self.tip(surf, fl.nodes[hover])
        if self.toast:
            T.text(surf, self.toast[0], (T.SCREEN_W // 2, 640), 22, (255, 220, 140), True, center=True, shadow=True)
        self.bag.draw(surf, run)

    def toggle_res(self):
        """Качество моделек между боями: 32×32 (пиксели) ↔ 64×64 (вдвое подробнее) — со следующего боя."""
        from ui import settings
        settings.SETTINGS["sprite_res"] = 64 if model_res() == 32 else 32
        if getattr(self.game, "save_settings", True):
            settings.save()
        r = model_res()
        self.toast = (f"Модели {r}×{r} — со следующего боя", 2.0)

    def draw_deck_strip(self, surf):
        run = self.game.run
        T.text(surf, f"Убито врагов: {run.kills} · выиграно боёв: {run.fight}", (44, 576), 15, T.TEXT_DIM, True)
        ready = [c for c in run.deck if c.growth_next()]
        near = sorted(ready, key=lambda c: c.insight_progress(), reverse=True)[:4]
        if near:
            T.text(surf, f"Прозрение: {int(M.INSIGHT_CHANCE * 100)}% за применение, "
                         f"гарантия на {M.INSIGHT_PITY}-м. Ближе всего: " + ", ".join(
                f"{c.name} {('готово' if c.insight_ready() else str(c.insight_misses) + '/' + str(M.INSIGHT_PITY))}"
                for c in near), (44, 600), 14, (255, 220, 140))

    def tip(self, surf, n):
        run = self.game.run
        edefs = run.data["enemies"]["enemies"]
        lines = [(NODE_NAMES[n["type"]], NODE_COLORS[n["type"]])]
        if n.get("fight"):
            f = n["fight"]
            lines.append((f["name"], T.TEXT))
            counts = {}
            for e in f["enemies"]:
                counts[edefs[e]["name"]] = counts.get(edefs[e]["name"], 0) + 1
            lines += [(f"{k} ×{v}" if v > 1 else k, T.TEXT_DIM) for k, v in counts.items()]
            lo, hi = run.floor_cfg["gold"][n["type"]]
            lines.append((f"Награда: карта из трёх, {lo}–{hi} золота", GOLD))
            if n["type"] == "boss":
                lines.append(("После — спуск на следующий этаж и отдых", (180, 230, 180)))
        elif n["type"] == "camp":
            lines.append((f"Отдохнуть (+{int(run.max_hp * 0.3)} HP) или удалить карту", T.TEXT_DIM))
        elif n["type"] == "shop":
            lines.append(("Карты, предметы, удаление карты, лечебное зелье", T.TEXT_DIM))
        elif n["type"] in ("chest", "altar"):
            lines.append(("Предмет на выбор: 1 из 3", T.TEXT_DIM))
        elif n["type"] == "workshop":
            lines.append(("Улучшить простое применение карты: 1 из 3", T.TEXT_DIM))
        w = max(T.font(14).size(s)[0] for s, _ in lines) + 20
        x, y = self.pos[n["id"]]
        box = pygame.Rect(min(x + 32, T.SCREEN_W - w - 10), max(10, y - 20), w, len(lines) * 19 + 12)
        T.frame(surf, box, 245)
        for i, (s, col) in enumerate(lines):
            T.text(surf, s, (box.x + 10, box.y + 6 + i * 19), 14, col, i == 0)


class DeckScreen:
    """Колода сеткой — крупные карты, колесо прокручивает, под мышью карта увеличивается. Просмотр (back) или
    выбор карты (on_pick — удалить у торговца или у костра)."""

    def __init__(self, game, title, cards, back, on_pick=None, sub=None):
        self.game = game
        self.title = title
        self.sub = sub
        self.cards = cards
        self.back = back
        self.on_pick = on_pick
        self.mouse = (0, 0)
        self.rects = []
        self.scroll = 0
        self.back_rect = pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 60, 220, 46)

    def update(self, dt):
        pass

    def layout(self):
        k = 1.12
        w, h = int(CW * k), int(CH * k)
        per = max(1, (T.SCREEN_W - 60) // (w + 14))
        x0 = (T.SCREEN_W - per * (w + 14) + 14) // 2
        rows = -(-len(self.cards) // per)
        top = 96
        view_h = T.SCREEN_H - 76 - top
        self.max_scroll = max(0, rows * (h + 16) - view_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        return [(pygame.Rect(x0 + (i % per) * (w + 14), top + (i // per) * (h + 16) - self.scroll, w, h), c)
                for i, c in enumerate(self.cards)]

    def card_under(self):
        return next((c for r, c in self.rects if r.collidepoint(self.mouse) and 90 < self.mouse[1] < T.SCREEN_H - 70),
                    None)

    def handle(self, ev):
        if reading_event(self, ev, self.card_under):
            return
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:
            self.scroll -= ev.y * 90
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.back_rect.collidepoint(ev.pos):
                self.back()
                return
            hb = getattr(self, "hover_big", None)
            if hb is not None and CF.level_at(hb[1], hb[0], ev.pos) is not None:   # кружок уровня — не выбор
                CF.set_level(hb[1], CF.level_at(hb[1], hb[0], ev.pos))
                return
            for r, c in self.rects:
                if r.collidepoint(ev.pos) and self.on_pick and 90 < ev.pos[1] < T.SCREEN_H - 70:
                    self.on_pick(c)
                    return
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_d):
            self.back()

    def draw(self, surf):
        backdrop(surf, 215)
        self.rects = self.layout()
        clip = pygame.Rect(0, 90, T.SCREEN_W, T.SCREEN_H - 160)
        surf.set_clip(clip)
        hover = None
        for r, c in self.rects:
            if r.bottom < clip.top or r.top > clip.bottom:
                continue
            CF.blit_card(surf, r, c)
            T.text(surf, c.rarity_name, (r.centerx, r.bottom + 2), 10,
                   M.CARD_RARITY_COLOR.get(c.rarity, T.TEXT_DIM), center=True)
            if r.collidepoint(self.mouse) and clip.collidepoint(self.mouse):
                hover = (r, c)
        surf.set_clip(None)
        self.hover_big = None
        if hover:                                        # под мышью — крупно, в полном разрешении
            r, c = hover
            big = pygame.Rect(0, 0, 300, round(300 * CF.FH / CF.FW))
            big.center = r.center
            big.clamp_ip(pygame.Rect(8, 8, T.SCREEN_W - 16, T.SCREEN_H - 16))
            self.hover_big = (big, c)
            sh = pygame.Surface(big.size, pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 140), sh.get_rect(), border_radius=22)
            surf.blit(sh, big.move(8, 10))
            CF.blit_card(surf, big, c, hot=self.on_pick is not None)
        T.text(surf, self.title, (T.SCREEN_W // 2, 30), 28, T.AMBER, True, center=True)
        if self.sub:
            T.text(surf, self.sub, (T.SCREEN_W // 2, 62), 15, T.TEXT_DIM, center=True)
        T.text(surf, "Shift над картой — читать подробно" + (" · колесо — прокрутка" if self.max_scroll else ""),
               (T.SCREEN_W - 330, T.SCREEN_H - 40), 13, T.TEXT_DIM)
        button(surf, self.back_rect, "Назад (Esc)", self.mouse)
        if getattr(self, "reading", None) is not None:
            self.reading.draw(surf, self.reading.mouse or self.mouse)


class ShopScreen:
    """Торговец: 3 карты, удаление карты (цена растёт), лечебное зелье."""

    def __init__(self, game):
        self.game = game
        run = game.run
        self.cfg = run.data["enemies"]["shop"]
        self.stock = run.shop_stock()
        self.sold = set()
        self.potion = True
        self.mouse = (0, 0)
        self.rects = []
        self.remove_rect = pygame.Rect(T.SCREEN_W // 2 - 480, 520, 300, 56)
        self.potion_rect = pygame.Rect(T.SCREEN_W // 2 - 150, 520, 300, 56)
        self.bag = Bag()
        offer = run.relic_offer(2, "shop") if hasattr(run, "relic_offer") else []
        lo, hi = self.cfg.get("relic_price", [110, 140])
        k = {"common": 0.8, "uncommon": 1.0, "rare": 1.35, "shop": 0.9}
        self.items = [[r, int(run.rng.randint(lo, hi) * k.get(r.get("rarity"), 1.0)),
                       pygame.Rect(T.SCREEN_W // 2 + 180, 520 + 62 * i, 300, 52)] for i, r in enumerate(offer)]
        self.leave_rect = pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 80, 220, 50)
        self.toast = None

    def update(self, dt):
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt)
            if self.toast[1] <= 0:
                self.toast = None

    def buy(self, i):
        run = self.game.run
        if i in self.sold:
            return False
        card, price = self.stock[i]
        if run.gold < price:
            self.toast = ("Не хватает золота", 1.2)
            return False
        if run.take(card) is False:
            self.toast = ("Уникальная карта уже есть в колоде", 1.2)
            return False
        run.gold -= price
        self.sold.add(i)
        return True

    @property
    def relic(self):
        """Совместимость: первый непроданный предмет."""
        return next((it[0] for it in self.items if it[0] is not None), None)

    def buy_relic(self, i=None):
        run = self.game.run
        if i is None:
            i = next((k for k, it in enumerate(self.items) if it[0] is not None), None)
        if i is None or self.items[i][0] is None or run.gold < self.items[i][1]:
            return False
        r, price, _ = self.items[i]
        run.gold -= price
        run.relics.append(r)
        self.toast = (f"Предмет: {r['name']}", 1.6)
        self.items[i][0] = None
        return True

    def drink(self):
        run = self.game.run
        price = self.cfg["potion_price"]
        if not self.potion or run.gold < price or run.hp >= run.max_hp:
            return False
        run.gold -= price
        run.hp = min(run.max_hp, run.hp + self.cfg["potion_heal"])
        self.potion = False
        return True

    def card_under(self):
        return next((self.stock[i][0] for r, i in self.rects if r.collidepoint(self.mouse)), None)

    def handle(self, ev):
        if self.bag.event(ev):
            return
        if reading_event(self, ev, self.card_under):
            return
        run = self.game.run
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:                    # колесо над картой Пиромантки — уровень
            CF.wheel_level(self.card_under(), ev.y)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, i in self.rects:
                c = self.stock[i][0]
                if r.collidepoint(ev.pos) and CF.level_at(c, r, ev.pos) is not None:
                    CF.set_level(c, CF.level_at(c, r, ev.pos))   # кружок уровня — не покупка
                    return
            for r, i in self.rects:
                if r.collidepoint(ev.pos):
                    self.buy(i)
                    return
            if self.remove_rect.collidepoint(ev.pos) and run.gold >= run.remove_price:
                self.game.pick_remove(back=self, paid=True)
            elif any(it[2].collidepoint(ev.pos) for it in self.items):
                self.buy_relic(next(k for k, it in enumerate(self.items) if it[2].collidepoint(ev.pos)))
            elif self.potion_rect.collidepoint(ev.pos):
                self.drink()
            elif self.leave_rect.collidepoint(ev.pos):
                self.game.to_map()
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.game.to_map()

    def draw(self, surf):
        run = self.game.run
        backdrop(surf, 200)
        run_header(surf, run, "Торговец", "Карты в колоду, избавиться от лишней, подлечиться")
        n = len(self.stock)
        w, h = int(CW * 1.25), int(CH * 1.25)
        x0 = T.SCREEN_W // 2 - (n * w + (n - 1) * 40) // 2
        self.rects = []
        for i, (card, price) in enumerate(self.stock):
            r = pygame.Rect(x0 + i * (w + 40), 120, w, h)
            sold = i in self.sold
            hot = r.collidepoint(self.mouse) and not sold
            CF.blit_card(surf, r, card, hot=hot, alpha=70 if sold else 255)
            T.text(surf, "продано" if sold else f"{price} золота", (r.centerx, r.bottom + 16), 17,
                   T.TEXT_DIM if sold else (GOLD if run.gold >= price else (200, 110, 100)), True, center=True)
            self.rects.append((r, i))
        button(surf, self.remove_rect, f"Удалить карту — {run.remove_price}", self.mouse,
               on=run.gold >= run.remove_price)
        pp = self.cfg["potion_price"]
        button(surf, self.potion_rect, f"Зелье +{self.cfg['potion_heal']} HP — {pp}" if self.potion else "Зелье продано",
               self.mouse, on=self.potion and run.gold >= pp and run.hp < run.max_hp)
        for rl, price, rr in self.items:
            if rl is None:
                button(surf, rr, "Продано", self.mouse, on=False)
                continue
            affordable = run.gold >= price
            button(surf, rr, "", self.mouse, on=affordable)
            draw_item_icon(surf, rl, (rr.x + 25, rr.centery), 34)
            lines = T.wrap(f"{rl['name']} — {price}", 15, rr.w - 62, True)
            for i, line in enumerate(lines):
                T.text(surf, line, (rr.centerx + 20, rr.centery + 17 * i - 8 * (len(lines) - 1)),
                       15, T.TEXT if affordable else T.TEXT_DIM, True, center=True)
        hot = next((it for it in self.items if it[0] is not None and it[2].collidepoint(self.mouse)), None)
        if hot is not None:
            from .items import RARITY_NAME
            rl, _, rr = hot
            from .items import about
            lines = T.wrap(f"{rl['name']} ({RARITY_NAME.get(rl.get('rarity'), '')}): {about(rl, run)}", 14, 520)
            for k, ln in enumerate(lines):
                T.text(surf, ln, (T.SCREEN_W // 2 - 160, 600 + 18 * k), 14, T.TEXT, center=True, shadow=True)
        self.bag.bar(surf, run, (T.SCREEN_W - 40, 84), self.mouse, right=True)
        button(surf, self.leave_rect, "Уйти (Esc)", self.mouse, primary=True)
        self.bag.draw(surf, run)
        if self.toast:
            T.text(surf, self.toast[0], (T.SCREEN_W // 2, 600), 18, (255, 160, 120), True, center=True, shadow=True)
        T.text(surf, "Shift над картой — читать подробно", (T.SCREEN_W // 2, T.SCREEN_H - 104), 13, T.TEXT_DIM, center=True)
        if getattr(self, "reading", None) is not None:
            self.reading.draw(surf, self.reading.mouse or self.mouse)


class StarterDeckScreen:
    """Своя стартовая колода: 6 базовых + 4 карты 1 тира.

    Компоновка: слева — собранная колода со счётчиками ×N, справа сверху — герой и пассивка,
    справа снизу — доступные карты 1 тира. Shift над картой открывает её как в забеге.
    """

    def __init__(self, game, hero, variant=None):
        self.game = game
        self.data = game.data
        self.hero = hero
        self.variant = variant
        self.h = self.data["heroes"]["heroes"][hero]
        self.basic = M.basic_starter(self.data, hero)
        self.pool = [M.Card(cid, self.data["cards"]["cards"]) for cid in M.tier1_pool(self.data, hero)]
        self.pool.sort(key=lambda c: (c.name, c.cid))
        self.selected = []
        self.mouse = (0, 0)
        self.scroll = 0
        self.rects = []
        self.deck_rects = []
        self.reading = None
        self.W, self.H = T.SCREEN_W, T.SCREEN_H
        self.canvas = None
        self.card_w = 132
        self.card_h = round(self.card_w * CF.FH / CF.FW)
        self.confirm_rect = pygame.Rect(T.SCREEN_W - 300, T.SCREEN_H - 58, 270, 44)
        self.back_rect = pygame.Rect(320, T.SCREEN_H - 58, 210, 44)
        self.toast = None
        self.toast_t = 0.0
        self.max_scroll = 0

    def update(self, dt):
        if self.toast_t > 0:
            self.toast_t = max(0.0, self.toast_t - dt)
            if self.toast_t <= 0:
                self.toast = None

    @property
    def ready(self):
        return len(self.selected) == 4

    def _leave(self):
        if self.canvas is not None:
            self.canvas.reset_layout()
            self.canvas = None

    def finish(self):
        if not self.ready:
            return False
        self._leave()
        self.game.start_run(self.hero, self.variant, starter=self.basic + self.selected)
        return True

    def deck_ids(self):
        return self.basic + self.selected

    def deck_counts(self):
        out = {}
        order = []
        for cid in self.deck_ids():
            if cid not in out:
                out[cid] = 0
                order.append(cid)
            out[cid] += 1
        return [(cid, out[cid]) for cid in order]

    def card_under(self):
        for r, c in self.deck_rects + self.rects:
            if r.collidepoint(self.mouse):
                return c
        return None

    def layout(self):
        gap = 9
        x0 = self.right_x + 12
        top = 326
        per = max(4, (self.right_w - 24) // (self.card_w + gap))
        rows = -(-len(self.pool) // per)
        view_h = self.H - 58 - top
        self.max_scroll = max(0, rows * (self.card_h + 8) - view_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        self.rects = [(pygame.Rect(x0 + (i % per) * (self.card_w + gap),
                                   top + (i // per) * (self.card_h + 8) - self.scroll,
                                   self.card_w, self.card_h), c)
                      for i, c in enumerate(self.pool)]

    def handle(self, ev):
        if reading_event(self, ev, self.card_under):
            return
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:
            self.scroll -= ev.y * 100
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self._leave()
                self.game.new_run()
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.finish()
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.back_rect.collidepoint(ev.pos):
                self._leave()
                self.game.new_run()
                return
            if self.confirm_rect.collidepoint(ev.pos):
                self.finish()
                return
            for r, c in self.deck_rects:
                if r.collidepoint(ev.pos):
                    if c.cid in self.selected:
                        self.selected.remove(c.cid)
                    else:
                        self.toast = ("Базовые карты уже закреплены", 1.2)
                        self.toast_t = 1.2
                    return
            for r, c in self.rects:
                if r.collidepoint(ev.pos) and 300 < ev.pos[1] < T.SCREEN_H - 62:
                    if len(self.selected) >= 4:
                        self.toast = ("Уже выбраны 4 карты · щёлкните по карте в колоде, чтобы убрать", 1.4)
                        self.toast_t = 1.4
                    elif M.deck_limit_reached(c.cid, self.data["cards"]["cards"], self.deck_ids()):
                        self.toast = ("Достигнут предел копий этой карты", 1.4)
                        self.toast_t = 1.4
                    else:
                        self.selected.append(c.cid)
                    return

    def draw(self, surf):
        if G.is_canvas(surf):                                   # широкий экран: используем боковые поля
            self.canvas = surf
            nw, nh = surf.native.get_size()
            self.W = max(T.SCREEN_W, round(T.SCREEN_H * nw / max(1, nh)))
            self.H = T.SCREEN_H
            surf.set_layout(self.W, self.H)
        else:
            self.W, self.H = T.SCREEN_W, T.SCREEN_H
        self.card_w = 132 if self.W < 1500 else 150
        self.card_h = round(self.card_w * CF.FH / CF.FW)
        self.left_w = 300 if self.W < 1500 else 350
        self.right_x = 16 + self.left_w + 18
        self.right_w = self.W - self.right_x - 18
        self.back_rect = pygame.Rect(self.right_x, self.H - 58, 210, 44)
        self.confirm_rect = pygame.Rect(self.W - 300, self.H - 58, 270, 44)
        backdrop(surf, 205)
        T.text(surf, f"Стартовая колода · {self.h['name']}", (self.W // 2, 22), 27, T.AMBER,
               True, center=True, shadow=True)
        passive = (self.h.get("passives") or {}).get(self.variant, {})
        sub = " · ".join(x for x in (passive.get("name", ""), "базовых: 6", f"выбрано: {len(self.selected)}/4") if x)
        T.text(surf, sub, (self.W // 2, 53), 14, T.TEXT_DIM, center=True)

        # ---------- слева: собранная колода ----------
        lr = pygame.Rect(16, 76, self.left_w, self.H - 150)
        T.frame(surf, lr, 232, accent=T.AMBER, fill=(24, 19, 15))
        T.text(surf, f"Колода  {len(self.deck_ids())}/10", (lr.x + 14, lr.y + 8), 18, T.AMBER, True)
        T.text(surf, "повторяющиеся карты показаны как ×N", (lr.x + 14, lr.y + 32), 11, T.TEXT_DIM)
        self.deck_rects = []
        cw = 78 if self.left_w < 330 else 90
        ch = round(cw * CF.FH / CF.FW)
        for i, (cid, n) in enumerate(self.deck_counts()):
            c = M.Card(cid, self.data["cards"]["cards"])
            r = pygame.Rect(lr.x + 14 + (i % 2) * (cw + 10), lr.y + 58 + (i // 2) * (ch + 8), cw, ch)
            CF.blit_card(surf, r, c)
            if n > 1:
                T.text(surf, f"×{n}", (r.right - 8, r.bottom - 16), 14, T.AMBER, True, center=True)
            self.deck_rects.append((r, c))
        if not self.selected:
            T.text(surf, "Добавьте 4 карты из 1 тира", (lr.centerx, lr.bottom - 24), 12, T.TEXT_DIM, center=True)
        T.text(surf, "Клик по карте колоды — убрать выбранную копию", (lr.centerx, lr.bottom - 8), 10,
               T.TEXT_DIM, center=True)

        # ---------- справа сверху: герой и пассивка ----------
        tr = pygame.Rect(self.right_x, 76, self.right_w, 178)
        T.frame(surf, tr, 232, accent=(200, 180, 110), fill=(24, 20, 16))
        img = self.game.hero_img(self.h["sprite"], 1.15)
        surf.blit(img, (tr.x + 16, tr.y + 18))
        T.text(surf, self.h["name"], (tr.x + 130, tr.y + 12), 24, T.AMBER, True)
        if passive:
            T.text(surf, passive.get("name", ""), (tr.x + 130, tr.y + 42), 16, (255, 220, 140), True)
            desc = passive.get("desc", "")
        else:
            desc = ""
        about = self.h.get("about", "")
        rule = self.h.get("rule", "")
        tx = tr.x + 130
        tw = tr.right - tx - 18
        lines = T.wrap(about, 13, tw)[:2] + (T.wrap(desc, 13, tw)[:2] if desc else [])
        for i, ln in enumerate(lines[:4]):
            T.text(surf, ln, (tx, tr.y + 68 + i * 16), 13, T.TEXT_DIM)
        for i, ln in enumerate(T.wrap(rule, 12, tw)[:2]):
            T.text(surf, ln, (tx, tr.bottom - 38 + i * 14), 12, (200, 190, 170))

        # ---------- справа снизу: доступные карты ----------
        br = pygame.Rect(self.right_x, 264, self.right_w, self.H - 330)
        T.frame(surf, br, 232, accent=(120, 170, 220), fill=(20, 18, 16))
        T.text(surf, "Доступные карты · 1 тир", (br.x + 14, br.y + 8), 16, (150, 210, 255), True)
        T.text(surf, "Нажмите карту, чтобы добавить · Shift — подробное чтение",
               (br.x + 14, br.y + 28), 11, T.TEXT_DIM)
        self.layout()
        clip = pygame.Rect(br.x + 8, br.y + 46, br.w - 16, br.h - 52)
        surf.set_clip(clip)
        for r, c in self.rects:
            if r.bottom < clip.top or r.top > clip.bottom:
                continue
            CF.blit_card(surf, r, c)
            n = self.selected.count(c.cid)
            if n:
                T.text(surf, f"×{n}", (r.right - 8, r.bottom - 16), 14, T.AMBER, True, center=True)
        surf.set_clip(None)

        if self.toast:
            T.text(surf, self.toast[0], (self.W // 2, self.H - 88), 14, (255, 180, 120),
                   center=True, shadow=True)
        button(surf, self.back_rect, "Назад (Esc)", self.mouse)
        button(surf, self.confirm_rect, "В подземелье" if self.ready else f"Выберите ещё {4 - len(self.selected)}",
               self.mouse, on=self.ready, primary=True)
        if self.reading is not None:
            self.reading.draw(surf, self.reading.mouse or self.mouse)


class HeroSelect:
    """Выбор героя перед спуском: у каждого своя механика; у Охотницы — ещё и пассивка на выбор."""

    def __init__(self, game):
        self.game = game
        self.data = game.data
        self.order = self.data["heroes"]["order"]
        self.heroes = self.data["heroes"]["heroes"]
        self.pick = self.order[0]
        self.variant = {hid: next(iter(h.get("passives") or {}), None) for hid, h in self.heroes.items()}
        self.mouse = (0, 0)
        self.hits = []
        self.go = pygame.Rect(T.SCREEN_W // 2 - 230, T.SCREEN_H - 74, 460, 56)
        self.cont = pygame.Rect(T.SCREEN_W - 300, T.SCREEN_H - 74, 270, 56)   # продолжить сохранённый забег
        self.sound_rect = pygame.Rect(T.SCREEN_W - 250, 24, 220, 38)           # звук доступен до выбора героя
        self.atlas_rect = pygame.Rect(24, T.SCREEN_H - 74, 250, 56)
        self.clock = 0.0
        self.saved = game.has_save()

    def update(self, dt):
        self.clock += dt

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.atlas_rect.collidepoint(ev.pos):
                self.game.open_atlas()
                return
            if self.sound_rect.collidepoint(ev.pos):
                if getattr(self.game, "sound", None) is not None:
                    self.game.sound.toggle()
                return
            if self.go.collidepoint(ev.pos):
                self.start()
                return
            if self.saved and self.cont.collidepoint(ev.pos):
                self.game.continue_run()
                return
            for r, what in reversed(self.hits):          # варианты лежат внутри карточки героя — они первыми
                if r.collidepoint(ev.pos):
                    if what[0] == "hero":
                        self.pick = what[1]
                    else:
                        self.pick = what[1]
                        self.variant[what[1]] = what[2]
                    return
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start()
            elif ev.key == pygame.K_c and self.saved:
                self.game.continue_run()
            elif pygame.K_1 <= ev.key <= pygame.K_9 and ev.key - pygame.K_1 < len(self.order):
                self.pick = self.order[ev.key - pygame.K_1]

    def start(self):
        self.game.open_starter(self.pick, self.variant.get(self.pick))

    def draw(self, surf):
        backdrop(surf, 185)
        T.text(surf, "Кто спустится в подземелье?", (T.SCREEN_W // 2, 34), 30, T.AMBER, True, center=True,
               shadow=True)
        button(surf, self.sound_rect, f"Звук: {audio.volume_text()} · F10", self.mouse)
        button(surf, self.atlas_rect, "Атлас · F2", self.mouse)
        self.hits = []
        n = len(self.order)
        gap = 18 if n < 4 else 12
        w = min(392, (T.SCREEN_W - 32 - (n - 1) * gap) // n)          # четверо и больше — уже
        x0 = (T.SCREEN_W - n * w - (n - 1) * gap) // 2
        for i, hid in enumerate(self.order):
            h = self.heroes[hid]
            r = pygame.Rect(x0 + i * (w + gap), 76, w, 618)
            sel = hid == self.pick
            T.frame(surf, r, 240, accent=T.SELECT if sel else T.PANEL_EDGE)
            if sel:                                            # выбранный — яркая рамка
                pygame.draw.rect(surf, T.SELECT, r.inflate(4, 4), 3, border_radius=9)
            self.hits.append((r, ("hero", hid)))
            img = self.game.hero_img(h["sprite"], 1.6)
            bob = int(3 * math.sin(self.clock * 2.4 + i)) if sel else 0
            surf.blit(img, (r.centerx - img.get_width() // 2, r.y + 150 - img.get_height() + bob))
            T.text(surf, h["name"], (r.centerx, r.y + 172), 26, T.TEXT, True, center=True)
            T.text(surf, f"HP {h['hp']} · " + ("жар вместо энергии" if h.get("mechanic") == "heat"
                                              else "свитки без цены" if h.get("mechanic") == "idols"
                                              else f"энергия {h.get('energy', 3)}"),
                   (r.centerx, r.y + 198), 14, T.TEXT_DIM, center=True)
            y = r.y + 220
            for line in T.wrap(h["about"], 15, w - 30):
                T.text(surf, line, (r.centerx, y), 15, T.TEXT, center=True)
                y += 19
            y += 6
            rich_rect = pygame.Rect(r.x + 16, y, w - 32, 10)
            hgt = CF.rich(surf, h["rule"].replace("Разгон:", "*Разгон*:").replace("Жар —", "*Жар* —"), rich_rect, 14,
                          (225, 210, 185))
            y = rich_rect.y + hgt + 14
            if h.get("passives"):                              # Охотница: пассивка на выбор
                compact = len(h["passives"]) > 3                 # много наборов — плотнее
                step = 50 if compact else 80
                for k, (pid, p) in enumerate(h["passives"].items()):
                    pr = pygame.Rect(r.x + 14, y + k * step, w - 28, step - 6)
                    on = self.variant[hid] == pid
                    T.frame(surf, pr, 235, accent=(255, 210, 120) if on else T.PANEL_EDGE,
                            fill=(60, 44, 24) if on else (34, 26, 20))
                    T.text(surf, ("● " if on else "○ ") + p["name"], (pr.x + 10, pr.y + 4), 14,
                           (255, 220, 140) if on else T.TEXT, True)
                    size, line_h, lines = (10, 11, 2) if compact else (12, 15, 3)
                    for j, line in enumerate(T.wrap(p["desc"], size, pr.w - 20)[:lines]):
                        T.text(surf, line, (pr.x + 12, pr.y + 21 + j * line_h), size, T.TEXT_DIM)
                    self.hits.append((pr, ("variant", hid, pid)))
            else:                                               # стартовые карты — лица
                seen = []
                for cid in h["starter"]:
                    if cid not in seen:
                        seen.append(cid)
                from .model import Card
                total = min(5, len(seen))
                cw = min(70, (w - 24) // total - 6)
                sx = r.centerx - (total * (cw + 6) - 6) // 2
                for k, cid in enumerate(seen[:5]):
                    cr = pygame.Rect(sx + k * (cw + 6), y + 4, cw, int(cw * CF.FH / CF.FW))
                    CF.blit_card(surf, cr, Card(cid, self.game.run_defs()))
                T.text(surf, "стартовые карты", (r.centerx, y + 120), 12, T.TEXT_DIM, center=True)
        h = self.heroes[self.pick]
        label = f"Начать спуск: {h['name']}"
        if h.get("passives"):
            label += f" · {h['passives'][self.variant[self.pick]]['name']}"
        button(surf, self.go, label, self.mouse, primary=True)
        if self.saved:                                     # сохранённый забег — продолжить
            button(surf, self.cont, "Продолжить забег (C)", self.mouse, primary=True)
