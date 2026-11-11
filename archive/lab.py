"""Хроники янтаря — лаборатория обучения нейросетей: смотреть, как учатся школы классов.

Пока окно открыто, идёт обучение (sim/nn_lab.py): процессы-бойцы (по умолчанию — 75 % логических ядер, сеть на
numpy) играют случайные бои похода на текущей сети героев, врагами управляет обычный автопилот игры, ученик
(отдельный процесс, видеокарта) обновляет сеть героев методом PPO. Окно только показывает и шлёт команды —
отрисовка не тормозит обучение. Подробно — docs/neural_lab.md.

Вкладки (щелчок вверху справа или `):
  Бой        — живой показательный бой на свежих весах; щелчок по юниту — что думает его сеть
  Графики    — победы, награды, потери PPO, энтропия, скорость, загрузка процессора и видеокарты
  Автопилот  — контрольные серии: одни и те же бои сетями и автопилотом
P — пауза обучения · S — сохранить точку (save/lab или save/lab_full) · E — контроль сейчас ·
U дважды — опубликовать в data/neural или data/neural_full

python lab.py                    — лаборатория (продолжает с save/lab/ckpt, если есть, иначе со школ data/neural)
python lab.py --full             — второй путь: полное наблюдение, отдельные save/lab_full и data/neural_full
python lab.py --workers 16       — число процессов-бойцов
python lab.py --fresh            — начать с чистого листа (новые случайные сети, без школ и точки)
python lab.py --cpu              — ученик на процессоре и окно без OpenGL
python lab.py --headless 600     — без окна: учиться 600 секунд, печатать ход, сохранить точку
python lab.py --night            — на ночь: без окна 8 часов (--hours N — иначе), ход — в save/lab/train.log,
                                  точка — каждые 10 минут, компьютер не уснёт, в конце — публикация в data/neural
--publish                        — в конце опубликовать школу героев в data/neural (у --night включено)
--focus 16                       — учиться на 16 одних и тех же боях по кругу (проверить, что обучение идёт)
--opponents rules=1              — с кем бьются герои (rules — правила игры, latest — сеть врагов, past — её прошлые)
--no-balance                     — не подстраивать силу врагов под balance_target: фиксированная сложность
--reward команда                 — пресет награды (по умолчанию команда)
--teacher-share 0.1 --dagger-share 0.1 — доли BC-учителя и DAgger (бот размечает состояния сети)
--net-autocast                   — сеть тоже пользуется автоприменением навыков
--eval-power 1.0 --eval-size 100 — фиксированная сила и длина контрольной серии
--hero-gear none                  — герои без снаряжения (по умолчанию auto: вещи по акту похода)

Полный путь не меняет старый: у него свои папки, своя точка и своя опубликованная школа. Планировщики в нём по
умолчанию выключены (полное наблюдение дороже), но испытания `tools/trials.py --full --modes planner` работают.

Точка сохраняется каждые 10 минут: прервали (Ctrl+C, сбой, свет) — следующий запуск продолжит с неё.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--headless", type=float, default=None)
    p.add_argument("--night", action="store_true")
    p.add_argument("--hours", type=float, default=8.0)
    p.add_argument("--publish", action="store_true")
    p.add_argument("--focus", type=int, default=0)
    p.add_argument("--opponents", default=None)
    p.add_argument("--no-balance", action="store_true")
    p.add_argument("--reward", default=None, help="пресет награды: команда/командный/роли/урон/победа")
    p.add_argument("--teacher-share", type=float, default=None, help="доля боёв подражания автопилоту")
    p.add_argument("--dagger-share", type=float, default=None, help="доля боёв DAgger (сеть играет, бот размечает)")
    p.add_argument("--bc", type=float, default=None, help="вес ошибки подражания в PPO")
    p.add_argument("--net-autocast", action="store_true", help="включить автоприменение навыков и для сети")
    p.add_argument("--eval-size", type=int, default=None, help="боёв в контрольной серии")
    p.add_argument("--eval-power", type=float, default=None, help="фиксированная сила врагов в контроле")
    p.add_argument("--hero-gear", default=None, choices=("auto", "none"),
                   help="снаряжение героев в лаборатории: auto (по акту) или none")
    p.add_argument("--power-jitter", type=float, default=None, help="разброс силы врагов вокруг баланса")
    p.add_argument("--balance-target", type=float, default=None, help="целевая доля побед героев")
    p.add_argument("--batch", type=int, default=None, help="образцов на шаг PPO")
    p.add_argument("--epochs", type=int, default=None, help="проходов по пачке PPO")
    p.add_argument("--minibatch", type=int, default=None, help="размер мини-пачки PPO")
    p.add_argument("--gamma", type=float, default=None, help="дисконт PPO")
    p.add_argument("--lr", type=float, default=None, help="скорость обучения")
    p.add_argument("--full", action="store_true", help="полное наблюдение и новая сеть (рядом со старой)")
    p.add_argument("--dir", default=None)
    args = p.parse_args()
    if args.dir is None:
        args.dir = os.path.join(ROOT, "save", "lab_full" if args.full else "lab")
    return args


def make_trainer(args):
    from sim import nn_lab as LAB
    cfg = {}
    if args.workers:
        cfg["workers"] = args.workers
    if args.cpu:
        cfg["device"] = "cpu"
    cfg.update(extra_cfg(args))
    return LAB.Trainer(args.dir, cfg, fresh=args.fresh)


def extra_cfg(args):
    """--focus N, --opponents rules=0.5,latest=0.3,past=0.2 → настройки лаборатории."""
    cfg = {}
    if args.focus:
        cfg["focus"] = args.focus
    if args.opponents:
        cfg["opponents"] = {k: float(v) for k, v in (x.split("=") for x in args.opponents.split(","))}
    if args.no_balance:
        cfg["balance"] = False
    for key, val in (("reward", args.reward), ("teacher_share", args.teacher_share),
                     ("dagger_share", args.dagger_share), ("bc", args.bc),
                     ("eval_size", args.eval_size), ("eval_power", args.eval_power),
                     ("hero_gear", args.hero_gear),
                     ("power_jitter", args.power_jitter), ("balance_target", args.balance_target),
                     ("batch", args.batch), ("epochs", args.epochs), ("minibatch", args.minibatch),
                     ("gamma", args.gamma), ("lr", args.lr)):
        if val is not None:
            cfg[key] = val
    if args.net_autocast:
        cfg["net_autocast"] = True
    if args.full:
        cfg["full"] = True
        cfg["planner_workers"] = 0
    return cfg


def keep_awake(on=True):
    """Windows: не уходить в сон, пока идёт обучение (экран гаснуть может). Выключается при выходе."""
    if os.name != "nt":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def headless(args):
    tr = make_trainer(args)
    os.makedirs(args.dir, exist_ok=True)
    log = open(os.path.join(args.dir, "train.log"), "a", encoding="utf-8")

    def say(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        log.write(line + chr(10))
        log.flush()
        try:
            print(line, flush=True)
        except UnicodeEncodeError:               # консоль без UTF-8 — пишем только в лог
            pass
    say(f"старт: ученик {tr.device}, бойцов {tr.cfg['workers']}, {args.headless / 3600:.1f} ч, награда "
        f"«{tr.cfg['reward']}», с боя {tr.battles}")
    keep_awake(True)
    tr.start()
    t0 = time.time()
    last = 0
    try:
        while time.time() - t0 < args.headless:
            time.sleep(10)
            if time.time() - last < (60 if args.night else 10):
                continue
            last = time.time()
            from game.lab_scene import status_line
            win = tr.history.get("win", [(0, 0)])[-1][1]
            ev = tr.evals[-1] if tr.evals else None
            say(f"{(time.time() - t0) / 60:5.0f} мин · {status_line(tr)} · побед {win:.0%}"
                + (f" · контроль: сети {ev[1]}/{ev[3]} ({ev[4]:.0%} HP), автопилот {ev[2]}/{ev[3]} ({ev[5]:.0%} HP)"
                   if ev else ""))
    except KeyboardInterrupt:
        say("остановлено (Ctrl+C)")
    finally:
        tr.stop()
        keep_awake(False)
    if tr.errors:
        say(f"упавших боёв: {len(tr.errors)}; последний:")
        say(tr.errors[-1]["trace"])
    if args.publish or args.night:
        tr.publish()
        say(f"сети опубликованы в {os.path.relpath(tr.defaults, ROOT)}")
    say(f"точка сохранена: {args.dir}")
    log.close()


def main():
    args = parse()
    if args.night and not args.headless:
        args.headless = args.hours * 3600
    if args.headless:
        headless(args)
        return
    import pygame
    from game.lab_scene import LabApp
    from sim.data import GameData
    from ui import settings
    from ui import theme as T
    from ui.present import Presenter
    from ui.display import Display

    pygame.init()
    settings.load()
    pygame.display.set_caption("Хроники янтаря — лаборатория обучения")
    disp = Display(not args.cpu)
    presenter = Presenter(disp.screen, not args.cpu, window=True)
    if not args.cpu and not presenter.gl:
        disp = Display(False)
        presenter = Presenter(disp.screen, False)
    from sim import nn_lab as LAB
    cfg = {"workers": args.workers} if args.workers else {}
    if args.cpu:
        cfg["device"] = "cpu"
    cfg.update(extra_cfg(args))
    tr = LAB.RemoteTrainer(args.dir, cfg, fresh=args.fresh)  # ученик — отдельным процессом: окно ему не мешает
    keep_awake(True)
    tr.start()
    clock = pygame.time.Clock()
    t0 = time.time()
    while LAB.latest_agents(tr.wdir, tr.ed, tr.cfg) is None or tr.poll()["version"] < 1:   # ждём первые веса
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                tr.stop()
                pygame.quit()
                return
        if not tr.proc.is_alive():
            print("ученик не запустился — см. сообщения выше")
            pygame.quit()
            return
        scr = disp.screen
        scr.fill(T.BG)
        T.text(scr, f"Запуск ученика и бойцов… {time.time() - t0:.0f} с", (scr.get_width() // 2, scr.get_height() // 2),
               22, (150, 200, 255), True, center=True)
        pygame.display.flip()
        clock.tick(10)
    holder = LabApp(GameData(), tr)

    def on_resize():
        presenter.resize()
        holder.relayout()

    disp.on_resize = on_resize
    try:
        while not holder.quit:
            dt = clock.tick(60) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    holder.quit = True
                elif ev.type == pygame.KEYDOWN and (ev.key == pygame.K_F11 or
                                                    (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT)):
                    disp.toggle_fullscreen()
                elif ev.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                    disp.sync()
                else:
                    holder.scene.handle(disp.to_logical(ev))
            holder.scene.update(dt)
            presenter.frame(holder.scene)
            pygame.display.flip()
    finally:
        tr.stop()
        keep_awake(False)
        pygame.quit()


if __name__ == "__main__":                  # бойцы — отдельные процессы (spawn): им этот код не нужен
    sys.exit(main())
