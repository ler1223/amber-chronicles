"""Первый тур, кодекс и одноразовые подсказки таверны."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from game import tavern_rooms as R  # noqa: E402
from game import onboarding as O  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((1280, 800))
DATA = GameData()
ED = X.expedition_data(DATA)


def profile(tmp_path):
    return X.ExpeditionProfile(ED, str(tmp_path / "profile.json"))


def main_app(tmp_path):
    app = App(DATA, profile=profile(tmp_path), start="title", launcher="main")
    app.to_hub()
    return app


def draw(app):
    app.scene.update(1 / 30)
    app.scene.draw(SCREEN)


def test_tutorial_flag_is_saved(tmp_path):
    p = profile(tmp_path)
    assert not p.tutorial_done()
    p.finish_tutorial()
    again = X.ExpeditionProfile(ED, p.path)
    assert again.tutorial_done()


def test_tour_walks_rooms_and_skip_finishes(tmp_path):
    app = main_app(tmp_path)
    assert isinstance(app.scene, R.HallRoom)
    assert isinstance(app.scene.overlay, O.TourOverlay)
    app.scene.act("tour_next")
    assert isinstance(app.scene, R.MusterRoom)
    assert isinstance(app.scene.overlay, O.TourOverlay)
    app.scene.act("tour_skip")
    assert app.tour is None and app.profile.tutorial_done()
    assert app.scene.overlay is None


def test_codex_tabs_and_close(tmp_path):
    app = main_app(tmp_path)
    app.scene.act("tour_skip")
    app.scene.act("codex")
    assert isinstance(app.scene.overlay, O.CodexOverlay)
    draw(app)
    for tid, _ in O.CodexOverlay.TABS:
        app.scene.overlay.act(("codex_tab", tid))
        draw(app)
    app.scene.key(pygame.K_ESCAPE)
    assert app.scene.overlay is None


def test_room_hint_is_shown_once(tmp_path):
    app = main_app(tmp_path)
    app.scene.act("tour_skip")
    R.go(app, "muster")
    assert app.scene.hint
    app.scene.act("hint_close")
    assert app.scene.hint is None
    R.go(app, "hall")
    R.go(app, "muster")
    assert app.scene.hint is None


def test_legacy_launcher_has_no_tour_or_hint(tmp_path):
    app = App(DATA, profile=profile(tmp_path), start="title")
    app.to_hub()
    assert app.scene.overlay is None
    assert app.scene.hint is None
