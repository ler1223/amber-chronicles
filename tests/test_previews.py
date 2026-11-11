"""Демонстрация навыков (окно выбора улучшения и листа героя): каждый навык пула каждого класса, кнопка механики
и ультимейты проигрываются в превью без ошибок и действительно применяются; превью держит реальную частоту кадров."""
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1280, 800))

from sim.data import GameData  # noqa: E402
from sim import expedition as X, story_meta as SM  # noqa: E402
from ui import projection as P  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
SCREEN = pygame.Surface((1280, 800))


def proto_with(cls, sid, level=15):
    h = X.Hero({"uid": "p", "name": "П", "cls": cls, "skills": [sid], "level": level})
    h.points = X.auto_points(ED, h)
    run = X.Expedition(ED, [h], seed=1)
    h = run.heroes[0]
    if sid not in h.skills:                            # набор чинится под класс — навык ставим сами
        h.skills = [sid] + [s for s in h.skills if s != sid][:2]
    if SM.is_ult(ED, cls, sid):
        h.skills = [s for s in h.skills if not SM.is_ult(ED, cls, s) or s == sid]
    h.quivers = list(DATA.config.get("arrows", {}))[:3] if run.has_quivers(h) else []
    return run.proto(h)


def test_every_pool_skill_previews():
    from ui.skill_preview import SkillPreview
    pv = SkillPreview(ED, pygame.Rect(588, 154, 668, 380))
    seen = 0
    silent = []
    for cls in DATA.classes:
        pool = SM.all_skills(ED, cls) + SM.notes_of(ED, cls) + ([SM.mech_of(ED, cls)] if SM.mech_of(ED, cls) else [])
        for sid in pool:
            p = proto_with(cls, sid)
            if sid not in p["skill_defs"]:
                continue                                # нота барда — только вместе с мелодией
            pv.show_proto(cls, p, sid, DATA.skills[sid]["name"])
            for _ in range(150):                        # 2.5 сек при 60 кадрах — как в игре
                pv.update(1 / 60)
            log = " ".join(t for t, _ in pv.view.log)
            if DATA.skills[sid]["name"] not in log:
                silent.append(f"{cls}/{sid}")
            seen += 1
        pv.draw_cpu(SCREEN)
    P.reset()
    assert seen >= 150
    assert not silent, f"в превью не применились: {silent}"


def test_preview_runs_at_real_frame_rates():
    """При 60 и 144 кадрах в секунду навык применяется в первом же цикле (шаг боя длиннее кадра)."""
    from ui.skill_preview import CYCLE, SkillPreview
    pv = SkillPreview(ED, pygame.Rect(588, 154, 668, 380))
    sid = random.Random(1).choice([s for s in SM.all_skills(ED, "mage") if not SM.is_ult(ED, "mage", s)])
    for fps in (60, 144):
        pv.show_proto("mage", proto_with("mage", sid), sid)
        applied = []
        for _ in range(int(CYCLE * fps) - 2):
            pv.update(1 / fps)
            applied.append(pv.caster.cooldowns.get(sid, 0) > 0 or pv.caster.ap < pv.caster.ap_max)
        assert any(applied), fps
        assert pv.c.time > CYCLE * 0.8
    P.reset()
