"""Условные предметы руки и комбинаций на настоящих событиях боя."""
from deck import model as M
from deck.relic_choice import RelicChoice
from deck.relic_hand import RELICS
from test_deck import _priest, finish, hero_battle, put
from test_pyro_spirits import arena


def equip(b, *ids):
    b.run.relics = [dict(RELICS[item_id], id=item_id) for item_id in ids]


def add_card(b, name, rules=(), do=(), reactions=None, target="self", kind="skill", use_opts=None):
    definition = {
        "name": name, "art": "gift_word_power", "cost": 0, "type": kind,
        "main": {"target": target, "do": list(do), **(use_opts or {})},
        "rules": list(rules), "reactions": reactions or {},
    }
    card = M.Card(name, {name: definition})
    b.receive_card(card)
    return card


def choose(gen, picker=lambda choices: choices[0][1]):
    choices_seen = []
    answer = None
    while True:
        try:
            event = gen.send(answer)
        except StopIteration:
            return choices_seen
        answer = None
        if isinstance(event, RelicChoice):
            choices_seen.append(event.prompt)
            answer = picker(event.options)


def test_link_spool_keeps_one_discarded_card_for_next_draw():
    b, _ = arena()
    equip(b, "link_spool")
    lead = add_card(b, "lead", ["linked"])
    first = add_card(b, "first", ["linked"])
    second = add_card(b, "second", ["linked"])
    assert choose(b.play(lead, "main", b.hero)) == ["Катушка связного"]
    assert first not in b.hand and first not in b.discard
    assert second in b.discard
    assert b.hand_relics.next_top == [first] and "linked" not in M.card_rules(first.d)
    b.hand_relics.before_draw(10)
    assert b.draw_pile[-1] is first


def test_wax_pocket_returns_ephemeral_to_hand_once():
    b, foe = arena()
    equip(b, "wax_pocket")
    ephemeral = add_card(b, "ephemeral", ["ephemeral"])
    foe.ds["stun"] = True
    assert choose(b.end_turn()) == ["Восковой карман"]
    assert ephemeral in b.hand
    foe.ds["stun"] = True
    assert choose(b.end_turn()) == []
    assert ephemeral in b.exhaust


def test_empty_binding_exchanges_only_a_card_held_the_entire_turn():
    b, _ = arena()
    equip(b, "empty_binding")
    held = add_card(b, "held", ["unactivatable"])
    finish(b.hand_relics.turn_start())
    late = add_card(b, "late", ["unactivatable"])
    top = add_card(b, "top")
    b.hand.remove(top)
    b.discard.append(top)
    assert choose(b.hand_relics.before_end(False)) == ["Пустой переплёт"]
    assert top in b.hand and late in b.hand and held in b.discard


def test_edge_coin_transfers_rolled_discount_but_cannot_recycle_donation():
    b, _ = arena()
    equip(b, "edge_coin")
    rolled = add_card(b, "rolled", ["lead"])
    paid = M.Card("m_duelist", b.run.defs)
    b.hand.append(paid)
    b.lead_discounts.add(rolled.uid)
    finish(b.hand_relics.turn_start())
    b.hand_relics.lost_lead()
    b.lead_discounts.clear()
    assert choose(b.hand_relics.turn_start()) == ["Монета на ребре"]
    assert b.effective_cost(paid) == 0
    b.hand_relics.lost_lead()
    assert not b.hand_relics.lead_credit


def test_black_sealing_wax_delays_only_the_quietus_reaction():
    b, _ = arena()
    equip(b, "black_sealing_wax")
    b.hero.hp -= 10
    initial = b.hero.hp
    card = add_card(b, "quiet", ["quietus"], reactions={
        "quietus": [{"op": "heal", "n": 4}],
        "discarded": [{"op": "heal", "n": 2}],
    })
    b.pending_discard = 1
    assert choose(b.resolve_discard_gen([card])) == ["Чёрная сургучница"]
    assert b.hero.hp == initial + 2
    assert choose(b.hand_relics.turn_start()) == []
    assert b.hero.hp == initial + 6


def test_last_word_book_is_offered_on_finale():
    b, foe = arena()
    equip(b, "last_word_book")
    held = add_card(b, "held")
    finale = add_card(b, "finale", ["finale"])
    foe.ds["stun"] = True
    assert choose(b.play(finale, "main", b.hero)) == ["Книга последнего слова"]
    assert held in b.hand and b.turn == 2


def test_split_seal_recovers_card_on_second_wound_of_same_enemy():
    b, foe = arena()
    equip(b, "split_seal")
    put(b, foe, (b.hero.cell[0] + 1, b.hero.cell[1]))
    attack = add_card(b, "double wound", ["exhaust_2"], [{"op": "damage", "n": 1}],
                      target="enemy", kind="attack")
    other = add_card(b, "other")
    b.hand.remove(other)
    b.discard.append(other)
    finish(b.play(attack, "main", foe))
    assert b.hand_relics.first_cuts[attack.uid] is foe
    b.used.remove(attack)
    b.receive_card(attack)
    assert choose(b.play(attack, "main", foe)) == ["Расколотая печать"]
    assert other in b.hand and attack in b.exhaust


def test_two_fates_binding_commits_choice_before_merging_and_expires():
    b, foe = arena()
    equip(b, "two_fates_binding")
    b.add_tokens("t_spirit_ember", 2)
    assert choose(b.react()) == ["Переплёт двух судеб"]
    embers = list(b.hand)
    assert len(embers) == 2 and all(c.rank == 1 and "ephemeral" in M.card_rules(c.d) for c in embers)
    foe.ds["stun"] = True
    assert choose(b.end_turn()) == []
    assert all(c in b.exhaust and "ephemeral" not in M.card_rules(c.d) for c in embers)


def test_salt_fuse_removes_poison_and_sets_surface():
    b, foe = arena()
    equip(b, "salt_fuse")
    foe.ds["poison"] = 3
    bolt = M.Card("p_bolt", b.run.defs)
    b.receive_card(bolt)
    assert choose(b.play(bolt, "main", foe)) == ["Солевой фитиль"]
    assert foe.ds["poison"] == 1
    assert any(cell.hazard == "poison" for cell in b.c.grid.cells.values())


def test_glass_buckler_spends_held_strike_for_counter():
    b, _ = arena()
    equip(b, "glass_buckler")
    strike = M.Card("strike", b.run.defs)
    b.receive_card(strike)
    b.set_stance("guard")
    b.hand_relics.retained(strike)
    assert choose(b.hand_relics.turn_start()) == ["Стеклянный щиток"]
    assert strike in b.discard and b.hero.ds["counter"] == 1 and b.stance == "guard"


def test_copper_spur_reuses_only_the_last_voluntary_step():
    b, _ = arena()
    equip(b, "copper_spur")
    origin = b.hero.cell
    destination = (origin[0], origin[1] + 1)
    step = add_card(b, "step", target="cell_step", use_opts={"step": 1})
    stance = add_card(b, "stance", do=[{"op": "stance", "id": "ready"}])
    finish(b.play(step, "main", destination))
    assert b.hero.cell == destination
    assert choose(b.play(stance, "main", b.hero)) == ["Медная шпора"]
    assert b.hero.cell == origin and b.stance == "ready"


def test_chess_pendant_pulls_to_the_jump_origin():
    b, foe = arena()
    equip(b, "chess_pendant")
    b.set_stance("knight")
    origin, marked = (1, 2), (2, 4)
    put(b, foe, (3, 4))
    assert choose(b.walk(b.hero, [marked])) == []
    assert b.hand_relics.knight_mark == marked
    finish(b.walk(b.hero, [origin]))
    assert choose(b.walk(b.hero, [marked])) == ["Шахматная подвеска"]
    assert b.hero.cell == marked and foe.cell == origin


def test_tuning_fork_redirects_only_the_resonance_repeat():
    from sim.grid import Grid

    b, _ = hero_battle("hunter")
    b.c.grid = Grid(["." * 9] * 7, {".": {}})
    b.hand.clear()
    equip(b, "tuning_fork")
    first, other, *rest = b.foes()
    for foe in rest:
        foe.alive = False
    put(b, b.hero, (2, 3))
    put(b, first, (3, 3))
    put(b, other, (3, 4))
    for foe in (first, other):
        foe.hp = 100
        foe.edef = {}
    b.played = 1
    b.turn_tags = [{"strike"}]
    strike = add_card(b, "Resonant hit", target="enemy", kind="attack",
                      do=[{"op": "damage", "n": 4}],
                      use_opts={"range": 2, "if": [{"when": {"k": "resonance", "tag": "strike", "n": 1}}]})
    assert choose(b.play(strike, "main", first)) == ["Камертон"]
    assert first.hp == 96 and other.hp == 96


def test_two_faced_chime_swaps_gods_only_after_different_statues():
    _, _, b = _priest()
    equip(b, "two_faced_chime")
    first, second, *_ = b.idols.statues
    origin, destination = first.cell, second.cell
    assert choose(b.hand_relics.after_scroll(first)) == []
    assert choose(b.hand_relics.after_scroll(first)) == []
    assert choose(b.hand_relics.after_scroll(second)) == ["Двуликий колокольчик"]
    assert first.cell == destination and second.cell == origin


def test_swap_bead_exchanges_after_second_resolved_combo():
    b, _ = arena()
    equip(b, "swap_bead")
    first = add_card(b, "first", use_opts={"if": [{"when": {"k": "first"}, "do": [{"op": "block", "n": 1}]}]})
    second = add_card(b, "second", use_opts={"if": [{"when": {"k": "series", "n": 1}, "do": [{"op": "block", "n": 1}]}]})
    held = add_card(b, "held")
    top = add_card(b, "top")
    b.hand.remove(top)
    b.draw_pile = [top]
    assert choose(b.play(first, "main", b.hero)) == []
    assert choose(b.play(second, "main", b.hero)) == ["Бусина перестановки"]
    assert b.draw_pile == [held] and top in b.hand


def test_oblique_seal_can_move_center_away_from_ballista():
    from types import SimpleNamespace

    b, foe = arena()
    equip(b, "oblique_seal")
    put(b, foe, (4, 3))
    b._ballistas.append(SimpleNamespace(alive=True, cell=(2, 4)))
    blast = add_card(b, "blast", target="area", kind="attack",
                     do=[{"op": "damage", "n": 4}], use_opts={"range": 5, "radius": 1})
    assert choose(b.play(blast, "main", (3, 3)), lambda options: (4, 3)) == ["Косая печать"]
    assert "oblique_seal" in b.hand_relics.turn_spent
