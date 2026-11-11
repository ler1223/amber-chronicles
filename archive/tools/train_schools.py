"""Школы для режима обучения: сеть героев и сеть врагов подражают автопилоту игры (sim/ai.py + sim/autopilot.py).

  python tools/train_schools.py                 — 10 минут подражания на всех ядрах (бои) и видеокарте (обучение)
  python tools/train_schools.py --seconds 1800  — дольше
  python tools/train_schools.py --workers 16    — число процессов-бойцов
  python tools/train_schools.py --planner       — учитель — планировщик (автопилот + поиск по копиям боя): сильнее
                                                  автопилота, но бои в ~15 раз дороже (сеть врагов — не учится)
  python tools/train_schools.py --full          — BC-база для полного наблюдения → data/neural_full

Как: лаборатория (sim/nn_lab.py) с долей боёв учителя 100 % — героями и врагами правят правила игры, сети записывают
их решения и учатся выбирать то же (клонирование поведения). В конце — контрольная серия (сети против автопилота) и
публикация в data/neural: school/hero.pt, enemies/enemy.pt. С них начинают новые герои learn.py и лаборатория
lab.py (там сети дальше учатся сами, PPO). Старые сети прежней архитектуры (по классам и видам) удаляются.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=600)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--eval", type=int, default=24)
    p.add_argument("--planner", action="store_true")
    p.add_argument("--full", action="store_true", help="полное наблюдение и новая сеть (data/neural_full)")
    args = p.parse_args()
    from sim import neural as NN
    from sim import nn_lab as LAB
    cfg = {"teacher_share": 1.0, "dagger_share": 0.0, "eval_every": 10 ** 9, "eval_size": args.eval,
           "epochs": 2, "planner_workers": 0}
    if args.full:
        cfg["full"] = True
        cfg["planner_workers"] = 0
    if args.planner:                                 # все бойцы — учителя-планировщики
        cfg.update(planner_workers=10 ** 6, opponents={"rules": 1.0})
    if args.workers:
        cfg["workers"] = args.workers
    # с планировщиком сеть врагов не учится — обе сети стартуют с текущих школ (враги останутся прежними)
    name = "lab_pretrain_full" if args.full else "lab_pretrain"
    tr = LAB.Trainer(os.path.join(ROOT, "save", name), cfg, fresh=not args.planner)
    print(f"подражание: ученик {tr.device}, бойцов {tr.cfg['workers']}, {args.seconds:.0f} с", flush=True)
    tr.start()
    t0 = time.time()
    try:
        while time.time() - t0 < args.seconds:
            time.sleep(15)
            bc = {k: (tr.history.get(f"loss_bc:{k}") or [(0, float("nan"))])[-1][1] for k in (NN.HERO_KEY,
                                                                                               NN.ENEMY_KEY)}
            print(f"{time.time() - t0:5.0f} с · боёв {tr.battles} · образцов {tr.samples / 1e6:.2f} млн · шагов "
                  f"{tr.updates} · ошибка подражания: герои {bc['hero']:.3f}, враги {bc['enemy']:.3f}", flush=True)
        tr.paused = True
        tr.start_eval()
        while tr.eval_pending:
            time.sleep(2)
        e = tr.evals[-1]
        print(f"контроль: сети {e[1]}/{e[3]} (здоровья {e[4]:.0%}), автопилот {e[2]}/{e[3]} (здоровья {e[5]:.0%})",
              flush=True)
    finally:
        tr.stop()
    tr.publish()
    defaults = LAB.DEFAULTS_FULL if args.full else LAB.DEFAULTS
    for kind, keep in (("school", "hero.pt"), ("enemies", "enemy.pt")):
        d = os.path.join(defaults, kind)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name.endswith(".pt") and name != keep:
                os.remove(os.path.join(d, name))
    if tr.errors:
        print(f"упавших боёв: {len(tr.errors)}")
    print(f"готово: {os.path.relpath(defaults, ROOT)}/school/hero.pt")


if __name__ == "__main__":
    main()
