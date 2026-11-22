"""Некромант: армия скелетов, трупы, Души и Алтарь."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()
SKILLS = ["corpse_blast", "summon_warrior", "blood_bones", "summon_archer", "devour",
          "summon_mage", "summon_guard", "summon_bomber", "summon_assassin", "summon_captain",
          "last_call", "bone_colossus", "death_knight"]


def battle(upgrades=None):
    p = build_proto(DATA, "necro", skills=SKILLS)
    if upgrades:
        p["necro_upgrades"] = list(upgrades)
    c = Combat(DATA, 1, squad=[{"cls": "necro", "proto": p}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    return c, c.heroes()[0]


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def run(c, sec=0.3):
    for _ in range(int(sec / c.dt)):
        c.step()


def corpses(c, cells):
    c.corpses = [{"cell": tuple(p), "left": 10, "name": "труп"} for p in cells]


def test_necro_pool_is_seven_summons_three_utility_three_ults():
    pool = DATA.story_progression["classes"]["necro"]["skills"]
    regular = [e for e in pool if not e.get("ult")]
    ults = [e for e in pool if e.get("ult")]
    assert len(regular) == 10 and len(ults) == 3
    assert {e["id"] for e in ults} == {"last_call", "bone_colossus", "death_knight"}
    assert {e["id"] for e in regular} & {"summon_warrior", "summon_archer", "summon_mage",
                                         "summon_guard", "summon_bomber", "summon_assassin",
                                         "summon_captain"} == {
        "summon_warrior", "summon_archer", "summon_mage", "summon_guard",
        "summon_bomber", "summon_assassin", "summon_captain"}


def test_summon_spends_corpse_and_creates_a_skeleton():
    c, h = battle()
    put(h, (1, 2))
    corpses(c, [(4, 2)])
    c._resolve_skill(h, "summon_warrior", (4, 2))
    run(c)
    assert not c.corpses
    assert any(u.alive and u.proto_id == "skeleton_warrior" for u in c.units)
    assert c.necro_souls >= 1


def test_army_cap_is_six_and_captain_is_unique():
    c, h = battle()
    put(h, (1, 2))
    corpses(c, [(4, 2), (4, 3), (5, 2), (5, 3), (6, 2), (6, 3), (7, 2), (7, 3)])
    for _ in range(8):
        c._resolve_skill(h, "summon_warrior", (4, 2))
    assert sum(1 for u in c.units if u.alive and u.proto_id == "skeleton_warrior") <= 6
    corpses(c, [(4, 2), (4, 3)])
    c._resolve_skill(h, "summon_captain", (4, 2))
    c._resolve_skill(h, "summon_captain", (4, 3))
    assert sum(1 for u in c.units if u.alive and u.proto_id == "skeleton_captain") == 1


def test_sacrifice_heals_and_buffs_skeletons():
    c, h = battle()
    put(h, (1, 2))
    corpses(c, [(4, 2)])
    c._resolve_skill(h, "summon_warrior", (4, 2))
    run(c)
    sk = next(u for u in c.units if u.proto_id == "skeleton_warrior")
    h.hp = 20
    corpses(c, [(2, 2)])
    c._resolve_skill(h, "devour", (2, 2))
    run(c)
    assert h.hp > 20
    assert sk.buff("atk_mult", 1.0) > 1.0


def test_start_guard_ritual_and_upgrade_are_applied():
    c, h = battle(["r_guard", "w_shield"])
    assert any(u.alive and u.proto_id == "skeleton_guard" for u in c.units)
    corpses(c, [(4, 2)])
    c._resolve_skill(h, "summon_warrior", (4, 2))
    run(c)
    sk = next(u for u in c.units if u.proto_id == "skeleton_warrior")
    assert sk.shield > 0


def test_souls_are_gained_for_kills_and_corpse_use():
    c, h = battle()
    f = next(u for u in c.units if u.team == ENEMY)
    c.damage(f, 10 ** 6, h, None, "spell")
    assert c.necro_souls >= 2
    corpses(c, [(4, 2)])
    c._resolve_skill(h, "summon_warrior", (4, 2))
    assert c.necro_souls >= 3


def test_first_double_ritual_summons_two_skeletons():
    c, h = battle(["r_double"])
    put(h, (1, 2))
    corpses(c, [(4, 2)])
    c._resolve_skill(h, "summon_warrior", (4, 2))
    assert sum(1 for u in c.units if u.alive and u.proto_id == "skeleton_warrior") == 2


def test_altar_rolls_offers_spends_souls_and_persists():
    hero = X.Hero({"uid": "n1", "name": "Некромант", "cls": "necro",
                   "skills": ["summon_warrior", "summon_archer", "corpse_blast"], "level": 6})
    run_ = X.Expedition(X.expedition_data(DATA), [hero], seed=3)
    run_.souls = 20
    offers = run_.roll_altar()
    assert len(offers) == 2
    cost = run_.altar_cost()
    uid = offers[0]
    assert run_.take_altar(uid)
    assert run_.souls == 20 - cost and uid in run_.necro_upgrades
    assert run_.altar_cost() > cost
    assert uid in run_.proto(run_.heroes[0])["necro_upgrades"]
    d = run_.to_dict()
    again = X.Expedition.from_dict(X.expedition_data(DATA), d)
    assert again.souls == run_.souls and again.necro_upgrades == run_.necro_upgrades


def test_map_altar_button_is_above_torch_and_material_hud():
    """Кнопка Алтаря душ не должна прятаться под полосой Факелов/Жара и материалами."""
    import pygame
    from ui import theme as T
    from game.expedition_scenes import MapScene

    pygame.init()
    hero = X.Hero({"uid": "n1", "name": "Некромант", "cls": "necro",
                   "skills": ["summon_warrior", "corpse_blast", "blood_bones"], "level": 6})
    run_ = X.Expedition(X.expedition_data(DATA), [hero], seed=3, chapter="crypt")

    class App:
        exp = run_
        run = None
        profile = None

        def switch(self, scene):
            self.scene = scene

    rect = MapScene(App()).altar_rect()
    assert rect.top == 14 and rect.bottom == 46
    assert not rect.colliderect(pygame.Rect(T.SCREEN_W - 420, 84, 300, 14))      # Факелы/Жар
    assert not rect.colliderect(pygame.Rect(T.SCREEN_W - 26 - 2 * 78, 52, 2 * 78, 24))  # материалы
    gold_w = T.font(22, True).size(f"Золото: {run_.gold}")[0]
    assert rect.right <= T.SCREEN_W - 26 - gold_w - 14                          # не наезжает на золото


def test_hero_menu_opens_altar_only_for_necromancer():
    """В меню Некроманта есть вход в Алтарь душ; у других классов его нет."""
    from game import expedition_scenes as E

    class Profile:
        def save(self, run):
            pass

    class App:
        profile = Profile()
        neural = None

        def __init__(self, run_):
            self.exp = run_
            self.scene = None

        def switch(self, scene):
            self.scene = scene

    necro = X.Hero({"uid": "n1", "name": "Некромант", "cls": "necro",
                    "skills": ["summon_warrior", "corpse_blast", "blood_bones"], "level": 6})
    run_ = X.Expedition(X.expedition_data(DATA), [necro], seed=3)
    app = App(run_)
    E.HeroScene(app, 0, back=lambda: None).act("altar")
    assert isinstance(app.scene, E.AltarScene)

    warrior = X.Hero({"uid": "w1", "name": "Воин", "cls": "warrior", "skills": ["power_strike"], "level": 1})
    other = X.Expedition(X.expedition_data(DATA), [warrior], seed=4)
    app2 = App(other)
    mark = object()
    app2.scene = mark
    E.HeroScene(app2, 0, back=lambda: None).act("altar")
    assert app2.scene is mark


def test_altar_escape_saves_purchase():
    """Закрытие Алтаря по Esc не теряет купленное улучшение."""
    import pygame
    from game import expedition_scenes as E

    class Profile:
        def __init__(self):
            self.saved = 0

        def save(self, run):
            self.saved += 1

    class App:
        neural = None

        def __init__(self, run_, profile):
            self.exp, self.profile = run_, profile

        def switch(self, scene):
            self.scene = scene

    hero = X.Hero({"uid": "n1", "name": "Некромант", "cls": "necro",
                   "skills": ["summon_warrior", "corpse_blast", "blood_bones"], "level": 6})
    run_ = X.Expedition(X.expedition_data(DATA), [hero], seed=5)
    run_.souls = 20
    prof = Profile()
    app = App(run_, prof)
    scene = E.AltarScene(app, back=lambda: None)
    uid = scene.offers[0]
    scene.act(("take", uid))
    assert uid in run_.necro_upgrades
    saved = prof.saved
    scene.key(pygame.K_ESCAPE)
    assert prof.saved == saved + 1
