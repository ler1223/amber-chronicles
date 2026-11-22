"""Фоновая музыка и её громкость.

Музыка одна на всю игру: тихий бесшовный эмбиент из assets/audio. Настройки хранятся вместе
с остальными в save/settings.json. Звук не должен ломать запуск на машине без аудиоустройства,
поэтому все ошибки mixer здесь намеренно проглатываются.
"""
import os

import pygame

from ui import settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC_PATH = os.path.join(ROOT, "assets", "audio", "outer_space_loop.ogg")
_VOLUMES = next(values for key, _, values, _ in settings.OPTIONS if key == "music_volume")
_loaded = False


def _ensure_mixer():
    """Инициализировать mixer по требованию; на headless/без звуковой карты вернуть False."""
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        return pygame.mixer.get_init() is not None
    except (pygame.error, OSError):
        return False


def _effective():
    if settings.SETTINGS.get("music_muted", False):
        return 0.0
    try:
        return max(0.0, min(1.0, float(settings.SETTINGS.get("music_volume", 0.35))))
    except (TypeError, ValueError):
        return 0.0


def start():
    """Запустить музыку (один раз) и применить сохранённую громкость."""
    global _loaded
    if not os.path.exists(MUSIC_PATH) or not _ensure_mixer():
        return False
    try:
        if not _loaded:
            pygame.mixer.music.load(MUSIC_PATH)
            _loaded = True
        pygame.mixer.music.set_volume(_effective())
        if not pygame.mixer.music.get_busy():
            pygame.mixer.music.play(loops=-1, fade_ms=1200)
        return True
    except pygame.error:
        return False


def apply():
    """Сразу применить громкость/выключение, не перезапуская трек."""
    if not _ensure_mixer():
        return
    try:
        pygame.mixer.music.set_volume(_effective())
        if _loaded and not pygame.mixer.music.get_busy() and _effective() > 0:
            pygame.mixer.music.play(loops=-1, fade_ms=600)
    except pygame.error:
        pass


def levels():
    """Доступные ступени громкости для ползунка."""
    return list(_VOLUMES)


def index():
    """Индекс текущей громкости в списке настроек (для ползунка)."""
    value = settings.SETTINGS.get("music_volume", 0.35)
    return _VOLUMES.index(value) if value in _VOLUMES else min(
        range(len(_VOLUMES)), key=lambda i: abs(_VOLUMES[i] - float(value)))


def is_muted():
    return bool(settings.SETTINGS.get("music_muted", False))


def set_index(i, save=True):
    """Поставить громкость по индексу ползунка и сразу применить."""
    i = max(0, min(len(_VOLUMES) - 1, int(i)))
    settings.SETTINGS["music_volume"] = _VOLUMES[i]
    settings.SETTINGS["music_muted"] = False
    if save:
        settings.save()
    apply()
    return _VOLUMES[i]


def adjust(step=1):
    """Стрелки/ползунок: изменить громкость на одну ступень."""
    i = max(0, min(len(_VOLUMES) - 1, index() + int(step)))
    return set_index(i)


def toggle_mute():
    """F10 / кнопка: выключить или вернуть музыку."""
    muted = not bool(settings.SETTINGS.get("music_muted", False))
    settings.SETTINGS["music_muted"] = muted
    if not muted and float(settings.SETTINGS.get("music_volume", 0.35)) <= 0:
        settings.SETTINGS["music_volume"] = 0.35
    settings.save()
    apply()
    return muted


def percent():
    return int(round(_VOLUMES[index()] * 100))


def volume_text():
    if settings.SETTINGS.get("music_muted", False):
        return f"{percent()}% · выкл"
    return f"{percent()}%"


def handle_key(ev):
    """Горячие клавиши «Хроник янтаря»: Ctrl+F10 — выключить, Ctrl+[ / ] — громкость.

    Ctrl обязателен: обычные F10 и [ / ] уже заняты подсказкой и скоростью боя.
    Возвращает True, если событие съедено.
    """
    if ev.type != pygame.KEYDOWN or not (getattr(ev, "mod", 0) & pygame.KMOD_CTRL):
        return False
    if ev.key == pygame.K_F10:
        toggle_mute()
        return True
    if ev.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS):
        adjust(-1)
        return True
    if ev.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS):
        adjust(1)
        return True
    return False
