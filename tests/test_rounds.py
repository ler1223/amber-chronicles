"""Бой раундами (прототип, sim/rounds.py, docs/vision.md §11): пауза перед раундом, намерения врагов по ролям,
навык за раунд и откаты в раундах, автоатака слабее, заряды на день, прогноз навыка, экран боя."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim import rounds as R  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from test_expedition import ED, X  # noqa: E402

pygame.init()


def run_and_node(tmp_path, seed=3, picks=(0, 2)):
    prof = X.ExpeditionProfile(ED, str(tmp_path / "exp.json"))
    run = prof.start([h.uid for h in prof.roster[picks[0]:picks[1]]], seed=seed)
    run.rounds_mode = True
    nid = run.available()[0]
    run.enter(nid)
    return run, nid


def combat(run, nid, teams=(ENEMY,)):
    return Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
                  ai_teams=teams, rounds=True)


def test_round_start_plans_enemy_intents_by_role(tmp_path):
    run, nid = run_and_node(tmp_path)
    c = combat(run, nid)
    c.step()
    assert c.rounds.n == 1 and c.rounds.awaiting
    foes = [u for u in c.units if u.team == ENEMY and not u.obj]
    assert all(u.round_role in ED.rounds["roles"] for u in foes)
    assert all(ED.rounds["roles"][u.round_role]["skill"] in u.skills for u in foes)
    assert all(u.intent is not None and u.intent["attack"] is not None for u in foes)   # кого бьют — видно
    for _ in range(int(ED.rounds["len"] / c.dt) + 2):
        c.step()
    assert c.rounds.n == 2                     # 3 секунды — новый раунд


def test_one_skill_per_round_and_cooldown_in_rounds(tmp_path):
    run, nid = run_and_node(tmp_path)
    c = combat(run, nid)
    c.step()
    h = c.heroes(PLAYER)[0]
    sid = next(s for s in h.skills if h.skill_defs[s]["ap"] > 0)
    sk = h.skill_defs[sid]
    tgt = h if sk["target"] == "self" else (c.alive(ENEMY)[0] if sk["target"] == "enemy" else
                                           (h if sk["target"] == "ally" else c.alive(ENEMY)[0].cell))
    assert c.check_skill(h, sid, tgt)[0]
    c._start_cast(h, sid, tgt)
    assert h.round_lock and not h.skill_ready(sid, sk)
    other = next((s for s in h.skills if s != sid and h.skill_defs[s]["ap"] > 0), None)
    if other:
        assert c.check_skill(h, other, h)[1] == "Навык раунда уже применён"
    k = c.rounds.cd_rounds(sk)
    n0 = c.rounds.n
    while c.rounds.n < n0 + 1:
        c.step()
    assert not h.round_lock                    # новый раунд — навык раунда снова есть
    assert (c.rounds.rounds_left(h, sid) > 0) == (k > 0)
    while c.rounds.n < n0 + k + 1:
        c.step()
    assert sid not in h.cooldowns              # откат — ровно k раундов


def test_stun_breaks_enemy_intent(tmp_path):
    run, nid = run_and_node(tmp_path)
    c = combat(run, nid)
    c.step()
    foe = next((u for u in c.units if u.team == ENEMY and u.intent and u.intent.get("skill")), None)
    if foe is None:                            # без навыка в первом раунде — задумываем вручную
        foe = c.alive(ENEMY)[0]
        sid = foe.skills[0]
        foe.intent.update(skill=sid, target=c.heroes(PLAYER)[0], start=1.0, fire=2.0, zone=[], name="x", done=False)
    c.apply_stun(foe, 1.5)
    assert foe.intent["done"] and foe.intent.get("broken")
    assert any(e.get("t") == "intent_broken" for e in c.events)


def test_heroes_without_orders_only_auto_attack_weaker(tmp_path):
    run, nid = run_and_node(tmp_path)
    for h in run.heroes:                       # даже с включённым автокастом — в раундах навыки только приказом
        h.autocast = {}
    run.autocast_mode = "on"
    c = combat(run, nid)
    c.assign_initial_targets(PLAYER)
    casts = 0
    while c.time < 9 and not c.result:
        c.step()
        casts += sum(1 for e in c.events if e.get("t") == "skill" and e["unit"].team == PLAYER)
        c.events.clear()
    assert casts == 0
    plain = Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
    h, h2 = c.heroes(PLAYER)[0], plain.heroes(PLAYER)[0]
    foe, foe2 = c.alive(ENEMY)[0], plain.alive(ENEMY)[0]
    for x in (foe, foe2):
        x.armor, x.shield = 0, 0
    hp, hp2 = foe.hp, foe2.hp
    c._land_basic(h, foe, h.atk_damage * ED.rounds["aa_mult"], None, "melee")
    plain._land_basic(h2, foe2, h2.atk_damage, None, "melee")
    assert hp - foe.hp < hp2 - foe2.hp


def test_three_skills_plus_ult_and_day_charges(tmp_path):
    run, nid = run_and_node(tmp_path)
    h = run.heroes[0]
    run.rounds_mode = False
    full = run.battle_skills(h)
    run.rounds_mode = True
    short = run.battle_skills(h)
    regular = [s for s in short if not run.data.skills[s].get("ult") and not run.data.skills[s].get("mech")]
    assert len(regular) <= ED.rounds["skills_in_battle"] and len(short) <= len(full)
    squad = run.combat_squad()
    p = squad[0]["proto"]
    assert p["day_charges"] and p["day_charges"] == p["day_max"]
    c = Combat(run.data, run.nodes[nid]["encounter"], squad=squad, enemy_scale=run.enemy_scale(), rounds=True)
    c.step()
    u = c.heroes(PLAYER)[0]
    sid = next(iter(u.day_charges))
    u.day_charges[sid] = 0
    assert not u.skill_ready(sid, u.skill_defs[sid])
    assert c.check_skill(u, sid, u)[1] in ("Нет зарядов до привала", "Навык раунда уже применён")
    c.result = "victory"
    run.finish_battle(c)
    assert h.day_used[sid] == p["day_max"][sid]            # потрачено до привала
    assert run.combat_squad()[0]["proto"]["day_charges"][sid] == 0
    run.camp_rest()
    assert not h.day_used                                    # привал вернул заряды


def test_forecast_and_intent_bot(tmp_path):
    run, nid = run_and_node(tmp_path)
    c = combat(run, nid)
    c.step()
    h = next(x for x in c.heroes(PLAYER))
    foe = c.alive(ENEMY)[0]
    sid = next((s for s in h.skills if h.skill_defs[s]["target"] == "enemy"
                and any(e["type"] == "damage" for e in h.skill_defs[s]["effects"])), None)
    if sid:
        fc = R.forecast(c, h, sid, foe)
        assert c.units.index(foe) in fc and fc[c.units.index(foe)][0] > 0
        assert foe.hp == foe.max_hp or foe.hp > 0           # прогноз — по копии, сам бой не тронут
    R.bot_round(c)                              # бот по намерениям раздаёт приказы без ошибок
    assert all(u.order or u.queue or not u.alive for u in c.heroes(PLAYER))


def test_battle_scene_pauses_every_round(tmp_path):
    from game.battle_scene import BattleScene
    from tests.test_expedition_ui import SCREEN
    run, nid = run_and_node(tmp_path)
    scene = BattleScene(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(),
                        enemy_scale=run.enemy_scale(), on_finish=lambda *a: None, simple=True, rounds=True)
    scene.begin_battle()
    assert scene.combat.rounds.n == 1 and scene.paused and not scene.auto_pause
    scene.draw(SCREEN)
    scene._key(pygame.K_SPACE)
    assert not scene.paused
    for _ in range(200):
        scene.update(1 / 30)
        if scene.paused:
            break
    assert scene.paused and scene.combat.rounds.n == 2      # сам встал на паузу перед раундом 2
    u, sid = next((h, s) for h in scene.combat.heroes(PLAYER) for s in h.skills
                  if h.skill_defs[s]["target"] in ("enemy", "cell", "self"))
    scene.selected = u
    scene.targeting = sid
    scene.hover_cell = scene.combat.alive(ENEMY)[0].cell
    scene.draw(SCREEN)                          # намерения, раунд, карточки и прогноз рисуются без ошибок


def test_rounds_setting_reaches_expedition_battle(tmp_path, monkeypatch):
    from ui import settings
    assert any(o[0] == "battle_rounds" for o in settings.OPTIONS) and settings.DEFAULTS["battle_rounds"] is False
    monkeypatch.setitem(settings.SETTINGS, "battle_rounds", True)
    from game import expedition_scenes as ES

    class App:
        autoplay = False
        profile = type("P", (), {"sandbox": False})()

        def switch(self, scene):
            self.scene = scene
    app = App()
    run, nid = run_and_node(tmp_path)
    run.node = nid
    app.exp = run
    ES.battle(app)
    assert run.rounds_mode and app.scene.combat.rounds is not None
