"""Глава 3 «Склеп нежити»: данные похода ссылаются на существующие бои, события и вещи."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import expedition as X  # noqa: E402
from sim.data import GameData  # noqa: E402

ED = X.expedition_data(GameData())
XD = ED.expedition
CD = XD["chapter_data"]["crypt"]
VIEW = X.chapter_view(XD, "crypt")


def test_crypt_chapter_is_registered():
    assert XD["chapters"]["crypt"]["file"] == "expedition_crypt.json"
    assert XD["chapters"]["crypt"]["unlock"] == "forge"
    assert XD["chapters"]["crypt"]["trophy"] in XD["trophies"]
    assert any(v.get("rare") and v.get("chapter") == "crypt" for v in XD["materials"].values())
    assert XD["config"]["mat_drops"]["common"]["crypt"]


def test_crypt_acts_reference_known_encounters():
    known = {e["id"] for e in ED.encounters}
    assert len(CD["acts"]) == 3
    for act in CD["acts"]:
        for pool in act["pools"].values():
            assert pool
            for eid in pool:
                assert eid in known, eid
        assert act["boss"] in known, act["boss"]
        assert act["rest"]
    assert CD["acts"][-1]["boss"] == "crypt_9"


def test_crypt_events_reference_known_data():
    known = {e["id"] for e in ED.encounters}
    curses = set(VIEW["curses"])
    mats = set(VIEW["mats"])
    uniques = set(VIEW["items"]["uniques"])
    assert "abandoned_camp" in CD["events"]
    for eid, ev in CD["events"].items():
        assert ev["steps"], eid
        for step in ev["steps"].values():
            for o in step.get("options", []):
                for branch in [o, o.get("success"), o.get("fail")]:
                    if not branch:
                        continue
                    for op in branch.get("do", []):
                        if "battle" in op:
                            assert op["battle"] in known, (eid, op)
                        if "curse" in op:
                            assert op["curse"] in curses, (eid, op)
                        if "mat" in op:
                            assert op["mat"] in mats, (eid, op)
                        item = op.get("item")
                        if isinstance(item, dict) and item.get("unique"):
                            assert item["unique"] in uniques, (eid, op)
                        node = op.get("add_node")
                        if isinstance(node, dict) and node.get("event"):
                            assert node["event"] in CD["events"], (eid, op)


def test_crypt_chapter_lists_its_bosses():
    assert {"crypt_abbot", "crypt_warden", "lich"} <= set(XD["chapters"]["crypt"]["enemies"])


def test_crypt_enemies_have_features_and_descriptions():
    ordinary = {"skeleton", "skeleton_archer", "ghoul"}
    medium = {"necromancer", "banshee", "bone_golem", "wraith"}
    bosses = {"lich", "crypt_abbot", "crypt_warden"}
    for key in ordinary | medium | bosses:
        e = CD["enemies"][key]
        assert e.get("desc"), key
        assert e.get("passive") and e["passive"].get("name") and e["passive"].get("desc"), key
        assert e.get("pp_max", 0) >= e["passive"]["pp"], key
    for key in medium:
        assert CD["enemies"][key]["skills"], key
    for key in bosses:
        e = CD["enemies"][key]
        assert e.get("boss"), key
        assert len(e["skills"]) == 2, key


def test_crypt_act_bosses_have_a_boss_unit():
    for eid in ("crypt_7", "crypt_8", "crypt_9"):
        enc = next(e for e in ED.encounters if e["id"] == eid)
        assert any(ED.enemies[x["type"]].get("boss") for x in enc["enemies"]), eid


def test_crypt_uniques_are_chapter_scoped():
    prof = X.ExpeditionProfile(ED, None, sandbox=True)
    run = prof.start([h.uid for h in prof.roster[:3]], seed=1, chapter="crypt")
    assert run.chapter == "crypt"
    run.xd["items"]["uniques"]["__other_chapter"] = {
        "name": "Чужая вещь", "base": "blade", "chapter": "forge", "desc": "",
    }
    for _ in range(60):
        item = run.new_item("boss", rarity="unique")
        assert item.get("unique") != "__other_chapter"
        if item["rarity"] == "unique":
            assert run.xd["items"]["uniques"][item["unique"]].get("chapter") in (None, "crypt")


def test_crypt_uniques_do_not_drop_in_swamp():
    prof = X.ExpeditionProfile(ED, None, sandbox=True)
    run = prof.start([h.uid for h in prof.roster[:2]], seed=1, chapter="swamp")
    assert run.chapter == "swamp"
    for _ in range(60):
        item = run.new_item("boss", rarity="unique")
        if item["rarity"] == "unique":
            assert run.xd["items"]["uniques"][item["unique"]].get("chapter") is None
