"""Фоновая музыка: настройки, ступени громкости и панель F10."""
import os

import pygame

from deck.sound import SoundPanel
from ui import audio
from ui import settings


def test_music_file_and_settings_exist():
    assert os.path.getsize(audio.MUSIC_PATH) > 100_000
    levels = audio.levels()
    assert len(levels) == 101
    assert levels[0] == 0.0 and levels[-1] == 1.0
    assert settings.DEFAULTS["music_volume"] in levels
    assert any(key == "music_volume" for key, _, _, _ in settings.OPTIONS)


def test_all_music_locations_have_existing_tracks():
    assert {"menu", "swamp", "dungeon", "forge", "battle", "boss", "camp", "shop", "end"} <= set(audio.TRACKS)
    for names in audio.TRACKS.values():
        assert names and all(os.path.getsize(os.path.join(audio.AUDIO_DIR, name)) > 100_000 for name in names)


def test_context_can_be_set_before_music_starts(monkeypatch):
    monkeypatch.setattr(audio, "_ensure_mixer", lambda: False)
    monkeypatch.setattr(audio, "_started", False)
    monkeypatch.setattr(audio, "_loaded", False)
    audio.set_context("battle")
    assert audio.context() == "battle"


def test_volume_steps_and_mute(monkeypatch):
    monkeypatch.setattr(audio, "_ensure_mixer", lambda: False)
    audio.set_index(0, save=False)
    assert audio.percent() == 0
    assert audio.volume_text() == "0%"
    audio.adjust(1)
    assert audio.percent() == 1
    audio.set_index(37, save=False)
    assert audio.percent() == 37
    audio.toggle_mute()
    assert audio.is_muted()
    assert audio.volume_text().endswith("выкл")
    audio.toggle_mute()
    assert not audio.is_muted()


def test_audio_hotkeys_require_ctrl(monkeypatch):
    monkeypatch.setattr(audio, "_ensure_mixer", lambda: False)
    plain = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10, mod=0)
    ctrl = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10, mod=pygame.KMOD_CTRL)
    assert not audio.handle_key(plain)
    assert audio.handle_key(ctrl)


def test_sound_panel_f10_and_escape(monkeypatch):
    monkeypatch.setattr(audio, "_ensure_mixer", lambda: False)
    panel = SoundPanel()
    assert not panel.open
    assert panel.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10))
    assert panel.open
    assert panel.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert not panel.open
