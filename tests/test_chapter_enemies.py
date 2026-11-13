"""Враги первых трёх глав похода: у каждого есть описание и пассивка, у средних — навык,
у боссов — ровно два навыка. Проверяем общий объединённый набор (база + файлы глав)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import expedition as X  # noqa: E402
from sim.data import GameData  # noqa: E402

ED = X.expedition_data(GameData())

SWAMP = {
    "slime", "beetle", "bog_archer", "frog_shaman", "slime_king", "ice_witch", "toxic_slime",
    "bog_horror", "drowned", "illusionist", "elder_leech", "mosquito_swarm", "bog_croc",
    "spore_shroom", "toad_spearman", "bog_hag", "will_wisp", "poacher", "reed_militia",
    "rust_merc", "rust_captain", "witch_hunter", "fog_double", "bell_ringer", "old_tooth",
    "leech_mother", "kvaks", "mire_king", "toad_queen",
}
FORGE = {
    "slag_slave", "ember_hound", "bellows_keeper", "chain_smith", "ash_wraith", "cinder_caster",
    "cult_zealot", "crucible_golem", "free_golem", "overseer_groh", "crucible_titan",
    "volcano_heart", "smith_ghost", "ash_wyrm", "fire_imp", "hammer_thrower", "flame_priest",
    "magma_golem", "salamander", "obsidian_guard", "living_lava", "forge_overseer", "forge_lord",
}
BOSSES = {
    "mire_king", "toad_queen", "bell_ringer", "old_tooth", "leech_mother", "kvaks", "ice_witch",
    "overseer_groh", "crucible_titan", "volcano_heart", "smith_ghost", "ash_wyrm", "forge_lord",
    "lich", "crypt_abbot", "crypt_warden",
}
PASSIVE_KINDS = {"block", "dodge", "rage", "siphon", "retaliate"}


def test_first_two_chapters_have_descriptions_and_passives():
    for key in SWAMP | FORGE:
        e = ED.enemies[key]
        assert e.get("desc"), key
        p = e.get("passive")
        assert p and p.get("name") and p.get("desc"), key
        assert p.get("kind") in PASSIVE_KINDS, (key, p.get("kind"))
        assert e.get("pp_max", 0) >= p.get("pp", 1), key


def test_chapter_bosses_have_exactly_two_skills_and_a_passive():
    data = GameData()
    for key in BOSSES:
        e = ED.enemies[key]
        assert e.get("boss"), key
        assert len(e.get("skills", [])) == 2, (key, e.get("skills"))
        assert all(s in data.skills for s in e["skills"]), key
        assert e.get("passive"), key


def test_non_boss_enemies_with_skills_are_medium_and_have_a_passive():
    for key in SWAMP | FORGE:
        e = ED.enemies[key]
        if e.get("boss"):
            continue
        if e.get("skills"):
            assert e.get("passive"), key
