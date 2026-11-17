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
        "stage": "clean_rough",
        "roughness": _clamp(0.72 + 0.22 * a),
        "dirt": 0.0,
        "film": 0.0,
        "damage": _clamp(0.08 + 0.14 * a),
        "polish": _clamp(0.04 + 0.08 * b),
        "wet": 0.0,
        "scratches": _clamp(0.12 + 0.16 * c),
        "cleaned": True,
    }
    return s


def cut_state(stone, cleaned=False):
    """Огранённый камень: качество полировки и остаточные дефекты."""
    q = _clamp(stone.get("q", 1.0) / 2.5)
    # Если поверхность уже посчитана при огранке — используем её.
    stored = stone.get("surface")
    if isinstance(stored, dict):
        s = dict(stored)
        s.setdefault("stage", "polished")
        s["dirt"] = 0.0
        s["film"] = 0.0
        s["cleaned"] = True
    else:
        s = {
            "stage": "polished" if q > 0.36 else "prepolished",
            "roughness": _clamp(0.10 - 0.07 * q + 0.04),
            "dirt": 0.0,
            "film": 0.0,
            "damage": _clamp(0.02 + 0.10 * (1.0 - q)),
            "polish": _clamp(0.45 + 0.55 * q),
            "wet": 0.0,
            "scratches": _clamp(0.10 + 0.35 * (1.0 - q)),
            "cleaned": True,
        }
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
        "dirt": 0.0,
        "film": 0.0,
        "damage": _clamp(0.03 + 0.16 * (1.0 - q) + 0.07 * grit),
        "polish": _clamp(0.35 + 0.65 * q),
        "wet": 0.0,
        "scratches": _clamp(0.08 + 0.35 * (1.0 - q) + 0.15 * grit),
        "cleaned": True,
    }


def diagnosis(surface, rough=False):
    """Короткий человеческий диагноз, а не таблица характеристик."""
    if not surface:
        return ["Поверхность не определена."]
    if rough:
        return ["Сырьё: природная поверхность, без грязи."]
    out = []
    if surface.get("damage", 0) > 0.18:
        out.append("Под поверхностью нарушенный слой — нужна более глубокая шлифовка.")
    if surface.get("roughness", 0) > 0.30:
        out.append("Микрорельеф грубый: грань ещё не выведена на полировку.")
    if surface.get("scratches", 0) > 0.35:
        out.append("Заметны следы абразива/царапины; полировка неполная.")
    if not out:
        out.append("Поверхность чистая; мутность, если есть, идёт из объёма.")
    return out


def value_factor(surface):
    """Во сколько раз видимая поверхность меняет цену камня."""
    if not surface:
        return 1.0
    return max(0.55, 1.0
               - 0.12 * surface.get("damage", 0.0)
               - 0.08 * (1.0 - surface.get("polish", 0.0))
               - 0.06 * surface.get("scratches", 0.0))


def short_line(surface):
    if not surface:
        return "поверхность: —"
    stage = surface.get("stage", "?")
    names = {
        "rough": "сырьё", "clean_rough": "сырьё, чистое",
        "prepolished": "предполировка", "polished": "полировка",
        "cleaned": "полировка",
    }
    return (f"поверхность: {names.get(stage, stage)} · "
            f"полировка {surface.get('polish', 0) * 100:.0f}%")
