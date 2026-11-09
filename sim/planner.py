"""Планировщик по симулятору: учитель умнее автопилота (Expert Iteration, как в AlphaZero, только без дерева).

В момент решения героя бой копируется (deepcopy ~4 мс), и для каждого из нескольких вариантов хода копия
проигрывается на horizon секунд вперёд: этот герой делает выбранное, дальше все (свои и чужие) — по правилам игры
(автопилот). Вариант с лучшим итогом — баланс сил команды (доля HP+щитов своих минус чужих) плюс убийства — и есть
ход учителя. Сеть учится ему подражать (пример, demo), а со временем делает то же без поиска.

Варианты: K лучших по мнению сети (тип × цель) + «как сделал бы автопилот» + «ничего не менять». Все копии
используют одно и то же случайное зерно (оно копируется вместе с боем), поэтому сравнение честное.
"""
import copy

import numpy as np

from . import battle_obs as B
from . import rewards as RW
from .teams import ENEMY, PLAYER


def clone(c):
    """Копия боя без контроллеров нейросетей: в копии все команды — правила игры (автопилот)."""
    from .ai import TeamAI
    memo = {id(c.data): c.data, id(c.controllers): []}
    d = copy.deepcopy(c, memo)
    have = {ai.team for ai in d.ais}
    for team in (PLAYER, ENEMY):
        if team not in have:
            d.ais.append(TeamAI(d, team))
    d.autocaster.force = True
    for u in d.units:
        for st in u.autocast.values():
            st["on"] = True
    d.events = []
    return d


def _map(c, d, x):
    """Объект исходного боя → тот же в копии (юнит — по номеру в списке, клетка — как есть)."""
    if x is None or isinstance(x, tuple):
        return x
    if hasattr(x, "cell"):
        try:
            return d.units[c.units.index(x)]
        except ValueError:
            return None
    return x


def _apply(d, du, cand):
    from .neural import apply
    if cand is None:
        return
    apply(d, du, cand)


def score(d, team, w_kill=0.15):
    """Итог копии для команды: баланс сил + разница убитых (на всякий — смерть союзника заметнее)."""
    phi = RW.balance(d, team)
    dead_own = sum(1 for v in d.units if v.team == team and not v.alive and not v.obj and not v.summon)
    dead_foe = sum(1 for v in d.units if v.team != team and not v.alive and not v.obj and not v.summon)
    win = 1.0 if (d.result == "victory") == (team == PLAYER) and d.result else 0.0
    return phi + w_kill * (dead_foe - dead_own) + win


def options(obs, cands, probs, k=5):
    """Кандидаты: (тип, цель) — лучшие по сети: по два лучших адресата у трёх лучших типов, без повторов."""
    pt, _, pu, pc = probs
    out = []
    for a in np.argsort(-pt):
        if not obs["tmask"][a] or len(out) >= k:
            break
        tt = obs["ttype"][a]
        if a == B.T_HOLD or tt == B.TGT_NONE:
            out.append((int(a), 0))
            continue
        row = np.where(obs["umask"][a] if tt == B.TGT_UNIT else obs["cmask"][a],
                       pu[a] if tt == B.TGT_UNIT else pc[a], -1)
        for t in np.argsort(-row)[:2]:
            if row[t] >= 0 and len(out) < k:
                out.append((int(a), int(t)))
    return out


def _back(c, d, x):
    """Объект копии → тот же в исходном бою."""
    if hasattr(x, "cell"):
        try:
            return c.units[d.units.index(x)]
        except ValueError:
            return None
    return x


def plan(c, u, obs, cands, probs, k=5, horizon=4.0, margin=0.02):
    """Оценки ходов героя u по проигрышу копий: {вариант: оценка}; None — «продолжать как есть» (автопилот).
    → (лучший вариант, оценки)."""
    opts = options(obs, cands, probs, k)
    steps = int(round(horizon / c.dt))
    scores = {}
    for opt in [None] + opts:
        d = clone(c)
        du = _map(c, d, u)
        if du is None:
            continue
        if opt is not None:
            cand = B.decode(cands, obs["ttype"], opt[0], opt[1])
            cand = tuple(_map(c, d, x) for x in cand)
            if cand[0] == "attack" and cand[1] is None:
                continue
            _apply(d, du, cand)
        for _ in range(steps):
            if d.result:
                break
            d.step()
        scores[opt] = score(d, u.team)
    if not scores:
        return None, scores
    return max(scores, key=lambda o: scores[o]), scores
