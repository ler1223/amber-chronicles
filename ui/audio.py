"""Фоновая музыка и её громкость.

Треки подобраны по локациям в фэнтезийном духе: меню, болото, подземелье,
кузни, бой, босс, лагерь, магазин и финал. Все файлы — CC0, источники и
авторы перечислены в assets/audio/README.md.

Музыка не должна ломать запуск на машине без аудиоустройства, поэтому все
ошибки mixer здесь намеренно проглатываются.
"""
import os
import random

import pygame

from ui import settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "assets", "audio")

# Локация → список треков. При смене локации выбирается другой трек, а при
# возвращении в ту же локацию после боя — соседний, чтобы не было повторов.
TRACKS = {
    "menu": ("menu_mythica.ogg", "menu_doodle.ogg"),
    "swamp": ("forest_ambience.ogg", "alone.ogg"),
    "dungeon": ("dungeon_ambience.ogg", "narrow_corridors.ogg", "cave_explorer.ogg"),
    "forge": ("portal.ogg", "crystal_cave.ogg"),
    "battle": ("battle_theme_a.ogg", "battle_random.ogg"),
    "boss": ("battle_theme_a.ogg", "war_boss.ogg", "battle_random.ogg"),
    "camp": ("tavern_grog.ogg", "forest_ambience.ogg"),
    "shop": ("tavern_grog.ogg", "menu_doodle.ogg"),
    "end": ("alone.ogg",),
}
MUSIC_PATH = os.path.join(AUDIO_DIR, TRACKS["menu"][0])   # совместимость/тест наличия
_VOLUMES = next(values for key, _, values, _ in settings.OPTIONS if key == "music_volume")
_started = False
_loaded = False
_current = None
_context = None


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


def _pick(context):
    """Выбрать существующий трек локации, по возможности не повторяя текущий."""
    names = [name for name in TRACKS.get(context, TRACKS["menu"])
             if os.path.exists(os.path.join(AUDIO_DIR, name))]
    if not names:
        names = list(TRACKS["menu"])
    if len(names) > 1 and _current in names:
        names = [name for name in names if name != _current] or names
    return os.path.join(AUDIO_DIR, random.choice(names))


def _switch(context, force=False):
    """Загрузить трек локации. Не запускает звук, пока start() не активировал музыку."""
    global _loaded, _current, _context
    if not _started or not _ensure_mixer():
        _context = context
        return False
    if not force and _loaded and _context == context:
        return True
    path = _pick(context)
    try:
        pygame.mixer.music.fadeout(300)
        pygame.mixer.music.load(path)
        _loaded = True
        _current = os.path.basename(path)
        _context = context
        pygame.mixer.music.set_volume(_effective())
        if _effective() > 0:
            pygame.mixer.music.play(loops=-1, fade_ms=1200)
        return True
    except pygame.error:
        return False


def start():
    """Запустить музыку и применить сохранённую громкость."""
    global _started
    _started = True
    return _switch(_context or "menu", force=True)


def set_context(context):
    """Сменить музыкальную локацию (menu, swamp, dungeon, forge, battle, boss, camp, shop, end)."""
    global _context
    if context not in TRACKS:
        context = "menu"
    if _started and _context == context and _loaded:
        return True
    return _switch(context)


def context():
    return _context or "menu"


def track_name():
    """Имя текущего файла — для панели звука и отладки."""
    return _current or ""


def apply():
    """Сразу применить громкость/выключение, не перезапуская трек."""
    if not _ensure_mixer():
        return
    try:
        pygame.mixer.music.set_volume(_effective())
        if _started and _loaded and not pygame.mixer.music.get_busy() and _effective() > 0:
            pygame.mixer.music.play(loops=-1, fade_ms=600)
    except pygame.error:
        pass


def levels():
    """Доступные ступени громкости для ползунка (0…100 с шагом 1%)."""
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
    """Стрелки/ползунок: изменить громкость на одну ступень (1%)."""
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
