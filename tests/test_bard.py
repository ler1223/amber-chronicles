"""Бард: обычные навыки поддержки, мотивы вместо автоатаки, без урона противникам."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import setup  # noqa: E402
from sim import story_meta  # noqa: E402
from sim.data import GameData  # noqa: E402

DATA = GameData()


def test_bard_has_ten_regular_and_three_ults():
    from sim import expedition as X
    xd = X.expedition_data(DATA)
    pool = story_meta.all_skills(xd, "bard")
    ults = story_meta.ults_of(xd, "bard")
    assert len([s for s in pool if s not in ults]) == 10
    assert len(ults) == 3
    assert not story_meta.notes_of(xd, "bard")


def test_bard_motif_support_instead_of_attack():
    c, h, foes = setup("bard", [])
    h.motifs = ["march"]
    h.motif_i = 0
    h.attack_timer = 0
    ally = c.summon(h, {"unit": "skeleton_minion", "duration": 30}, (2, 3))
    ally.hp = 5
    hp = foes[0].hp
    c._auto_attack(h)
    assert foes[0].hp == hp
    assert ally.buff("armor", 0) == 2
    assert ally.buff("dmg_taken", 1.0) < 1.0


def test_bard_motif_boost_is_stronger():
    c, h, foes = setup("bard", [])
    h.motifs = ["march"]
    h.motif_boost = True
    h.motif_i = 0
    h.attack_timer = 0
    ally = c.summon(h, {"unit": "skeleton_minion", "duration": 30}, (2, 3))
    ally.hp = 5
    c._auto_attack(h)
    assert ally.buff("armor", 0) > 2


def test_bard_gets_motif_choice_and_boosted_motifs_in_proto():
    from sim import expedition as X
    from sim.expedition import Expedition, Hero
    xd = X.expedition_data(DATA)
    h = Hero({"uid": "bard-test", "name": "Бард", "cls": "bard",
              "skills": ["bard_march", "bard_hymn", "bard_encore"], "level": 1})
    run = Expedition(xd, [h], seed=1, chapter="swamp", tier=0)
    hero = run.heroes[0]
    assert run.motif_pending(hero) == 1
    cards = run.pick_cards(hero)
    assert cards and all(c["type"] == "motif" for c in cards)
    assert run.take_card(hero, 0)
    assert len(hero.motifs) == 1
    assert run.proto(hero)["motifs"] == hero.motifs


def test_bard_ordered_attack_still_does_not_damage_enemy():
    c, h, foes = setup("bard", [])
    h.motifs = ["rhythm"]
    h.motif_i = 0
    h.attack_timer = 0
    ally = c.summon(h, {"unit": "skeleton_minion", "duration": 30}, (2, 3))
    ally.hp = 5
    hp = foes[0].hp
    c._basic_attack(h, foes[0])
    assert foes[0].hp == hp
    assert ally.buff("atk_speed", 1.0) < 1.0
