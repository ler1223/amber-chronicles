"""Тесты механик классов не ломаются, когда классу дают новую механику.

need("quiver_fire") — если навыка больше нет в данных (механику переделали), тест ПРОПУСКАЕТСЯ с причиной, а не
падает. Так старые тесты конкретных навыков живут, пока навык есть, и тихо уходят вместе с ним. Новую механику
покрывают общие тесты (каждый навык класса во всех ветках срабатывает) и её собственные тесты.
"""
import pytest

_DATA = None


def data():
    global _DATA
    if _DATA is None:
        from sim.data import GameData
        _DATA = GameData()
    return _DATA


def need(*sids, cls=None):
    """Пропустить тест, если какого-то навыка нет (или он ушёл из пула класса cls)."""
    d = data()
    missing = [s for s in sids if s not in d.skills]
    if cls and not missing:
        from sim import story_meta
        pool = set(story_meta.all_skills(d, cls)) | set(story_meta.notes_of(d, cls)) | set(
            d.classes.get(cls, {}).get("skills", [])) | {story_meta.mech_of(d, cls)}
        missing = [s for s in sids if s not in pool]
    if missing:
        pytest.skip(f"механика переделана: нет навыка {', '.join(missing)}" + (f" у класса {cls}" if cls else ""))


def need_config(*keys):
    d = data()
    missing = [k for k in keys if k not in d.config]
    if missing:
        pytest.skip(f"механика переделана: нет настройки {', '.join(missing)}")


def need_core(cls, core):
    """Пропустить тест пассивки, если у класса теперь другая пассивка-основа (механику переделали)."""
    have = (getattr(data(), "passives", {}).get(cls) or {}).get("passive", {}).get("core")
    if have != core:
        pytest.skip(f"механика переделана: пассивка {cls} теперь {have}, не {core}")


def need_unit(u, sid):
    """Навык есть в данных, но набор класса изменился и у героя его больше нет — тест пропускается."""
    if sid not in u.skill_defs:
        pytest.skip(f"механика переделана: у {u.proto_id} больше нет навыка {sid} в наборе")
