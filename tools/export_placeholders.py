"""Выгружает пиксельные заглушки юнитов в assets/sprites/_templates/<id>.png (32×32) — шаблоны для перерисовки.

python tools/export_placeholders.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim.data import GameData  # noqa: E402
from ui.sprites import ASSET_DIR, DRAWERS, ROLE_FALLBACK, placeholder  # noqa: E402


def main():
    pygame.init()
    data = GameData()
    out = os.path.join(ASSET_DIR, "_templates")
    os.makedirs(out, exist_ok=True)
    units = {**data.classes, **data.enemies}
    for uid, proto in units.items():
        kind = uid if uid in DRAWERS else ROLE_FALLBACK.get(proto["role"], "warrior")
        pygame.image.save(placeholder(kind, proto["color"]), os.path.join(out, f"{uid}.png"))
    for pid, path in data.paths.items():
        cls = data.classes[path["class"]]
        pygame.image.save(placeholder(path["class"], cls["color"]), os.path.join(out, f"{pid}.png"))
    print(f"шаблоны: {out}")


if __name__ == "__main__":
    main()
