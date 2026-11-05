"""Время полёта снаряда, заданное боем (sim/combat.py, hit_delay): пока визуал навыка или выстрела запускается,
все снаряды (ui/vfx.py, ui/pixfx.py, ui/pix_spells.py) летят ровно столько — урон и вспышка совпадают."""
from contextlib import contextmanager

NOW = [None]


def get():
    return NOW[0]


@contextmanager
def fixed(dur):
    old = NOW[0]
    NOW[0] = dur if dur else None
    try:
        yield
    finally:
        NOW[0] = old
