"""Прогон целого забега через экраны (бои — ИИ), с отрисовкой каждого кадра."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from game.battle_scene import BattleScene  # noqa: E402
from game.allies_scene import NewAlliesScene  # noqa: E402
from game.hub_scene import HubScene, RosterScene  # noqa: E402
from game.run_scenes import ChoiceScene, MapScene, RunEndScene, rest_scene, reward_scene, shop_scene  # noqa: E402
from game.title_scene import SettingsScene, TitleScene  # noqa: E402
from sim.combat import ENEMY, Combat  # noqa: E402
from game.world_scene import WorldScene  # noqa: E402
from sim.data import GameData  # noqa: E402
from ui import theme as T  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
DATA = GameData()


def key(scene, k):
    scene.handle(pygame.event.Event(pygame.KEYDOWN, key=k))


def click(scene, pos):
    scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=pos))
    scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def expedition_app(seed, region="reeds"):
    """Приложение сразу в вылазке по региону."""
    app = App(DATA, seed)
    app.start_expedition(region)
    return app


def play_run(seed, prefer=None, region=None):
    app = App(DATA, seed, autoplay=True)
    seen = set()
    for _ in range(400):
        s = app.scene
        s.update(1 / 30)
        s.draw(SCREEN)
        seen.add(type(s).__name__)
        if isinstance(s, TitleScene):
            key(s, pygame.K_RETURN)
        elif isinstance(s, NewAlliesScene):          # открылась глава — новые герои, дальше
            key(s, pygame.K_RETURN)
        elif isinstance(s, HubScene):
            key(s, pygame.K_m)
        elif isinstance(s, WorldScene):
            if region:
                s.selected = region
            key(s, pygame.K_RETURN)
        elif isinstance(s, MapScene):
            avail = app.run.available()
            nid = next((n for n in avail if app.run.nodes[n]["type"] == prefer), avail[0])
            seen.add(app.run.nodes[nid]["type"])
            click(s, s.node_pos[nid])
        elif isinstance(s, BattleScene):
            for _ in range(60 * 300):
                s.update(1 / 20)
                if s.combat.result:
                    break
            s.draw(SCREEN)
            key(s, pygame.K_RETURN)
        elif isinstance(s, ChoiceScene):
            seen.add(s.title)
            idx = next((i for i, o in enumerate(s.options) if o.enabled), None)
            if idx is None:
                s.skip[1]()
            else:
                key(s, pygame.K_1 + idx)
        elif isinstance(s, RunEndScene):
            last_run = app.run
            key(s, pygame.K_RETURN)
            assert isinstance(app.scene, (HubScene, NewAlliesScene))
            app.run = last_run
            return app, seen
    raise AssertionError(f"забег не закончился: {seen}")


def test_full_run_through_screens():
    app, seen = play_run(seed=8)
    assert app.run.result in ("victory", "defeat")
    assert {"TitleScene", "NewAlliesScene", "HubScene", "WorldScene", "MapScene", "BattleScene", "ChoiceScene",
            "RunEndScene"} <= seen
    assert app.run.battles_won >= 1
    assert app.profile.expeditions == 1 and app.profile.amber > 0
    assert ("reeds" in app.profile.captured) == (app.run.result == "victory")


def frame(app):
    app.scene.update(1 / 30)
    app.scene.draw(SCREEN)


def test_rest_and_shop_screens():
    app = expedition_app(3)
    run = app.run
    war = run.squad[0]
    war.hp = 10
    app.switch(rest_scene(app))
    frame(app)
    key(app.scene, pygame.K_1)            # отдых
    assert isinstance(app.scene, MapScene) and war.hp > 10

    app.switch(rest_scene(app))
    key(app.scene, pygame.K_2)            # тренировка → кто
    frame(app)
    key(app.scene, pygame.K_1)            # воин получает уровень (статы, без выбора)
    assert isinstance(app.scene, MapScene) and war.level == 2

    run.gold = 500
    run.shop_stock = run.shop_offers()
    app.switch(shop_scene(app))
    frame(app)
    key(app.scene, pygame.K_1)            # купить предмет → кому
    frame(app)
    key(app.scene, pygame.K_2)            # лучнику
    assert run.squad[1].items and run.gold < 500
    assert isinstance(app.scene, ChoiceScene) and app.scene.title == "Торговец"
    frame(app)
    relic = next(i for i, o in enumerate(app.scene.options) if o.header == "Реликвия отряда")
    key(app.scene, pygame.K_1 + relic)
    assert run.relics and isinstance(app.scene, ChoiceScene)
    frame(app)


def test_reward_reroll_button():
    app = expedition_app(4)
    run = app.run
    run.rerolls = 1
    run.node = run.available()[0]
    summary = {"gold": 25, "xp": 60, "level_ups": [], "fallen": []}
    app.switch(reward_scene(app, summary))
    frame(app)
    click(app.scene, app.scene.alt_rect.center)
    assert run.rerolls == 0 and app.scene.alt is None
    frame(app)


def test_map_equip_from_bag():
    app = expedition_app(3)
    s = app.scene
    app.run.inventory.append("power_belt")
    s.draw(SCREEN)
    r, item = s.bag_rects[0]
    click(s, r.center)
    assert s.picked_item == "power_belt"
    s.draw(SCREEN)
    card, slots, m = s.member_rects[0]
    click(s, card.center)
    assert m.items == {"armor": "power_belt"} and not app.run.inventory
    s.draw(SCREEN)
    click(s, s.member_rects[0][1]["armor"].center)
    assert not m.items and app.run.inventory == ["power_belt"]


def test_guard_victory_gives_trophy_and_mastery():
    app = expedition_app(5)
    run = app.run
    run.node = next(n for n, v in run.nodes.items() if not v["next"])
    c = Combat(DATA, run.nodes[run.node]["encounter"], squad=run.combat_squad())
    c.win_now()
    app.battle_done(c, None)
    assert app.scene.title == "Трофей стража"
    frame(app)
    key(app.scene, pygame.K_1)
    assert isinstance(app.scene, RunEndScene) and len(app.profile.arsenal) == 1
    frame(app)
    assert all(app.profile.heroes[c]["xp"] > 0 for c in app.profile.squad)


def test_boss_victory_end_screen():
    app = App(DATA, 9)
    app.profile.captured = ["reeds", "mill", "nest"]
    app.start_expedition("tower")
    run = app.run
    run.result, run.battles_won = "victory", 5
    end = app.profile.finish_run(run)
    assert end["captured"] and end["bonus"] is None and end["biome_done"]
    app.switch(RunEndScene(app, end))
    frame(app)


def test_title_settings_hub_roster_flow(tmp_path, monkeypatch):
    from ui import settings
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    app = App(DATA, 1)
    assert isinstance(app.scene, TitleScene)
    frame(app)
    settings_btn = next(r for r, k, _ in app.scene.buttons if k == "settings")
    click(app.scene, settings_btn.center)
    assert isinstance(app.scene, SettingsScene)
    frame(app)
    r, k, _ = app.scene.rows[0]
    before = settings.SETTINGS["bloom"]
    click(app.scene, r.center)
    assert settings.SETTINGS["bloom"] != before
    settings.SETTINGS["bloom"] = before
    key(app.scene, pygame.K_ESCAPE)
    assert isinstance(app.scene, TitleScene)
    key(app.scene, pygame.K_RETURN)
    assert isinstance(app.scene, NewAlliesScene)            # глава 1 открывает своих героев
    assert {h["cls"] for _, h in app.scene.entries} == {"shaman", "ram"}
    frame(app)
    key(app.scene, pygame.K_RETURN)
    assert isinstance(app.scene, HubScene)
    frame(app)
    key(app.scene, pygame.K_o)
    assert isinstance(app.scene, RosterScene)
    frame(app)
    prof = app.profile
    prof.amber = 100
    assert "ram" in prof.unlocked and prof.amber == 100   # герой главы 1 — уже в лагере, бесплатно
    app.scene.act(("toggle", "binder"))               # герой главы 9 — ещё закрыт
    assert "binder" not in prof.squad and app.scene.toast
    app.scene.act(("toggle", "ram"))                  # отряд полон
    assert "ram" not in prof.squad
    app.scene.act(("toggle", "archer"))
    app.scene.act(("toggle", "ram"))
    assert prof.squad == ["warrior", "mage", "priest", "ram"]
    frame(app)
    app.scene.act(("prep", "ram"))
    frame(app)
    key(app.scene, pygame.K_ESCAPE)                         # из подготовки — обратно в «Отряд»
    assert isinstance(app.scene, RosterScene)
    key(app.scene, pygame.K_ESCAPE)
    assert isinstance(app.scene, HubScene)
    key(app.scene, pygame.K_m)
    assert isinstance(app.scene, WorldScene)
    key(app.scene, pygame.K_RETURN)
    assert [m.cls for m in app.run.squad] == prof.squad
