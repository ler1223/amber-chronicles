"""Окно и масштабирование: игра рисует кадр 1280×800 (логический экран), он растягивается под окно с сохранением
пропорций — по краям остаются поля с приглушённым кадром. Окно можно тянуть мышью; F11 или Alt+Enter — полный
экран; стартовый размер — в настройках («Окно»). Координаты мыши из событий переводятся обратно в логический
экран, поэтому сцены про масштаб ничего не знают.
"""
import warnings

import pygame

from ui import theme as T
from ui.settings import SETTINGS

SIZES = {"1280x800": (1280, 800), "1600x1000": (1600, 1000), "1920x1200": (1920, 1200)}
MIN_W, MIN_H = 960, 600          # меньше — интерфейс становится нечитаемым
CURRENT = None


def fit(window_w, window_h, logical_w=T.SCREEN_W, logical_h=T.SCREEN_H):
    """Прямоугольник кадра на окне: (x, y, w, h) — по центру, пропорции сохранены."""
    w, h = max(1, int(window_w)), max(1, int(window_h))
    k = min(w / logical_w, h / logical_h)
    vw, vh = max(1, int(logical_w * k)), max(1, int(logical_h * k))
    return (w - vw) // 2, (h - vh) // 2, vw, vh


class Display:
    def __init__(self, use_gl):
        global CURRENT
        self.use_gl = use_gl
        self.flags = (pygame.OPENGL | pygame.DOUBLEBUF if use_gl else 0) | pygame.RESIZABLE
        self.screen = pygame.display.set_mode(self._wanted(), self.flags, vsync=1 if use_gl else 0)
        with warnings.catch_warnings():      # pygame-ce пока помечает from_display_module как устаревший
            warnings.simplefilter("ignore", DeprecationWarning)
            self.window = pygame.Window.from_display_module()
        self._clamp_minimum()
        self.full = False
        if SETTINGS.get("window") == "fullscreen":
            self.toggle_fullscreen()
        CURRENT = self

    def _desktop(self):
        try:
            return pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError):
            return T.SCREEN_W, T.SCREEN_H

    def _clamp_minimum(self):
        """Не даём утянуть окно до нечитаемого размера (но и не больше экрана)."""
        dw, dh = self._desktop()
        try:
            self.window.minimum_size = (min(MIN_W, max(320, dw - 80)), min(MIN_H, max(240, dh - 80)))
        except (AttributeError, pygame.error):
            pass

    def _wanted(self):
        """Стартовый размер окна: пресет из настроек или 85% рабочего стола с пропорциями игры."""
        mode = SETTINGS.get("window", "auto")
        if mode in SIZES:
            return SIZES[mode]
        dw, dh = self._desktop()
        base = min(dw * 0.85 / T.SCREEN_W, dh * 0.85 / T.SCREEN_H)
        # не меньше 960×600 (если экран позволяет) и не больше 2× логического кадра
        k = max(min(MIN_W / T.SCREEN_W, base), min(base, 2.0))
        return int(T.SCREEN_W * k), int(T.SCREEN_H * k)

    def size(self):
        try:
            w, h = self.window.size
        except (AttributeError, pygame.error):
            w, h = self.screen.get_size()
        return max(1, int(w)), max(1, int(h))

    def view(self):
        """Где на окне кадр игры: (x, y, ширина, высота) — по центру, с сохранением пропорций."""
        return fit(*self.size())

    def to_logical(self, ev):
        """Событие мыши в координатах логического экрана 1280×800."""
        if ev.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            return ev
        x, y, vw, vh = self.view()
        kx, ky = T.SCREEN_W / vw, T.SCREEN_H / vh
        d = dict(ev.dict)
        px, py = ev.pos
        d["pos"] = (int((px - x) * kx), int((py - y) * ky))
        if "rel" in d:
            d["rel"] = (int(d["rel"][0] * kx), int(d["rel"][1] * ky))
        return pygame.event.Event(ev.type, d)

    def apply(self):
        """Настройка «Окно» изменилась: размер или полный экран."""
        mode = SETTINGS.get("window", "auto")
        if (mode == "fullscreen") != self.full:
            self.toggle_fullscreen()
        if not self.full:
            self.window.size = self._wanted()
            self.window.position = pygame.WINDOWPOS_CENTERED
            self._clamp_minimum()

    def toggle_fullscreen(self):
        """Полный экран без рамки (desktop fullscreen) и обратно — с восстановлением размера окна."""
        try:
            if self.full:
                self.window.set_windowed()
            else:
                self.window.set_fullscreen(desktop=True)
            self.full = not self.full
        except pygame.error:
            pass
