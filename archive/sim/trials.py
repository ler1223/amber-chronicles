"""Испытания сетей: одни и те же бои для автопилота, обученной сети, случайных ходов, бездействия и
планировщика. Это мерка качества обучения, а не обучение: веса не меняются, опыт не копится.

  python tools/trials.py                                  — 16 боёв: автопилот / сеть / случай / бездействие
  python tools/trials.py --modes autopilot,net --battles 100 --powers 0.5,0.75,1.0,1.25
                                                           — кривая силы; JSON несёт 95 % интервалы и разбивки
  python tools/trials.py --modes autopilot,planner --battles 24 --powers 0.6,0.8
  python tools/trials.py --modes autopilot,net,net_auto --battles 100 --powers 1.0
  python tools/trials.py --checkpoint data/neural --json save/trials.json
  python tools/trials.py --full --checkpoint save/lab_full --battles 100
  python tools/trials.py --hero-gear none --battles 100   — сравнение с прежними «голыми» героями

Сценарии берутся с постоянными номерами (seed = 10 000 + k), поэтому все режимы играют ровно одни и те же бои.
Враги везде — правила игры: сравниваются только решения за героев. HP в конце — среднее по боям, поражение
считается за 0 %, как в контрольной серии лаборатории.
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import sys

import numpy as np

from . import battle_obs as B
from . import neural as NN
from . import nn_lab as LAB
from . import np_net as NP
from .combat import PLAYER

MODES = ("autopilot", "net", "net_auto", "random", "idle", "planner")
MODE_LABELS = {
    "autopilot": "автопилот",
    "net": "обученная сеть",
    "net_auto": "сеть + автокаст",
    "random": "случайные ходы",
    "idle": "ничего не делать",
    "planner": "планировщик",
}
SEED_BASE = 10_000
_W = {}                                  # данные и сети процесса-испытателя (--jobs > 1)


def _ed():
    from . import expedition as X
    from .data import GameData
    return X.expedition_data(GameData())


# ---------- сценарии ----------

def scenarios(ed, n, seed=SEED_BASE, power=1.0, gear=None):
    """N постоянных боёв. seed один и тот же для всех режимов; power — множитель HP/урона врагов;
    gear — снаряжение героев (auto/none), None — значение из CONFIG."""
    out = []
    for k in range(n):
        sc = LAB.scenario(ed, seed + k, gear=gear)
        sc["power"] = float(power)
        out.append(sc)
    return out


# ---------- сети ----------

def resolve_checkpoint(path=None, cfg=None):
    """Где искать сеть: живая точка лаборатории, её ckpt или опубликованные школы."""
    if path and path != "auto":
        return path
    name = "lab_full" if (cfg or {}).get("full") else "lab"
    lab = os.path.join(LAB.ROOT, "save", name)
    live = os.path.join(lab, "live")
    if os.path.exists(os.path.join(live, "version.txt")):
        return live
    ckpt = os.path.join(lab, "ckpt")
    if os.path.exists(ckpt):
        return ckpt
    return LAB.DEFAULTS_FULL if (cfg or {}).get("full") else LAB.DEFAULTS


def _torch_state(path):
    """hero.pt / enemy.pt → состояние для NpAgent (numpy-веса, имена признаков, архитектура)."""
    import torch
    d = torch.load(path, map_location="cpu", weights_only=False)
    if not d.get("names"):
        return None
    net = {k: (v.detach().cpu().numpy() if hasattr(v, "detach") else np.asarray(v))
           for k, v in d["net"].items()}
    return {"net": net, "names": d["names"], "arch": d["arch"]}


def load_agents(path, ed, cfg=None):
    """Сеть героев (и врагов, если есть) из .npz, живой точки лаборатории или .pt-школы."""
    path = resolve_checkpoint(path, cfg)
    states = {}
    if os.path.isfile(path):
        if path.endswith(".npz"):
            states, _ = NP.load(path)
        elif path.endswith(".pt"):
            st = _torch_state(path)
            if st:
                key = NN.ENEMY_KEY if "enemy" in os.path.basename(path).lower() else NN.HERO_KEY
                states[key] = st
        else:
            raise ValueError(f"не понимаю формат сети: {path}")
    else:
        root = path
        live = os.path.join(root, "live")
        if os.path.exists(os.path.join(live, "version.txt")):
            root = live
        if os.path.exists(os.path.join(root, "version.txt")):
            got = LAB.latest_agents(root, ed, cfg)
            if got is None:
                raise FileNotFoundError(f"нет опубликованных весов в {root}")
            return got[0]
        for key, kind in LAB.SIDES:
            p = os.path.join(root, kind, f"{key}.pt")
            if not os.path.exists(p):
                p = os.path.join(root, f"{key}.pt")
            if os.path.exists(p):
                st = _torch_state(p)
                if st:
                    states[key] = st
    if not states:
        raise FileNotFoundError(f"нет сетей в {path}")
    obs, _, np_net = LAB.model_mods(cfg)
    agents = {k: NN.NpAgent(k, st, obs=obs, np_net=np_net) for k, st in states.items()}
    for ag in agents.values():
        ag.ensure(ed)
    return agents


# ---------- управление героями ----------

def _hero_factory(c, agents):
    heroes = c.heroes(PLAYER)

    def make(u):
        return agents[NN.HERO_KEY] if u in heroes else None
    return make


class RandomController:
    """Случайные допустимые ходы раз в 0.5 с: та же маска, что у сети, но выбор без обучения."""

    def __init__(self, c, seed=0, every=0.5, teams=(PLAYER,), obs=None):
        self.c = c
        self.B = obs or B
        self.teams = set(teams)
        self.every = every
        self.rng = random.Random(seed)
        self.next_t = 0.0
        self.decisions = 0
        c.ais = [ai for ai in c.ais if ai.team not in self.teams]
        for u in c.units:
            if u.team in self.teams and not u.obj:
                for st in u.autocast.values():
                    st["on"] = False

    def tick(self, c, dt):
        if c.time < self.next_t:
            return
        self.next_t = c.time + self.every
        view = self.B.View(c)
        for u in c.units:
            if u.team not in self.teams or not u.alive or u.obj or u.cast or u.stun > 0:
                continue
            obs, cands = view.observe(u)
            types = np.flatnonzero(obs["tmask"])
            if not len(types):
                continue
            a = int(self.rng.choice(types))
            tt = obs["ttype"][a]
            if a == self.B.T_HOLD or tt == self.B.TGT_NONE:
                tgt = 0
            else:
                mask = obs["umask"][a] if tt == self.B.TGT_UNIT else obs["cmask"][a]
                targets = np.flatnonzero(mask)
                if not len(targets):
                    continue
                tgt = int(self.rng.choice(targets))
            NN.apply(c, u, self.B.decode(cands, obs["ttype"], a, tgt))
            self.decisions += 1


def _controller(c, mode, agents, planner, seed, cfg=None):
    obs, net, _ = LAB.model_mods(cfg)
    if mode == "idle":
        return None
    if mode == "autopilot":
        return NN.Controller(c, lambda u: None, teams=(PLAYER,), learn=False, teacher=True, obs=obs, net=net)
    if mode == "net":
        return NN.Controller(c, _hero_factory(c, agents), teams=(PLAYER,), learn=False, greedy=True,
                             obs=obs, net=net, autocast=(cfg or {}).get("net_autocast", False))
    if mode == "net_auto":
        return NN.Controller(c, _hero_factory(c, agents), teams=(PLAYER,), learn=False, greedy=True,
                             obs=obs, net=net, autocast=True)
    if mode == "random":
        return RandomController(c, seed=seed, obs=obs)
    if mode == "planner":
        ctl = NN.Controller(c, _hero_factory(c, agents), teams=(PLAYER,), learn=False, obs=obs, net=net)
        return ctl.use_planner(planner)
    raise ValueError(f"неизвестный режим: {mode}")


# ---------- один бой ----------

def run_trial(ed, sc, mode, agents=None, cfg=None, planner=None):
    """Один бой сценария. → {mode, power, seed, win, hp, time, squad, act, chapter, boss, objective}."""
    cfg = dict(LAB.CONFIG, **(cfg or {}))
    run, c = LAB.build_battle(ed, sc)
    ctl = _controller(c, mode, agents or {}, planner, sc["seed"], cfg)
    if ctl is not None:
        c.controllers.append(ctl)
    while not c.result and c.time < cfg["max_time"]:
        c.step()
    c.result = c.result or "defeat"
    hs = c.heroes(PLAYER)
    hp = sum(max(0, u.hp) for u in hs) / max(1, sum(u.max_hp for u in hs))
    return {"mode": mode, "power": float(sc.get("power", 1.0)), "seed": sc["seed"],
            "win": c.result == "victory", "hp": hp if c.result == "victory" else 0.0,
            "time": round(c.time, 2), "squad": list(sc["squad"]), "act": sc["act"],
            "chapter": sc["chapter"], "boss": bool(sc["boss"]),
            "objective": (c.objective or {}).get("type", "none")}


def _wilson(wins, n, z=1.96):
    """95 % доверительный интервал доли побед (Wilson): на 24 боях он широкий, на 100 — уже полезный."""
    if n <= 0:
        return [0.0, 0.0]
    p = wins / n
    den = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return [max(0.0, center - half), min(1.0, center + half)]


def summarize(results):
    n = max(1, len(results))
    wins = sum(1 for r in results if r["win"])
    hp = sum(r["hp"] for r in results) / n
    var = sum((r["hp"] - hp) ** 2 for r in results) / max(1, len(results) - 1) if len(results) > 1 else 0.0
    se = (var / n) ** 0.5
    return {"battles": len(results), "wins": wins, "win_rate": wins / n,
            "ci95": _wilson(wins, len(results)), "hp": hp, "hp_se": se,
            "hp_ci95": [max(0.0, hp - 1.96 * se), min(1.0, hp + 1.96 * se)],
            "time": sum(r["time"] for r in results) / n}


def breakdown(results, key):
    """Разбивка по цели боя, акту, боссу, главе или составу отряда — где именно сеть проседает."""
    groups = {}
    for r in results:
        v = r.get(key)
        if key == "boss":
            v = "босс" if v else "обычный"
        elif isinstance(v, (list, tuple)):
            v = "+".join(str(x) for x in v)
        groups.setdefault(str(v), []).append(r)
    return {k: summarize(v) for k, v in sorted(groups.items())}


# ---------- параллельные испытания ----------

def _worker_init(checkpoint, cfg, planner):
    _W.clear()
    _W["ed"] = _ed()
    _W["agents"] = load_agents(checkpoint, _W["ed"], cfg) if checkpoint else {}
    _W["cfg"] = cfg
    _W["planner"] = planner


def _worker_run(task):
    sc, mode, power = task
    sc = dict(sc, power=power)
    return run_trial(_W["ed"], sc, mode, _W["agents"], _W["cfg"], _W["planner"])


def run_trials(ed, modes, battles, powers, seed=SEED_BASE, agents=None, cfg=None, planner=None, jobs=1,
               verbose=False, checkpoint=None):
    """Все режимы на одних и тех же сценариях. → [(power, mode, [результаты])].
    При jobs > 1 сети загружаются в каждом процессе из checkpoint (путь или "auto")."""
    tasks = []
    for power in powers:
        scs = scenarios(ed, battles, seed, power, (cfg or {}).get("hero_gear"))
        for mode in modes:
            for sc in scs:
                tasks.append((sc, mode, power))
    results = []
    if jobs > 1 and len(tasks) > 1:
        with mp.Pool(jobs, initializer=_worker_init, initargs=(checkpoint, cfg, planner)) as pool:
            for i, res in enumerate(pool.imap(_worker_run, tasks), 1):
                results.append(res)
                if verbose:
                    print(f"{i}/{len(tasks)}: {MODE_LABELS[res['mode']]} · бой {res['seed']} · "
                          f"{'победа' if res['win'] else 'поражение'} · HP {res['hp']:.0%}", file=sys.stderr)
    else:
        for i, (sc, mode, power) in enumerate(tasks, 1):
            res = run_trial(ed, sc, mode, agents, cfg, planner)
            results.append(res)
            if verbose:
                print(f"{i}/{len(tasks)}: {MODE_LABELS[mode]} · бой {sc['seed']} · "
                      f"{'победа' if res['win'] else 'поражение'} · HP {res['hp']:.0%}", file=sys.stderr)
    out = []
    for power in powers:
        for mode in modes:
            got = [r for r in results if r["power"] == power and r["mode"] == mode]
            out.append((power, mode, got))
    return out


# ---------- таблица и CLI ----------

def format_table(rows):
    """Таблица как в docs/neural_lab.md: по одной силе врагов или несколько."""
    powers = []
    for power, _, _ in rows:
        if power not in powers:
            powers.append(power)
    modes = []
    for _, mode, _ in rows:
        if mode not in modes:
            modes.append(mode)
    lines = []
    if len(powers) == 1:
        lines.append(f"{'Кто управляет героями':<24} {'Побед':<8} HP в конце")
        for _, mode, got in rows:
            s = summarize(got)
            lines.append(f"{MODE_LABELS[mode]:<24} {s['wins']}/{s['battles']:<6} {s['hp']:.0%}")
        return "\n".join(lines)
    head = f"{'Сила врагов':<12}"
    for mode in modes:
        head += f" {MODE_LABELS[mode]:<24}"
    lines.append(head.rstrip())
    for power in powers:
        line = f"{power:<12.2f}"
        for mode in modes:
            got = next((g for p, m, g in rows if p == power and m == mode), [])
            s = summarize(got)
            line += f" {s['wins']}/{s['battles']} HP {s['hp']:.0%}".ljust(25)
        lines.append(line.rstrip())
    return "\n".join(lines)


def _parse_modes(text):
    modes = [m.strip() for m in text.split(",") if m.strip()]
    bad = [m for m in modes if m not in MODES]
    if bad:
        raise SystemExit(f"неизвестные режимы: {', '.join(bad)} (есть: {', '.join(MODES)})")
    return modes


def main(argv=None):
    p = argparse.ArgumentParser(description="Испытания сетей на одних и тех же боях")
    p.add_argument("--modes", default="autopilot,net,random,idle",
                   help="через запятую: autopilot,net,net_auto,random,idle,planner")
    p.add_argument("--battles", type=int, default=16, help="боёв в серии (по умолчанию 16)")
    p.add_argument("--powers", default="1.0", help="сила врагов через запятую (например 0.6,0.8)")
    p.add_argument("--seed", type=int, default=SEED_BASE, help="первый номер сценария")
    p.add_argument("--max-time", type=float, default=LAB.CONFIG["max_time"], help="лимит боя, сек")
    p.add_argument("--checkpoint", default="auto", help="точка лаборатории, .npz, .pt или папка школ")
    p.add_argument("--planner-k", type=int, default=LAB.CONFIG["planner"]["k"])
    p.add_argument("--planner-horizon", type=float, default=LAB.CONFIG["planner"]["horizon"])
    p.add_argument("--jobs", type=int, default=1, help="процессов испытаний (1 — по очереди)")
    p.add_argument("--json", default=None, help="записать результаты в JSON")
    p.add_argument("--hero-gear", default=LAB.CONFIG["hero_gear"], choices=("auto", "none"),
                   help="снаряжение героев: auto (по акту) или none")
    p.add_argument("--full", action="store_true", help="полное наблюдение и новая сеть (full_obs)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    modes = _parse_modes(args.modes)
    powers = [float(x) for x in args.powers.split(",") if x.strip()]
    need_net = any(m in ("net", "net_auto", "planner") for m in modes)
    cfg = dict(LAB.CONFIG, max_time=args.max_time, hero_gear=args.hero_gear)
    if args.full:
        cfg["full"] = True
        cfg["planner_workers"] = 0
    ed = _ed()
    agents = {}
    if need_net:
        try:
            agents = load_agents(args.checkpoint, ed, cfg)
        except (OSError, ValueError, KeyError, ImportError) as e:
            print(f"нет сети для режимов {', '.join(m for m in modes if m in ('net', 'net_auto', 'planner'))}: {e}",
                  file=sys.stderr)
            modes = [m for m in modes if m not in ("net", "net_auto", "planner")]
            if not modes:
                return 2
    planner = dict(LAB.CONFIG["planner"], k=args.planner_k, horizon=args.planner_horizon)
    print(f"Испытания: {args.battles} боёв, сценарии {args.seed}..{args.seed + args.battles - 1}, "
          f"враги — правила", file=sys.stderr)
    rows = run_trials(ed, modes, args.battles, powers, args.seed, agents, cfg, planner, args.jobs, args.verbose,
                      args.checkpoint if need_net else None)
    print(format_table(rows))
    if args.json:
        out = [{"power": p, "mode": m, "summary": summarize(got),
                "by_objective": breakdown(got, "objective"), "by_act": breakdown(got, "act"),
                "by_boss": breakdown(got, "boss"), "by_chapter": breakdown(got, "chapter"),
                "by_squad": breakdown(got, "squad"), "battles": got} for p, m, got in rows]
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"JSON: {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
