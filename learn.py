"""Хроники янтаря — режим обучения: та же экспедиция (отряд или одиночка), но героями и врагами управляют нейросети.

Каждый герой учится в каждом бою (своя сеть, ветеран уносит её в следующий поход; новичок начинает со «школы
класса» — data/neural, её готовит tools/train_schools.py). Игрок может вмешаться: его приказ главнее, а сеть
учится на нём. В бою слева — «что думает сеть» выбранного героя; в лагере — «Тренировка сети» (20 быстрых боёв
без графики); в листе героя — график награды. Враги — тоже сети, по одной на вид врага, и тоже учатся.

Отдельное сохранение: save/learn.json и сети save/learn_nets/ (обычная игра main.py их не трогает).


python learn.py                  — режим обучения: таверна, поход отрядом или в одиночку (выбор в таверне);
                                  окно тянется мышью, F11 / Alt+Enter — полный экран, размер — в настройках
python learn.py --solo           — таверна сразу в режиме «Одиночка»
python learn.py --seed 42        — походы с конкретными картами
python learn.py --autoplay       — отрядом в боях управляет ИИ (демо)
python learn.py --cpu            — без OpenGL (эффекты упрощённо, без свечения; в Одиночке — без камеры за героем)
python learn.py --sandbox        — песочница: открыто всё (свой профиль, настоящий не трогается);
                                  в бою F7 — полные AP, перезарядки и шкалы, F8 — мгновенная победа
python learn.py --screenshot out.png --seconds 3
                                — без окна: таверна, прокрутить и сохранить кадр

"""
import argparse
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--autoplay", action="store_true")
parser.add_argument("--sandbox", action="store_true")
parser.add_argument("--cpu", action="store_true")
parser.add_argument("--solo", action="store_true")
parser.add_argument("--expedition", action="store_true")
parser.add_argument("--screenshot")
parser.add_argument("--seconds", type=float, default=3.0)
args = parser.parse_args()

if args.screenshot:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.app import App, stats_path  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.expedition import ExpeditionProfile, expedition_data  # noqa: E402
from ui import settings  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.present import Presenter  # noqa: E402


def make_app(data):
    """Приложение в режиме Экспедиции или Одиночки — каждый со своим сохранением рядом с save/profile.json."""
    base = os.path.join(ROOT, "save", "sandbox.json" if args.sandbox else "profile.json")
    mode = "solo" if args.solo else "expedition"
    path = None if args.screenshot else stats_path(base, "learn")           # свой сейв режима обучения
    prof = ExpeditionProfile(expedition_data(data), path, sandbox=args.sandbox, solo=mode == "solo")
    prof.mode, prof.path = mode, path
    app = App(data, args.seed, args.autoplay, prof, start="hub" if args.screenshot else "title", launcher="learn")
    app._base_path = None
    from game.learn_mode import Learner
    app.neural = Learner(os.path.join(ROOT, "save", "sandbox_learn_nets" if args.sandbox else "learn_nets"))
    return app


def main():
    pygame.init()
    settings.load()
    pygame.display.set_caption("Хроники янтаря — обучение")
    use_gl = not args.cpu
    disp = None
    if args.screenshot:
        screen = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
        presenter = Presenter(screen, use_gl, window=False)
    else:                                            # окно тянется, кадр 1280×800 растягивается под него
        from ui.display import Display
        disp = Display(use_gl)
        presenter = Presenter(disp.screen, use_gl, window=True)
        if use_gl and not presenter.gl:              # окно OpenGL не взлетело — обычное окно
            disp = Display(False)
            presenter = Presenter(disp.screen, False)
    clock = pygame.time.Clock()
    holder = make_app(GameData())

    if args.screenshot:
        for _ in range(int(args.seconds * 60)):
            holder.scene.update(1 / 60)
        presenter.frame(holder.scene)
        pygame.image.save(presenter.snapshot(), args.screenshot)
        pygame.quit()
        return

    def on_resize():
        presenter.resize()
        holder.relayout()

    disp.on_resize = on_resize
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and (ev.key == pygame.K_F11 or
                                                (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT)):
                disp.toggle_fullscreen()
            elif ev.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                disp.sync()                      # пересчитать холст: ширина сцен следует за окном
            else:
                ev = disp.to_logical(ev)
                scene = holder.scene
                if getattr(scene, "stage", False) and ev.type in (
                        pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    ox = T.content_ox()          # сцена-колонка 1280: сдвигаем мышь в её координаты
                    d = dict(ev.dict)
                    if "pos" in d:
                        d["pos"] = (d["pos"][0] - ox, d["pos"][1])
                    ev = pygame.event.Event(ev.type, d)
                scene.handle(ev)
        holder.scene.update(dt)
        if holder.quit:
            running = False
            continue
        presenter.frame(holder.scene)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
