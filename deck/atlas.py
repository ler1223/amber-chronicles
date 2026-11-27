"""Атлас карт и предметов «Спуска», доступный вне забега и во время него.

Экран не зависит от забега: его можно открыть из выбора героя или с карты этажа.
Карты читаются теми же лицами и тем же Inspector, что и в бою.
"""
import pygame

from ui import theme as T

from . import cardface as CF
from . import gfx as G
from . import model as M
from .items import RARITY_COLOR, RARITY_NAME, about
from .ui import Inspector, backdrop, button, draw_item_icon, wide_layout

FILTERS = [
    ("all", "Все"),
    ("merc", "Наёмник"),
    ("hunter", "Охотница"),
    ("pyro", "Пиромантка"),
    ("priest", "Жрец"),
    ("elf", "Эльф"),
    ("neutral", "Нейтральные"),
    ("basic", "Базовые"),
    ("scroll", "Свитки"),
]
HERO_PREFIX = {"merc": "m_", "hunter": "h_", "pyro": "p_", "priest": "sc_", "elf": "e_"}
HERO_ORDER = {"merc": 0, "hunter": 1, "pyro": 2, "priest": 3, "elf": 4, "neutral": 5, "basic": 6, "other": 7}
GRID_TOP = 150
GRID_BOTTOM = 76
CW = 128
GAP = 10
COLS = 7
ITEM_FILTERS = [("all", "Все"), ("common", "Обычные"), ("uncommon", "Необычные"),
                ("rare", "Редкие"), ("boss", "От стражей"), ("shop", "Товары")]


class CardAtlasScreen:
    def __init__(self, game, back=None):
        self.game = game
        self.back = back
        self.data = game.data
        self.cards = [M.Card(cid, self.data["cards"]["cards"])
                      for cid in self.data["cards"]["cards"]]
        self.filter = "all"
        self.mouse = (0, 0)
        self.scroll = 0.0
        self.scroll_target = 0.0
        self.max_scroll = 0
        self.reading = None
        self.filter_rects = []
        self.card_rects = []
        self.W = T.SCREEN_W
        self.back_rect = pygame.Rect(T.SCREEN_W - 250, T.SCREEN_H - 54, 220, 38)
        self._filter_cache = {}
        self._thumbs = {}
        self.tab = "cards"
        self.tab_rects = []
        self.item_page = ItemAtlas(self)

    def update(self, dt):
        """Плавная прокрутка: колесо задаёт цель, кадры догоняют её с easing."""
        if self.tab == "items":
            self.item_page.update(dt)
            return
        if abs(self.scroll_target - self.scroll) < 0.35:
            self.scroll = self.scroll_target
        else:
            self.scroll += (self.scroll_target - self.scroll) * min(1.0, dt * 18)

    def _thumb(self, card, hot, S):
        """Готовая миниатюра в родном разрешении — без повторного compose/blit_hd каждый кадр."""
        key = (card.uid, bool(hot), round(S, 3))
        img = self._thumbs.get(key)
        if img is None:
            img = CF.face(card, True, True, hot, width=round(CW * S))
            if len(self._thumbs) > 500:
                self._thumbs.clear()
            self._thumbs[key] = img
        return img

    def _owner(self, card):
        c = card.d
        if c.get("category") == "neutral":
            return "neutral"
        if c.get("category") == "basic":
            for hid, h in self.data["heroes"]["heroes"].items():
                if card.cid in (h.get("basic") or {}).values():
                    return hid
            return "basic"
        for hid, prefix in HERO_PREFIX.items():
            if card.cid.startswith(prefix):
                return hid
        return c.get("owner") or "other"

    def filtered(self):
        got = self._filter_cache.get(self.filter)
        if got is not None:
            return got
        cards = self.cards
        if self.filter == "basic":
            cards = [c for c in cards if c.d.get("category") == "basic"]
        elif self.filter == "scroll":
            cards = [c for c in cards if c.d.get("meaning")]
        elif self.filter != "all":
            cards = [c for c in cards if self._owner(c) == self.filter]
        cards = sorted(cards, key=lambda c: (HERO_ORDER.get(self._owner(c), 9), c.category != "basic",
                                             -c.rarity, c.name))
        self._filter_cache[self.filter] = cards
        return cards

    def _layout_filters(self):
        gap = 6
        w = 124
        x0 = (self.W - (len(FILTERS) * w + (len(FILTERS) - 1) * gap)) // 2
        self.filter_rects = [(pygame.Rect(x0 + i * (w + gap), 78, w, 34), key, label)
                             for i, (key, label) in enumerate(FILTERS)]

    def _grid(self):
        cards = self.filtered()
        card_h = round(CW * CF.FH / CF.FW)
        rows = (len(cards) + COLS - 1) // COLS
        total = rows * (card_h + GAP)
        view_h = T.SCREEN_H - GRID_TOP - GRID_BOTTOM
        self.max_scroll = max(0, total - view_h)
        self.scroll_target = max(0.0, min(self.scroll_target, float(self.max_scroll)))
        self.scroll = max(0.0, min(self.scroll, float(self.max_scroll)))
        x0 = (self.W - (COLS * CW + (COLS - 1) * GAP)) // 2
        out = []
        for i, card in enumerate(cards):
            y = GRID_TOP + (i // COLS) * (card_h + GAP) - round(self.scroll)
            if y + card_h < GRID_TOP - 1 or y > T.SCREEN_H - GRID_BOTTOM:
                continue
            r = pygame.Rect(x0 + (i % COLS) * (CW + GAP), y, CW, card_h)
            out.append((r, card))
        self.card_rects = out
        return cards, card_h

    def card_at(self, pos):
        if not GRID_TOP <= pos[1] < T.SCREEN_H - GRID_BOTTOM:
            return None
        return next((c for r, c in self.card_rects if r.collidepoint(pos)), None)

    def handle(self, ev):
        if self.reading is not None:
            if ev.type == pygame.MOUSEMOTION:
                self.reading.mouse = ev.pos
            elif ev.type == pygame.MOUSEWHEEL:
                self.reading.wheel(ev.y)
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.reading = None
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if self.reading.click(ev.pos, ev.button):
                    return
                if not self.reading.contains(ev.pos):
                    self.reading = None
            return
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            if self.back_rect.collidepoint(ev.pos):
                self.game.scene = self.back or self.game.scene
                return
            for r, tab, _ in self.tab_rects:
                if r.collidepoint(ev.pos):
                    self.tab = tab
                    return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.game.scene = self.back or self.game.scene
            return
        if self.tab == "items":
            self.item_page.handle(ev)
            return
        if ev.type == pygame.MOUSEWHEEL:
            self.scroll_target -= ev.y * 110
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                c = self.card_at(self.mouse)
                if c is not None:
                    self.reading = Inspector(c, pinned=True)
                    self.reading.mouse = self.mouse
            elif ev.key == pygame.K_HOME:
                self.scroll_target = 0
            elif ev.key == pygame.K_END:
                self.scroll_target = self.max_scroll
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, key, _ in self.filter_rects:
                if r.collidepoint(ev.pos):
                    self.filter = key
                    self.scroll = self.scroll_target = 0
                    return
            c = self.card_at(ev.pos)
            if c is not None:
                self.reading = Inspector(c, pinned=True)
                self.reading.mouse = ev.pos

    def draw(self, surf):
        self.W = wide_layout(surf)[0]
        self.back_rect.right = self.W - 30
        mid = self.W // 2
        self.tab_rects = [(pygame.Rect(mid - 164, 20, 160, 38), "cards", "Атлас карт"),
                          (pygame.Rect(mid + 4, 20, 160, 38), "items", "Атлас предметов")]
        backdrop(surf, 210)
        for r, tab, label in self.tab_rects:
            button(surf, r, label, self.mouse, primary=tab == self.tab)
        if self.tab == "items":
            self.item_page.draw(surf)
        else:
            self.draw_cards(surf)
        button(surf, self.back_rect, "Назад (Esc)", self.mouse)
        T.text(surf, "Колесо — прокрутка", (18, T.SCREEN_H - 30), 13, T.TEXT_DIM)
        if self.reading is not None:
            self.reading.draw(surf, self.reading.mouse or self.mouse)

    def draw_cards(self, surf):
        cards, _ = self._grid()
        self._layout_filters()
        for r, key, label in self.filter_rects:
            hot = r.collidepoint(self.mouse)
            active = key == self.filter
            pygame.draw.rect(surf, (62, 46, 30) if hot or active else (40, 30, 22), r, border_radius=7)
            pygame.draw.rect(surf, T.AMBER if active else T.PANEL_EDGE, r, 2 if active else 1, border_radius=7)
            T.text(surf, label, r.center, 15, T.TEXT if active else T.TEXT_DIM, True, center=True)
        T.text(surf, f"{len(cards)} карт · клик — открыть · Shift — закрепить",
               (self.W // 2, 129), 14, T.TEXT_DIM, center=True)
        clip = pygame.Rect(18, GRID_TOP, self.W - 36, T.SCREEN_H - GRID_TOP - GRID_BOTTOM)
        surf.set_clip(clip)
        for r, card in self.card_rects:
            hot = r.collidepoint(self.mouse)
            if G.is_canvas(surf):
                img = self._thumb(card, hot, surf.S)
                x, y = surf.pt(r.topleft)
                surf.native.blit(img, (round(x), round(y)))
            else:
                CF.blit_card(surf, r, card, hot=hot)
            if hot:
                pygame.draw.rect(surf, T.SELECT, r.inflate(6, 6), 2, border_radius=8)
        surf.set_clip(None)
        if not self.card_rects:
            T.text(surf, "В этом фильтре карт нет", (self.W // 2, T.SCREEN_H // 2), 20,
                   T.TEXT_DIM, center=True)
        if self.max_scroll:
            track = pygame.Rect(self.W - 17, GRID_TOP, 7, T.SCREEN_H - GRID_TOP - GRID_BOTTOM)
            pygame.draw.rect(surf, (30, 24, 18), track, border_radius=4)
            h = max(28, round(track.h * (T.SCREEN_H - GRID_TOP - GRID_BOTTOM) /
                              max(1, T.SCREEN_H - GRID_TOP - GRID_BOTTOM + self.max_scroll)))
            y = track.y + round((track.h - h) * self.scroll / max(1, self.max_scroll))
            pygame.draw.rect(surf, T.AMBER_DIM, (track.x, y, track.w, h), border_radius=4)


class ItemAtlas:
    def __init__(self, atlas):
        self.atlas = atlas
        self.items = sorted((dict(item, id=iid) for iid, item in atlas.data["relics"]["relics"].items()),
                            key=lambda item: item["name"].casefold().replace("ё", "е"))
        self.filter = "all"
        self.selected = self.items[0] if self.items else None
        self.scroll = self.scroll_target = self.max_scroll = 0
        self.filters = []
        self.entries = []
        self.viewport = pygame.Rect(0, 0, 0, 0)
        back_pick = getattr(atlas.back, "pick", None)
        self.hero_id = back_pick if isinstance(back_pick, str) else getattr(atlas.game.run, "hero_id", None)

    def filtered(self):
        return [item for item in self.items if self.filter in ("all", item.get("rarity"))]

    def update(self, dt):
        self.scroll_target = max(0, min(self.scroll_target, self.max_scroll))
        delta = self.scroll_target - self.scroll
        self.scroll = self.scroll_target if abs(delta) < 0.35 else self.scroll + delta * min(1.0, dt * 18)

    def handle(self, ev):
        if ev.type == pygame.MOUSEWHEEL:
            self.scroll_target -= ev.y * 128
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_HOME, pygame.K_END):
            self.scroll_target = 0 if ev.key == pygame.K_HOME else self.max_scroll
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, rarity, _ in self.filters:
                if r.collidepoint(ev.pos):
                    self.filter = rarity
                    self.scroll = self.scroll_target = 0
                    items = self.filtered()
                    if self.selected not in items:
                        self.selected = items[0] if items else None
                    return
            if self.viewport.collidepoint(ev.pos):
                for r, item in self.entries:
                    if r.collidepoint(ev.pos):
                        self.selected = item
                        return

    def draw(self, surf):
        items = self.filtered()
        mouse = self.atlas.mouse
        sw = self.atlas.W
        x = (sw - 1200) // 2
        self.viewport = pygame.Rect(x, GRID_TOP, 764, T.SCREEN_H - GRID_TOP - GRID_BOTTOM)
        filters_width = len(ITEM_FILTERS) * 124
        left = (sw - filters_width) // 2
        self.filters = [(pygame.Rect(left + i * 124, 78, 118, 34), key, label)
                        for i, (key, label) in enumerate(ITEM_FILTERS)]
        for r, key, label in self.filters:
            button(surf, r, label, mouse, primary=key == self.filter)
        T.text(surf, f"Предметов: {len(items)}", (x, 123), 15, T.TEXT_DIM)
        row_h = 76
        self.max_scroll = max(0, ((len(items) + 1) // 2) * row_h - self.viewport.h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        self.entries = []
        surf.set_clip(self.viewport)
        for i, item in enumerate(items):
            y = GRID_TOP + (i // 2) * row_h - round(self.scroll)
            r = pygame.Rect(x + (i % 2) * 378, y, 370, 68)
            if not r.colliderect(self.viewport):
                continue
            self.entries.append((r, item))
            color = RARITY_COLOR.get(item.get("rarity"), T.AMBER)
            active = item is self.selected
            hot = self.viewport.collidepoint(mouse) and r.collidepoint(mouse)
            T.frame(surf, r, 225, accent=color if hot or active else T.PANEL_EDGE, corners=False,
                    fill=(56, 41, 27) if active else None)
            draw_item_icon(surf, item, (r.x + 34, r.centery), 44)
            T.text(surf, item["name"], (r.x + 66, r.y + 12), 17, T.TEXT, True)
            T.text(surf, RARITY_NAME.get(item.get("rarity"), "").capitalize(), (r.x + 66, r.y + 38), 14, color)
        surf.set_clip(None)
        if self.max_scroll:
            track = pygame.Rect(self.viewport.right - 6, self.viewport.top, 5, self.viewport.h)
            pygame.draw.rect(surf, T.PANEL_EDGE, track, border_radius=3)
            h = max(28, round(track.h * self.viewport.h / (self.viewport.h + self.max_scroll)))
            y = track.y + round((track.h - h) * self.scroll / self.max_scroll)
            pygame.draw.rect(surf, T.AMBER_DIM, (track.x, y, track.w, h), border_radius=3)
        panel = pygame.Rect(x + 786, GRID_TOP, 414, self.viewport.h)
        T.frame(surf, panel, 235, accent=T.PANEL_EDGE)
        if self.selected is None:
            T.text(surf, "В этом фильтре нет предметов", panel.center, 18, T.TEXT_DIM, center=True)
            return
        self.draw_details(surf, panel, self.selected)

    def draw_details(self, surf, panel, item):
        color = RARITY_COLOR.get(item.get("rarity"), T.AMBER)
        draw_item_icon(surf, item, (panel.centerx, panel.top + 80), 108)
        y = panel.top + 151
        for line in T.wrap(item["name"], 25, panel.w - 44, True):
            T.text(surf, line, (panel.centerx, y), 25, T.TEXT, True, center=True)
            y += 29
        heroes = self.atlas.data["heroes"]["heroes"]
        hero = item.get("hero")
        rarity = RARITY_NAME.get(item.get("rarity"), "").capitalize()
        if hero in heroes:
            rarity += " · " + heroes[hero]["name"]
        T.text(surf, rarity, (panel.centerx, y + 5), 15, color, True, center=True)
        y += 35
        description = about(item, hero=hero or self.hero_id)
        for line in T.wrap(description, 19, panel.w - 48):
            T.text(surf, line, (panel.x + 24, y), 19, T.TEXT)
            y += 27
