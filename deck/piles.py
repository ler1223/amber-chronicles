"""Просмотр боевых стопок: колода, сыгранные за ход, сброс и изгнанные карты.

Экран открывается кликом по стопке в бою. «Сыграно» и «Сброшено» специально
разделены: в конце хода сыгранные карты уходят в сброс, но до этого игрок видит
их отдельно.
"""
import pygame

from ui import theme as T

from .ui import DeckScreen


class PileScreen(DeckScreen):
    """Стопки боя сеткой; вкладки не дают смешать сыгранное и сброшенное."""

    def __init__(self, game, battle_screen, initial="deck"):
        self.battle_screen = battle_screen
        self.b = battle_screen.b
        self.sources = {
            "deck": list(self.b.draw_pile),
            "used": list(self.b.used),
            "discard": list(self.b.discard),
            "exhaust": list(self.b.exhaust),
        }
        self.tab = initial if initial in self.sources else "deck"
        self.tab_rects = []
        super().__init__(game, "Стопки боя", self.sources[self.tab],
                         lambda: setattr(game, "scene", battle_screen), sub=None)
        self.back_rect = pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 60, 220, 46)

    def switch(self, key):
        if key in self.sources:
            self.tab = key
            self.cards = self.sources[key]
            self.scroll = 0

    def _tabs(self):
        labels = [
            ("deck", f"Колода {len(self.sources['deck'])}"),
            ("used", f"Сыграно {len(self.sources['used'])}"),
            ("discard", f"Сброс {len(self.sources['discard'])}"),
            ("exhaust", f"Изгнано {len(self.sources['exhaust'])}"),
        ]
        widths = [max(150, T.font(16, True).size(label)[0] + 30) for _, label in labels]
        gap = 8
        x = (T.SCREEN_W - sum(widths) - gap * (len(labels) - 1)) // 2
        self.tab_rects = []
        for (key, label), w in zip(labels, widths):
            self.tab_rects.append((pygame.Rect(x, 62, w, 30), key, label))
            x += w + gap

    def handle(self, ev):
        self._tabs()
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            for r, key, _ in self.tab_rects:
                if r.collidepoint(ev.pos):
                    self.switch(key)
                    return
        super().handle(ev)

    def draw(self, surf):
        super().draw(surf)
        self._tabs()
        for r, key, label in self.tab_rects:
            hot = r.collidepoint(self.mouse)
            active = key == self.tab
            pygame.draw.rect(surf, (62, 46, 30) if hot or active else (40, 30, 22), r, border_radius=7)
            pygame.draw.rect(surf, T.AMBER if active else T.PANEL_EDGE, r, 2 if active else 1, border_radius=7)
            T.text(surf, label, r.center, 15, T.TEXT if active else T.TEXT_DIM, True, center=True)
        if not self.cards:
            T.text(surf, "Здесь пока нет карт", (T.SCREEN_W // 2, T.SCREEN_H // 2), 20,
                   T.TEXT_DIM, center=True)
