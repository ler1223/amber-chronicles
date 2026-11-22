"""Небольшая панель звука поверх любого экрана «Спуска» (F10).

Музыка играет непрерывно; панель меняет только громкость, поэтому её можно открыть
в бою, на карте, в магазине и не потерять ход.
"""
import pygame

from ui import audio
from ui import theme as T

from . import gfx as G


def _shade(surf, alpha=190):
    """Затемнить настоящий экран; на Canvas — его native-поверхность."""
    target = surf.native if G.is_canvas(surf) else surf
    shade = pygame.Surface(target.get_size(), pygame.SRCALPHA)
    shade.fill((7, 5, 4, alpha))
    target.blit(shade, (0, 0))


class SoundPanel:
    def __init__(self):
        self.open = False
        self.mouse = (0, 0)
        self.box = pygame.Rect(0, 0, 0, 0)
        self.bar = pygame.Rect(0, 0, 0, 0)
        self.minus = pygame.Rect(0, 0, 0, 0)
        self.plus = pygame.Rect(0, 0, 0, 0)
        self.mute = pygame.Rect(0, 0, 0, 0)
        self.close = pygame.Rect(0, 0, 0, 0)
        self._layout()

    def _layout(self):
        w, h = T.SCREEN_W, T.SCREEN_H
        self.box = pygame.Rect((w - 580) // 2, (h - 310) // 2, 580, 310)
        b = self.box
        self.bar = pygame.Rect(b.x + 118, b.y + 125, b.w - 236, 24)
        self.minus = pygame.Rect(b.x + 66, b.y + 120, 40, 34)
        self.plus = pygame.Rect(b.right - 106, b.y + 120, 40, 34)
        self.mute = pygame.Rect(b.centerx - 170, b.y + 202, 166, 42)
        self.close = pygame.Rect(b.centerx + 8, b.y + 202, 166, 42)

    def toggle(self):
        self.open = not self.open
        return self.open

    def _click_volume(self, pos):
        rel = max(0.0, min(1.0, (pos[0] - self.bar.x) / max(1, self.bar.w)))
        levels = audio.levels()
        audio.set_index(round(rel * (len(levels) - 1)))

    def handle(self, ev):
        if not self.open:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F10:
                self.open = True
                return True
            return False
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            if self.close.collidepoint(ev.pos):
                self.open = False
            elif self.mute.collidepoint(ev.pos):
                audio.toggle_mute()
            elif self.minus.collidepoint(ev.pos):
                audio.adjust(-1)
            elif self.plus.collidepoint(ev.pos):
                audio.adjust(1)
            elif self.bar.collidepoint(ev.pos):
                self._click_volume(ev.pos)
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_F10):
                self.open = False
            elif ev.key == pygame.K_m:
                audio.toggle_mute()
            elif ev.key in (pygame.K_LEFT, pygame.K_MINUS):
                audio.adjust(-1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_PLUS):
                audio.adjust(1)
        return True

    def draw(self, surf):
        if not self.open:
            return
        self._layout()
        _shade(surf)
        b = self.box
        T.frame(surf, b, 248, accent=T.AMBER, corners=True)
        T.text(surf, "Звук", (b.centerx, b.y + 32), 30, T.AMBER, True, center=True, shadow=True)
        T.text(surf, "Фоновая музыка", (b.x + 28, b.y + 80), 18, T.TEXT, True)
        T.text(surf, audio.volume_text(), (b.right - 28, b.y + 80), 18, T.AMBER, True)
        # ползунок
        pygame.draw.rect(surf, (31, 24, 18), self.bar, border_radius=10)
        pygame.draw.rect(surf, T.PANEL_EDGE, self.bar, 1, border_radius=10)
        fill = self.bar.copy()
        fill.w = max(2, round(self.bar.w * audio.levels()[audio.index()]))
        if fill.w > 3:
            pygame.draw.rect(surf, T.AMBER_DIM, fill, border_radius=10)
        knob_x = self.bar.x + fill.w
        pygame.draw.circle(surf, T.AMBER, (knob_x, self.bar.centery), 8)
        for r, label in ((self.minus, "−"), (self.plus, "+")):
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (62, 46, 30) if hot else (39, 29, 21), r, border_radius=7)
            pygame.draw.rect(surf, T.SELECT if hot else T.PANEL_EDGE, r, 1, border_radius=7)
            T.text(surf, label, r.center, 24, T.TEXT, True, center=True)
        # кнопки
        for r, label, accent in ((self.mute, "Выключить (M)" if not audio.is_muted() else "Включить (M)",
                                  T.AMBER_DIM), (self.close, "Готово (Esc)", T.SELECT)):
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (62, 46, 30) if hot else (39, 29, 21), r, border_radius=7)
            pygame.draw.rect(surf, accent if hot else T.PANEL_EDGE, r, 1, border_radius=7)
            T.text(surf, label, r.center, 17, T.TEXT, True, center=True)
        T.text(surf, "F10 — открыть/закрыть · ← → или − + — громкость", (b.centerx, b.bottom - 24), 13,
               T.TEXT_DIM, center=True)
