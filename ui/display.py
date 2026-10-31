"""Окно и масштабирование: логический холст подстраивается под окно (ui/layout.py) — на ультрашироком
экране он шире 1280, поэтому интерфейс занимает всю ширину, а не стоит колонной с полями. Окно можно
тянуть мышью; F11 или Alt+Enter — полный экран; стартовый размер — в настройках («Окно»). Координаты
мыши из событий переводятся обратно в логический холст, поэтому сцены про масштаб ничего не знают.
"""
import warnings

import pygame

from ui import layout
from ui import theme as T
from ui.settings import SETTINGS

SIZES = {"1280x800": (1280, 800), "1600x1000": (1600, 1000), "1920x1200": (1920, 1200)}
MIN_W, MIN_H = 960, 600          # меньше — интерфейс становится нечитаемым
CURRENT = None


def fit(window_w, window_h, logical_w=None, logical_h=None):
    """Прямоугольник кадра на окне: (x, y, w, h) — по центру, пропорции сохранены."""
    logical_w = T.SCREEN_W if logical_w is None else logical_w
    logical_h = T.SCREEN_H if logical_h is None else logical_h
    w, h = max(1, int(window_w)), max(1, int(window_h))
    k = min(w / logical_w, h / logical_h)
    vw, vh = max(1, int(round(logical_w * k))), max(1, int(round(logical_h * k)))
    if vw >= w - 1:                    # округление не должно оставлять полоску в 1 px
        vw = w
    if vh >= h - 1:
        vh = h
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
        self.on_resize = None            # main ставит сюда presenter.resize + app.relayout
        self._sync()                     # холст = окно по высоте 800
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
        """Стартовый размер окна: пресет из настроек или 85% рабочего стола (пропорции — как у экрана)."""
        mode = SETTINGS.get("window", "auto")
        if mode in SIZES:
            return SIZES[mode]
        dw, dh = self._desktop()
        w, h = int(dw * 0.85), int(dh * 0.85)
        if w < MIN_W or h < MIN_H:               # маленький экран: вписать, но не раздувать
            k = min(w / MIN_W, h / MIN_H)
            w, h = int(w / k), int(h / k)
        return max(MIN_W, w), max(MIN_H, h)

    def size(self):
        try:
            w, h = self.window.size
        except (AttributeError, pygame.error):
            w, h = self.screen.get_size()
        return max(1, int(w)), max(1, int(h))

    def view(self):
        """Где на окне кадр игры: (x, y, ширина, высота) — по центру, с сохранением пропорций."""
        return fit(*self.size(), T.SCREEN_W, T.SCREEN_H)

    def sync(self):
        """Окно изменилось: пересчитать логический холст и сообщить презентеру/сцене."""
        w, h = self.size()
        lw, lh = layout.logical_size(w, h)
        if (lw, lh) == (T.SCREEN_W, T.SCREEN_H):
            return False
        T.SCREEN_W, T.SCREEN_H = lw, lh
        cb = getattr(self, "on_resize", None)
        if cb:
            cb()
        return True

    def _sync(self):
        return self.sync()

    def to_logical(self, ev):
        """Событие мыши в координатах логического холста."""
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
        self._sync()

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
        self._sync()
