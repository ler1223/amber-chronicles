"""Оптические профили камней для осмотра и рендера.

Значения приближены к реальным минералам: показатель преломления, дисперсия,
прозрачность и двупреломление. Игрок видит их через блик, игру света и
просвечивание, а не через таблицу характеристик.
"""

PROFILES = {
    "ruby": {
        "mineral": "Корунд", "ior": (1.760, 1.768, 1.778), "dispersion": 0.018,
        "transparency": 0.62, "birefringence": "слабое", "fire": "средняя",
        "hardness": 9.0, "pleochroism": "слабое", "word": "стеклянный, тёплый",
    },
    "sapphire": {
        "mineral": "Корунд", "ior": (1.760, 1.768, 1.778), "dispersion": 0.018,
        "transparency": 0.68, "birefringence": "слабое", "fire": "средняя",
        "hardness": 9.0, "pleochroism": "слабое", "word": "холодный, чистый",
    },
    "emerald": {
        "mineral": "Берилл", "ior": (1.564, 1.576, 1.602), "dispersion": 0.014,
        "transparency": 0.58, "birefringence": "заметное", "fire": "мягкая",
        "hardness": 7.8, "pleochroism": "заметное", "word": "маслянистый, глубокий",
    },
    "topaz": {
        "mineral": "Топаз", "ior": (1.609, 1.620, 1.643), "dispersion": 0.014,
        "transparency": 0.72, "birefringence": "заметное", "fire": "средняя",
        "hardness": 8.0, "pleochroism": "заметное", "word": "стеклянный, искристый",
    },
    "amethyst": {
        "mineral": "Кварц", "ior": (1.544, 1.550, 1.553), "dispersion": 0.013,
        "transparency": 0.76, "birefringence": "слабое", "fire": "низкая",
        "hardness": 7.0, "pleochroism": "слабое", "word": "прозрачный, фиолетовый",
    },
}

_DEFAULT = {
    "mineral": "Минерал", "ior": (1.58, 1.60, 1.62), "dispersion": 0.014,
    "transparency": 0.6, "birefringence": "слабое", "fire": "средняя",
    "hardness": 7.0, "pleochroism": "слабое", "word": "стеклянный",
}


def profile(gid):
    return dict(PROFILES.get(gid, _DEFAULT))


def absorption(gid, color):
    """Поглощение по каналам: прозрачный камень почти не глушит свет."""
    p = profile(gid)
    t = max(0.15, float(p["transparency"]))
    rgb = [max(0.0, min(1.0, c / 255.0)) for c in color[:3]]
    return tuple(min(0.055, (1.0 - c) ** 1.35 * 0.022 / t + 0.0003) for c in rgb)


def transparency_word(gid):
    t = profile(gid)["transparency"]
    if t >= 0.72:
        return "высокая"
    if t >= 0.6:
        return "средняя"
    return "низкая"


def optics_text(gid):
    p = profile(gid)
    return [f"{p['mineral']} · игра света: {p['fire']}",
            f"Прозрачность: {transparency_word(gid)} · двупреломление: {p['birefringence']}",
            f"Плеохроизм: {p['pleochroism']} · твёрдость {p['hardness']:g}",
            f"Блеск: {p['word']}"]
