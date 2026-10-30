"""Настройки отображения: свечение, тряска, стоп-кадр, вспышки и аберрация, зум камеры, пиксельные эффекты. Хранятся в save/settings.json.

Действуют сразу: эффекты читают их при запуске экранного эффекта, рендер — каждый кадр.
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "save", "settings.json")

# (ключ, название, варианты, подписи)
OPTIONS = [
    ("bloom", "Свечение эффектов", [0.0, 0.5, 1.0, 1.4], ["выкл", "слабое", "обычное", "сильное"]),
    ("shake", "Тряска экрана", [0.0, 0.5, 1.0], ["выкл", "слабая", "обычная"]),
    ("hitstop", "Стоп-кадр на ударах", [False, True], ["выкл", "вкл"]),
    ("flash", "Вспышки и аберрация", [0.0, 0.5, 1.0], ["выкл", "слабые", "обычные"]),
    ("zoom", "Зум камеры", [False, True], ["выкл", "вкл"]),
    ("pixel_fx", "Пиксельные огонь и лёд (F9 в бою)", [False, True], ["старые", "пиксельные"]),
]
DEFAULTS = {"bloom": 1.0, "shake": 1.0, "hitstop": True, "flash": 1.0, "zoom": True, "pixel_fx": True}
SETTINGS = dict(DEFAULTS)


def load(path=PATH):
    SETTINGS.clear()
    SETTINGS.update(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for key, _, values, _ in OPTIONS:
            if d.get(key) in values:
                SETTINGS[key] = d[key]
    except (OSError, ValueError):
        pass
    return SETTINGS


def save(path=PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def cycle(key):
    """Следующее значение настройки по кругу."""
    values = next(o[2] for o in OPTIONS if o[0] == key)
    i = values.index(SETTINGS[key]) if SETTINGS[key] in values else 0
    SETTINGS[key] = values[(i + 1) % len(values)]
    return SETTINGS[key]


def label(key):
    _, _, values, labels = next(o for o in OPTIONS if o[0] == key)
    return labels[values.index(SETTINGS[key])] if SETTINGS[key] in values else str(SETTINGS[key])
