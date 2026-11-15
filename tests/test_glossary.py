"""Описания навыков: проценты от характеристик и ссылки на эффекты."""
from sim.data import GameData
from sim.build import build_proto
from sim import stats
from ui import glossary as GL

DATA = GameData()


def test_glossary_contains_tags_reactions_and_buffs():
    gl = GL.build(DATA)
    for name in ("Гроза", "Огонь", "Заморозка", "Уязвимость", "Молчание"):
        assert name in gl
        assert gl[name][1]


def test_description_marks_effect_terms_as_links():
    gl = GL.build(DATA)
    segs = GL.segments("Урон + Гроза, затем Огонь и Заморозка.", gl)
    keys = [k for _, k in segs if k]
    assert "Гроза" in keys and "Огонь" in keys and "Заморозка" in keys


def test_rich_text_draw_records_link_rects():
    import pygame
    pygame.init()
    surf = pygame.Surface((400, 200), pygame.SRCALPHA)
    gl = GL.build(DATA)
    h, links = GL.draw(surf, "Гроза и Огонь", (4, 4), 14, 380, gl)
    assert h > 0 and len(links) >= 2


def test_skill_scale_text_uses_percent_of_stat():
    p = build_proto(DATA, "warrior")
    p["ref"] = {"atk": 10, "hp": 100}
    text = stats.skill_scale_text(p, DATA.skills["power_strike"])
    assert "Скейл:" in text and "70% атаки" in text


def test_skill_scale_text_falls_back_to_power_for_flat_skills():
    p = build_proto(DATA, "mage")
    text = stats.skill_scale_text(p, DATA.skills["fireball"])
    assert "сила навыков" in text and "урон" in text
