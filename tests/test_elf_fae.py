"""Эльф: феи, пороги, растения, прививки, звери и сборка оружия."""
import pygame

from deck import model as M
from deck.battle import finish
from deck.game import DescentGame
from deck.ui import BattleScreen, Inspector, full_card_text
from test_deck import card, hero_battle, put
from tests.test_expedition import ED


def test_elf_starts_with_fae_starter_and_mechanic():
    b, run = hero_battle("elf")
    assert b.mech == "fae"
    assert run.hero_name == "Эльф"
    assert [c.cid for c in run.deck] == [
        "e_basic_attack", "e_basic_attack", "e_basic_attack",
        "e_basic_defense", "e_basic_defense", "e_basic_defense",
        "e_basic_move", "e_basic_move", "e_call_fae", "e_firefly",
        "e_moon_arrow", "e_moon_shield",
    ]
    assert b.hero.ds["fae"] == 0


def test_elf_insights_have_five_named_distinct_branches():
    import json
    run = M.Run(seed=1, hero="elf")
    for cid, d in run.defs.items():
        if not cid.startswith("e_") or d.get("token"):
            continue
        opts = d["growth"][0]["options"]
        assert len(opts) == 5, cid
        assert all(not o["label"].startswith("mod_") for o in opts), cid
        assert len({json.dumps(o["main"], sort_keys=True, ensure_ascii=False) for o in opts}) == 5, cid


def test_elf_fae_gain_and_burn_use_dedicated_text_tokens():
    run = M.Run(seed=1, hero="elf")
    call = M.Card("e_call_fae", run.defs)
    arrow = M.Card("e_moon_arrow", run.defs)
    shield = M.Card("e_moon_shield", run.defs)
    assert "^+2" in M.phrase(call.d["main"])
    assert "Усиление" not in M.card_extras(call.d)            # генератор не тратит фей
    assert "^-3" in M.card_extras(arrow.d)
    assert "^-2" in M.card_extras(shield.d)


def test_full_card_text_keeps_long_descriptions_and_extras():
    run = M.Run(seed=1, hero="elf")
    txt = full_card_text(M.Card("e_thorn_seed", run.defs))
    assert "Усиление" in txt and "созревании" in txt
    assert "…" not in txt
    assert txt.endswith(".")


def test_full_description_panel_only_for_clipped_cards():
    run = M.Run(seed=1, hero="elf")
    long_card = Inspector(M.Card("e_thorn_seed", run.defs), pinned=True)
    short_card = Inspector(M.Card("e_moon_arrow", run.defs), pinned=True)
    assert any(name == "Полное описание" for name, _, _ in long_card.panels())
    assert not any(name == "Полное описание" for name, _, _ in short_card.panels())


def test_fae_does_not_scale_card_draw():
    run = M.Run(seed=1, hero="elf")
    fae_conditions = {"fae", "fae_min", "fae_before"}
    for cid, d in run.defs.items():
        if not cid.startswith("e_") or d.get("token"):
            continue
        mains = [d["main"]] + [o["main"] for tier in d.get("growth", []) for o in tier.get("options", [])]
        for main in mains:
            assert "draw" not in (main.get("fae_bonus") or {}), cid
            for cond in main.get("if", []):
                if (cond.get("when") or {}).get("k") in fae_conditions:
                    assert all(op.get("op") != "draw" for op in cond.get("do", [])), cid


def test_plant_cards_have_exhaust_2_or_3_by_rarity():
    run = M.Run(seed=1, hero="elf")
    for cid, d in run.defs.items():
        if "plant" not in M.card_tag_ids(d):
            continue
        want = "exhaust_3" if d.get("rarity") == 3 else "exhaust_2"
        assert want in M.card_tag_ids(d), cid
    assert "Изгнание 2" in full_card_text(M.Card("e_moon_moss", run.defs))


def test_plant_cards_exhaust_after_their_limit():
    b, _ = hero_battle("elf")
    b.energy = 99
    seed = card(b, "e_thorn_seed")
    for i in range(2):
        spots = b.targets(seed, "main")
        finish(b.play(seed, "main", spots[0]))
        if i == 0:
            assert seed not in b.exhaust
            b.hand.append(seed)
    assert seed in b.exhaust

    b, _ = hero_battle("elf")
    b.energy = 99
    tree = card(b, "e_world_tree")
    for i in range(3):
        spots = b.targets(tree, "main")
        finish(b.play(tree, "main", spots[0]))
        if i < 2:
            assert tree not in b.exhaust
            b.hand.append(tree)
    assert tree in b.exhaust


def test_card_face_cache_does_not_mix_text_and_underlay():
    from deck import cardart
    run = M.Run(seed=1, hero="elf")
    card = M.Card("e_moon_moss", run.defs)
    cardart._faces.clear()
    under = cardart.compose(card, _under=True)
    full = cardart.compose(card)
    assert under is not full


def test_generator_cards_do_not_burn_fae_at_the_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    h.ds["fae"] = 6
    finish(b.play(card(b, "e_firefly"), "main", h))
    assert h.ds["fae"] == 8                                   # +2, траты нет


def test_elf_uses_its_own_high_detail_hero_sprite():
    b, run = hero_battle("elf")
    assert run.hero.get("art_sprite") == "elf"
    assert getattr(b.hero, "art_sprite", b.hero.proto.get("path")) == "elf"
    from ui import settings as S
    from ui.sprites import SpriteBank
    old = S.SETTINGS.get("sprite_res", 32)
    try:
        S.SETTINGS["sprite_res"] = 128
        img = SpriteBank().get(["elf"], "elf", (200, 200, 200))
        assert img.get_height() == 64 and img.get_width() > 0
        game = DescentGame(seed=1, gd=ED)
        game.run = run
        view = BattleScreen(game, b).view
        assert view.sprite_of(b.hero, full_resolution=True).get_size() == (128, 128)
    finally:
        S.SETTINGS["sprite_res"] = old


def test_elf_skips_the_starter_deck_picker():
    game = DescentGame(seed=1, gd=ED)
    game.open_starter("elf")
    assert game.run is not None and game.run.hero_id == "elf"
    assert game.scene.__class__.__name__ == "MapScreen"


def test_basic_elf_cards_are_stronger_and_scale_with_fae():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    attack = card(b, "e_basic_attack")
    hp = foe.hp
    finish(b.play(attack, "main", foe))
    assert hp - foe.hp == 5
    h.ds["fae"] = 4
    attack = card(b, "e_basic_attack")
    hp = foe.hp
    finish(b.play(attack, "main", foe))
    assert hp - foe.hp == 7                               # 5 + 2 пассивно; порога 6 нет
    assert h.ds["fae"] == 4

    h.ds["fae"] = 0
    defense = card(b, "e_basic_defense")
    finish(b.play(defense, "main", h))
    assert h.shield == 6
    h.ds["fae"] = 4
    defense = card(b, "e_basic_defense")
    finish(b.play(defense, "main", h))
    assert h.shield == 14                                 # 6 + 8 пассивно; траты нет
    assert h.ds["fae"] == 4
    assert b.move_value(card(b, "e_basic_move").d["main"], "step") == 3


def test_basic_attack_and_defense_burn_fae_at_the_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    h.ds["fae"] = 6
    hp = foe.hp
    finish(b.play(card(b, "e_basic_attack"), "main", foe))
    assert hp - foe.hp == 17                                  # 5 + 3 пассивно + 3×3
    assert h.ds["fae"] == 3

    h.ds["fae"] = 6
    before = h.shield
    finish(b.play(card(b, "e_basic_defense"), "main", h))
    assert h.shield - before == 13                            # 6 + 3 пассивно + 2×2
    assert h.ds["fae"] == 4


def test_fae_gain_event_is_drawn_by_battle_screen_without_crashing():
    game = DescentGame(seed=1, gd=ED)
    battle, game.run = hero_battle("elf")
    screen = BattleScreen(game, battle)
    battle.gain_fae(2)
    screen.update(1 / 60)
    assert battle.hero.ds["fae"] == 2
    assert len(screen.fae_flight.arrivals) == 2


def test_fae_flight_tracks_gains_spends_and_thresholds(monkeypatch):
    from deck import skin
    from ui import settings

    game = DescentGame(seed=1, gd=ED)
    battle, game.run = hero_battle("elf")
    screen = BattleScreen(game, battle)
    screen.pump()
    battle.gain_fae(5)
    battle.gain_fae(4)
    battle.spend_fae(3)
    screen.pump()
    flight = screen.fae_flight
    assert len(flight.arrivals) == battle.garden.fae() == 6
    assert len(flight.departures) == 3
    assert [threshold for _, threshold in flight.waves] == [6, 8]
    assert flight.waves[0][0] < flight.waves[1][0]
    flight.update(.04, (150, 160))
    flight.update(.04, (154, 160))
    assert flight.trail.x < 0
    flight.update(1.0, (154, 160))
    assert not flight.departures and not flight.waves
    hero = pygame.Rect(120, 100, 64, 64)
    for theme in ("grove", "moon"):
        monkeypatch.setitem(settings.SETTINGS, "elf_theme", theme)
        sk = skin.use("elf")
        frames = [sk.art(f"fae_flight_{i}") for i in range(4)]
        assert len({pygame.image.tobytes(frame, "RGBA") for frame in frames}) == 4
        surf = pygame.Surface((300, 210), pygame.SRCALPHA)
        flight.draw(surf, sk, hero, -1)
        assert surf.get_bounding_rect()
        assert not surf.subsurface(hero.inflate(-20, -8)).get_bounding_rect()
        halo = flight._halo(sk, 30, False)
        assert 0 < halo.get_at((5, 15)).a < halo.get_at((15, 15)).a


def test_elf_hud_themes_switch_and_render_energy(monkeypatch):
    from deck import elf_ui, skin
    from ui import settings

    frames = []
    for theme in ("grove", "moon"):
        monkeypatch.setitem(settings.SETTINGS, "elf_theme", theme)
        elf = skin.use("elf")
        assert elf.variant == theme
        assert all(elf.art(name) is not None for name in ("panel", "button", "fairy", "bud", "orb", "orb_mask"))
        def frame(energy, t=0):
            surf = pygame.Surface((120, 134), pygame.SRCALPHA)
            elf_ui.draw_energy(surf, elf, 60, 48, energy, 3, t=t)
            return pygame.image.tobytes(surf.subsurface((12, 0, 96, 92)), "RGBA")

        snapshots = [frame(energy) for energy in range(4)]
        assert len(set(snapshots)) == 4
        assert frame(0, 1) == snapshots[0]
        assert frame(2, 1) != snapshots[2]
        assert frame(3, 1) != snapshots[3]
        frames.append(snapshots[2])
    assert frames[0] != frames[1]


def test_elf_hud_energy_level_eases_after_spend_and_refill(monkeypatch):
    game = DescentGame(seed=1, gd=ED)
    battle, game.run = hero_battle("elf")
    screen = BattleScreen(game, battle)
    monkeypatch.setattr(screen, "ready", lambda: True)
    assert screen.shown_energy == 1
    battle.energy = 0
    screen.update(1 / 60)
    assert 0 < screen.shown_energy < 1
    for _ in range(40):
        screen.update(1 / 60)
    assert screen.shown_energy == 0
    battle.energy = battle.max_energy
    screen.update(1 / 60)
    assert 0 < screen.shown_energy < 1
    for _ in range(40):
        screen.update(1 / 60)
    assert screen.shown_energy == 1


def test_fae_are_capped_and_excess_becomes_shield():
    b, _ = hero_battle("elf")
    b.gain_fae(12)
    assert b.hero.ds["fae"] == 10
    assert b.hero.shield == 2


def test_moon_arrow_scales_from_current_fae_and_has_line_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 5
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    arrow = card(b, "e_moon_arrow")
    hp = foe.hp
    finish(b.play(arrow, "main", foe))
    assert hp - foe.hp == 11                               # 6 + 5 пассивно; порог ещё не достигнут
    assert h.ds["fae"] == 5
    h.ds["fae"] = 6
    assert b.line_only(arrow.d["main"])


def test_moon_arrow_pierces_the_whole_line_at_the_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    first, second = b.foes()[:2]
    put(b, first, (h.cell[0] + 1, h.cell[1]))
    put(b, second, (h.cell[0] + 2, h.cell[1]))
    first.hp = first.max_hp = 200
    second.hp = second.max_hp = 200
    hp1, hp2 = first.hp, second.hp
    h.ds["fae"] = 6
    finish(b.play(card(b, "e_moon_arrow"), "main", first))
    assert hp1 - first.hp == 21 and hp2 - second.hp == 21
    assert h.ds["fae"] == 3

    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    first, second = b.foes()[:2]
    put(b, first, (h.cell[0] + 1, h.cell[1]))
    put(b, second, (h.cell[0] + 2, h.cell[1]))
    second.hp = second.max_hp = 200
    hp2 = second.hp
    h.ds["fae"] = 5
    finish(b.play(card(b, "e_moon_arrow"), "main", first))
    assert second.hp == hp2                                # до порога — только цель


def test_plant_grows_each_turn_and_matures():
    b, _ = hero_battle("elf")
    b.energy = 9
    seed = card(b, "e_thorn_seed")
    spots = b.targets(seed, "main")
    assert spots
    finish(b.play(seed, "main", spots[0]))
    plant = b.garden.plants[0]
    assert plant.growth == 0
    finish(b.end_turn())
    assert plant.growth == 1
    finish(b.end_turn())
    assert plant.growth == 2
    finish(b.end_turn())
    assert plant not in b.garden.plants


def test_attachment_gives_host_retain_and_triggers_after_main_card():
    b, _ = hero_battle("elf")
    h = b.hero
    host = card(b, "e_basic_attack")
    graft = card(b, "e_ivy_graft")
    finish(b.play(graft, "main", host))
    assert b.garden.attached(host)
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    finish(b.play(host, "main", foe))
    assert not b.garden.attached(host)
    assert b.attach_reveal is not None and b.attach_reveal[0].cid == "e_ivy_graft"
    assert h.ds["fae"] == 2
    assert h.shield >= 4


def test_blueprint_scatters_parts_and_assembles_them_from_hand():
    b, _ = hero_battle("elf")
    b.energy = 9
    blueprint = card(b, "e_moon_scythe")
    finish(b.play(blueprint, "main", b.hero))
    parts = [c for c in b.draw_pile + b.discard if c.cid.startswith("e_part_scythe")]
    assert len(parts) == 3
    assert any(c in b.draw_pile for c in parts) and any(c in b.discard for c in parts)
    assert not any(c.cid.startswith("e_part_scythe") for c in b.hand)

    for c in parts:
        if c in b.draw_pile:
            b.draw_pile.remove(c)
        if c in b.discard:
            b.discard.remove(c)
        b.receive_card(c)
    assert b.garden.pending_assemblies
    assert not any(c.cid == "e_weapon_scythe" for c in b.hand)
    finish(b.garden.flush_assemblies())
    weapons = [c for c in b.hand if c.cid == "e_weapon_scythe"]
    assert len(weapons) == 1
    assert "retain" in M.card_rules(weapons[0].d)
    assert not any(c.cid.startswith("e_part_scythe") for c in b.hand)


def test_part_scatter_works_for_any_part_count():
    for n in (2, 3, 4, 5):
        b, _ = hero_battle("elf")
        cards = [M.Card("e_part_scythe_arc", b.run.defs) for _ in range(n)]
        placed = b.scatter_parts(cards)
        assert len(placed) == n
        assert any(card in b.draw_pile for card, dest in placed if dest == "draw")
        assert any(card in b.discard for card, dest in placed if dest == "discard")
        assert {dest for _, dest in placed} == {"draw", "discard"}


def test_multiple_complete_sets_assemble_multiple_weapons():
    b, _ = hero_battle("elf")
    parts = []
    for _ in range(2):
        for pid in ("e_part_scythe_arc", "e_part_scythe_blade", "e_part_scythe_seal"):
            parts.append(M.Card(pid, b.run.defs))
    b.hand.extend(parts)
    b.garden.check_assembly()
    finish(b.garden.flush_assemblies())
    assert len([c for c in b.hand if c.cid == "e_weapon_scythe"]) == 2


def test_blueprint_registry_does_not_hardcode_three_parts(monkeypatch):
    from deck import fae
    monkeypatch.setitem(fae.BLUEPRINTS, "e_test_blueprint",
                        ("e_weapon_scythe", ("e_part_scythe_arc",) * 4))
    b, _ = hero_battle("elf")
    b.garden.make_parts("e_test_blueprint")
    parts = [c for c in b.draw_pile + b.discard if c.cid == "e_part_scythe_arc"]
    assert len(parts) == 4
    assert any(c in b.draw_pile for c in parts) and any(c in b.discard for c in parts)


def test_weapon_merge_animation_blocks_input_until_finished():
    game = DescentGame(seed=1, gd=ED)
    battle, game.run = hero_battle("elf")
    screen = BattleScreen(game, battle)
    for _ in range(20):
        screen.update(1 / 60)
    parts = [M.Card(pid, battle.run.defs) for pid in
             ("e_part_scythe_arc", "e_part_scythe_blade", "e_part_scythe_seal")]
    weapon = M.Card("e_weapon_scythe", battle.run.defs)
    battle.hand.append(weapon)
    screen.deck_fx({"kind": "merge_weapon", "unit": battle.hero, "parts": parts,
                    "weapon": weapon, "dur": 0.5})
    assert screen.merge is not None and screen.busy
    screen.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert screen.merge is not None
    assert screen.merge_deferred
    for _ in range(40):
        screen.update(1 / 60)
    assert screen.merge is None


def test_plant_and_graft_insight_bonuses_apply():
    b, _ = hero_battle("elf")
    b.energy = 9
    seed = M.Card("e_thorn_seed", b.run.defs, picks=[3])
    b.hand.append(seed)
    foe = b.foes()[0]
    put(b, foe, (b.hero.cell[0] + 2, b.hero.cell[1]))
    finish(b.play(seed, "main", b.targets(seed, "main")[0]))
    plant = b.garden.plants[0]
    plant.growth = 10
    hp = foe.hp
    finish(b.garden.mature(plant))
    assert hp - foe.hp == 9 and foe.ds["root"] == 2

    b, _ = hero_battle("elf")
    b.energy = 9
    host = card(b, "e_basic_attack")
    graft = M.Card("e_ivy_graft", b.run.defs, picks=[2])
    b.hand.append(graft)
    finish(b.play(graft, "main", host))
    foe = b.foes()[0]
    put(b, foe, (b.hero.cell[0] + 1, b.hero.cell[1]))
    hp = foe.hp
    finish(b.play(host, "main", foe))
    assert hp - foe.hp >= 7


def test_beast_and_ring_insights_apply():
    b, _ = hero_battle("elf")
    b.energy = 9
    owl = M.Card("e_owl_herald", b.run.defs, picks=[3])
    b.hand.append(owl)
    finish(b.play(owl, "main", b.hero))
    b.energy = 0
    finish(b.start_player_turn())
    assert b.energy == 4

    b, _ = hero_battle("elf")
    b.energy = 9
    ring = M.Card("e_fae_ring", b.run.defs, picks=[3])
    b.hand.append(ring)
    finish(b.play(ring, "main", b.targets(ring, "main")[0]))
    foe = b.foes()[0]
    put(b, foe, b.garden.rings[0]["cell"])
    finish(b.start_player_turn())
    assert foe.ds["root"] == 1


def test_blueprint_insights_change_recipe_and_weapon():
    b, _ = hero_battle("elf")
    b.energy = 9
    bp = M.Card("e_moon_scythe", b.run.defs, picks=[0])
    b.hand.append(bp)
    finish(b.play(bp, "main", b.hero))
    parts = [c for c in b.draw_pile + b.discard if c.cid.startswith("e_part_scythe")]
    assert len(parts) == 2
    for c in parts:
        if c in b.draw_pile:
            b.draw_pile.remove(c)
        if c in b.discard:
            b.discard.remove(c)
        b.receive_card(c)
    finish(b.garden.flush_assemblies())
    assert any(c.cid == "e_weapon_scythe" for c in b.hand)

    b, _ = hero_battle("elf")
    b.energy = 9
    bp = M.Card("e_moon_scythe", b.run.defs, picks=[1])
    b.hand.append(bp)
    finish(b.play(bp, "main", b.hero))
    parts = [c for c in b.draw_pile + b.discard if c.cid.startswith("e_part_scythe")]
    for c in parts[:2]:
        if c in b.draw_pile:
            b.draw_pile.remove(c)
        if c in b.discard:
            b.discard.remove(c)
        b.receive_card(c)
    finish(b.garden.flush_assemblies())
    assert any(c.cid == "e_weapon_scythe" for c in b.hand) and parts[2] not in b.hand


def test_fae_is_spent_only_when_the_enhanced_threshold_is_reached():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    h.ds["fae"] = 5
    hp = foe.hp
    finish(b.play(card(b, "e_moon_arrow"), "main", foe))
    assert hp - foe.hp == 11 and h.ds["fae"] == 5            # базовая версия не тратит фей

    h.ds["fae"] = 6
    hp = foe.hp
    finish(b.play(card(b, "e_moon_arrow"), "main", foe))
    assert hp - foe.hp == 21 and h.ds["fae"] == 3            # усиленная: 3 феи → +9


def test_attacks_burn_three_four_or_all_fae_for_damage():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    h.ds["fae"] = 6
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.hp = foe.max_hp = 200
    hp = foe.hp
    finish(b.play(card(b, "e_fate_thread"), "main", foe))
    assert hp - foe.hp == 26 and h.ds["fae"] == 2       # 8 + 6 пассивно + 4×3

    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    h.ds["fae"] = 6
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.hp = foe.max_hp = 200
    finish(b.play(card(b, "e_fae_roar"), "main", h))
    assert h.ds["fae"] == 0                              # сжигает всех


def test_linked_partner_stays_in_hand_and_boosts_damage():
    b, _ = hero_battle("elf")
    h = b.hero
    first = card(b, "e_ariadne_thread")
    partner = card(b, "e_twin_stars")
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    hp = foe.hp
    finish(b.play(first, "main", foe))
    assert partner in b.hand
    assert hp - foe.hp == 9


def test_fae_crown_and_forest_pact_gain_fae_and_shield_at_turn_start():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 5
    b.energy = 9
    for cid in ("e_fae_crown", "e_forest_pact"):
        finish(b.play(card(b, cid), "main", h))
    assert h.ds["fae"] == 5                                  # ниже порога — феи не тратятся
    finish(b.start_player_turn())
    assert h.ds["fae"] == 7                                  # по +1 от каждой Силы
    assert h.shield >= 7                                     # Корона: 2 сверх 5, Лесной завет: 5


def test_eclipse_spends_all_and_stuns_at_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 8
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.hp = foe.max_hp = 100
    finish(b.play(card(b, "e_eclipse"), "main", h))
    assert h.ds["fae"] == 7                                  # не-атака сжигает 1 фею
    assert foe.ds["stun"]


def test_weapon_balance_spends_all_and_heals_at_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 8
    h.hp = 30
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    weapon = card(b, "e_weapon_balance")
    finish(b.play(weapon, "main", foe.cell))
    assert h.ds["fae"] == 0
    assert h.shield >= 10 and h.hp == 38


def test_owl_herald_draws_at_the_start_of_the_next_turn():
    b, _ = hero_battle("elf")
    b.energy = 9
    owl = card(b, "e_owl_herald")
    finish(b.play(owl, "main", b.hero))
    assert "owl" in b.garden.beasts
    b.hand = []
    b.draw_pile = [M.Card("e_basic_attack", b.run.defs) for _ in range(10)] + b.draw_pile
    finish(b.start_player_turn())
    assert len(b.hand) == 6                                   # 5 обычных + карта совы


def test_moon_moss_draws_once_even_at_the_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    host = card(b, "e_basic_attack")
    graft = card(b, "e_moon_moss")
    finish(b.play(graft, "main", host))
    b.hand = [host]
    b.draw_pile = [M.Card("e_basic_attack", b.run.defs) for _ in range(5)] + b.draw_pile
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    h.ds["fae"] = 6
    finish(b.play(host, "main", foe))
    assert len(b.hand) == 1                                   # +1 карта, без второй за порог


def test_fae_does_not_add_owl_or_deer_draws():
    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    h.ds["fae"] = 6
    finish(b.play(card(b, "e_owl_herald"), "main", h))
    b.hand = []
    b.draw_pile = [M.Card("e_basic_attack", b.run.defs) for _ in range(10)] + b.draw_pile
    finish(b.start_player_turn())
    assert len(b.hand) == 6                                   # сова всегда даёт 1 карту

    b, _ = hero_battle("elf")
    h = b.hero
    b.energy = 9
    h.ds["fae"] = 6
    finish(b.play(card(b, "e_deer_guide"), "main", h))
    b.hand = []
    b.draw_pile = [M.Card("e_basic_attack", b.run.defs) for _ in range(10)] + b.draw_pile
    finish(b.start_player_turn())
    assert len(b.hand) == 5                                   # олень даёт шаги, но не добор
