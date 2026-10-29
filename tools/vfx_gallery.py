"""Галерея эффектов: поле боя с юнитами, эффекты по очереди — навыки (база и обе ветки на 2-й ступени), атаки,
реакции, смерть.

python tools/vfx_gallery.py                 окно: ←/→ — эффект, Space — повтор, A — автоповтор, Esc — выход
python tools/vfx_gallery.py --sheet out.png раскадровка без окна (кадры 0.12/0.35/0.7 с)
python tools/vfx_gallery.py --sheet out.png --only fireball,heal
python tools/vfx_gallery.py --sheet out.png --times 0.1,0.25,0.5,0.9
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

parser = argparse.ArgumentParser()
parser.add_argument("--sheet")
parser.add_argument("--only")
parser.add_argument("--times", default="0.12,0.35,0.7")
args = parser.parse_args()
if args.sheet:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.battle_scene import BattleScene  # noqa: E402
from sim.build import skill_in_branch  # noqa: E402
from sim.data import GameData  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.present import Presenter  # noqa: E402


def entries(data, scene):
    """(подпись, функция запуска): навыки игроков и врагов, атаки, реакции, смерть."""
    view, c = scene.view, scene.combat
    caster = c.units[2]              # маг
    ally = c.units[0]
    foes = [u for u in c.units if u.team != caster.team]
    target, second = foes[0], foes[1]
    caster.cell, caster.prev_cell = (2, 3), (2, 3)
    ally.cell, ally.prev_cell = (3, 1), (3, 1)
    target.cell, target.prev_cell = (6, 2), (6, 2)
    second.cell, second.prev_cell = (7, 3), (7, 3)
    out = []
    lib = view.vfx.lib["skills"]
    for sid in lib:
        if sid.startswith("_"):
            continue
        for branch in [None] + sorted(lib[sid].get("branches", {})):
            sk = skill_in_branch(data, sid, branch, 2) if branch else data.skills[sid]

            def run(sid=sid, sk=sk):
                caster.skill_defs[sid] = sk
                caster.stun = 0
                target.stun = 2.0 if any(e["type"] == "stun" for e in sk["effects"]) else 0
                if sk["cast"] > 0:
                    caster.cast = {"skill": sid, "target": None, "left": 0.0, "total": sk["cast"]}
                    view.consume([{"t": "cast_start", "unit": caster, "skill": sid}])
                    caster.cast = None
                tgt = {"enemy": target, "ally": ally, "self": caster}.get(sk["target"])
                center = tgt.cell if tgt else target.cell
                tag = next((e.get("tag") for e in sk["effects"] if e.get("tag")), None)
                evs = [{"t": "skill", "unit": caster, "skill": sid, "center": center, "target": tgt, "auto": False}]
                types = {e["type"] for e in sk["effects"]}
                if "line" in types:
                    evs.append({"t": "line", "src": caster, "cells": [(3, 3), (4, 3), (5, 2), (6, 2), (7, 2)]})
                if "chain" in types:
                    evs.append({"t": "link", "src": target, "dst": second, "color": (255, 150, 60)})
                evs.append({"t": "damage", "unit": target, "amount": 30, "absorbed": 0, "kind": "spell", "tag": tag,
                            "cover": False, "blocked": None})
                view.consume(evs)
            label = sk["name"] + (f" ({branch}2)" if branch else "")
            out.append((f"{sid} — {label}", run))
    for kind, src in (("melee", c.units[0]), ("ranged", c.units[1]), ("spell", caster)):
        def run(kind=kind, src=src):
            view.consume([{"t": "attack", "src": src, "dst": target, "kind": "melee" if kind == "melee" else "ranged",
                           "tag": None}])
        out.append((f"атака: {kind}", run))
    for rid, tags in (("steam", ["fire", "water"]), ("melt", ["fire", "ice"]), ("freeze", ["water", "ice"])):
        out.append((f"реакция: {rid}", lambda rid=rid, tags=tags: view.consume(
            [{"t": "reaction", "unit": target, "id": rid, "name": rid, "tags": tags}])))
    out.append(("смерть врага", lambda: view.consume([{"t": "death", "unit": target}])))
    out.append(("взрыв жука", lambda: view.consume([{"t": "skill", "unit": target, "skill": None, "center": target.cell,
                                                      "target": None}])))
    return out


def main():
    pygame.init()
    data = GameData()
    size = (T.SCREEN_W, T.SCREEN_H)
    if args.sheet:
        screen = pygame.display.set_mode((10, 10))
        presenter = Presenter(screen, True, window=False)
    else:
        screen = pygame.display.set_mode(size, pygame.OPENGL | pygame.DOUBLEBUF, vsync=1)
        presenter = Presenter(screen, True, window=True)
    scene = BattleScene(data, 0, autoplay=False)
    scene.phase = "battle"
    for u in scene.combat.units:
        u.ap = u.ap_max
    items = entries(data, scene)
    if args.only:
        keep = args.only.split(",")
        items = [it for it in items if any(it[0].startswith(k) for k in keep)]

    def reset():
        scene.view.reset(scene.combat)
        scene.combat.events.clear()

    if args.sheet:
        times = [float(t) for t in args.times.split(",")]
        tw, th = 400, 250
        sheet = pygame.Surface((tw * len(times), th * len(items)))
        for row, (name, run) in enumerate(items):
            reset()
            run()
            t = 0.0
            for col, at in enumerate(times):
                while t < at:
                    scene.view.update(1 / 60, 1 / 60)
                    t += 1 / 60
                presenter.frame(scene)
                img = presenter.snapshot().subsurface(pygame.Rect(T.GRID_X + 60, T.GRID_Y - 40, 640, 400))
                sheet.blit(pygame.transform.smoothscale(img, (tw, th)), (col * tw, row * th))
            T.text(sheet, f"{name}", (8, row * th + 6), 18, (255, 255, 120), True, shadow=True)
        pygame.image.save(sheet, args.sheet)
        return

    clock = pygame.time.Clock()
    i, auto, timer = 0, True, 0.0
    reset()
    items[i][1]()
    running = True
    while running:
        dt = clock.tick(60) / 1000
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RIGHT, pygame.K_LEFT):
                    i = (i + (1 if ev.key == pygame.K_RIGHT else -1)) % len(items)
                    reset()
                    items[i][1]()
                    timer = 0.0
                elif ev.key == pygame.K_SPACE:
                    items[i][1]()
                elif ev.key == pygame.K_a:
                    auto = not auto
        timer += dt
        if auto and timer > 2.2:
            timer = 0.0
            items[i][1]()
        k = scene.view.vfx.screen.time_k()          # стоп-кадр и замедление — как в бою
        scene.view.update(dt * k, dt)
        scene.toast = (f"{i + 1}/{len(items)}  {items[i][0]}   ←/→ эффект · Space повтор · A автоповтор", 1)
        presenter.frame(scene)
        pygame.display.flip()


if __name__ == "__main__":
    main()
