"""«Спуск» — прототип карточного рогалика (docs/descent.md). Отдельно от экспедиции (main.py).

python descent.py               — играть: Наёмник спускается по этажам подземелья (карта этажа, бои, костёр, торговец)
python descent.py --seed 5      — те же раздачи
python descent.py --window      — в окне (по умолчанию — во весь экран; F11 / Alt+Enter — переключить)
python descent.py --screenshot out.png [--seconds 2]  — без окна: кадр боя

Бой: тяните карту на цель — ЛКМ основное применение (за энергию), ПКМ простое (бесплатно: шаг, слабый удар, малая
защита); или клик по карте, затем по цели. Space — конец хода. Наведите на врага — его намерение и ход.
Карта этажа: клик по узлу или 1–3, D — колода. Esc — назад/пауза с выходом из забега или игры;
в бою Esc только закрывает чтение и снимает выбор — выйти из боя нельзя.
"""
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--screenshot")
parser.add_argument("--seconds", type=float, default=2.0)
parser.add_argument("--window", action="store_true")
args = parser.parse_args()
if args.screenshot:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from ui import theme as T  # noqa: E402


def main():
    pygame.init()
    pygame.display.set_caption("Спуск — прототип")
    from deck import gfx as G
    from ui import audio, settings
    settings.load()                                  # качество моделек (M на карте этажа) и прочее — с прошлого раза
    if not args.screenshot:
        audio.start()                                # тихий фон; громкость — F10 в игре
    full = not args.window and not args.screenshot

    def open_window(full):
        """Во весь экран — в родном разрешении монитора (интерфейс рисуется чётко, не растягивается)."""
        if full:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H), pygame.RESIZABLE)

    screen = open_window(full)
    canvas = G.Canvas(screen)
    from deck.game import DescentGame
    from deck import save as SV
    game = DescentGame(seed=args.seed, save_path=None if args.screenshot else SV.PATH)   # забег сохраняется сам
    clock = pygame.time.Clock()
    t = 0.0
    while True:
        dt = min(0.05, clock.tick(60) / 1000.0)
        t += dt
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                return
            if ev.type == pygame.KEYDOWN and (ev.key == pygame.K_F11 or
                                              (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT)):
                full = not full
                screen = open_window(full)
                canvas = G.Canvas(screen)
                continue
            if ev.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                screen = pygame.display.get_surface()
                canvas = G.Canvas(screen)
                continue
            if hasattr(ev, "pos"):                          # мышь — в логические координаты 1280×800
                d = dict(ev.dict)
                d["pos"] = tuple(int(v) for v in G.to_logical(canvas, ev.pos))
                if "rel" in d:
                    d["rel"] = (int(d["rel"][0] / canvas.S), int(d["rel"][1] / canvas.S))
                ev = pygame.event.Event(ev.type, d)
            game.handle(ev)
            if game.quit_requested:
                pygame.quit()
                return
        game.update(dt)
        screen.fill((10, 8, 6))
        with G.native(canvas):
            game.draw(canvas)
        pygame.display.flip()
        if args.screenshot and t >= args.seconds:
            pygame.image.save(screen, args.screenshot)
            pygame.quit()
            return


if __name__ == "__main__":
    main()
