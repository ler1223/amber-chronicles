"""Запуск прототипа.

python main.py                  — игра: карта биома (профиль в save/profile.json), вылазки, бои;
                                  окно тянется мышью, F11 / Alt+Enter — полный экран, размер — в настройках
python main.py --seed 42        — вылазки с конкретными картами
python main.py --new-profile    — начать мету заново (старый профиль перезаписывается)
python main.py --profile p.json — другой файл профиля
python main.py --battle 2       — песочница: отдельный бой №2 (R/N/F5/F6 листают бои)
python main.py --autoplay       — отрядом в боях управляет ИИ (демо)
python main.py --battle 1 --autoplay --screenshot out.png --seconds 6
                                — без окна: прокрутить и сохранить кадр
python main.py --cpu            — без OpenGL (эффекты упрощённо, без свечения)
python main.py --stats          — режим героев: уровни, атрибуты, скейлы (свой профиль save/stats.json)
python main.py --sandbox        — песочница: открыто всё (свой профиль save/sandbox.json, настоящий не трогается);
                                  в бою F7 — полные AP, перезарядки и шкалы отряду, F8 — мгновенная победа
"""
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--battle", type=int, default=None)
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--autoplay", action="store_true")
parser.add_argument("--profile", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "save", "profile.json"))
parser.add_argument("--new-profile", action="store_true")
parser.add_argument("--sandbox", action="store_true")
parser.add_argument("--stats", action="store_true")
parser.add_argument("--cpu", action="store_true")
parser.add_argument("--screenshot")
parser.add_argument("--seconds", type=float, default=3.0)
args = parser.parse_args()

if args.screenshot:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from ui import settings  # noqa: E402
from game.battle_scene import BattleScene  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.profile import Profile  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.present import Presenter  # noqa: E402


class Sandbox:
    """Одиночный бой без забега."""

    def __init__(self, data):
        self.scene = BattleScene(data, args.battle, autoplay=args.autoplay)

    def relayout(self):
        if hasattr(self.scene, "relayout"):
            self.scene.relayout()


def main():
    pygame.init()
    settings.load()
    pygame.display.set_caption("Хроники янтаря — прототип")
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
    data = GameData()
    if args.battle is not None:
        holder = Sandbox(data)
    else:
        # скриншот без окна не трогает настоящий профиль
        path = None if args.screenshot else args.profile
        if args.sandbox and not args.screenshot:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save", "sandbox.json")
        base_path = path
        if args.stats and path:            # режим героев — свой профиль save/stats.json
            from game.app import stats_path
            path = stats_path(path)
        profile = Profile(data, None if args.new_profile else path, sandbox=args.sandbox,
                          mode="stats" if args.stats else "base")
        profile.path = path
        holder = App(data, args.seed, args.autoplay, profile, start="world" if args.screenshot else "title")
        holder._base_path = base_path

    if args.screenshot:
        frames = int(args.seconds * 60)
        for _ in range(frames):
            holder.scene.update(1 / 60)
        presenter.frame(holder.scene)
        pygame.image.save(presenter.snapshot(), args.screenshot)
        pygame.quit()
        return

    def on_resize():
        presenter.resize()
        if hasattr(holder, "relayout"):
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
                    # сцена-колонка 1280: сдвигаем мышь в её координаты
                    ox = T.content_ox()
                    d = dict(ev.dict)
                    if "pos" in d:
                        d["pos"] = (d["pos"][0] - ox, d["pos"][1])
                    if "rel" in d:
                        d["rel"] = (d["rel"][0], d["rel"][1])
                    ev = pygame.event.Event(ev.type, d)
                scene.handle(ev)
        holder.scene.update(dt)
        if getattr(holder, "quit", False):
            running = False
            continue
        presenter.frame(holder.scene)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
