"""Оптические профили камней для осмотра, оценки и рендера.

Значения — ориентиры по реальным минералам: показатель преломления, дисперсия,
двупреломление, плеохроизм, прозрачность, твёрдость и спайность. Игрок видит
их через блик, игру света, просвечивание и двоение, а не через сухую таблицу.
"""
from __future__ import annotations

import math


def _critical(n):
    n = max(1.0001, float(n))
    return math.degrees(math.asin(1.0 / n))


PROFILES = {
    "diamond": {
        "mineral": "Алмаз", "crystal_system": "кубическая",
        "ior": (2.410, 2.417, 2.424), "dispersion": 0.044,
        "transparency": 0.96, "birefringence": 0.0, "pleochroism": 0.0,
        "hardness": 10.0, "cleavage": "совершенная по {111}", "toughness": 0.45,
        "fire": "очень сильная", "luster": "адамантиновый",
        "forms": ("octahedron", "macle", "cube"),
        "word": "холодный, предельно яркий",
    },
    "ruby": {
        "mineral": "Корунд", "crystal_system": "тригональная",
        "ior": (1.760, 1.768, 1.778), "dispersion": 0.018,
        "transparency": 0.62, "birefringence": 0.008, "pleochroism": 0.38,
        "hardness": 9.0, "cleavage": "нет, есть отдельность", "toughness": 0.62,
        "fire": "средняя", "luster": "стеклянный",
        "forms": ("prism", "massive", "macle"),
        "word": "тёплый, густой",
    },
    "sapphire": {
        "mineral": "Корунд", "crystal_system": "тригональная",
        "ior": (1.760, 1.768, 1.778), "dispersion": 0.018,
        "transparency": 0.68, "birefringence": 0.008, "pleochroism": 0.42,
        "hardness": 9.0, "cleavage": "нет, есть отдельность", "toughness": 0.62,
        "fire": "средняя", "luster": "стеклянный",
        "forms": ("prism", "massive", "macle"),
        "word": "холодный, чистый",
    },
    "emerald": {
        "mineral": "Берилл", "crystal_system": "гексагональная",
        "ior": (1.564, 1.576, 1.602), "dispersion": 0.014,
        "transparency": 0.58, "birefringence": 0.006, "pleochroism": 0.58,
        "hardness": 7.8, "cleavage": "несовершенная", "toughness": 0.50,
        "fire": "мягкая", "luster": "стеклянный, маслянистый",
        "forms": ("prism", "massive"),
        "word": "маслянистый, глубокий",
    },
    "topaz": {
        "mineral": "Топаз", "crystal_system": "ромбическая",
        "ior": (1.609, 1.620, 1.643), "dispersion": 0.014,
        "transparency": 0.72, "birefringence": 0.009, "pleochroism": 0.46,
        "hardness": 8.0, "cleavage": "совершенная по {001}", "toughness": 0.38,
        "fire": "средняя", "luster": "стеклянный",
        "forms": ("prism", "massive"),
        "word": "стеклянный, искристый",
    },
    "amethyst": {
        "mineral": "Кварц", "crystal_system": "тригональная",
        "ior": (1.544, 1.550, 1.553), "dispersion": 0.013,
        "transparency": 0.76, "birefringence": 0.009, "pleochroism": 0.22,
        "hardness": 7.0, "cleavage": "нет", "toughness": 0.66,
        "fire": "низкая", "luster": "стеклянный",
        "forms": ("prism", "massive"),
        "word": "прозрачный, фиолетовый",
    },
    "spinel": {
        "mineral": "Шпинель", "crystal_system": "кубическая",
        "ior": (1.712, 1.720, 1.736), "dispersion": 0.020,
        "transparency": 0.72, "birefringence": 0.0, "pleochroism": 0.0,
        "hardness": 8.0, "cleavage": "нет", "toughness": 0.58,
        "fire": "средняя", "luster": "стеклянный",
        "forms": ("octahedron", "macle"),
        "word": "яркий, чистый",
    },
    "zircon": {
        "mineral": "Циркон", "crystal_system": "тетрагональная",
        "ior": (1.810, 1.920, 2.024), "dispersion": 0.039,
        "transparency": 0.70, "birefringence": 0.050, "pleochroism": 0.16,
        "hardness": 7.5, "cleavage": "несовершенная", "toughness": 0.42,
        "fire": "сильная", "luster": "адамантиновый",
        "forms": ("prism", "massive"),
        "word": "сухой, яркий",
    },
    "tourmaline": {
        "mineral": "Турмалин", "crystal_system": "тригональная",
        "ior": (1.614, 1.640, 1.666), "dispersion": 0.017,
        "transparency": 0.66, "birefringence": 0.020, "pleochroism": 0.82,
        "hardness": 7.3, "cleavage": "нет", "toughness": 0.55,
        "fire": "средняя", "luster": "стеклянный",
        "forms": ("prism", "massive"),
        "word": "двухцветный, живой",
    },
    "peridot": {
        "mineral": "Перидот", "crystal_system": "ромбическая",
        "ior": (1.640, 1.670, 1.700), "dispersion": 0.020,
        "transparency": 0.68, "birefringence": 0.036, "pleochroism": 0.20,
        "hardness": 6.8, "cleavage": "несовершенная", "toughness": 0.48,
        "fire": "средняя", "luster": "стеклянный, маслянистый",
        "forms": ("prism", "massive"),
        "word": "оливковый, тёплый",
    },
    "garnet": {
        "mineral": "Гранат", "crystal_system": "кубическая",
        "ior": (1.720, 1.780, 1.940), "dispersion": 0.024,
        "transparency": 0.62, "birefringence": 0.0, "pleochroism": 0.0,
        "hardness": 7.0, "cleavage": "нет", "toughness": 0.50,
        "fire": "средняя", "luster": "стеклянный, смолистый",
        "forms": ("dodecahedron", "massive"),
        "word": "густой, тёмный",
    },
    "opal": {
        "mineral": "Опал", "crystal_system": "аморфный",
        "ior": (1.37, 1.42, 1.47), "dispersion": 0.0,
        "transparency": 0.55, "birefringence": 0.0, "pleochroism": 0.0,
        "hardness": 6.0, "cleavage": "нет", "toughness": 0.30,
        "fire": "play-of-color", "luster": "смолистый",
        "forms": ("massive",),
        "word": "молочный, переливчатый",
    },
}

_DEFAULT = {
    "mineral": "Минерал", "crystal_system": "неизвестная",
    "ior": (1.58, 1.60, 1.62), "dispersion": 0.014,
    "transparency": 0.6, "birefringence": 0.004, "pleochroism": 0.25,
    "hardness": 7.0, "cleavage": "неизвестная", "toughness": 0.5,
    "fire": "средняя", "luster": "стеклянный",
    "forms": ("prism", "massive"),
    "word": "стеклянный",
}


def profile(gid):
    """Профиль с вычисляемыми оптическими величинами."""
    p = dict(_DEFAULT)
    p.update(PROFILES.get(gid, {}))
    ior = tuple(float(v) for v in p["ior"])
    p["ior"] = ior
    p["n_mean"] = sum(ior) / len(ior)
    p["critical_low"] = _critical(max(ior))
    p["critical_high"] = _critical(min(ior))
    p["critical_angle"] = _critical(p["n_mean"])
    p["birefringence_value"] = float(p.get("birefringence", 0.0))
    p["pleochroism_value"] = float(p.get("pleochroism", 0.0))
    return p


def absorption(gid, color):
    """Поглощение по каналам: прозрачный камень почти не глушит свет."""
    p = profile(gid)
    t = max(0.15, float(p["transparency"]))
    rgb = [max(0.0, min(1.0, c / 255.0)) for c in color[:3]]
    return tuple(min(0.055, (1.0 - c) ** 1.35 * 0.022 / t + 0.0003) for c in rgb)


def pleo_value(gid):
    """Безразмерная сила плеохроизма для шейдера."""
    return profile(gid)["pleochroism_value"]


def biref_value(gid):
    """Двупреломление для визуального разделения лучей."""
    return profile(gid)["birefringence_value"]


def transparency_word(gid):
    t = profile(gid)["transparency"]
    if t >= 0.72:
        return "высокая"
    if t >= 0.6:
        return "средняя"
    return "низкая"


def fire_word(gid):
    return profile(gid)["fire"]


def optics_text(gid):
    p = profile(gid)
    return [
        f"{p['mineral']} · игра света: {p['fire']}",
        f"Прозрачность: {transparency_word(gid)} · двупреломление: {p['birefringence_value']:.3f}",
        f"Плеохроизм: {p['pleochroism_value']:.2f} · твёрдость {p['hardness']:g}",
        f"Крит. угол: {p['critical_low']:.1f}–{p['critical_high']:.1f}° · {p['cleavage']}",
        f"Блеск: {p['luster']}",
    ]
