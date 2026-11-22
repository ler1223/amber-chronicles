"""Ученичество у мастера: первые три дня (docs/design_reading_progress.md, §7).

Мастер даёт камни с известным ответом: первые метки, первое окошко, первый распил.
Потом уходит на покой — лавка и шкаф с его образцами переходят игроку.
Образец — копия учебного камня, у которой всегда можно посмотреть ответ.
"""
from __future__ import annotations

import copy
import random

from sim import gems as GM

DAYS = 3

LESSONS = {
    1: {
        "title": "День 1 · Читать камень",
        "text": ("«Возьми фонарик. Сзади — просвет: всё, что мешает свету, темнеет. Сбоку — тёмное поле: "
                 "светится то, что рассеивает. Отметь в каждом камне, что видишь, и сверься со мной — "
                 "кнопка «Ответ мастера» в осмотре.»"),
        "stones": ("read_a", "read_b"),
    },
    2: {
        "title": "День 2 · Окошко и пила",
        "text": ("«Корка прячет нутро. Открой в окатыше окошко, найди перо, поверни его ребром и распили "
                 "по нему. Гранить бери чистую половину — пусть маленькую. Засорённую — скупщику.»"),
        "stones": ("saw",),
    },
    3: {
        "title": "День 3 · Партия",
        "text": ("«Сегодня ты сам на рынке. Мешочек продают целиком и по виду — что внутри, торговец не знает. "
                 "Высыпь на стол, осмотри каждый кусок с фонариком. Хорошее нутро под плохой коркой — "
                 "твой заработок. Аренду пока плачу я.»"),
        "stones": (),
    },
}

RETIRE_TEXT = ("Мастер ушёл на покой. Лавка теперь твоя, аренда — тоже. Его учебные камни остались "
               "в шкафу «Образцы мастера»: смотри их с фонариком и сверяйся с ответом, когда сомневаешься.")


def _inc(k, p, r, **kw):
    d = {"k": k, "p": list(p), "r": r, "seed": round(random.Random(str(p)).random(), 4)}
    d.update(kw)
    return d


def _stone(xd, key, gid, shape, form, size, col, incl, seed):
    r = GM.roll_rough(xd, gid, random.Random(seed), f"lesson_{key}", size)
    r.update({"shape": shape, "form": form, "col": col, "incl": incl, "stain": 0.0, "lesson": key})
    return r


def make_stones(xd, day):
    """Учебные камни дня: включения крупные и наглядные."""
    out = []
    for key in LESSONS.get(day, {}).get("stones", ()):
        if key == "read_a":           # аметист-кристалл: перо, кристаллик, полость с пузырьком
            out.append(_stone(xd, key, "amethyst", "crystal", "prism", 2.4, 0.6, [
                _inc("feather", (0.30, -0.15, 0.25), 0.17, n=[0.55, 0.35, 0.76]),
                _inc("crystal", (-0.25, 0.25, -0.15), 0.07, axis=[0.3, 0.2, 0.93], aspect=1.4),
                _inc("two_phase", (0.10, 0.30, -0.45), 0.07, aspect=1.6),
            ], 9101))
        elif key == "read_b":         # сапфир-обломок: отпечаток, облако, белая зона
            out.append(_stone(xd, key, "sapphire", "fragment", "massive", 2.2, 0.55, [
                _inc("fingerprint", (-0.20, 0.10, 0.20), 0.22, n=[0.2, 0.8, 0.56]),
                _inc("cloud", (0.25, -0.20, -0.10), 0.11, axis=[0, 0, 1], aspect=1.3),
                _inc("milky", (0.10, 0.35, -0.50), 0.22),
            ], 9102))
        elif key == "saw":            # окатыш с пером поперёк середины: распилить по нему
            out.append(_stone(xd, key, "sapphire", "pebble", "massive", 2.6, 0.6, [
                _inc("feather", (0.0, 0.0, 0.0), 0.45, n=[1.0, 0.0, 0.0]),
                _inc("crystal", (-0.35, 0.10, 0.30), 0.05, axis=[0, 1, 0], aspect=1.2),
            ], 9103))
    return out


def sample_copy(stone):
    s = copy.deepcopy(stone)
    s["uid"] = f"sample_{stone['uid']}"
    s["sample"] = True
    s.pop("marks", None)
    return s
