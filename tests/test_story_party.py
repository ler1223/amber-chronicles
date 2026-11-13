"""Сюжетный отряд растёт по главам: 2 / 3 / 3 / 4 / 4 / 5..."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim.story import StoryProfile, story_data  # noqa: E402

DATA = story_data(GameData())


def test_story_party_grows_by_chapter():
    prof = StoryProfile(DATA, None)
    assert prof.current_chapter() == "swamp"
    assert prof.squad_size() == 2

    done = []
    expect = {"swamp": 2, "forge": 3, "crypt": 3, "pass": 4, "steppe": 4, "tomb": 5}
    for chapter, cap in expect.items():
        prof.done = list(done)
        assert prof.current_chapter() == chapter
        assert prof.squad_size() == cap, chapter
        done += [e["id"] for e in prof.expeditions_list() if e["chapter"] == chapter]

    assert prof.squad_size() == prof.story["squad_max"] == 5


def test_new_hero_joins_but_party_stays_at_chapter_cap():
    prof = StoryProfile(DATA, None)
    prof.done = ["prologue"]
    assert prof.current()["join"] == "priest"
    run = prof.start_chain(seed=1)
    assert len(run.squad) == 2 and any(h.cls == "priest" for h in run.squad)
