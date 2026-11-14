"""Колесо и средняя/боковые кнопки мыши не должны срабатывать как клики интерфейса."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.expedition_scenes import XScene  # noqa: E402
import main  # noqa: E402


class Probe(XScene):
    stage = False

    def __init__(self):
        super().__init__(None)
        self.hits = [(pygame.Rect(0, 0, 100, 100), "click", None)]
        self.acted = []

    def act(self, action, button=1):
        self.acted.append((action, button))


def down(button):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 50), button=button)


def test_scene_ignores_wheel_and_middle_clicks():
    p = Probe()
    for button in (2, 4, 5, 6, 7):
        p.acted.clear()
        p.handle(down(button))
        assert not p.acted, f"button {button} must not click"
    p.acted.clear()
    p.handle(down(1))
    assert p.acted == [("click", 1)]


def test_main_dispatch_drops_wheel_and_middle_events():
    class Target:
        stage = False

        def __init__(self):
            self.events = []

        def handle(self, ev):
            self.events.append(ev)

    t = Target()
    for button in (2, 4, 5, 6, 7):
        main.dispatch(t, down(button))
    assert not t.events
    main.dispatch(t, down(1))
    assert len(t.events) == 1
