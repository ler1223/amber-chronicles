"""Настройки отображения: свечение, тряска, стоп-кадр, вспышки и аберрация, зум камеры, детализация моделей,
пиксельные эффекты. Хранятся в save/settings.json.

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
    ("window", "Окно (F11 — полный экран)", ["auto", "1280x800", "1600x1000", "1920x1200", "fullscreen"],
     ["по экрану", "1280×800", "1600×1000", "1920×1200", "полный экран"]),
    ("sprite_res", "Детализация моделей", [16, 32, 64], ["низкая (16 px)", "обычная (32 px)", "высокая (64 px)"]),
    ("fx_alpha", "Прозрачность эффектов боя", [1.0, 0.75, 0.5, 0.3], ["нет", "лёгкая", "средняя", "сильная"]),
    ("text_status", "Надписи: криты и состояния", [True, False], ["вкл", "выкл"]),
    ("text_skills", "Надписи: названия навыков", [True, False], ["вкл", "выкл"]),
    ("text_numbers", "Числа урона и лечения", [True, False], ["вкл", "выкл"]),
    ("gl_safe_upload", "Совместимость графики (Mac)", [False, True],
     ["авто", "вкл"]),
    ("autocast_start", "Автокаст в начале похода", ["default", "on", "off"],
     ["как задумано", "всё включено", "всё выключено"]),
    ("fx_style", "Стиль огня и льда (F9)", ["old", "pixel", "flipbook", "shader", "mesh", "fluid"],
     ["старые", "пиксельные", "флипбуки Blender", "шейдеры", "меш-эффекты", "симуляция"]),
]
DEFAULTS = {"bloom": 1.0, "shake": 1.0, "hitstop": True, "flash": 1.0, "zoom": True, "window": "auto",
            "sprite_res": 32, "fx_style": "pixel", "autocast_start": "default", "battle_speed": 1,
            "fx_alpha": 1.0, "text_status": True, "text_skills": True, "text_numbers": True,
            "gl_safe_upload": False}
STYLES = next(o[2] for o in OPTIONS if o[0] == "fx_style")


def style():
    return SETTINGS.get("fx_style", "pixel")


def next_style():
    """F9: следующий стиль эффектов по кругу. Возвращает подпись."""
    cycle("fx_style")
    return label("fx_style")
SETTINGS = dict(DEFAULTS)


def load(path=None):
    path = path or PATH                  # PATH читается при вызове: тесты подменяют его на временный файл
    SETTINGS.clear()
    SETTINGS.update(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for key, _, values, _ in OPTIONS:
            if d.get(key) in values:
                SETTINGS[key] = d[key]
        if isinstance(d.get("battle_speed"), int) and not isinstance(d["battle_speed"], bool):
            SETTINGS["battle_speed"] = d["battle_speed"]     # скорость боя: индекс в config.speeds, без пункта меню
    except (OSError, ValueError):
        pass
    return SETTINGS


def save(path=None):
    path = path or PATH
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def put(key, value):
    """Запомнить значение и сразу сохранить (скорость боя, автокаст похода)."""
    if SETTINGS.get(key) != value:
        SETTINGS[key] = value
        save()


def cycle(key):
    """Следующее значение настройки по кругу."""
    values = next(o[2] for o in OPTIONS if o[0] == key)
    i = values.index(SETTINGS[key]) if SETTINGS[key] in values else 0
    SETTINGS[key] = values[(i + 1) % len(values)]
    return SETTINGS[key]


def label(key):
    _, _, values, labels = next(o for o in OPTIONS if o[0] == key)
    return labels[values.index(SETTINGS[key])] if SETTINGS[key] in values else str(SETTINGS[key])
