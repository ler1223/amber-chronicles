"""Атлас карт «Спуска»: все карты игры с фильтрами по герою и свиткам.

Экран не зависит от забега: его можно открыть из выбора героя или с карты этажа.
Карты читаются теми же лицами и тем же Inspector, что и в бою.
"""
import pygame

from ui import theme as T

from . import cardface as CF
from . import model as M
from .ui import Inspector, backdrop, button

FILTERS = [
    ("all", "Все"),
    ("merc", "Наёмник"),
    ("hunter", "Охотница"),
    ("pyro", "Пиромантка"),
    ("priest", "Жрец"),
    ("neutral", "Нейтральные"),
    ("basic", "Базовые"),
    ("scroll", "Свитки"),
]
HERO_PREFIX = {"merc": "m_", "hunter": "h_", "pyro": "p_", "priest": "sc_"}
HERO_ORDER = {"merc": 0, "hunter": 1, "pyro": 2, "priest": 3, "neutral": 4, "basic": 5, "other": 6}
GRID_TOP = 150
GRID_BOTTOM = 76
CW = 128
GAP = 10
COLS = 7


class CardAtlasScreen:
    def __init__(self, game, back=None):
        self.game = game
        self.back = back
        self.data = game.data
        self.cards = [M.Card(cid, self.data["cards"]["cards"])
                      for cid in self.data["cards"]["cards"]]
        self.filter = "all"
        self.mouse = (0, 0)
        self.scroll = 0
        self.max_scroll = 0
        self.reading = None
        self.filter_rects = []
        self.card_rects = []
        self.back_rect = pygame.Rect(T.SCREEN_W - 250, T.SCREEN_H - 54, 220, 38)

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
        cards = self.cards
        if self.filter == "basic":
            cards = [c for c in cards if c.d.get("category") == "basic"]
        elif self.filter == "scroll":
            cards = [c for c in cards if c.d.get("meaning")]
        elif self.filter != "all":
            cards = [c for c in cards if self._owner(c) == self.filter]
        return sorted(cards, key=lambda c: (HERO_ORDER.get(self._owner(c), 9), c.category != "basic",
                                            -c.rarity, c.name))

    def _layout_filters(self):
        gap = 6
        w = 124
        x0 = (T.SCREEN_W - (len(FILTERS) * w + (len(FILTERS) - 1) * gap)) // 2
        self.filter_rects = [(pygame.Rect(x0 + i * (w + gap), 78, w, 34), key, label)
                             for i, (key, label) in enumerate(FILTERS)]

    def _grid(self):
        cards = self.filtered()
        card_h = round(CW * CF.FH / CF.FW)
        rows = (len(cards) + COLS - 1) // COLS
        total = rows * (card_h + GAP)
        view_h = T.SCREEN_H - GRID_TOP - GRID_BOTTOM
        self.max_scroll = max(0, total - view_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        x0 = (T.SCREEN_W - (COLS * CW + (COLS - 1) * GAP)) // 2
        out = []
        for i, card in enumerate(cards):
            y = GRID_TOP + (i // COLS) * (card_h + GAP) - self.scroll
            if y + card_h < GRID_TOP - 1 or y > T.SCREEN_H - GRID_BOTTOM:
                continue
            r = pygame.Rect(x0 + (i % COLS) * (CW + GAP), y, CW, card_h)
            out.append((r, card))
        self.card_rects = out
        return cards, card_h

    def card_at(self, pos):
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
        elif ev.type == pygame.MOUSEWHEEL:
            self.scroll -= ev.y * 120
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.game.scene = self.back or self.game.scene
            elif ev.key in (pygame.K_lshift, pygame.K_RSHIFT):
                c = self.card_at(self.mouse)
                if c is not None:
                    self.reading = Inspector(c, pinned=True)
                    self.reading.mouse = self.mouse
            elif ev.key == pygame.K_HOME:
                self.scroll = 0
            elif ev.key == pygame.K_END:
                self.scroll = self.max_scroll
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            if self.back_rect.collidepoint(ev.pos):
                self.game.scene = self.back or self.game.scene
                return
            for r, key, _ in self.filter_rects:
                if r.collidepoint(ev.pos):
                    self.filter = key
                    self.scroll = 0
                    return
            c = self.card_at(ev.pos)
            if c is not None:
                self.reading = Inspector(c, pinned=True)
                self.reading.mouse = ev.pos

    def draw(self, surf):
        cards, card_h = self._grid()
        self._layout_filters()
        backdrop(surf, 210)
        T.text(surf, "Атлас карт", (T.SCREEN_W // 2, 22), 30, T.AMBER, True, center=True, shadow=True)
        T.text(surf, f"{len(cards)} карт · клик — открыть · Shift — закрепить · Esc — назад",
               (T.SCREEN_W // 2, 54), 14, T.TEXT_DIM, center=True)
        for r, key, label in self.filter_rects:
            hot = r.collidepoint(self.mouse)
            active = key == self.filter
            pygame.draw.rect(surf, (62, 46, 30) if hot or active else (40, 30, 22), r, border_radius=7)
            pygame.draw.rect(surf, T.AMBER if active else T.PANEL_EDGE, r, 2 if active else 1, border_radius=7)
            T.text(surf, label, r.center, 15, T.TEXT if active else T.TEXT_DIM, True, center=True)
        clip = pygame.Rect(18, GRID_TOP, T.SCREEN_W - 36, T.SCREEN_H - GRID_TOP - GRID_BOTTOM)
        surf.set_clip(clip)
        for r, card in self.card_rects:
            hot = r.collidepoint(self.mouse)
            CF.blit_card(surf, r, card, hot=hot)
            if hot:
                pygame.draw.rect(surf, T.SELECT, r.inflate(6, 6), 2, border_radius=8)
        surf.set_clip(None)
        if not self.card_rects:
            T.text(surf, "В этом фильтре карт нет", (T.SCREEN_W // 2, T.SCREEN_H // 2), 20,
                   T.TEXT_DIM, center=True)
        if self.max_scroll:
            track = pygame.Rect(T.SCREEN_W - 17, GRID_TOP, 7, T.SCREEN_H - GRID_TOP - GRID_BOTTOM)
            pygame.draw.rect(surf, (30, 24, 18), track, border_radius=4)
            h = max(28, round(track.h * (T.SCREEN_H - GRID_TOP - GRID_BOTTOM) /
                              max(1, T.SCREEN_H - GRID_TOP - GRID_BOTTOM + self.max_scroll)))
            y = track.y + round((track.h - h) * self.scroll / max(1, self.max_scroll))
            pygame.draw.rect(surf, T.AMBER_DIM, (track.x, y, track.w, h), border_radius=4)
        button(surf, self.back_rect, "Назад (Esc)", self.mouse)
        T.text(surf, "Колесо — прокрутка", (18, T.SCREEN_H - 30), 13, T.TEXT_DIM)
        if self.reading is not None:
            self.reading.draw(surf, self.reading.mouse or self.mouse)
