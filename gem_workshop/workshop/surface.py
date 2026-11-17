"""Слоистое состояние поверхности камня.

Это не «текстура шероховатости», а маленькая модель истории обработки:
геометрия грани, микрорельеф, плёнка, нарушенный слой, полировка и грязь.
Числа здесь — не физические единицы, а безразмерные параметры для шейдера;
важно, чтобы они были согласованы между собой и менялись от действий игрока.
"""
from __future__ import annotations

import math


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))


def _seed01(stone, salt=0):
    seed = int(stone.get("seed", 0) or 0)
    uid = str(stone.get("uid", ""))
    h = (seed * 1103515245 + 12345 + salt * 2654435761) & 0xFFFFFFFF
    for ch in uid:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return (h & 0xFFFF) / 65535.0


def rough_state(stone, cleaned=False):
    """Сырьё: кора, глина, масло, каверны, следы природы."""
    a = _seed01(stone, 1)
    b = _seed01(stone, 2)
    c = _seed01(stone, 3)
    s = {
        "stage": "rough",
        "roughness": _clamp(0.72 + 0.22 * a),
        "dirt": _clamp(0.55 + 0.35 * b),
        "film": _clamp(0.32 + 0.34 * c),
        "damage": _clamp(0.18 + 0.24 * a),
        "polish": _clamp(0.04 + 0.10 * b),
        "wet": 0.0,
        "scratches": _clamp(0.30 + 0.30 * c),
        "cleaned": False,
    }
    if cleaned:
        s["dirt"] *= 0.12
        s["film"] *= 0.18
        s["wet"] = 0.0
        s["cleaned"] = True
        s["stage"] = "cleaned_rough"
    return s


def cut_state(stone, cleaned=False):
    """Огранённый камень: качество полировки и остаточные дефекты."""
    q = _clamp(stone.get("q", 1.0) / 2.5)
    # Если поверхность уже посчитана при огранке — используем её.
    stored = stone.get("surface")
    if isinstance(stored, dict):
        s = dict(stored)
        s.setdefault("stage", "polished")
    else:
        s = {
            "stage": "polished" if q > 0.36 else "prepolished",
            "roughness": _clamp(0.10 - 0.07 * q + 0.04),
            "dirt": _clamp(0.08 + 0.06 * (1.0 - q)),
            "film": _clamp(0.04 + 0.04 * (1.0 - q)),
            "damage": _clamp(0.02 + 0.10 * (1.0 - q)),
            "polish": _clamp(0.45 + 0.55 * q),
            "wet": 0.0,
            "scratches": _clamp(0.10 + 0.35 * (1.0 - q)),
            "cleaned": False,
        }
    if cleaned:
        s["dirt"] *= 0.10
        s["film"] *= 0.20
        s["wet"] = 0.0
        s["cleaned"] = True
        s["stage"] = "cleaned"
    return s


def for_stone(stone, rough=None, cleaned=False):
    """Единая точка входа для осмотра: сырьё или готовая огранка."""
    if rough is None:
        rough = "seed" in stone and "q" not in stone
    stored = stone.get("surface_clean" if cleaned else "surface")
    if isinstance(stored, dict):
        return dict(stored)
    return rough_state(stone, cleaned) if rough else cut_state(stone, cleaned)


def from_cutter(cutter):
    """Сохранить в готовый камень следы реального диска и качества огранки."""
    try:
        q = _clamp(getattr(cutter, "quality", 1.0) / 2.5)
        disk = getattr(cutter, "disk", None)
        try:
            from sim import gems as GM
            grit = float(GM.GRIT.get(disk, 0.42))
        except Exception:
            grit = 0.42
        finish = getattr(cutter, "finish_of", {}) or {}
        avg_finish = sum(finish.values()) / max(1, len(finish))
    except Exception:
        q, grit, avg_finish = 0.4, 0.42, 0.9
    return {
        "stage": "polished" if q > 0.36 else "prepolished",
        "roughness": _clamp(0.06 + 0.16 * (1.0 - q) + 0.08 * grit),
        "dirt": _clamp(0.10 + 0.08 * (1.0 - q) + 0.06 * (1.0 - avg_finish)),
        "film": _clamp(0.04 + 0.05 * (1.0 - q)),
        "damage": _clamp(0.03 + 0.16 * (1.0 - q) + 0.07 * grit),
        "polish": _clamp(0.35 + 0.65 * q),
        "wet": 0.0,
        "scratches": _clamp(0.08 + 0.35 * (1.0 - q) + 0.15 * grit),
        "cleaned": False,
    }


def diagnosis(surface, rough=False):
    """Короткий человеческий диагноз, а не таблица характеристик."""
    if not surface:
        return ["Поверхность не определена."]
    out = []
    if surface.get("dirt", 0) > 0.30:
        out.append("Плёнка грязи/масла: поверхностная мутность, можно снять чисткой.")
    if surface.get("film", 0) > 0.20:
        out.append("Тонкая плёнка рассеивает свет; часть блеска потеряна.")
    if surface.get("damage", 0) > 0.18:
        out.append("Под поверхностью нарушенный слой — нужна более глубокая шлифовка.")
    if surface.get("roughness", 0) > 0.30:
        out.append("Микрорельеф грубый: грань ещё не выведена на полировку.")
    if surface.get("scratches", 0) > 0.35:
        out.append("Заметны следы абразива/царапины; полировка неполная.")
    if not out:
        out.append("Поверхность ровная; мутность, если есть, идёт из объёма.")
    if rough:
        out.append("Сырьё: корка и глина могут скрывать включения у поверхности.")
    return out


def value_factor(surface):
    """Во сколько раз видимая поверхность меняет цену камня."""
    if not surface:
        return 1.0
    return max(0.55, 1.0
               - 0.18 * surface.get("dirt", 0.0)
               - 0.12 * surface.get("damage", 0.0)
               - 0.08 * (1.0 - surface.get("polish", 0.0))
               - 0.06 * surface.get("scratches", 0.0))


def short_line(surface):
    if not surface:
        return "поверхность: —"
    stage = surface.get("stage", "?")
    names = {
        "rough": "сырьё", "cleaned_rough": "сырьё, очищено",
        "prepolished": "предполировка", "polished": "полировка",
        "cleaned": "полировка, очищено",
    }
    return (f"поверхность: {names.get(stage, stage)} · "
            f"грязь {surface.get('dirt', 0) * 100:.0f}% · "
            f"полировка {surface.get('polish', 0) * 100:.0f}%")
