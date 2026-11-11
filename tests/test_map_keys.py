"""Карта похода: узлы — клавишами 1–3; выбор улучшений с карточки героя — дальше к следующему герою."""
import pygame

from tests.test_expedition_ui import click, frame, key, new_app


def start(tmp_path):
    app = new_app(tmp_path)
    key(app, pygame.K_2)                       # «Сборы»
    for h in app.profile.roster[:3]:
        click(app, ("recruit", h.uid))
    key(app, pygame.K_SPACE)
    key(app, pygame.K_SPACE)
    return app


def test_digit_enters_open_node(tmp_path):
    from game.expedition_scenes import MapScene, to_map
    app = start(tmp_path)
    to_map(app)
    assert isinstance(app.scene, MapScene)
    frame(app)
    opts = app.scene.open_nodes()
    assert opts
    key(app, pygame.K_1 + len(opts))          # номер без узла — ничего
    assert isinstance(app.scene, MapScene)
    key(app, pygame.K_1)
    assert app.exp.node == opts[0]


def test_pick_goes_to_next_hero(tmp_path):
    from game.expedition_scenes import PickScene, to_map
    app = start(tmp_path)
    to_map(app)
    hs = app.exp.heroes
    assert len(hs) >= 2
    for h in hs:
        h.sp, h.pick_offer = 0, None
    hs[0].sp = hs[1].sp = 1
    back = app.scene
    app.switch(PickScene(app, then=lambda: app.switch(back), only=hs[0]))
    frame(app)
    key(app, pygame.K_RETURN)
    assert isinstance(app.scene, PickScene) and app.scene.hero is hs[1]
    frame(app)
    key(app, pygame.K_RETURN)
    assert app.scene is back
