"""Экран: вписывание кадра 1280×800 в окно, перевод мыши в логические координаты, стартовый размер окна,
поля вокруг кадра без OpenGL и настройка «Окно»."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from ui import display  # noqa: E402
from ui import settings  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.present import Presenter  # noqa: E402


class _Win:
    """Заглушка pygame.Window: нужен только размер."""

    def __init__(self, size):
        self.size = size


def test_fit_keeps_aspect_and_centers():
    assert display.fit(1280, 800) == (0, 0, 1280, 800)
    # 16:9 шире кадра — поля слева и справа
    assert display.fit(1920, 1080) == (96, 0, 1728, 1080)
    # окно меньше кадра — кадр уменьшается целиком
    assert display.fit(1000, 700) == (0, 37, 1000, 625)
    # сверхширокий экран
    assert display.fit(3440, 1440) == (568, 0, 2304, 1440)
    # нулевой размер не ломает масштаб
    assert display.fit(0, 0)[2] >= 1 and display.fit(0, 0)[3] >= 1


def test_fit_fills_window_when_aspect_matches():
    # адаптивный холст 1911×800 и окно 2924×1224 (2.3889): округление не оставляет полоску в 1 px
    assert display.fit(2924, 1224, 1911, 800) == (0, 0, 2924, 1224)
    assert display.fit(3440, 1440, 1911, 800) == (0, 0, 3440, 1440)
    assert display.fit(1600, 900, 1422, 800) == (0, 0, 1600, 900)


def test_mouse_maps_from_window_to_frame():
    d = object.__new__(display.Display)
    d.window = _Win((1920, 1080))
    ev = pygame.event.Event(pygame.MOUSEMOTION,
                            {"pos": (96 + 864, 540), "rel": (10, 0), "buttons": (0, 0, 0)})
    out = d.to_logical(ev)
    assert out.pos == (640, 400)            # центр кадра
    assert out.rel == (7, 0)                # скорость мыши тоже в логических пикселях
    # клик в поле слева попадает за пределы кадра, а не в интерфейс
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (10, 540), "button": 1})
    assert d.to_logical(ev).pos[0] < 0


def test_keyboard_events_pass_through():
    d = object.__new__(display.Display)
    ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_F11})
    assert d.to_logical(ev) is ev


def test_wanted_size_uses_preset(monkeypatch):
    d = object.__new__(display.Display)
    monkeypatch.setitem(display.SETTINGS, "window", "1600x1000")
    assert d._wanted() == (1600, 1000)


def test_wanted_size_fits_small_desktop(monkeypatch):
    d = object.__new__(display.Display)
    monkeypatch.setitem(display.SETTINGS, "window", "auto")
    monkeypatch.setattr(pygame.display, "get_desktop_sizes", lambda: [(1366, 768)])
    w, h = d._wanted()
    assert w <= 1366 and h <= 768
    assert (w, h) == (int(1366 * 0.85), int(768 * 0.85))   # 85% рабочего стола, пропорции экрана


def test_wanted_size_fills_most_of_huge_desktop(monkeypatch):
    d = object.__new__(display.Display)
    monkeypatch.setitem(display.SETTINGS, "window", "auto")
    monkeypatch.setattr(pygame.display, "get_desktop_sizes", lambda: [(3840, 2160)])
    assert d._wanted() == (int(3840 * 0.85), int(2160 * 0.85))


def test_logical_size_follows_window_aspect():
    assert display.layout.logical_size(1280, 800) == (1280, 800)       # 16:10 — базовый холст
    assert display.layout.logical_size(1920, 1080) == (1422, 800)      # 16:9 — шире
    assert display.layout.logical_size(3440, 1440) == (1911, 800)      # 21:9 — ультраширокий
    assert display.layout.logical_size(1024, 768) == (1280, 800)       # уже 16:10 — поля
    assert display.layout.logical_size(5120, 1440) == (2844, 800)      # 32:9
    assert display.layout.logical_size(10000, 1000) == (3200, 800)     # дальше — предел


def test_content_ox_centers_design_column():
    assert display.layout.content_ox(1280) == 0
    assert display.layout.content_ox(1911) == 315
    assert display.layout.content_ox(960) == 0


def test_battle_rects_pin_panel_to_right():
    assert display.layout.battle_rects(1280) == (24, 924)
    grid_x, right_x = display.layout.battle_rects(1911)
    assert right_x == 1911 - 356
    assert grid_x == (right_x - 880) // 2


def test_sync_recomputes_canvas_and_notifies():
    d = object.__new__(display.Display)
    d.window = _Win((3440, 1440))
    calls = []
    d.on_resize = lambda: calls.append(1)
    assert d.sync()
    assert (T.SCREEN_W, T.SCREEN_H) == (1911, 800)
    assert calls == [1]
    assert not d.sync()                     # тот же размер — без лишней перекладки
    assert calls == [1]


def test_stage_scene_is_composited_centered():
    pygame.init()
    T.SCREEN_W, T.SCREEN_H = 1911, 800
    screen = pygame.display.set_mode((1911, 800))
    d = object.__new__(display.Display)
    d.window = _Win((1911, 800))
    old, display.CURRENT = display.CURRENT, d

    class StageScene:
        stage = True

        def draw(self, surf):
            assert (T.SCREEN_W, T.SCREEN_H) == (1280, 800)   # сцена рисуется в дизайн-колонке
            surf.fill((200, 10, 10))

    try:
        pres = Presenter(screen, use_gl=False, window=True)
        pres.frame(StageScene())
        ox = (1911 - 1280) // 2
        left = screen.get_at((10, 10))[:3]
        right = screen.get_at((ox + 1280 + 5, 10))[:3]
        assert left != (200, 10, 10) and max(left) < 80      # поля — размытая копия сцены
        assert right != (200, 10, 10) and max(right) < 80
        assert left != T.BG and right != T.BG
        assert screen.get_at((ox + 10, 10))[:3] == (200, 10, 10)
    finally:
        display.CURRENT = old
        pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))


def test_settings_have_window_mode():
    opts = {key: values for key, _, values, _ in settings.OPTIONS}
    assert "fullscreen" in opts["window"]
    assert settings.DEFAULTS["window"] in opts["window"]


class _WinApply:
    """Заглушка pygame.Window для apply(): помнит размер и режим."""

    def __init__(self, size):
        self.size = size
        self.position = None
        self.minimum_size = None
        self.fullscreen = False

    def set_fullscreen(self, desktop=False):
        self.fullscreen = True
        self.size = (1920, 1080)

    def set_windowed(self):
        self.fullscreen = False
        self.size = (1280, 800)


def test_apply_switches_fullscreen_and_back(monkeypatch):
    d = object.__new__(display.Display)
    d.window = _WinApply((1280, 800))
    d.screen = None
    d.full = False

    monkeypatch.setitem(display.SETTINGS, "window", "fullscreen")
    d.apply()
    assert d.full and d.window.fullscreen

    monkeypatch.setitem(display.SETTINGS, "window", "1600x1000")
    d.apply()
    assert not d.full and not d.window.fullscreen
    assert d.window.size == (1600, 1000)


def test_cpu_presenter_letterboxes_and_scales():
    pygame.init()
    screen = pygame.display.set_mode((1920, 1080))
    d = object.__new__(display.Display)
    d.window = _Win((1920, 1080))
    old, display.CURRENT = display.CURRENT, d

    class Scene:
        def draw(self, surf):
            surf.fill((10, 20, 30))

    try:
        pres = Presenter(screen, use_gl=False, window=True)
        pres.frame(Scene())
        assert pres.canvas.get_size() == (T.SCREEN_W, T.SCREEN_H)
        bar = screen.get_at((10, 10))[:3]
        assert bar != (10, 20, 30) and max(bar) < 20        # поле — тёмный оттенок края кадра
        assert screen.get_at((960, 540))[:3] == (10, 20, 30)   # кадр по центру
    finally:
        display.CURRENT = old
        pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
