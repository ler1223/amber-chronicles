"""Сложности похода (sim/mutators.py): подкрепление, механики врагов, фазы боссов, открытие сложностей, мозг ИИ."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_expedition import ED, X  # noqa: E402
from sim import brain as B  # noqa: E402
from sim import mutators as MU  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402


def run_on(tier):
    h = [X.Hero({"uid": f"u{i}", "name": "Т", "cls": c, "skills": []}) for i, c in enumerate(("warrior", "priest", "archer"))]
    return X.Expedition(ED, h, seed=3, tier=tier)


def battle(run, kind="battle"):
    nid = next(n for n, v in run.nodes.items() if v["type"] == kind)
    run.node = nid
    return Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
                  difficulty=run.difficulty)


def test_wanderer_is_unchanged_and_harder_tiers_add_variety_and_mutators():
    r0, r2 = run_on(0), run_on(2)
    r0.act = r2.act = 2                                        # к третьему акту — в полную силу
    c0, c2 = battle(r0), battle(r2)
    assert "tier" not in r0.enemy_scale()
    n0, n2 = len(c0.alive(ENEMY)), len(c2.alive(ENEMY))
    assert n2 >= n0 + 1
    assert any(u.mutator for u in c2.alive(ENEMY)) and not any(u.mutator for u in c0.alive(ENEMY))
    assert r2.enemy_scale()["hp"] > r0.enemy_scale()["hp"]


def test_mutators_work():
    run = run_on(1)
    c = battle(run)
    c.ais = []
    hero = c.heroes(PLAYER)[0]
    foe = [u for u in c.alive(ENEMY) if not u.boss][0]
    MU.mutate(c, foe, "suppressor")
    MU.on_hit(c, foe, hero, 10, "melee")
    assert "silence" in hero.buffs
    MU.mutate(c, foe, "decay")
    MU.on_hit(c, foe, hero, 10, "melee")
    assert hero.buff("heal_taken", 1.0) == 0.5
    n = len(c.alive(ENEMY))
    MU.mutate(c, foe, "splitter")
    c.damage(foe, 10 ** 6, hero, None, "reaction")
    assert len(c.alive(ENEMY)) >= n + 1                       # погиб — двое меньших


def test_boss_phases_call_help_and_enrage():
    run = run_on(next(i for i, t in enumerate(ED.expedition["config"]["tiers"]) if t["boss_phases"]))
    c = battle(run, "boss")
    boss = next(u for u in c.alive(ENEMY) if u.phases_left)
    assert boss.phases_left == [0.7, 0.35]
    n = len(c.alive(ENEMY))
    boss.hp = int(boss.max_hp * 0.3)
    MU.tick(c, 0.05)
    MU.tick(c, 0.05)
    assert not boss.phases_left and "atk_speed" in boss.buffs and len(c.alive(ENEMY)) > n


def test_victory_opens_next_tier_and_glory_scales():
    prof = X.ExpeditionProfile(ED)
    assert prof.tier_open == 0
    run = prof.start([h.uid for h in prof.roster[:2]], seed=1, tier=2)
    assert run.tier == 0                                       # закрытая сложность не выбирается
    run.result = "victory"
    prof.finish(run)
    assert prof.tier_open == 1
    r = run_on(2)
    r.result, r.counts = "victory", {"battle": 3}
    k = ED.expedition["config"]["tiers"][2]["glory"]
    assert k > 1 and r.glory() == round((3 * ED.expedition["config"]["glory"]["battle"]
                                         + ED.expedition["config"]["glory"]["victory"]) * k)


def test_custom_brain_is_used():
    class Rusher(B.Brain):
        def decide(self, obs):
            return {"type": "attack", "target": min(obs["foes"], key=lambda f: f["hp"])["id"]} if obs["foes"] else None
    run = run_on(0)
    c = battle(run)
    ai = next(a for a in c.ais if a.team == ENEMY)
    ai.brain = Rusher()
    for _ in range(10):
        c.step()
    weakest = min(c.alive(PLAYER), key=lambda u: u.hp)
    assert any(u.order and u.order.get("target") in c.alive(PLAYER) for u in c.alive(ENEMY))
    assert B.observe(c, c.alive(ENEMY)[0])["foes"] and weakest
