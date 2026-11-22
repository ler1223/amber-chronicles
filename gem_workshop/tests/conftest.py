"""Тесты подпроекта «Грань» — против его собственных пакетов.

В корне репозитория есть одноимённые пакеты основной игры (game, sim, ui, workshop) и
свой pytest.ini; без этой правки тест мог взять, например, game.jewel_view основной игры.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.path[0] != HERE:
    sys.path.insert(0, HERE)
for _name in list(sys.modules):
    if _name.split(".")[0] in ("game", "sim", "ui", "workshop"):
        _f = getattr(sys.modules[_name], "__file__", "") or ""
        if not os.path.abspath(_f).startswith(HERE):
            del sys.modules[_name]
