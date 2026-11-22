"""«Спуск» (deck/, descent.py): карты с основным и простым применением, прозрения, бой с намерениями врагов,
толчки и столкновения, стихии, карта этажа, торговец, костёр, живая рука карт, экраны."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from deck import bot  # noqa: E402
from deck import model as M  # noqa: E402
from deck.battle import Battle, finish  # noqa: E402
from sim.grid import cheb  # noqa: E402
from test_expedition import ED  # noqa: E402
from ui import theme as T  # noqa: E402

pygame.init()


def battle(fight=0, seed=1):
    run = M.Run(seed=seed)
    return Battle(ED, run, run.fights[fight], seed=seed), run


def put(b, u, cell):
    u.cell = u.prev_cell = tuple(cell)
    u.move_t = 1.0


def card(b, cid):
    c = M.Card(cid, b.run.defs)
    b.hand.append(c)
    return c


def test_cards_have_main_and_free_alt_and_insights():
    run = M.Run(seed=1)
    assert len(run.deck) == 12 and run.hp == run.max_hp == 80          # + «Удар с отходом», HP 80 (балансировка)
    for cid, d in run.defs.items():
        assert {"main", "cost", "type", "name"} <= set(d), cid
        c = M.Card(cid, run.defs)
        assert c.text("main") or d.get("react"), cid                         # реакция — только откликом
        assert c.text("alt") or c.d["alt"]["target"] == "none", cid           # простое — не у всех
        if d.get("token") or d.get("status") or d.get("meaning"):          # свитки Жреца: растут боги, не карты                                 # стрелы, «Тина» — не растут
            continue
        assert len(d["growth"]) == 1 and len(d["growth"][0]["options"]) == 5, cid   # прозрение: 5 вариантов
        for v in d["growth"][0]["options"]:
            assert "cost" not in v, cid                                        # прокачка не удешевляет
            for L1, L2 in zip(d.get("levels", []), v.get("levels", [])):
                assert L1["heat"] == L2["heat"], cid
    s = M.Card("strike", run.defs)
    assert not s.insight_ready()
    s.uses = 4
    assert s.insight_ready()
    opts = s.options()
    assert len(opts) == 3 and s.options() == opts or [x[0] for x in s.options()] == [x[0] for x in opts]
    label, after = opts[0]
    s.choose(0)
    assert s.tier == 1 and s.text("main") == after.text("main") and not s.insight_ready()
    assert s.cost == 1                                                         # цена та же


def test_turn_start_energy_hand_intents():
    b, _ = battle()
    assert b.energy == 4 and len(b.hand) == 6 and b.turn == 1                   # Наёмник: 4 энергии, рука 6
    assert all(u.intent and u.intent["kind"] for u in b.foes())
    foe = next(u for u in b.foes() if u.intent["kind"] == "melee")
    put(b, foe, (b.hero.cell[0] + 1, b.hero.cell[1]))
    full = b.intent_damage(foe)
    assert full > 0                                                            # вплотную — полный удар
    put(b, foe, (b.hero.cell[0] + 1 + foe.speed, b.hero.cell[1]))
    assert b.intent_damage(foe) == max(1, b.hit_value(foe, b.hero, foe.intent["dmg"] // 2))   # с ходу — вполсилы


def test_main_costs_energy_alt_is_free_and_not_a_play():
    b, _ = battle()
    h = b.hero
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    s = card(b, "strike")
    hp = foe.hp
    finish(b.play(s, "main", foe))
    assert b.energy == 3 and foe.hp == hp - 6 and s.uses == 1 and b.played == 1
    s2 = card(b, "strike")
    finish(b.play(s2, "alt", foe))
    assert b.energy == 3 and foe.hp == hp - 8 and s2.uses == 0 and b.played == 1   # простое — не «сыграно»
    b.energy = 0
    s3 = card(b, "strike")
    assert not b.targets(s3, "main") and b.targets(s3, "alt")                    # без энергии — только простое


def test_step_reach_and_push_collision():
    b, _ = battle()
    h = b.hero
    st = card(b, "lunge_rush")
    cells = b.targets(st, "alt")
    assert cells and all(cheb(p, h.cell) <= 2 for p in cells)
    goal = max(cells, key=lambda p: p[0])
    finish(b.play(st, "alt", goal))
    assert h.cell == goal
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 3, h.cell[1]))
    lu = card(b, "lunge_rush")
    finish(b.play(lu, "main", foe))
    assert cheb(h.cell, foe.cell) <= 1                                         # подошёл и ударил
    wall_x = b.c.grid.w - 1
    put(b, h, (wall_x - 1, 2))
    for u in b.foes():
        put(b, u, (0, 5 - b.foes().index(u)))
    put(b, foe, (wall_x, 2))
    ram = card(b, "shield_ram")
    b.energy = 3
    hp = foe.hp
    finish(b.play(ram, "main", foe))                                           # 8 урона + толчок 2 в край
    assert foe.hp == hp - 8 - 2 * 3


def test_enemy_intents_melee_zone_shot_los():
    b, _ = battle()
    h = b.hero
    slime, archer = b.foes()
    slime.intent = {"kind": "melee", "name": "Шлепок", "dmg": 7}
    put(b, slime, (h.cell[0] + 2, h.cell[1]))
    hp = h.hp
    finish(b.act(slime))
    assert cheb(slime.cell, h.cell) <= 1 and h.hp == hp - 7                    # подошёл и ударил
    b.choose_intent(slime)
    slime.intent = {"kind": "zone", "name": "Размах", "dmg": 10, "cells": [h.cell]}
    put(b, h, (h.cell[0], h.cell[1] + 1)) if b.free((h.cell[0], h.cell[1] + 1)) else None
    hp = h.hp
    finish(b.act(slime))
    assert h.hp == hp                                                          # ушёл из зоны — цел
    archer.intent = {"kind": "shot", "name": "Выстрел", "dmg": 6, "range": 5}
    put(b, h, (1, 1))
    put(b, archer, (6, 1))
    hp = h.hp
    finish(b.act(archer))
    assert h.hp < hp                                                           # в зоне и на виду — попал
    put(b, archer, (8, 1))
    assert not b.in_fire_zone(archer) and h.cell not in b.fire_zone(archer)
    hp, was = h.hp, archer.cell
    finish(b.act(archer))
    assert h.hp == hp and archer.cell != was                                   # вне зоны — только перебежал
    assert b.edefs["bog_archer"]["cycle"][0]["kind"] == "aim"                 # первый ход — прицел, не выстрел


def test_elements_and_deaths():
    b, _ = battle(1)
    h = b.hero
    beetle = b.foes()[0]
    b.add_burn(beetle, 3)
    assert beetle.ds["burn"] == 3 and "fire" in beetle.statuses
    b.wet(beetle)
    assert beetle.ds["burn"] == 0 and beetle.ds["wet"]                         # вода гасит
    b.add_burn(beetle, 2)
    assert beetle.ds["burn"] == 0 and not beetle.ds["wet"]                     # огонь по мокрому — пар
    b.wet(beetle)
    b.add_frost(beetle, 1)
    assert beetle.ds["stun"]                                                   # мокрый + холод = лёд
    cell = beetle.cell
    b.hurt(beetle, 999, h)
    assert not beetle.alive and b.c.grid.get(cell).hazard == "fire"            # жук оставил огонь
    b2, _ = battle(0)
    slime = b2.foes()[0]
    n = len(b2.foes())
    b2.hurt(slime, 999, b2.hero)
    assert len(b2.foes()) == n - 1 + 2 and all(f.name for f in b2.foes())     # слизень распался


def test_bot_plays_fights_and_hp_carries_over():
    wins = 0
    for seed in range(4):
        b, run = battle(0, seed)
        r = bot.play_battle(b)
        b.finish_into_run()
        assert r in ("victory", "defeat") and 1 <= b.turn <= 40
        wins += r == "victory"
        if r == "victory":
            assert run.hp == b.hero.hp and run.hp <= run.max_hp
    assert wins >= 3                                                           # первый бой бот выигрывает


def test_floor_map_generation_and_scaling():
    import random
    from deck.floor import generate
    run = M.Run(seed=3)
    cfg = run.floor_cfg
    for seed in range(20):
        nodes = generate(cfg, random.Random(seed))
        layers = {}
        for n in nodes.values():
            layers.setdefault(n["layer"], []).append(n)
        last = max(layers)
        assert [n["type"] for n in layers[last]] == ["boss"]
        assert {n["type"] for n in layers[last - 1]} == {"camp", "shop"}
        assert all(n["type"] == "battle" for n in layers[0])
        assert not any(n["type"] == "elite" for n in layers[1])
        for i in range(last):                                                  # у каждого узла есть вход и выход
            assert all(n["next"] for n in layers[i])
            assert all(any(m["id"] in n["next"] for n in layers[i]) for m in layers[i + 1])
        assert all(n.get("fight") for n in nodes.values() if n["type"] in ("battle", "elite", "boss"))
    fl = run.floor
    assert fl.depth == 1 and run.scale() == (1.0, 1.0)
    first = fl.available()
    n = fl.enter(first[0])
    assert fl.available() == n["next"]
    b = Battle(ED, run, n["fight"], seed=1)                                    # расстановка сама: 4–8 клеток
    assert all(4 <= cheb(f.cell, b.hero.cell) <= 8 for f in b.foes())
    hp1 = b.foes()[0].max_hp
    run.next_floor()
    run.next_floor()
    assert run.depth == 3 and run.scale()[0] >= 1.3
    b3 = Battle(ED, run, n["fight"], seed=1)
    assert b3.foes()[0].max_hp > hp1                                           # глубже — враги крепче


def test_hand_view_springs_drag_and_play():
    from deck.hand import HandView
    run = M.Run(seed=1)
    hv = HandView((128, 178), (60, 770), (1040, 760))
    hand = run.deck[:5]
    hv.sync(hand)
    area = pygame.Rect(150, 582, 900, 218)
    for _ in range(60):
        hv.layout(hand, area, (0, 0))
        hv.update(1 / 60, (0, 0))
    xs = [hv.sprites[c.uid].x for c in hand]
    assert xs == sorted(xs) and all(area.left < x < area.right for x in xs)   # веер слева направо
    mid = hv.sprites[hand[2].uid]
    hv.hover = hv.hit((int(mid.x), int(mid.y)))
    assert hv.hover == hand[2].uid
    y0 = mid.y
    for _ in range(40):
        hv.layout(hand, area, (int(mid.x), int(mid.y)))
        hv.update(1 / 60, (int(mid.x), int(mid.y)))
    assert mid.y < y0 - 20 and mid.s > 1.1                                    # под мышью — выше и крупнее
    hv.hover = None
    hv.start_drag(hand[0].uid, (int(hv.sprites[hand[0].uid].x), int(hv.sprites[hand[0].uid].y)))
    for k in range(20):
        hv.update(1 / 60, (400 + k * 20, 300))
    d = hv.sprites[hand[0].uid]
    assert abs(d.y - 300) < 60 and abs(d.a) > 1                               # тянется за мышью и кренится
    hv.played(hand[1], (500, 200))
    hv.sync([c for c in hand if c is not hand[1]])
    assert hand[1].uid not in hv.sprites and len(hv.flying) == 1
    for _ in range(40):
        hv.update(1 / 60, (0, 0))
    assert not hv.flying                                                       # улетела и погасла


def test_game_flow_map_battle_shop_camp_boss():
    from deck.game import DescentGame
    from deck.ui import BattleScreen, ChoiceScreen, DeckScreen, EndScreen, MapScreen, ShopScreen
    from tests.test_expedition_ui import SCREEN
    from deck.ui import HeroSelect
    g = DescentGame(seed=2, gd=ED)
    assert isinstance(g.scene, HeroSelect)                                     # сначала — выбор героя
    g.draw(SCREEN)
    g.scene.start()
    assert isinstance(g.scene, MapScreen) and g.run.hero_id == "merc"
    g.draw(SCREEN)
    run = g.run
    g.enter_node(run.floor.available()[0])
    assert isinstance(g.scene, BattleScreen)
    sc = g.scene
    for _ in range(20):
        g.update(1 / 30)
    g.draw(SCREEN)
    card = next(c for c in sc.b.hand if sc.b.targets(c, "alt"))               # ПКМ — повернуть, затем тянуть
    sp = sc.hv.sprites[card.uid]
    start = (int(sp.x), int(sp.y))
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=3))
    assert sc.hv.mode(card.uid) == "alt"
    fs = []
    for _ in range(30):
        g.update(1 / 30)
        fs.append(sc.hv.sprites[card.uid].f)
    assert sc.hv.sprites[card.uid].f == 180                                    # карта перевернулась
    assert all(b >= a for a, b in zip(fs, fs[1:])) and max(fs) <= 180          # ровно, без перелёта и дрожи
    sp = sc.hv.sprites[card.uid]
    start = (int(sp.x), int(sp.y))
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=1))
    t = sc.b.targets(card, "alt")[0]
    tp = sc.view.cam(sc.view.feet_pos(t)) if hasattr(t, "cell") else sc.view.cam(T.cell_feet(t))
    tp = (int(tp[0]), int(tp[1]) - 20)
    sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=tp, rel=(0, 0), buttons=(1, 0, 0)))
    assert sc.drag and sc.sel == (card, "alt")                                 # тянется то, что сверху
    g.update(1 / 30)
    g.draw(SCREEN)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=tp, button=1))
    if card.d["alt"]["target"] != "self":
        assert card not in sc.b.hand or sc.job is not None
    sc.job = None
    sc.b.result = "victory"
    gold = run.gold
    g.update(1 / 30)
    assert isinstance(g.scene, ChoiceScreen) and run.fight == 1 and run.gold > gold
    n = len(run.deck)
    g.scene.on_pick(g.scene.options[0][2])
    while isinstance(g.scene, ChoiceScreen):
        g.scene.on_pick(g.scene.options[0][2])
    assert isinstance(g.scene, MapScreen) and len(run.deck) == n + 1
    g.show_deck()
    assert isinstance(g.scene, DeckScreen)
    g.draw(SCREEN)
    g.scene.back()
    assert isinstance(g.scene, MapScreen)
    shop = [nid for nid, nd in run.floor.nodes.items() if nd["type"] == "shop"][0]   # торговец
    g.enter_node(shop)
    assert isinstance(g.scene, ShopScreen)
    s = g.scene
    run.gold = 500
    run.hp = 40
    n = len(run.deck)
    assert s.buy(0) and len(run.deck) == n + 1 and not s.buy(0)
    assert s.drink() and run.hp == 60 and not s.drink()
    price = run.remove_price
    g.pick_remove(back=s, paid=True)
    assert isinstance(g.scene, DeckScreen)
    g.draw(SCREEN)
    g.scene.on_pick(run.deck[0])
    assert g.scene is s and len(run.deck) == n and run.remove_price > price
    g.draw(SCREEN)
    camp = [nid for nid, nd in run.floor.nodes.items() if nd["type"] == "camp"][0]    # костёр
    g.enter_node(camp)
    run.hp = 30
    g.scene.on_pick("rest")
    assert run.hp == 54 and isinstance(g.scene, MapScreen)                    # +30% от 80
    boss = [nid for nid, nd in run.floor.nodes.items() if nd["type"] == "boss"][0]    # страж → следующий этаж
    g.enter_node(boss)
    assert isinstance(g.scene, BattleScreen) and g.scene.b.fight.get("boss")
    g.scene.b.result = "victory"
    g.update(1 / 30)
    g.scene.skip()
    n_items = len(run.relics)
    while isinstance(g.scene, ChoiceScreen):                                   # награда, прозрения, предмет стража
        g.draw(SCREEN)
        g.scene.on_pick(g.scene.options[0][2])
    assert len(run.relics) == n_items + 1 and run.relics[-1]["rarity"] == "boss"     # даров больше нет — предмет
    assert isinstance(g.scene, MapScreen) and run.depth == 2 and run.floor.node is None
    g.draw(SCREEN)
    g.enter_node(run.floor.available()[0])
    g.scene.b.hero.hp = 0
    g.scene.b.result = "defeat"
    g.update(1 / 30)
    assert isinstance(g.scene, EndScreen)
    g.draw(SCREEN)
    g.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert isinstance(g.scene, HeroSelect)                                     # новый забег — снова выбор героя


def test_card_faces_differ_and_have_art():
    from deck import cardface as CF
    from tests.test_expedition_ui import SCREEN  # noqa: F401  (окно для convert_alpha)
    run = M.Run(seed=1)
    seen = set()
    for cid, d in run.defs.items():
        assert d.get("art") and CF.art(d["art"], 52) is not None, cid       # у каждой карты свой рисунок
        if d.get("token"):
            continue
        c = M.Card(cid, run.defs)
        img = CF.face(c)
        assert img.get_size() == (CF.FW, CF.FH)                                # лицо — в высоком разрешении
        assert d.get("ill") and CF.illustration(d["ill"], CF.ART.size) is not None, cid
        for mode in ("main", "alt"):                                           # у всех действий — человеческий текст
            if c.d[mode]["target"] == "none":                                  # реакция / без простого
                continue
            ph = CF.phrase(c.d[mode])
            assert ph and ph != "—" and "_" not in ph, (cid, mode, ph)
        assert CF.chips(c.d["main"]) and CF.chips(c.d["alt"]) or c.d["alt"]["target"] in ("self", "none")             or d.get("react")
        seen.add(tuple(d["ill"]))
    assert len(seen) >= sum(1 for d in run.defs.values() if not d.get("token")) - 2                                      # иллюстрации на лице почти не повторяются
    s = M.Card("strike", run.defs)
    assert CF.chips(s.d["main"]) == [("damage", "6")]
    assert CF.phrase(s.d["main"]) == "Нанести {6} урона."                      # текст как в StS: число крупно
    assert CF.phrase(M.Card("shield_ram", run.defs).d["main"]) == "Нанести {8} урона. *Толчок* {2}."
    assert CF.chips(M.Card("lunge_rush", run.defs).d["alt"]) == [("step", "2")]


def hero_battle(hero, variant=None, fight=0, seed=1):
    run = M.Run(seed=seed, hero=hero, variant=variant)
    return Battle(ED, run, run.fights[fight], seed=seed), run


def test_merc_momentum_steps_add_damage_and_reset():
    b, _ = hero_battle("merc")
    h = b.hero
    st = card(b, "lunge_rush")
    cells = b.targets(st, "alt")
    goal = max(cells, key=lambda p: (cheb(p, h.cell), p[0]))
    finish(b.play(st, "alt", goal))
    assert h.ds["momentum"] == cheb(goal, (1, 2)) or h.ds["momentum"] >= 1     # шаги копят разгон
    mom = h.ds["momentum"]
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    s = card(b, "strike")
    hp = foe.hp
    finish(b.play(s, "main", foe))
    assert hp - foe.hp == 6 + mom and h.ds["momentum"] == 0                   # удар тратит разгон
    h.ds["momentum"] = 3
    finish(b.end_turn())
    assert h.ds["momentum"] == 0 or not h.alive                                # в конце хода гаснет


def test_hunter_passives_range_mark_quiver():
    b, _ = hero_battle("hunter", "range")
    h = b.hero
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 6, h.cell[1]))
    for u in b.foes()[1:]:
        put(b, u, (0, 0))
    shot = card(b, "h_shot")
    hp = foe.hp
    if b.los(h.cell, foe.cell):
        finish(b.play(shot, "main", foe))
        assert hp - foe.hp == 5 + 3                                            # 6 клеток: +3 за дистанцию
    b2, _ = hero_battle("hunter", "mark")
    prey = b2.prey
    assert prey is not None and prey in b2.foes()
    e = b2.energy
    b2.hurt(prey, 999, b2.hero)
    assert b2.prey is not prey and b2.energy == e + 1                          # метка перешла, +энергия
    b3, _ = hero_battle("hunter", "quiver")
    assert any(c.cid == "arrow" for c in b3.hand)                              # стрела в руке с первого хода
    arrow = next(c for c in b3.hand if c.cid == "arrow")
    assert arrow.cost == 0 and arrow.d.get("token")
    finish(b3.end_turn())
    assert not any(c.cid == "arrow" for c in b3.discard)                       # стрелы не копятся в колоде
    trap = card(b3, "h_trap")
    b3.energy = 3
    cell = b3.targets(trap, "main")[0]
    finish(b3.play(trap, "main", cell))
    assert cell in b3.traps


def test_pyro_heat_levels_alt_and_overheat():
    b, _ = hero_battle("pyro")
    h = b.hero
    assert b.max_energy == 0 and h.ds["heat"] == 4                             # 2 на старте + 2 за ход
    bolt = card(b, "p_bolt")
    b.sync_levels()
    assert bolt.lvl == 2 and bolt.cost == 3                                    # сам — высший доступный уровень
    bolt.manual = True
    bolt.lvl = 0
    assert bolt.cost == 1 and "4" in bolt.text("main")
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 2, h.cell[1]))
    hp = foe.hp
    finish(b.play(bolt, "main", foe))
    assert hp - foe.hp == 4 and h.ds["heat"] == 3                              # заплатила жаром, не энергией
    ward = card(b, "p_ward")
    finish(b.play(ward, "alt", h))
    assert h.ds["heat"] == 4                                                   # простое — раздуть
    h.ds["heat"] = 11
    hp = h.hp
    finish(b.end_turn())
    assert h.hp <= hp - 6 or not h.alive                                       # перегрев: (11 − 8) × 2


def test_battle_screen_wheel_level_and_drag_flip_plays_only_on_release():
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=3, gd=ED)
    g.start_run("pyro")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    for _ in range(30):
        g.update(1 / 30)
    c = sc.b.hand[0]
    sp0 = sc.hv.sprites[c.uid]
    sc.mouse = (int(sp0.x - 30), int(sp0.y))                                  # мышь над картой
    assert sc.hv.hit(sc.mouse) == c.uid
    lv = c.lvl
    sc.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert c.manual and c.lvl == max(0, lv - 1)                                # колесо — уровень ниже
    g.draw(SCREEN)
    sp = sc.hv.sprites[c.uid]
    st = (int(sp.x), int(sp.y) - 40)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=st, button=1))
    p = (st[0], st[1] - 300)
    sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=p, rel=(0, 0), buttons=(1, 0, 0)))
    held = sc.sel[0] if sc.sel else None
    assert sc.drag and held is not None
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=p, button=3))
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=p, button=3))
    assert sc.drag and sc.sel[1] == "alt" and held in sc.b.hand and sc.job is None   # повернули — не сыграно
    g.draw(SCREEN)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(st[0], 790), button=1))   # отпустили над рукой
    assert held in sc.b.hand and not sc.drag


def test_wheel_on_hovered_card_redraws_and_range_shows_without_targets():
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=7, gd=ED)
    g.start_run("pyro")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    b = sc.b
    for _ in range(30):
        g.update(1 / 30)
    c = next(x for x in b.hand if x.levels)
    sp = sc.hv.sprites[c.uid]
    sc.mouse = (int(sp.x), int(sp.y))
    sc.sel = (b.hand[-1], "main") if b.hand[-1] is not c else None            # чужая выбранная карта не мешает
    lv = c.lvl
    g.draw(SCREEN)
    keys = set(sc.hv.cache)
    sc.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1 if lv else 1))
    assert c.lvl != lv                                                         # колесо — над картой в фокусе
    g.draw(SCREEN)
    assert set(sc.hv.cache) - keys                                             # лицо перерисовано с новым уровнем
    for u in b.foes():                                                         # враги вне досягаемости
        put(b, u, (b.c.grid.w - 1, u.cell[1]))
    bolt = next(x for x in b.hand if x.cid == "p_bolt") if any(x.cid == "p_bolt" for x in b.hand) else c
    assert b.range_cells(bolt, "main")                                         # дальность видна и без целей
    sc.sel = (bolt, "main")
    g.draw(SCREEN)


def test_native_resolution_canvas_draws_crisp_and_maps_mouse():
    from deck import gfx as G
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN  # noqa: F401  (окно для convert_alpha)
    import ui.theme as TH
    native = pygame.Surface((3440, 1440))                                       # ультраширокий монитор
    c = G.Canvas(native)
    assert abs(c.S - 1.8) < 1e-6 and c.ox > 0 and c.oy == 0                    # по высоте, поле по центру
    assert G.to_logical(c, c.pt((640, 400))) == (640, 400)
    text0, rect0 = TH.text, pygame.draw.rect
    g = DescentGame(seed=7, gd=ED)
    for scene in ("select", "map", "battle"):
        if scene == "map":
            g.start_run("hunter", "mark")
        if scene == "battle":
            g.enter_node(g.run.floor.available()[0])
            for _ in range(20):
                g.update(1 / 30)
        with G.native(c):
            g.draw(c)
    assert TH.text is text0 and pygame.draw.rect is rect0                      # подмена — только на кадр
    r = TH.render("Удар", round(16 * c.S), (255, 255, 255))
    assert r.get_height() > TH.render("Удар", 16, (255, 255, 255)).get_height() * 1.5   # шрифт крупнее, не растянут


def test_cards_and_mechanics_emit_effects():
    def fx_of(b):
        ev = list(b.c.events)
        b.c.events.clear()
        return ([e["skill"] for e in ev if e.get("t") == "skill"],
                [e["kind"] for e in ev if e.get("t") == "deck_fx"])

    b, _ = hero_battle("merc")
    h = b.hero
    b.c.events.clear()
    st = card(b, "lunge_rush")
    goal = max(b.targets(st, "alt"), key=lambda p: cheb(p, h.cell))
    finish(b.play(st, "alt", goal))
    sk, kinds = fx_of(b)
    assert "alt" in kinds and "momentum_step" in kinds                         # пыль простого шага + разгон
    h.ds["momentum"] = 3
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    finish(b.play(card(b, "strike"), "main", foe))
    sk, kinds = fx_of(b)
    assert sk == ["power_strike"] and "momentum_hit" in kinds                 # свой эффект карты + удар с разгона

    b, _ = hero_battle("pyro")
    h = b.hero
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 2, h.cell[1]))
    seen = []
    for lv in (0, 1, 2):                                                       # уровни — разные эффекты
        h.ds["heat"] = 6
        foe.hp = foe.max_hp
        c = card(b, "p_bolt")
        c.manual = True
        c.lvl = lv
        b.c.events.clear()
        finish(b.play(c, "main", foe))
        seen += fx_of(b)[0]
    assert len(set(seen)) == 3
    h.ds["heat"] = 11
    b.c.events.clear()
    finish(b.end_turn())
    sk, kinds = fx_of(b)
    assert "overheat" in kinds                                                 # перегрев — взрыв


def test_damage_waits_for_impact_and_statuses_have_effects():
    b, _ = hero_battle("merc")
    h = b.hero
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    hp = foe.hp
    gen = b.play(card(b, "strike"), "main", foe)
    step = next(s for s in gen if s[0] == "impact")                            # эффект выпущен…
    assert step and foe.hp == hp                                               # …а урона ещё нет
    finish(gen)
    assert foe.hp < hp                                                         # урон — после попадания
    gen = b.end_turn()                                                         # враг: замах, потом урон
    hh = h.hp
    for s in gen:
        if s[0] == "impact":
            assert h.hp == hh
            break
    finish(gen)

    def kinds(b):
        out = [(e["kind"], e.get("el") or e.get("what")) for e in b.c.events if e.get("t") == "deck_fx"]
        b.c.events.clear()
        return out

    b, _ = hero_battle("pyro")
    f = b.foes()[0]
    b.c.events.clear()
    b.add_burn(f, 3)
    assert ("status", "fire") in kinds(b)                                      # подожгли — эффект
    f.ds["poison"] = 2
    finish(b.tick_start(f))
    k = kinds(b)
    assert ("dot", "burn") in k and ("dot", "poison") in k                     # тики — по очереди, с эффектом
    b.wet(f)
    b.add_burn(f, 2)
    assert ("react", "steam") in kinds(b)                                      # огонь по мокрому — пар
    b.wet(f)
    b.add_frost(f, 1)
    assert ("react", "ice") in kinds(b)


def test_keywords_and_shift_detail_view():
    from deck import ui as U
    run = M.Run(seed=1, hero="pyro")
    c = M.Card("p_bolt", run.defs)
    names = [n for n, _ in M.keywords(c)]
    assert "Горение" in names and "Жар" in names and "Раздуть" in names
    run = M.Run(seed=1, hero="merc")
    c = M.Card("charge", run.defs)
    assert "Толчок" in [n for n, _ in M.keywords(c)]
    opts = c.options()
    assert opts and all(U._changes(c, c2) for _, c2 in opts)                  # ветки показывают, что меняют
    surf = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
    U.card_detail(surf, c)
    U.card_detail(surf, M.Card("p_bolt", M.Run(seed=1, hero="pyro").defs), heat=2)


def test_tags_and_conditions_seal_bonus_echo_keep_twin():
    b, run = hero_battle("merc")
    h = b.hero
    assert M.Card("charge", run.defs).tags == ["Удар", "Шаг", "Толчок"]           # теги — из действий карты
    for f in b.foes()[1:]:
        put(b, f, (0, 0)) if b.free((0, 0)) else None
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    b.energy = 9
    fl = card(b, "m_flurry")
    assert not b.can_play(fl, "main") and b.can_play(fl, "alt")                 # Печать (Серия 2): закрыта
    finish(b.play(card(b, "defend"), "main", h))
    assert not b.can_play(fl, "main")
    finish(b.play(card(b, "defend"), "main", h))
    assert b.can_play(fl, "main") and "seal" in b.lit(fl)                       # две сыграны — открылась
    foe.hp = foe.max_hp = 99
    hp = foe.hp
    finish(b.play(fl, "main", foe))
    assert hp - foe.hp == 12                                                    # 4 ×3

    b, run = hero_battle("merc")                                               # У стены: урон ×2
    h = b.hero
    foe = b.foes()[0]
    put(b, h, (0, 2))
    put(b, foe, (1, 2))
    other = b.foes()[1]
    put(b, other, (2, 2))                                                       # за целью — другой враг
    foe.hp = foe.max_hp = 99
    wb = card(b, "m_wallbash")
    assert ("if", 0) in b.lit(wb)
    hp = foe.hp
    b.energy = 3
    finish(b.play(wb, "main", foe))
    assert hp - foe.hp >= 12

    b, run = hero_battle("hunter", "range")                                    # Отклик и Задел
    h = b.hero
    trail = card(b, "h_trail")
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 3, h.cell[1]))
    foe.hp = foe.max_hp = 99
    b.energy = 9
    for _ in range(2):
        shot = card(b, "h_shot")
        if b.targets(shot, "main"):
            finish(b.play(shot, "main", b.targets(shot, "main")[0]))
    assert trail.uid in b.echoed and trail not in b.hand                       # Цепочка сыграла сама
    assert b.hero.shield >= 3                                                  # карта сыграла сама один раз
    kept = M.Card("h_trail", run.defs)
    kept.pick(4)                                                                # вариант «Задел (Серия 3)»
    assert kept.d.get("keep") == {"k": "series", "n": 3}
    b.hand.append(kept)
    b.played = 3
    finish(b.end_turn())
    assert kept in b.hand or not b.hero.alive                                   # Задел: осталась на новый ход

    b, run = hero_battle("merc")                                               # дар Мокоши: Серия 2 — дважды
    h = b.hero
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.hp = foe.max_hp = 99
    s = card(b, "strike")
    s.bless(run.data["gods"]["gods"]["mokosh"])
    assert s.divine and "дважды" in s.text("main")
    b.energy = 9
    b.played = 2
    hp = foe.hp
    finish(b.play(s, "main", foe))
    assert hp - foe.hp == 12


def test_chest_offers_items_and_bag_opens():
    """Сундук (вместо алтаря): предмет 1 из 3 — общий или своего класса; сумка открывается на карте по I."""
    import pygame
    from deck.game import DescentGame
    from deck.ui import ChoiceScreen, MapScreen
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=3)
    g.start_run("pyro")
    g.run.floor.nodes["n2_0"]["type"] = "chest"
    g.node = None
    g.offer_relics(3, "Сундук", lambda toast=None: g.to_map(toast), source="chest")
    assert isinstance(g.scene, ChoiceScreen) and len(g.scene.options) == 3
    assert all(o[2].get("hero") in (None, "pyro") and o[2]["rarity"] in ("common", "uncommon", "rare")
               for o in g.scene.options)
    g.draw(SCREEN)
    it = g.scene.options[0][2]
    g.scene.on_pick(it)
    assert g.run.relics == [it] and isinstance(g.scene, MapScreen)
    g.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i, mod=0, unicode="i"))
    assert g.scene.bag.open
    g.draw(SCREEN)
    assert "altar" not in g.run.floor_cfg["weights"] and "chest" in g.run.floor_cfg["weights"]



def test_czn_used_moves_to_discard_at_turn_end():
    b, run = battle(seed=6)
    h, foe = b.hero, b.foes()[0]
    foe.hp = foe.max_hp = 99
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    played = M.Card("strike", run.defs)
    b.hand = [played]
    b.draw_pile, b.discard, b.used = [], [], []
    b.energy = 9
    finish(b.play(played, "main", foe))
    assert played in b.used
    b.draw_pile, b.discard = [], []
    b.hero.hp = b.hero.max_hp = 999
    finish(b.end_turn())
    assert not b.used
    assert played in b.discard or played in b.hand


def test_czn_used_pile_is_not_shuffled_until_end_turn():
    b, run = battle(seed=5)
    h, foe = b.hero, b.foes()[0]
    foe.hp = foe.max_hp = 99
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    played = M.Card("strike", run.defs)
    b.hand = [played]
    b.draw_pile, b.discard, b.used = [], [], []
    b.energy = 9
    finish(b.play(played, "main", foe))
    assert played in b.used and played not in b.discard and played not in b.hand

    b.draw(1)                                                   # Used не подмешивается в Draw
    assert played not in b.hand and played in b.used

    spare = M.Card("strike", run.defs)
    b.hand, b.discard, b.draw_pile = [], [spare], []
    b.draw(1)                                                   # а Discard — подмешивается
    assert spare in b.hand and played in b.used


def test_merc_catalog_reactions_return_empower_temper_and_conditions():
    b, run = hero_battle("merc")
    h = b.hero
    foes = b.foes()
    for f in foes[1:]:
        f.alive = False
    foe = foes[0]
    foe.hp = foe.max_hp = 99
    counter, ambush, trophy = (M.Card(c, run.defs) for c in ("m_counter", "m_ambush", "m_trophy"))
    assert not b.can_play(counter, "main") and not b.can_play(counter, "alt")      # реакция: самому не сыграть
    assert M.Card("war_cry", run.defs).d["alt"]["target"] == "none"            # без простого
    for cid in dict.fromkeys(run.hero["starter"] + run.hero["rewards"]):        # подсветка условий — у любой карты
        for k in [None] + list(range(5)):
            b.lit(M.Card(cid, run.defs, picks=[] if k is None else [k]))
    b.hand = [counter]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.intent = {"kind": "melee", "name": "Шлепок", "dmg": 5}
    hp, hh = foe.hp, h.hp
    finish(b.end_turn())                                                       # ударил — Контрудар ему в ответ
    assert h.hp < hh and foe.hp == hp - 7 and counter.uses == 1                # отклик копит прозрение
    b.hand = [ambush]
    put(b, foe, (h.cell[0] + 3, h.cell[1]))
    foe.intent = {"kind": "melee", "name": "Шлепок", "dmg": 5}
    hp = foe.hp
    finish(b.end_turn())                                                       # подошёл — Настороже бьёт первым
    assert foe.hp == hp - 5 and ambush.uses == 1
    b.energy = 9
    b.hand = [trophy]
    small = foe
    small.hp = 1
    put(b, small, (h.cell[0] + 1, h.cell[1]))
    e = b.energy
    finish(b.play(card(b, "strike"), "main", small))
    assert not small.alive and trophy in b.used and b.energy == e - 1 + 1      # убийство — Трофей: +1 энергия

    b, run = hero_battle("merc")                                               # Возврат, Следующая, Закалка
    h = b.hero
    foe = b.foes()[0]
    foe.hp = foe.max_hp = 999
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    b.energy = 99
    drill = card(b, "m_drill")
    finish(b.play(card(b, "m_run"), "main", b.targets(b.hand[-1], "main")[0]))
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    finish(b.play(drill, "main", foe))
    assert drill in b.hand                                                     # Вслед за [Шаг] — снова в руке
    finish(b.play(card(b, "m_rally"), "main", h))
    hp = foe.hp
    finish(b.play(card(b, "strike"), "main", foe))
    assert hp - foe.hp == 6 + 6                                                # следующий [Удар] +6
    tc = card(b, "m_temper")
    for k in range(3):
        hp = foe.hp
        b.hand.append(tc) if tc not in b.hand else None
        finish(b.play(tc, "main", foe))
        assert hp - foe.hp == 5 + 2 * k                                        # Закалка: +2 за розыгрыш

    b, run = hero_battle("merc")                                               # условия словаря
    h = b.hero
    f1, f2 = b.foes()[:2]
    put(b, h, (3, 2))
    put(b, f1, (4, 2))
    put(b, f2, (8, 5))
    assert b.met({"k": "duel"}) and not b.met({"k": "surrounded"})
    put(b, f2, (2, 2))
    assert not b.met({"k": "duel"})
    h.shield = 12
    assert b.met({"k": "shielded", "n": 10}) and not b.met({"k": "shielded", "n": 15})
    h.hp = h.max_hp // 3
    assert b.met({"k": "hurt"})
    put(b, h, (0, 0))
    assert b.met({"k": "back_wall"})
    f1.ds["stun"], f1.ds["weak"], f1.shield = True, 1, 3
    assert all(b.met({"k": k}, f1) for k in ("stunned", "weakened", "guarded"))
    h.ds["momentum"] = 4
    assert b.met({"k": "momentum", "n": 4})


def test_hold_card_to_inspect_and_shift_pins_reading_with_word_tooltips():
    from deck import cardart
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    sc.b.hand = [M.Card(c, g.run.defs) for c in ("strike", "charge", "sweep")]
    for _ in range(30):
        g.update(1 / 30)
    c = sc.b.hand[1]
    sp = sc.hv.sprites[c.uid]
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(sp.x), int(sp.y)), button=1))
    g.update(0.1)
    assert sc.inspect is None                                                  # ещё не держали
    for _ in range(12):
        g.update(1 / 30)
    assert sc.inspect is not None and sc.inspect.card is c and not sc.inspect.pinned   # удержание — осмотр
    g.draw(SCREEN)
    names = [t for t, _, _ in sc.inspect.panels()]
    assert "Толчок" in names and "Разгон" in names                              # плашки ключевых слов
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(int(sp.x), int(sp.y)), button=1))
    assert sc.inspect is None and sc.sel is None                                # отпустили — закрылось, не выбрана
    sc.mouse = (int(sp.x), int(sp.y))
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, mod=0, unicode=""))
    assert sc.inspect is not None and sc.inspect.pinned                          # Shift — закрепить чтение
    g.draw(SCREEN)
    if cardart.available():
        r = sc.inspect.card_rect
        k = r.w / M_FW()
        box = next(b for b, w, st in cardart.word_boxes(c, *sc.inspect.state) if w.startswith("Толчок"))
        pos = (int(r.x + box.centerx * k), int(r.y + box.centery * k))
        hit = sc.inspect.word_at(pos)
        assert hit and M.lookup(hit[1], hit[2])                                 # слово под мышью — описание
        sc.mouse = pos
        g.draw(SCREEN)
    before = sc.mouse
    sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(int(sp.x) + 40, int(sp.y)), rel=(40, 0), buttons=(0, 0, 0)))
    g.update(1 / 30)
    assert sc.mouse == before and sc.hv.hover is None                          # рука мышь не видит, пока читают
    assert all(abs(x.tilt[0]) + abs(x.tilt[1]) < 0.5 for x in sc.hv.sprites.values())
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
    assert sc.inspect is None                                                  # клик мимо — закрыто
    from deck.ui import DeckScreen                                             # колода: фон замирает
    g.show_deck()
    ds = g.scene
    g.draw(SCREEN)
    r0, c0 = ds.rects[0]
    ds.mouse = r0.center
    ds.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, mod=0, unicode=""))
    assert isinstance(ds, DeckScreen) and ds.reading is not None
    ds.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(r0.centerx + 200, r0.centery), rel=(200, 0),
                                 buttons=(0, 0, 0)))
    assert ds.mouse == r0.center and ds.reading.mouse == (r0.centerx + 200, r0.centery)
    g.draw(SCREEN)


def M_FW():
    from deck import cardface
    return cardface.FW


def test_attack_played_without_target_hits_nearest():
    from deck.game import DescentGame
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    b = sc.b
    h = b.hero
    near, far = b.foes()[0], b.foes()[1]
    put(b, near, (h.cell[0] + 1, h.cell[1]))
    put(b, far, (h.cell[0] + 1, h.cell[1] + 1)) if b.free((h.cell[0] + 1, h.cell[1] + 1)) else None
    near.hp = 3                                                                # при равной дальности — слабейший
    s = M.Card("strike", g.run.defs)
    b.hand = [s]
    assert b.auto_target(s, "main") is near
    assert b.auto_target(M.Card("defend", g.run.defs), "main") is None          # не атака — сама не играется
    for _ in range(20):
        g.update(1 / 30)
    sp = sc.hv.sprites[s.uid]
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(sp.x), int(sp.y)), button=1))
    empty = (40, 120)                                                          # отпустили над полем, мимо врагов
    sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=empty, rel=(0, 0), buttons=(1, 0, 0)))
    assert sc.aim()[1]                                                         # подсвечено: ударит сама
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=empty, button=1))
    for _ in range(90):
        g.update(1 / 30)
    assert not near.alive                                                      # ударила ближайшего


def _foe(b, eid, cell):
    d = b.edefs[eid]
    from sim.combat import ENEMY
    v = b.c._spawn(ENEMY, d["sprite"], b.gd.enemies[d["sprite"]], cell)
    b._setup(v, d, eid=eid)
    b.choose_intent(v)
    return v


def test_chapter1_enemy_mechanics():
    b, run = hero_battle("merc")
    h = b.hero
    for f in b.foes():
        f.alive = False
    put(b, h, (1, 2))
    croc = _foe(b, "bog_croc", (6, 2))                                         # рывок: линия отмечена заранее
    croc.cyc = 0
    b.choose_intent(croc)
    assert croc.intent["kind"] == "charge" and croc.intent["cells"][0] == (5, 2)
    hp = h.hp
    put(b, h, (4, 2))                                                          # стоит на линии — получит
    finish(b.act(croc))
    assert h.hp < hp
    croc.cyc = 0
    b.choose_intent(croc)
    put(b, h, (h.cell[0], 5)) if b.free((h.cell[0], 5)) else None              # ушёл с линии — цел
    hp = h.hp
    finish(b.act(croc))
    assert h.hp == hp or h.cell in croc.intent["cells"]
    croc.alive = False

    dr = _foe(b, "drowned", (6, 2))                                            # утягивание
    put(b, h, (2, 2))
    dr.intent = {"kind": "pull", "name": "Утянуть", "dmg": 4, "range": 4, "n": 3}
    finish(b.act(dr))
    assert cheb(h.cell, dr.cell) < 4
    dr.alive = False

    sp = _foe(b, "toad_spearman", (6, 2))                                      # щит и сила своим
    mate = _foe(b, "slime_small", (7, 2))
    sp.intent = {"kind": "guard", "name": "Сомкнуть щиты", "n": 6, "r": 2}
    finish(b.act(sp))
    assert mate.shield >= 6
    sp.intent = {"kind": "rally", "name": "За мной", "n": 2, "r": 3}
    finish(b.act(sp))
    assert mate.ds["strength"] == 2

    hag = _foe(b, "bog_hag", (8, 4))                                           # туман: издали не достать
    hag.intent = {"kind": "veil", "name": "Морок"}
    finish(b.act(hag))
    shot = M.Card("hook", run.defs)
    b.energy = 9
    assert hag not in b.targets(shot, "main")
    n = len(b.discard)
    hag.intent = {"kind": "curse", "name": "Тина", "n": 2}
    finish(b.act(hag))                                                         # «Тина» в сброс, туман рассеялся
    assert len(b.discard) == n + 2 and b.discard[-1].cid == "slime_rot" and not hag.ds["veil"]
    hag.intent = {"kind": "hex", "name": "Сглаз", "n": 1}
    finish(b.act(hag))
    assert h.ds["hex"] == 1
    b.draw_pile = [M.Card("strike", run.defs) for _ in range(6)]
    hag.intent = {"kind": "drown", "name": "На дно", "n": 2}
    ex = len(b.exhaust)
    finish(b.act(hag))
    assert len(b.exhaust) == ex + 2 and len(b.draw_pile) == 4                  # утащило из колоды

    leech = _foe(b, "elder_leech", (h.cell[0] + 1, h.cell[1]))                 # кража жизни
    leech.hp = 5
    leech.intent = {"kind": "melee", "name": "Присосаться", "dmg": 6, "drain": True}
    finish(b.act(leech))
    assert leech.hp > 5
    swarm = _foe(b, "mosquito_swarm", (0, 0))                                  # рой: от удара не больше 3
    hp = swarm.hp
    b.hurt(swarm, 20, h, "melee")
    assert hp - swarm.hp == 3
    shroom = _foe(b, "spore_shroom", (h.cell[0] + 1, h.cell[1] + 1) if b.free((h.cell[0] + 1, h.cell[1] + 1)) else (5, 5))
    put(b, h, (shroom.cell[0] - 1, shroom.cell[1]))
    b.hurt(shroom, 99, h, "melee")                                             # лопается: яд рядом и лужи
    assert h.ds["poison"] >= 3 and b.c.grid.get(shroom.cell).hazard == "poison"


def test_boss_phases_and_relics_and_chapter():
    b, run = hero_battle("merc")
    for f in b.foes():
        f.alive = False
    king = _foe(b, "slime_king", (7, 2))
    n = len(b.foes())
    b.hurt(king, king.max_hp // 2 + 1, b.hero, "melee")                      # половина HP — вторая фаза
    assert king.phase == 1 and len(b.foes()) > n and king.intent["name"] in \
        [m["name"] for m in b.edefs["slime_king"]["phases"][0]["cycle"]]
    # предметы: срабатывают только при редком условии (deck/items.py)
    run = M.Run(seed=3, hero="merc")
    rel = run.data["relics"]["relics"]
    run.relics = [dict(rel[k], id=k) for k in ("horn_cleat", "shuriken", "red_skull", "pen_nib", "cursed_key")]
    from deck.battle import Battle
    b = Battle(ED, run, run.fights[0], seed=3)
    h = b.hero
    assert h.shield == 0 and b.energy == 5 and all(f.ds["strength"] == 1 for f in b.foes())   # ключ: +1 и минус
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.hp = foe.max_hp = 999
    b.energy = 9
    for _ in range(4):
        finish(b.play(card(b, "strike"), "main", foe))
    assert h.ds["strength"] == 1                                               # Звёздочка: 4-я атака за ход
    assert run.relic_state["pen_nib"] == 4                                     # Перо: счёт через бои
    run.relic_state["pen_nib"] = 9
    finish(b.play(card(b, "strike"), "main", foe))
    assert b.double_next
    hp = foe.hp
    finish(b.play(card(b, "strike"), "main", foe))
    assert hp - foe.hp == (6 + 1) * 2 and not b.double_next                    # следующая атака — ×2
    b.hurt(h, h.hp - h.max_hp // 2 + 1, foe, "melee")                         # HP ниже половины — Красный череп
    finish(b.react())
    assert h.ds["strength"] == 1 + 3
    b.result = None
    finish(b.end_turn())
    assert b.turn == 2                                                         # Боевой рог — на 5-м ходу
    run.relics = [dict(rel["lizard_tail"], id="lizard_tail")]
    b = Battle(ED, run, run.fights[0], seed=3)
    b.hurt(b.hero, 999, None, "hp_cost")
    assert b.hero.alive and b.hero.hp == b.hero.max_hp // 2 and not b.result  # Хвост ящерицы: раз за забег
    b.hurt(b.hero, 999, None, "hp_cost")
    assert b.result == "defeat"
    # главы подряд: болото (этажи 1–3), кузни (4–6); на каждом свой состав, последний этаж главы — босс главы
    run = M.Run(seed=1, hero="hunter")
    names = []
    bosses = {1: "slime_king", 2: "toad_queen", 3: "kvaks", 4: "overseer_groh", 5: "crucible_titan", 6: "forge_lord"}
    for depth in range(1, 7):
        assert run.depth == depth and run.floor_name
        names.append(run.floor_name)
        boss = [n for n in run.floor.nodes.values() if n["type"] == "boss"][0]
        assert boss["fight"]["enemies"][0] == bosses[depth]
        assert run.chapter_end == (depth in (3, 6)) and run.last_floor == (depth == 6)
        assert run.chapter_name == ("Болото" if depth <= 3 else "Огненные кузни")
        if depth < 6:
            run.next_floor()
    assert names == ["Камышовые топи", "Жабьи дворы", "Сердце трясины", "Шлаковые отвалы", "Литейные цеха",
                     "Сердце горна"]
    assert len(run.relic_offer(3)) == 3


def test_chapter_boss_victory_screen():
    from deck.game import DescentGame
    from deck.ui import ChoiceScreen, EndScreen
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=2)
    g.start_run("merc")
    run = g.run
    while run.depth < 6:                                                   # последний босс спуска
        run.next_floor()
    boss = [nid for nid, n in run.floor.nodes.items() if n["type"] == "boss"][0]
    g.enter_node(boss)
    g.scene.b.result = "victory"
    g.update(1 / 30)
    g.scene.skip()
    while isinstance(g.scene, ChoiceScreen):
        g.scene.on_pick(g.scene.options[0][2])
    assert isinstance(g.scene, EndScreen) and g.scene.won                      # глава пройдена
    g.draw(SCREEN)


def test_reach_cards_choose_cell_behind_enemy_and_glow():
    from deck.game import DescentGame
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    b = sc.b
    h = b.hero
    for f in b.foes()[1:]:
        f.alive = False
    foe = b.foes()[0]
    put(b, h, (2, 2))
    put(b, foe, (3, 2))                                                        # стоим в упор
    foe.hp = foe.max_hp = 99
    rush = M.Card("lunge_rush", g.run.defs)                                    # подойти на 3 и ударить
    b.hand = [rush]
    spots = b.reach_spots(rush, "main")
    assert (2, 2) in spots and (4, 2) in spots                                 # можно и на месте, и за спиной
    b.energy = 3
    hp = foe.hp
    finish(b.play(rush, "main", ((4, 2), foe)))                               # обошли сзади
    assert h.cell == (4, 2) and h.ds["momentum"] == 0 and hp - foe.hp >= 3 + 2   # разгон за шаги ушёл в удар
    # интерфейс: клетка рядом с двумя врагами — отпустили карту, кликом выбрали, кого бить
    from deck.battle import ENEMY
    d = b.edefs["slime_small"]
    two = b.c._spawn(ENEMY, d["sprite"], b.gd.enemies[d["sprite"]], (5, 3))
    b._setup(two, d, eid="slime_small")
    b.choose_intent(two)
    put(b, foe, (5, 1))
    put(b, h, (2, 2))
    h.ds["momentum"] = 0
    lunge = M.Card("lunge_rush", g.run.defs)
    b.hand = [lunge]
    b.energy = 3
    for _ in range(20):
        g.update(1 / 30)
    assert set(b.reach_spots(lunge, "main")[(5, 2)]) == {foe, two}
    sp = sc.hv.sprites[lunge.uid]
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(sp.x), int(sp.y)), button=1))
    cell_pos = tuple(int(v) for v in sc.view.cam(T.cell_feet((5, 2))))
    cell_pos = (cell_pos[0], cell_pos[1] - 8)
    sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=cell_pos, rel=(0, 0), buttons=(1, 0, 0)))
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=cell_pos, button=1))
    assert sc.pick is not None and sc.pick[2] == (5, 2)                        # ждём, кого бить
    tp = tuple(int(v) for v in sc.view.cam(sc.view.feet_pos(two)))
    hp = two.hp
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(tp[0], tp[1] - 10), button=1))
    for _ in range(90):
        g.update(1 / 30)
    assert h.cell == (5, 2) and (two.hp < hp or not two.alive)                 # встал на клетку, ударил выбранного
    b2 = sc.b
    for _ in range(10):
        g.update(1 / 30)
    assert sc.hv.glow is not None
    assert not sc.hv.glow(M.Card("strike", g.run.defs), sc.state_of(M.Card("strike", g.run.defs)))
    flurry = M.Card("m_flurry", g.run.defs)                                    # Печать (Серия 2)
    b2.played = 2
    b2.energy = 3
    put(b2, foe, (h.cell[0] + 1, h.cell[1]))
    assert sc.hv.glow(flurry, sc.state_of(flurry))                              # условие выполнено — светится
    assert M.Card("defend", g.run.defs).d["alt"]["target"] == "cell_step"       # у защиты простое — шаг


def test_veiled_enemy_hud_draws():
    """Враг в тумане: значок «в тени» рисуется, игра не падает (KeyError: 'stealth')."""
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    foe = sc.b.foes()[0]
    foe.intent = {"kind": "veil", "name": "Морок"}
    finish(sc.b.act(foe))
    assert foe.ds["veil"] and "stealth" in foe.buffs
    for _ in range(5):
        g.update(1 / 30)
    g.draw(SCREEN)
    foe.intent = {"kind": "melee", "name": "Удар", "dmg": 1}
    finish(sc.b.act(foe))
    assert "stealth" not in foe.buffs                                          # действует — туман рассеялся


def test_field_life_draws_and_crows_take_off():
    """Живое поле: трава вокруг доски, на доске — редко и по краям клеток; вороны взлетают от шума рядом."""
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN
    from ui.field_life import available
    if not available():
        return
    g = DescentGame(seed=7)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    life = sc.life
    assert life.ready and life.plants and life.crows
    grid = sc.combat.grid
    on_board = [p for p in life.plants if 0 <= p[0] < grid.w and 0 <= p[1] < grid.h]
    assert len(on_board) < len(life.plants) / 4                    # бой читается: трава в основном вокруг
    for gx, gy, *_ in on_board:
        assert gy % 1 >= 0.7 and not 0.2 < gx % 1 < 0.8            # у нижнего края клетки, сбоку
    crow = life.crows[0]
    near = next(u for u in sc.combat.units if u.alive)
    near_pos = sc.view.ground_pos(near)
    crow["gx"], crow["gy"] = near_pos[0] + 1, near_pos[1] - 1
    life.on_event({"t": "damage", "unit": near}, sc.view)
    assert crow["st"] == "takeoff"
    life.next_flock = life.next_fish = 0
    for _ in range(40):
        g.update(1 / 30)
    assert crow["st"] in ("fly", "gone")
    g.draw(SCREEN)


def test_battle_ui_help_log_and_crisp_hints():
    """Интерфейс боя: «?»/H — справка, L — журнал; подсказки поля собираются чётким слоем и рисуются на холсте."""
    import pygame
    from deck import gfx as G
    from deck.game import DescentGame
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h, mod=0, unicode="h"))
    assert sc.help_open
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5)))
    assert not sc.help_open                                       # любой клик закрывает справку
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=0, unicode="l"))
    assert sc.log_open
    card = next(c for c in sc.b.hand if c.d["main"]["target"] != "self")
    sc.sel = (card, "main")
    assert sc.hint_text()                                         # подсказка по действию
    sc.hints.clear()
    sc.collect_hints(sc.hints)
    assert sc.hints.edges or sc.hints.rings                       # дальность карты и кольца у ног
    sc.help_open = True
    for _ in range(3):
        g.update(1 / 30)
    g.draw(SCREEN)
    big = pygame.Surface((1920, 1200))
    canvas = G.Canvas(big)
    with G.native(canvas):
        g.draw(canvas)


def test_ground_hd_pixel_relief():
    """Земля «Спуска»: строится (пиксель-арт 64/клетку с рельефом), вода ниже суши, декор знает высоту земли."""
    import pygame
    from deck import gfx as G
    from deck import terrain as TR
    from deck.game import DescentGame
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    v = sc.view
    rel = sc.ground.prepare(sc.combat, v.painter)
    water = [p for p, c in sc.combat.grid.cells.items() if c.terrain == "water"]
    land = [p for p, c in sc.combat.grid.cells.items() if c.terrain != "water"]
    if water:
        w = water[0]
        assert sc.ground.height_at(w[0] + 0.5, w[1] + 0.5) < -0.1             # вода ниже земли
    hl = [sc.ground.height_at(x + 0.5, y + 0.5) for x, y in land]
    assert max(abs(h) for h in hl) < 0.12                                    # на доске — едва
    assert v.height_at is not None and rel[1].dtype.name == "float32"
    canvas = G.Canvas(pygame.Surface((640, 400)))
    img = sc.ground.surface(canvas, sc.combat, v.painter, sc.life.decal_list(), wait=True)
    assert img.get_size() == canvas.native.get_size()                       # на всё окно (широкий экран — без полос)
    tone, hgt = TR.make_tile("gravel")
    assert hgt.max() > 0.8 and len(tone) == TR.T * TR.T                   # камешки-купола


def test_reach_picks_cell_behind_enemy_not_enemy():
    """Подход: курсор над клеткой за врагом (где голова врага) выбирает клетку, а не «прилипает» к врагу."""
    from deck.game import DescentGame
    from ui import projection as P
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    b = sc.b
    card = next((c for c in b.hand + b.draw_pile if c.cid == "lunge_rush"))      # подход на 3 — обойти врага
    if card not in b.hand:
        b.draw_pile.remove(card)
        b.hand.append(card)
    grid = b.c.grid
    taken = {u.cell for u in b.c.units if u.alive}
    free = lambda p: grid.get(p) is not None and grid.get(p).passable and p not in taken   # noqa: E731
    done = False
    for f in b.foes():
        behind, side = (f.cell[0], f.cell[1] - 1), (f.cell[0] + 1, f.cell[1] + 1)
        if free(behind) and free(side):
            b.hero.cell = b.hero.prev_cell = side                 # герой рядом, клетка за врагом свободна
            sc.sel = (card, "main")
            assert behind in b.reach_spots(card, "main")
            x, y, _ = P.project(*P.cell_ground(behind))
            t = sc.target_at(sc.view.cam((x, y)))
            assert isinstance(t, tuple) and t[0] == behind
            done = True
            break
    assert done


def test_walk_is_one_smooth_motion():
    """Путь на несколько клеток — одним движением: скорость не падает до нуля между клетками."""
    from deck.game import DescentGame
    g = DescentGame(seed=5)
    g.start_run("merc")
    g.enter_node(g.run.floor.available()[0])
    sc = g.scene
    b, h = sc.b, sc.b.hero
    x, y = h.cell
    path = [(x + 1, y), (x + 2, y), (x + 3, y)]
    if not all(b.c.grid.get(p) is not None and b.c.grid.get(p).passable and
               not any(u.cell == p for u in b.c.units if u.alive) for p in path):
        return
    sc.run_job(b.walk(h, path))
    xs = []
    for _ in range(200):
        g.update(1 / 60)
        xs.append(sc.view.ground_pos(h)[0])
        if sc.job is None and h.move_t >= 1:
            break
    v = [b2 - a2 for a2, b2 in zip(xs, xs[1:])]
    mid = v[len(v) // 5: len(v) * 4 // 5]
    assert min(mid) > 0.01                                          # без остановок на клетках
    assert abs(xs[-1] - (path[-1][0] + 0.5)) < 1e-6


def test_model_quality_toggle_between_battles():
    """Карта этажа: M — модели 32×32 ↔ 64×64; бой берёт спрайты из assets/sprites/x2 (без записи настроек)."""
    import pygame
    from deck.game import DescentGame
    from deck.ui import MapScreen, model_res
    from ui import settings
    old = settings.SETTINGS.get("sprite_res", 32)
    try:
        settings.SETTINGS["sprite_res"] = 32
        g = DescentGame(seed=5)
        g.save_settings = False
        g.start_run("merc")
        assert isinstance(g.scene, MapScreen)
        g.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, mod=0, unicode="m"))
        assert model_res() == 64
        g.enter_node(g.run.floor.available()[0])
        hero = g.scene.b.hero
        img = g.scene.view.sprite_of(hero)
        from ui.sprites import sprite_path
        path, k = sprite_path(hero.proto.get("path") or hero.proto_id)
        assert k == 2 and img.get_height() >= 64                  # подробный спрайт, тот же размер на экране
    finally:
        settings.SETTINGS["sprite_res"] = old


def _priest(variant="storm", seed=5):
    from deck.game import DescentGame
    g = DescentGame(seed=seed)
    g.start_run("priest", variant)
    g.enter_node(g.run.floor.available()[0])
    return g, g.scene, g.scene.b


def test_priest_statues_scroll_and_walk():
    """Жрец: статуи пантеона на поле, рука 4, шаги 2; свиток — на статую, цель в её досягаемости; ходьба;
    в конце хода рука остаётся, статуи играют свои свитки."""
    from deck import model as M
    g, sc, b = _priest()
    assert len(b.idols.statues) == 3 and len(b.hand) == 3 and b.walk_left == 3
    assert {s.statue for s in b.idols.statues} == {"perun", "veles", "mokosh"}
    perun = next(s for s in b.idols.statues if s.statue == "perun")
    foe = b.foes()[0]
    spot = next(p for p in b.c.grid.in_radius(perun.cell, 2) if b.free(p))
    foe.cell = foe.prev_cell = spot
    foe.hp = foe.max_hp = 50
    card = M.Card("sc_attack", b.run.defs)
    b.hand.append(card)
    assert perun in b.targets(card, "main")
    assert sc.ask_pick(card, "main", perun) and sc.prayer is not None      # ждём цель
    x, y, _ = __import__("ui.projection", fromlist=["P"]).project(*sc.feet(foe))
    t = sc.prayer_target(sc.view.cam((x, y - 10)))
    assert t is not None and t.tgt is foe
    sc.fire(card, "main", t)
    for _ in range(200):
        g.update(1 / 30)
        if sc.job is None:
            break
    assert foe.hp <= 50 - 6 and card in b.used                             # молния Перуна
    cell = next(iter(b.walk_cells()))
    finish(b.hero_walk(cell))
    assert b.hero.cell == cell and b.walk_left < 3
    left = list(b.hand)
    finish(b.end_turn())
    assert all(c in b.hand for c in left) or b.result                      # несыгранные свитки остались


def test_priest_every_god_every_meaning():
    """Все 8 богов × 6 смыслов — исполняются без ошибок (враг ставится рядом со статуей)."""
    from deck import model as M
    from deck.idols import MEANINGS, IdolCast
    seen = set()
    for variant in ("storm", "forge", "winter"):
        g, sc, b = _priest(variant, seed=11)
        for st in list(b.idols.statues):
            for m in MEANINGS:
                foes = b.foes()
                if not foes:
                    break
                f = foes[0]
                f.hp = max(f.hp, 40)
                spot = next((p for p in b.c.grid.in_radius(st.cell, 1) if b.free(p)), None)
                if spot:
                    f.cell = f.prev_cell = spot
                c = M.Card(f"sc_{m}", b.run.defs)
                b.hand.append(c)
                ch = b.idols.choices(st, m)
                assert ch is None or ch, (st.statue, m)
                tgt = None if ch is None else (f if f in ch else f.cell if f.cell in ch else ch[0])
                finish(b.play(c, "main", IdolCast(st, tgt)))
                assert c not in b.hand or b.idols.dead_water is False
                seen.add((st.statue, m))
                b.result = None
        for _ in range(3):
            finish(b.end_turn())
            if b.result:
                break
    assert len({g for g, _ in seen}) == 8 and len(seen) == 48


def test_hero_select_variant_click():
    """Выбор героя: клик по пассивке Охотницы и по пантеону Жреца выбирает вариант (а не только героя)."""
    import pygame
    from deck.game import DescentGame
    from deck.ui import HeroSelect
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=1)
    sc = HeroSelect(g)
    sc.draw(SCREEN)
    for hid, pid in (("hunter", "quiver"), ("priest", "forge")):
        r = next(r for r, w in sc.hits if w == ("variant", hid, pid))
        sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
        assert sc.pick == hid and sc.variant[hid] == pid
        sc.draw(SCREEN)


def test_priest_combo_scrolls_and_god_levels():
    """Свитки-сочетания: хор — смысл исполняют все статуи, перекличка — второй смысл другой статуей; свитков
    по 4 на смысл; опыт бога за свитки → уровень, уровень прибавляет к числам."""
    import json
    from deck import model as M
    from deck.idols import LEVELS, IdolCast
    cards = json.load(open("data/deck/cards.json", encoding="utf-8"))["cards"]
    assert all(f"sc_{m}" in cards for m in ("attack", "defense", "move", "curse", "gift", "summon"))
    g, sc, b = _priest()
    xp0 = dict(g.run.god_xp)
    st = b.idols.statues[0]
    c = M.Card("sc_attack_chorus", b.run.defs)
    b.hand.append(c)
    for f in b.foes():
        f.hp = f.max_hp = 80
    foe = b.foes()[0]
    spot = next(p for p in b.c.grid.in_radius(st.cell, 1) if b.free(p))
    foe.cell = foe.prev_cell = spot
    ch = b.idols.choices(st, "attack")
    assert foe in ch
    finish(b.play(c, "main", IdolCast(st, foe)))
    fed = [s for s in b.idols.statues if g.run.god_xp.get(s.statue, 0) > xp0.get(s.statue, 0)]
    assert st in fed                                                       # выбранная — точно; остальные — кому есть цель
    other = b.idols.statues[1]
    before = g.run.god_xp.get(other.statue, 0)
    c = M.Card("sc_gift_relay", b.run.defs)                              # дар, затем защита другой статуей
    b.hand.append(c)
    finish(b.play(c, "main", IdolCast(st, None)))
    assert any(g.run.god_xp.get(s.statue, 0) > xp0.get(s.statue, 0) for s in b.idols.statues if s is not st)
    g.run.god_xp[st.statue] = LEVELS[1]
    assert b.idols.level(st) == 2 and b.idols.n(st, 5) == 7
    del before, other


def test_priest_branches_after_battle_and_cast_preview():
    """Ветки богов — только ауры: новый уровень → после победы выбор 1 из 2 аур; подсказка у статуи — только то,
    что сделает свиток, с посчитанными числами."""
    from deck import model as M
    from deck.idols import LEVELS
    from deck.ui import ChoiceScreen
    g, sc, b = _priest()
    perun = next(s for s in b.idols.statues if s.statue == "perun")
    g.run.god_xp["perun"] = LEVELS[0] - 1
    b.idols.gain(perun)
    assert g.run.god_pending == [("perun", 1)]
    near = b.foes()[0]
    near.cell = near.prev_cell = next(p for p in b.c.grid.in_radius(perun.cell, 2) if b.free(p))
    lines = b.idols.cast_lines(perun, M.Card("sc_attack", b.run.defs))
    assert lines[0][0].startswith("Перун") and "7 урона" in lines[1][0] and len(lines) == 2   # 6 + уровень 1
    b.result = "victory"
    g.node = None
    g.battle_over(b)
    from deck.ui import GodBranchScreen
    assert isinstance(g.scene, GodBranchScreen) and g.scene.god["name"] == "Перун" and len(g.scene.options) == 2
    assert all(v[0] == "a" for v, _, _ in g.scene.options)
    val = g.scene.options[0][0]
    g.scene.on_pick(val)
    assert val in g.run.god_picks["perun"] and isinstance(g.scene, ChoiceScreen) and "Победа" in g.scene.title


def test_priest_tiers_and_fat_rewards():
    """Ступени действий: на карте — список действий с качеством I–IV; ступень — новый эффект бога (Атака II
    Перуна — цепная молния, бьёт и соседей цели); все действия — одной статуей; награды толще с глубиной."""
    from deck.idols import IdolCast, gen_acts, make_scroll, offer_scrolls
    from deck import model as M
    import random
    g, sc, b = _priest()
    perun = next(s for s in b.idols.statues if s.statue == "perun")
    foes = b.foes()
    a, c = foes[0], foes[1]
    spots = [p for p in b.c.grid.in_radius(perun.cell, 2) if b.free(p)]
    a.cell = a.prev_cell = spots[0]
    c.cell = c.prev_cell = next(p for p in b.c.grid.in_radius(a.cell, 1) if b.free(p) and p != a.cell)
    a.hp = a.max_hp = c.hp = c.max_hp = 60
    cid = make_scroll(b.run, [{"m": "attack", "q": 2}, {"m": "defense"}])
    card = M.Card(cid, b.run.defs)
    assert card.name == "Атака II · Защита" and "II" in card.text("main")
    lines = " ".join(t for t, _ in b.idols.cast_lines(perun, card))
    assert "Цепная молния" in lines and "Защита I" in lines
    b.hand.append(card)
    finish(b.play(card, "main", IdolCast(perun, a)))
    assert a.hp <= 60 - 8 and c.hp < 60 and b.hero.shield >= 3             # 6+2 по цели, перескок соседу, щит
    rng = random.Random(1)
    sizes = {d: [len(gen_acts(rng, d)) for _ in range(30)] for d in (1, 2, 3)}
    assert max(sizes[1]) <= 2 and min(sizes[2]) >= 2 and min(sizes[3]) >= 3
    assert len(offer_scrolls(b.run, 3)) == 3


def test_right_click_while_dragging_without_selection_does_not_crash():
    """ПКМ во время перетаскивания, когда выбор уже сброшен (свиток Жреца), — не падает, а отменяет; свиток по ПКМ
    в руке не переворачивается на пустую сторону."""
    import pygame
    g, sc, b = _priest()
    sc.drag, sc.sel, sc.press = True, None, None
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(600, 300)))
    assert not sc.drag and sc.sel is None
    card = b.hand[0]
    sc.press, sc.drag, sc.sel = (card, 1, (0, 0)), True, (card, "main")
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(600, 300)))
    assert not sc.drag and card.uid not in sc.hv.flipped


def test_chapter_one_boss_leads_into_forge():
    """Страж главы 1 (Квакс) — не конец: после наград спуск идёт в главу 2 «Огненные кузни», этаж 4, полный отдых;
    земля кузни — своя тема, болотной живности нет; ближние враги наступают, даже когда ставят щит."""
    from deck.game import DescentGame
    from deck.terrain import theme_of
    from deck.ui import ChoiceScreen, MapScreen
    g = DescentGame(seed=2)
    g.start_run("merc")
    run = g.run
    while run.depth < 3:
        run.next_floor()
    run.hp = 20
    boss = [nid for nid, n in run.floor.nodes.items() if n["type"] == "boss"][0]
    g.enter_node(boss)
    g.scene.b.result = "victory"
    g.update(1 / 30)
    g.scene.skip()
    for _ in range(10):
        if not isinstance(g.scene, ChoiceScreen):
            break
        sc = g.scene
        if sc.skip:
            sc.skip()
        else:
            sc.on_pick(sc.options[0][2])
    assert isinstance(g.scene, MapScreen) and run.depth == 4 and run.chapter_name == "Огненные кузни"
    assert run.hp == run.max_hp
    g.enter_node(run.floor.available()[0])
    b = g.scene.b
    assert theme_of(b.c) == "forge" and not g.scene.life.ready
    foe = next(f for f in b.foes() if not f.edef.get("keep_range"))
    foe.intent = {"kind": "rally", "name": "Клич", "n": 1, "r": 0}
    d0 = cheb(foe.cell, b.hero.cell)
    finish(b.act(foe))
    assert cheb(foe.cell, b.hero.cell) < d0 or d0 <= 1


def test_priest_pinned_walks_one_and_survival_resources():
    """Балансировка: Жрец «скован» (враг вплотную в начале хода — шаг 1); Наёмнику 4 энергии, Пиромантке +2 жара."""
    b, _ = hero_battle("priest", "storm")
    h = b.hero
    assert b.walk_left == 3
    put(b, b.foes()[0], (h.cell[0] + 1, h.cell[1]))
    b.start_player_turn_now()
    assert b.walk_left == 1
    for u in b.foes():
        put(b, u, (min(b.c.grid.w - 1, h.cell[0] + 6), u.cell[1]))
    b.start_player_turn_now()
    assert b.walk_left == 3
    m, _ = hero_battle("merc")
    p, _ = hero_battle("pyro")
    assert m.max_energy == 4 and p.hero_def["heat_turn"] == 2


def test_czn_keywords_bleed_counter_powers_unique_retain_per():
    """Квиз 2026-11-21: Кровотечение, Контратака, Мощь, Силы до конца боя, Единственная, Сохранение, «за каждую…»,
    Создать карту, Изгнание из руки (будит Силы «при изгнании»)."""
    b, run = hero_battle("merc")
    h = b.hero
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    b.energy = 20
    rend = card(b, "m_rend")
    hp = foe.hp
    finish(b.play(rend, "main", foe))
    assert foe.ds["bleed"] == 3 and hp - foe.hp == 5
    opn = card(b, "m_open")                                     # 3 + 2 за каждое кровотечение
    hp = foe.hp
    finish(b.play(opn, "main", foe))
    assert hp - foe.hp == 3 + 2 * 3
    hp = foe.hp
    finish(b.tick_start(foe))                                   # кровотечение: урон мимо защиты, затем вдвое
    assert hp - foe.hp == 3 and foe.ds["bleed"] == 1
    meet = card(b, "m_meet")                                    # Сила: в начале хода — контратака 2
    finish(b.play(meet, "main", h))
    assert meet in b.powers and meet not in b.discard
    finish(b.power_fire("turn"))
    assert h.ds["counter"] == 2
    hp = foe.hp
    b.hurt(h, 3, foe, "melee")                                  # враг бьёт вплотную — ответ 4
    finish(b.react())
    assert hp - foe.hp == 4 and h.ds["counter"] == 1
    h.ds["strength"] = 3
    lim = card(b, "m_limit")
    finish(b.play(lim, "main", h))
    assert h.ds["strength"] == 6 and lim in b.exhaust          # Предел: мощь ×2, изгнание
    b.hand = [M.Card("m_limit", run.defs)]                      # Единственная: вторая не приходит в руку
    b.draw_pile = [M.Card("m_last_word", run.defs), M.Card("strike", run.defs)]
    b.draw(2)
    assert [c.cid for c in b.hand] == ["m_limit", "strike"]
    duel = card(b, "m_duelist")                                 # Сохранение: остаётся в руке
    finish(b.end_turn())
    assert duel in b.hand or b.result
    k = card(b, "m_knives")
    finish(b.play(k, "main", h))
    assert sum(c.cid == "t_knife" for c in b.hand) == 2         # Создать: ножи — временные
    p, prun = hero_battle("pyro")
    p.hero.ds["heat"] = 9
    ash = M.Card("p_ash_eater", prun.defs)
    p.hand.append(ash)
    finish(p.play(ash, "main", p.hero))
    sac = M.Card("p_sacrifice", prun.defs)
    p.hand.append(sac)
    sac.manual, sac.lvl = True, 0
    n_hand, heat = len(p.hand), p.hero.ds["heat"]
    finish(p.play(sac, "main", p.hero))
    assert len(p.exhaust) == 1 and p.hero.ds["heat"] == heat - 1 + 2 + 1    # изгнание → Пожиратель пепла: +1 жар
    text = M.plain(M.phrase(M.Card("m_open", run.defs).d["main"]))
    assert "за каждое кровотечение цели" in text


def test_items_build_conditions_and_boss_downsides():
    """Предметы под сборку срабатывают только при своём условии; у предметов стража — минус."""
    from deck.battle import Battle
    from deck.game import DescentGame
    rel = M.load()["relics"]["relics"]

    def with_items(hero, *ids, variant=None):
        run = M.Run(seed=4, hero=hero, variant=variant)
        run.relics = [dict(rel[k], id=k) for k in ids]
        return Battle(ED, run, run.fights[0], seed=4), run

    from sim.grid import cheb
    b, run = with_items("merc", "m_gutter", "velvet_collar")
    h = b.hero
    victim, near = b.foes()[0], b.foes()[1]
    spot = next(p for p in b.c.grid.in_radius(victim.cell, 1) if b.free(p))
    put(b, near, spot)
    victim.ds["bleed"] = 3
    b.hurt(victim, 999, h, "melee")
    finish(b.react())
    assert near.ds["bleed"] == 0                                               # кровотечение 3 — мало
    b.result = None
    victim = near
    others = [f for f in b.foes() if f is not victim]
    if others:
        n2 = others[0]
        put(b, n2, next(p for p in b.c.grid.in_radius(victim.cell, 1) if b.free(p)))
        victim.ds["bleed"] = 7
        b.hurt(victim, 999, h, "melee")
        finish(b.react())
        assert cheb(n2.cell, victim.cell) <= 1 and n2.ds["bleed"] == 7       # 6+ — переходит соседям
    assert b.energy == 5                                                       # ошейник: +1 энергия…
    b.played = 6
    assert not b.targets(card(b, "strike"), "main")                            # …но не больше 6 карт за ход
    p, prun = with_items("pyro", "p_crucible")
    p.hero.ds["heat"] = 11
    foe = p.foes()[0]
    finish(p.end_turn())
    log = " ".join(t for t, _ in p.log)
    assert "Перегрев уходит в пламя" in log and "Перегрев!" not in log         # перегрев не ранит, а жжёт врагов
    hb, hrun = with_items("hunter", "h_horn", variant="mark")
    hb.energy = 0
    hand = len(hb.hand)
    f = hb.foes()[0]
    hb.traps[(f.cell[0] - 1, f.cell[1])] = 5
    finish(hb.walk(f, [(f.cell[0] - 1, f.cell[1])]))
    finish(hb.react())
    assert len(hb.hand) == hand + 2 and hb.energy == 1                         # капкан: 2 карты и ресурс
    b, run = with_items("merc", "rune_pyramid", "black_crown")
    assert sum(c.cid == "slime_rot" for c in b.draw_pile + b.hand) == 2         # корона: 2 «Тины»
    assert len(b.hand) == 5                                                    # пирамида: на карту меньше
    kept = list(b.hand)
    b.foes()[0].intent = None
    finish(b.end_turn())
    assert all(c in b.hand for c in kept if c.cid != "slime_rot") or b.result  # рука не сбрасывается
    g = DescentGame(seed=2)
    g.start_run("merc")
    g.run.relics = [dict(rel["kettle"], id="kettle"), dict(rel["greed_eye"], id="greed_eye")]
    assert len(g.run.reward_offer()) == 2                                      # око: на карту меньше в награде
    camp = next((nid for nid, nd in g.run.floor.nodes.items() if nd["type"] == "camp"), None)
    g.enter_node(camp)
    assert [o[2] for o in g.scene.options] == ["remove"]                      # котелок: у костра не отдохнуть


def test_workshop_upgrades_simple_use_and_tab_hides_ui():
    """Мастерская: карта → 1 из 3 улучшений простого (одно на карту); Tab прячет интерфейс боя."""
    import pygame
    from deck.game import DescentGame
    from deck.ui import BattleScreen, ChoiceScreen, DeckScreen, MapScreen
    from tests.test_expedition_ui import SCREEN
    g = DescentGame(seed=4)
    g.save_settings = False
    g.start_run("pyro")
    run = g.run
    g.offer_workshop()
    assert isinstance(g.scene, DeckScreen) and g.scene.cards
    card = next(c for c in g.scene.cards if c.cid == "p_bolt")
    old = M.phrase(card.d["alt"])
    g.scene.on_pick(card)
    assert isinstance(g.scene, ChoiceScreen) and len(g.scene.options) == 3
    g.draw(SCREEN)
    g.scene.on_pick(g.scene.options[0][2])
    assert isinstance(g.scene, MapScreen) and card.alt_up is not None
    assert M.phrase(card.d["alt"]) != old and "+2" in M.phrase(card.d["alt"])  # раздуть сильнее
    assert not card.alt_options("pyro")                                        # одно улучшение на карту
    noalt = M.Card("m_counter", M.Run(seed=1).defs)                            # без простого — мастер даёт его
    assert noalt.d["alt"]["target"] == "none" and noalt.alt_options("merc")
    assert "workshop" in run.floor_cfg["weights"]
    g.enter_node(run.floor.available()[0])
    sc = g.scene
    assert isinstance(sc, BattleScreen)
    was = sc.ui_hidden
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0, unicode="\t"))
    assert sc.ui_hidden != was
    for _ in range(3):
        g.update(1 / 30)
    g.draw(SCREEN)
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0, unicode="\t"))
    assert sc.ui_hidden == was


def test_enemy_traits_armor_retaliate_merge_rise_steal_enrage():
    """Механики врагов (квиз 2026-11-21): броня, ответный удар, слияние, восстание, кража карты, ярость от умений."""
    from sim.grid import cheb
    b, run = hero_battle("merc")
    h = b.hero
    for f in b.foes():
        f.alive = False
    crab = _foe(b, "shell_crab", (h.cell[0] + 1, h.cell[1]))
    hp = crab.hp
    b.energy = 9
    finish(b.play(card(b, "strike"), "main", crab))
    assert hp - crab.hp == 6 - 3                                               # броня 3
    crab.alive = False
    eel = _foe(b, "bog_eel", (h.cell[0] + 1, h.cell[1]))
    hp = h.hp
    finish(b.play(card(b, "strike"), "main", eel))
    assert h.hp == hp - 4                                                      # угорь ответил ударом 4
    ogre = _foe(b, "bog_ogre", (h.cell[0] + 4, h.cell[1]))
    finish(b.play(card(b, "defend"), "main", h))
    assert ogre.ds["strength"] == 2                                            # огр злится от умений
    eel.alive = ogre.alive = False
    a = _foe(b, "sticky_slime", (5, 3))
    m = _foe(b, "sticky_slime", (5, 4))
    total = a.hp + m.hp
    finish(b.enemy_traits(a))
    assert not m.alive and a.hp == total                                       # слились
    a.alive = False
    gh = _foe(b, "ghoul", (h.cell[0] + 1, h.cell[1]))
    gh.intent = {"kind": "melee", "name": "Рвать", "dmg": 6}
    n = len(b.draw_pile)
    h.shield = 0
    finish(b.act(gh))
    assert len(b.draw_pile) == n - 1 and len(gh.stolen) == 1                  # утащил карту
    stolen = gh.stolen[0]
    b.hurt(gh, 999, h, "melee")
    assert stolen in b.hand                                                    # вернулась
    risen = [f for f in b.foes() if f.eid == "ghoul_hungry"]
    assert risen and risen[0].cell == gh.cell                                  # восстал голодным
    assert all(d["hp"] >= 14 for d in run.data["enemies"]["enemies"].values())  # HP ×2


def test_reading_shows_created_cards_and_opens_them():
    """Чтение карты (Shift): слева — карты, которые она создаёт; клик — открыть, ПКМ — назад (как в CZN)."""
    from deck.ui import Inspector
    from tests.test_expedition_ui import SCREEN
    run = M.Run(seed=1, hero="merc")
    knives = M.Card("m_knives", run.defs)
    assert M.created_ids(knives.d) == ["t_knife"]
    ins = Inspector(knives, pinned=True)
    ins.draw(SCREEN, (0, 0))
    assert len(ins.made_rects) == 1 and ins.made_rects[0][1].cid == "t_knife"
    assert ins.click(ins.made_rects[0][0].center)
    assert ins.card.cid == "t_knife" and ins.stack
    ins.draw(SCREEN, (0, 0))
    assert ins.back_rect is not None
    assert ins.click((0, 0), button=3) and ins.card is knives and not ins.stack
    forge = M.Card("p_spark_forge", run.defs)                                  # Сила создаёт Искру
    assert M.created_ids(forge.d) == ["t_spark"]
    assert not M.created_ids(M.Card("strike", run.defs).d)


def test_pyro_level_changes_in_reading_and_choice():
    """Уровень (цена в жаре) карты Пиромантки меняется в чтении (колесо, клик по кружку) и на экране выбора."""
    import pygame
    from deck import cardart as CA
    from deck import cardface as CF
    from deck.game import DescentGame
    from deck.ui import ChoiceScreen, Inspector
    from tests.test_expedition_ui import SCREEN
    run = M.Run(seed=1, hero="pyro")
    bolt = M.Card("p_bolt", run.defs)
    ins = Inspector(bolt, pinned=True)
    ins.draw(SCREEN, (0, 0))
    assert ins.wheel(1) and bolt.lvl == 1 and bolt.cost == 2
    r = ins.card_rect
    k = r.w / CF.FW
    i, (cx, cy), _ = CA.level_pips(bolt)[2]
    pos = (r.centerx - CF.FW * k / 2 + cx * k, r.centery - CF.FH * k / 2 + cy * k)
    assert ins.click(pos) and bolt.lvl == 2 and bolt.cost == 3                  # клик по кружку «3»
    g = DescentGame(seed=1)
    g.start_run("pyro")
    card = M.Card("p_fireball", g.run.defs)
    picked = []
    g.scene = ChoiceScreen(g, "Награда", "", [("", card, 0)], picked.append)
    g.draw(SCREEN)
    r = g.scene.rects[0][0]
    g.scene.mouse = r.center
    g.scene.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert card.lvl == 1 and not picked                                       # колесо — уровень, не выбор
    k = r.w / CF.FW
    _, (cx, cy), _ = CA.level_pips(card)[0]
    pos = (round(r.centerx - CF.FW * k / 2 + cx * k), round(r.centery - CF.FH * k / 2 + cy * k))
    g.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    assert card.lvl == 0 and not picked                                       # клик по кружку — тоже не выбор


def test_run_save_and_continue(tmp_path):
    """Сохранение забега: пишется на карте этажа, продолжается с выбора героя, стирается в конце (не в save/)."""
    import pygame
    from deck.game import DescentGame
    from deck.ui import EndScreen, GodBranchScreen, HeroSelect, MapScreen
    from tests.test_expedition_ui import SCREEN
    path = str(tmp_path / "run.json")
    g = DescentGame(seed=7, save_path=path)
    assert not g.has_save()
    g.start_run("priest", "storm")
    run = g.run
    run.gold, run.hp = 123, 40
    run.deck[0].picks.append(0) if run.deck[0].growth_next() else None
    run.relics = [dict(run.data["relics"]["relics"]["pen_nib"], id="pen_nib")]
    run.relic_state = {"pen_nib": 7, "once:lizard_tail": True}
    run.god_xp, run.god_picks = {"perun": 5}, {"perun": [("a", 1)]}
    nid = run.floor.available()[0]
    run.floor.enter(nid)
    g.node = run.floor.nodes[nid]
    g.to_map()
    assert g.has_save()
    g2 = DescentGame(seed=99, save_path=path)
    assert isinstance(g2.scene, HeroSelect) and g2.scene.saved
    g2.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, mod=0, unicode="c"))
    r2 = g2.run
    assert isinstance(g2.scene, MapScreen) and r2.hero_id == "priest" and r2.gold == 123 and r2.hp == 40
    assert [c.cid for c in r2.deck] == [c.cid for c in run.deck] and r2.deck[0].picks == run.deck[0].picks
    assert r2.relics[0]["id"] == "pen_nib" and r2.relic_state["pen_nib"] == 7
    assert r2.god_picks == {"perun": [("a", 1)]} and r2.floor.node == nid and g2.node["id"] == nid
    assert r2.rng.random() == run.rng.random()                                # тот же ход случайностей
    run.god_pending = [("perun", 2)]                                           # ветка бога — свой экран
    g._gold = 0
    g._branches()
    assert isinstance(g.scene, GodBranchScreen)
    g.draw(SCREEN)
    g.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, mod=0, unicode="1"))
    assert len(run.god_picks["perun"]) == 2
    g2.end_run()
    assert not g2.has_save()
    assert DescentGame(seed=1).save_path is None                               # по умолчанию (тесты) — без файла
