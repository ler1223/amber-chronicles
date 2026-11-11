"""Экраны экспедиции без окна: таверна → поход → бои, события, лагерь, торговец, лист героя → выход и продолжение."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from sim.data import GameData  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((1280, 800))
DATA = GameData()


def frame(app, dt=1 / 30):
    app.scene.update(dt)
    app.scene.draw(SCREEN)


def key(app, k):
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode="", mod=0))


def click(app, action):
    """Клик по элементу экрана с этим действием (как мышью)."""
    frame(app)
    r = next(r for r, a, _ in app.scene.hits if a == action)
    app.scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=r.center))
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))


def new_app(tmp_path):
    app = App(DATA, seed=4)
    app.profile.path = str(tmp_path / "profile.json")
    app.switch_mode("expedition")
    app.to_hub()
    return app


def walk(app, steps=60):
    """Проходит узлы: бои выигрываются сразу, в событиях — первый доступный вариант и лучший герой."""
    seen = set()
    for _ in range(steps):
        name = type(app.scene).__name__
        seen.add(name)
        frame(app)
        sc = app.scene
        if name == "MapScene":
            nid = sc.run.available()[0]
            x, y = sc.node_pos[nid]
            sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(x), int(y)), button=1))
        elif name == "BattleScene":
            if sc.phase == "deploy":
                sc.begin_battle()
            sc.combat.win_now()
            for _ in range(4):
                frame(app)
            key(app, pygame.K_RETURN)
        elif name == "EventScene":
            if sc.phase == "choose":
                opts = sc.ev["steps"][sc.step]["options"]
                i = next(i for i, o in enumerate(opts) if sc.run.option_ok(o))
                click(app, ("opt", i))
            elif sc.phase == "pick":
                click(app, ("roller", 0))
            elif sc.phase == "roll":
                key(app, pygame.K_SPACE)                   # бросить кубик
                for _ in range(70):
                    frame(app)
                key(app, pygame.K_SPACE)
            else:
                key(app, pygame.K_SPACE)
        elif name == "RewardScene":
            key(app, pygame.K_1)
            if type(app.scene).__name__ == "RewardScene" and app.scene.gift is not None:
                i = next(i for i, h in enumerate(sc.run.heroes) if app.scene.party_highlight(h))
                key(app, pygame.K_1 + i)
        elif name == "CampScene":
            key(app, pygame.K_1)
        elif name == "PickScene":                          # карты улучшения / колчан лучника — первая
            key(app, pygame.K_RETURN)
        elif name == "ShopScene":
            key(app, pygame.K_ESCAPE)
        elif name == "ActScene":
            key(app, pygame.K_SPACE)
        elif name in ("EndScene", "HallRoom"):
            break
    return seen


def test_tavern_start_walk_quit_and_resume(tmp_path):
    app = new_app(tmp_path)
    assert type(app.scene).__name__ == "HallRoom"
    prof = app.profile
    key(app, pygame.K_2)                     # комната «Сборы»
    assert type(app.scene).__name__ == "MusterRoom"
    for h in prof.roster[:3]:
        click(app, ("recruit", h.uid))
    key(app, pygame.K_SPACE)
    assert type(app.scene).__name__ == "ActScene" and app.exp is not None
    key(app, pygame.K_SPACE)
    seen = walk(app, 14)
    assert {"MapScene", "BattleScene", "RewardScene"} <= seen
    # лист героя: ранг навыка, надеть вещь
    run = app.exp
    if type(app.scene).__name__ != "MapScene":
        walk(app, 6)
    from game.expedition_scenes import HeroScene, MapScene, to_map
    to_map(app)
    key(app, pygame.K_F1)                    # 1–3 на карте — узлы, F1–F4 — листы героев
    assert isinstance(app.scene, HeroScene)
    h = run.heroes[0]
    for o in run.heroes[1:]:                 # выбор у других героев — свой экран (автопереход), здесь не нужен
        o.sp, o.pick_offer = 0, None
    h.sp = 1
    h.pick_offer = None
    click(app, "levelup")
    assert type(app.scene).__name__ == "PickScene"
    before = (dict(h.ranks), dict(h.branches), len(h.perks))
    click(app, ("card", 0))
    assert h.sp == 0 and (dict(h.ranks), dict(h.branches), len(h.perks)) != before
    assert isinstance(app.scene, HeroScene)
    if run.bag:
        it = run.bag[0]
        click(app, ("equip", it["uid"]))
        assert any(i["uid"] == it["uid"] for x in run.heroes for i in x.gear.values())
    key(app, pygame.K_ESCAPE)
    assert isinstance(app.scene, MapScene)
    # выход в таверну и продолжение
    level, path = h.level, list(run.path)
    key(app, pygame.K_ESCAPE)
    assert type(app.scene).__name__ == "HallRoom" and app.profile.run_state
    frame(app)
    again = App(DATA, seed=4)
    again.profile.path = str(tmp_path / "profile.json")
    again.switch_mode("expedition")
    again.to_hub()
    assert again.profile.run_state
    key(again, pygame.K_SPACE)
    assert type(again.scene).__name__ == "MapScene"
    assert again.exp.path == path and again.exp.heroes[0].level == level


def test_event_camp_shop_screens(tmp_path):
    app = new_app(tmp_path)
    prof = app.profile
    from game import expedition_scenes as XS
    XS.start_run(app, [h.uid for h in prof.roster[:2]])
    run = app.exp
    nid = run.available()[0]
    run.enter(nid)
    for eid in ("sunken_chapel", "witch_hut", "smith_cart", "toad_bazaar"):
        run.start_event(eid)
        app.switch(XS.EventScene(app, eid, "start"))
        frame(app)
        opts = run.event(eid)["steps"]["start"]["options"]
        i = next(i for i, o in enumerate(opts) if "check" in o) if any("check" in o for o in opts) else 0
        click(app, ("opt", i))
        if "check" in opts[i]:                 # бросает сам лучший по шансу герой — выбора нет
            assert app.scene.phase == "roll"
            assert app.scene.roller is run.best_roller(opts[i]["check"])
            app.scene._die_click()
            for _ in range(70):
                frame(app)
            app.scene._die_click()
        frame(app)
        assert app.scene.phase == "result" and (app.scene.roll or "check" not in opts[i])
    run.nodes[run.node]["stock"] = run.shop_stock()
    run.gold = 999
    app.switch(XS.ShopScene(app))
    click(app, ("buy", 0))
    assert run.nodes[run.node]["stock"][0] is None and run.bag
    app.switch(XS.CampScene(app))
    run.heroes[0].wounded = True
    click(app, "rest")
    assert not run.heroes[0].wounded and type(app.scene).__name__ == "MapScene"
    from game import tavern_rooms as R
    for sc in (R.BuildRoom(app), XS.HeroScene(app, 0, back=lambda: None, respec=True), XS.ActScene(app)):
        app.switch(sc)
        frame(app)
