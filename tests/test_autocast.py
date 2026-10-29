"""Автокаст и новые механики веток навыков."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim import autocast as AC  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.grid import cheb  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim import meta  # noqa: E402
from sim.profile import Profile  # noqa: E402
from sim.run import Run  # noqa: E402

DATA = GameData()


def combat(enc=0, branches=None):
    squad = [{"cls": c, "proto": build_proto(DATA, c, branches=(branches or {}).get(c))}
             for c in DATA.squad["units"]]
    c = Combat(DATA, enc, squad=squad)
    c.ais = []
    return c, c.alive(PLAYER), c.alive(ENEMY)


def steps(c, n=10):
    for _ in range(n):
        c.step()


def skill_events(c, unit):
    return [e for e in c.events if e["t"] == "skill" and e["unit"] is unit]


def test_heal_autocast_waits_for_threshold():
    c, (war, archer, mage, priest), _ = combat()
    for u in (war, archer, mage):
        for st in u.autocast.values():
            st["on"] = False
    war.hp = int(war.max_hp * 0.85)          # Обет жреца — от 75% HP
    steps(c, 20)
    assert not skill_events(c, priest)
    priest.cell, war.cell = (1, 1), (1, 2)
    war.hp = int(war.max_hp * 0.4)
    steps(c, 40)
    ev = skill_events(c, priest)
    assert ev and ev[0]["auto"] and ev[0]["target"] is war


def test_autocast_off_and_manual_priority():
    c, (war, archer, mage, priest), foes = combat()
    for u in (war, archer, mage, priest):
        for st in u.autocast.values():
            st["on"] = False
    archer.autocast["aimed_shot"] = {"on": True, "conds": []}
    foes[0].cell = (5, 1)
    c.order_skill(archer, "volley", foes[0].cell)       # ручной навык в очереди
    steps(c, 3)
    assert archer.cast and archer.cast["skill"] == "volley" and not archer.cast["auto"]
    steps(c, 20)
    first = skill_events(c, archer)
    assert first and first[0]["skill"] == "volley" and not first[0]["auto"]


def test_conditions_and_sanitize():
    sk = DATA.skills["heal"]
    st = AC.sanitize({"on": True, "conds": [{"type": "enemies_in_area", "value": 2},
                                            {"type": "target_hp_below", "value": 30},
                                            {"type": "ap_at_least", "value": 4}]}, sk)
    assert [x["type"] for x in st["conds"]] == ["target_hp_below", "ap_at_least"]
    assert AC.setting_label(st) == "авто: HP цели < 30% и AP ≥ 4"
    assert AC.setting_label({"on": False, "conds": []}) == "авто выкл"


def test_ap_condition_blocks_cast():
    c, (war, *_), foes = combat()
    war.autocast["power_strike"] = {"on": True, "conds": [{"type": "ap_at_least", "value": 6}]}
    war.autocast["taunt"]["on"] = False
    foes[0].cell = (3, 2)
    war.ap = 5
    steps(c, 5)
    assert not skill_events(c, war)
    war.ap = 6
    steps(c, 10)
    assert skill_events(c, war)


def test_autocast_survives_between_battles():
    run = Run(DATA, 2)
    war = run.squad[0]
    run.autocast_for(war)["power_strike"]["on"] = False
    run.enter(run.available()[0])
    c = Combat(DATA, 0, ai_teams=(PLAYER, ENEMY), squad=run.combat_squad())
    assert c.alive(PLAYER)[0].autocast["power_strike"]["on"] is False
    c.alive(PLAYER)[0].autocast["taunt"]["on"] = False
    while not c.result:
        c.step()
    run.finish_battle(c)
    assert war.autocast["taunt"]["on"] is False and war.autocast["power_strike"]["on"] is False


def test_branch_at_prep_resets_autocast():
    prof = Profile(DATA)
    mage = prof.heroes["mage"]
    mage["xp"] = 40                                   # мастерство 2 → 3 очка
    mage["autocast"]["fireball"] = {"on": False, "conds": []}
    assert meta.click_branch(DATA, mage, "fireball", "B", 1)
    assert "fireball" not in mage["autocast"]
    run = prof.start_run("reeds", 1)
    m = run.squad[2]
    st = run.autocast_for(m)["fireball"]
    assert st["on"] and run.proto(m)["skill_defs"]["fireball"]["target"] == "enemy"


def test_chain_line_thorns_transfer_execute():
    c, (war, archer, mage, priest), foes = combat()
    a, b, d = foes[0], foes[1], foes[2]
    a.cell, b.cell, d.cell = (5, 2), (6, 2), (7, 2)
    # цепь
    hp_b = b.hp
    c.apply_effects(mage, [{"type": "chain", "amount": 20, "jumps": 2, "range": 2, "kind": "spell"}], a.cell, a)
    assert b.hp < hp_b and d.hp < d.max_hp
    # линия
    archer.cell = (3, 2)
    hp = [f.hp for f in (a, b, d)]
    c.apply_effects(archer, [{"type": "line", "amount": 30, "length": 6, "kind": "spell"}], a.cell, a)
    assert all(f.hp < h for f, h in zip((a, b, d), hp))
    # шипы
    c.add_buff(war, "thorns", 0.5, 5)
    hp_a = a.hp
    c.damage(war, 30, a, None, "melee")
    assert a.hp < hp_a
    # перенос тегов вызывает реакцию на враге
    c.apply_status(priest, "water")
    c.apply_status(a, "fire")
    priest.cell = (4, 3)
    c.apply_effects(priest, [{"type": "transfer_statuses", "range": 4}], priest.cell, priest)
    assert not priest.statuses
    assert any(e["t"] == "reaction" and e["unit"] is a for e in c.events)
    # казнь
    b.hp = 10
    c.apply_effects(war, [{"type": "damage", "amount": 6, "kind": "spell", "execute": {"below": 0.35, "mult": 2}}],
                    b.cell, b)
    assert any(e["t"] == "execute" for e in c.events)


def test_battle_ui_autocast_toggle_and_editor():
    from game.battle_scene import BattleScene
    from ui import theme as T
    pygame.init()
    screen = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
    s = BattleScene(DATA, 0)
    s.update(1 / 60)
    s.draw(screen)
    war = s.selected
    st = war.autocast["power_strike"]
    was = st["on"]
    card, _ = s.view.skill_rects[0]
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=card.center, button=3))
    assert st["on"] != was
    strip, _ = s.view.auto_rects[0]
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=strip.center, button=1))
    assert s.editor
    s.draw(screen)
    ed = s.editor["editor"]
    type_next = next(r for r, a in ed.hits if a == ("type", (0, 1)))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=type_next.center, button=1))
    assert st["conds"] and st["conds"][0]["type"] == AC.allowed_conds(war.skill_defs["power_strike"])[0]
    s.draw(screen)
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
    assert s.editor is None


def test_retarget_nearest_after_kill():
    c, (war, archer, mage, priest), foes = combat()
    for u in (war, archer, mage, priest):
        for st in u.autocast.values():
            st["on"] = False
    a, near, far = foes[0], foes[1], foes[2]
    war.cell, a.cell, near.cell, far.cell = (2, 2), (3, 2), (5, 2), (8, 4)
    c.order_attack(war, a)
    a.hp = 1
    steps(c, 30)
    assert not a.alive
    assert war.order and war.order["type"] == "attack" and war.order["target"] is near
    # без приказа: добил цель в досягаемости — идёт к следующей
    near.hp = 1
    war.order, war.last_target = None, near
    steps(c, 30)
    assert war.order and war.order["target"] is not near and war.order["target"].alive


def test_fireball_autocast_avoids_allies_cells():
    c, (war, archer, mage, priest), foes = combat()
    for u in (war, archer, priest):
        for st in u.autocast.values():
            st["on"] = False
    mage.autocast["fireball"] = {"on": True, "conds": []}
    war.cell, mage.cell = (5, 3), (2, 3)
    foes[0].cell, foes[1].cell = (6, 2), (6, 4)
    t = c.autocaster._pick_target(mage, mage.skill_defs["fireball"], [])
    assert t is not None and cheb(t, war.cell) > AC.ally_danger_radius(mage.skill_defs["fireball"], DATA.tags)
