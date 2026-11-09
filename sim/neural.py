"""Нейросети юнитов: герои и враги учатся воевать сами.

Как устроено
  Состояние боя (sim/battle_obs.py) — для каждого юнита набор токенов переменной длины: все бойцы на поле (кто,
                           где, куда идёт, здоровье, щит, броня, урон, баффы и дебаффы, статусы, метки, каст, приказ,
                           контроль), его навыки (из описания: эффекты, числа, тип цели, готовность), карта 11×11
                           вокруг (проходимость, опасности, зоны, касты, юниты) и общее о бое.
  Сеть (sim/entity_net.py) — трансформер над токенами; выбирает тип действия (ждать / атака / шаг / навык k) и
                           цель: юнита указателем или клетку на карте 11×11. Невозможное закрыто масками.
  Контроллер (Controller)— раз в 0.2 сек боя все свои юниты думают разом (одна пачка на сеть); опасность под
                           ногами, новый каст по нам и потеря HP будят раньше, не чаще раза в 0.05 сек. Награда
                           юнита между решениями — из его статистики боя: урон и лечение, минус полученный урон,
                           убийства, смерть, итог боя.
  Обучение (Agent.learn) — PPO (актор-критик с обрезкой шага) + подражание примерам: приказам игрока и автопилота.
  Сети                   — одна школа героев (класс — метка вида в токене юнита) и одна сеть врагов (вид — метка);
                           в режиме обучения у героя своя копия школы, ветеран уносит её.

Хранение (Store): папка с файлами .pt — сеть, имена признаков, статистика. Состав признаков меняется — веса
переносятся по именам (entity_net.adapt), старое обучение не теряется.
torch — только для этих режимов: обычная игра его не загружает.
"""
import os
import random

import numpy as np

from . import battle_obs as B
from . import entity_net as E
from . import np_net as NP
from . import rewards as RW
from .teams import ENEMY, PLAYER

THINK = 0.1                   # самое долгое молчание: раз в 0.1 с решение есть всегда
MIN_GAP = 0.05                # не чаще одного кадра: событие (каст, опасность, удар) будит сразу
MASK_REFRESH = 0.05           # лаборатория: панель «что видит сеть» пересчитывает маски 20 раз в секунду
HP_TRIGGER = 0.05             # потерял 5 % HP с прошлого решения — думаем заново
DISCOUNT_DT = 0.5             # дисконт шага считается по прежней шкале 0.5 с, а не по THINK
REWARD_DT = 0.5               # отрезок командной награды — 0.5 с
HERO_KEY, ENEMY_KEY = "hero", "enemy"
GAMMA, LAM = 0.97, 0.95


def limits(arch):
    """Размеры полного наблюдения из arch (пусто для старой battle_obs)."""
    return E.limits(arch)


def _torch():
    import torch
    torch.set_num_threads(1)
    return torch


# ---------- агент: сеть и её опыт ----------

class Agent:
    """Сеть (школа героев, сеть врагов или сеть одного героя) и её опыт: траектории юнитов за бой."""

    def __init__(self, key, state=None, stats=None, obs=None, net=None, arch=None):
        self.key = key
        self.B = obs or B             # battle_obs или full_obs
        self.E = net or E             # entity_net (формулы общие; размеры — в arch)
        self.arch = arch              # arch новой сети; для старой — None
        self.net = None
        self.names = None             # имена признаков, на которых сеть обучалась
        self._state = state           # загруженное с диска: {"net", "names", "arch"} — сеть строится при первом бое
        self.stats = dict(stats or {"battles": 0, "rewards": [], "wins": 0})
        self.buf = []                 # траектории: [[(образец, тип, цель, logp, ценность, награда, конец, пример)], ...]
        self.rng = np.random.default_rng()
        self._fast = None             # ускоренная копия сети для решений (TorchScript), сбрасывается при обучении

    def ensure(self, data):
        """Сеть под признаки этих данных игры: построить, загрузить, перенести веса по именам."""
        return self.ensure_names(self.B.names(self.B.schema(data)))

    def ensure_names(self, cur):
        dims = {k: len(v) for k, v in cur.items()}
        if self.net is None:
            st = self._state
            if st and st.get("names") and self.arch:
                old_arch = dict(st.get("arch") or {})
                cap = ("d", "heads", "layers", "ff", "conv")
                if any(old_arch.get(k) != self.arch.get(k) for k in cap):
                    st = None                          # другая ёмкость сети: старые веса не переносятся формой
                    self._state = None
            if st and st.get("names"):
                old = st["names"]
                arch = dict(st.get("arch") or {})
                if self.arch:
                    arch.update(self.arch)             # full_obs: свои пределы/ёмкость важнее старых
                net = self.E.make_net({k: len(v) for k, v in old.items()}, arch)
                net.load_state_dict(st["net"])
                self.net, self.names = net, old
            else:
                self.net, self.names = self.E.make_net(dims, self.arch), cur
            self._state = None
        if self.names != cur:
            fresh = self.E.make_net(dims, self.net.arch)
            fresh.load_state_dict(self.E.adapt(self.net.state_dict(), self.names, cur, fresh.state_dict()))
            self.net, self.names = fresh, cur
            self._fast = None
        return self.net

    def copy_from(self, other):
        """Начать с чужой сети (новичок — копия школы)."""
        if other.net is None and other._state is not None:
            self._state = other._state
            return
        if other.net is not None:
            self._state = {"net": {k: v.clone() for k, v in other.net.state_dict().items()}, "names": other.names,
                           "arch": other.net.arch}
            self.net = None
            self._fast = None

    def state(self):
        return {"net": self.net.state_dict(), "names": self.names, "arch": self.net.arch}

    def act(self, obs_list, greedy=False):
        if self._fast is None:
            self._fast = self.E.fast(self.net) or False
        return self.E.act(self.net, obs_list, greedy, self.rng, self._fast or None)

    def changed(self):
        """Веса сети изменились — ускоренную копию для решений собрать заново."""
        self._fast = None

    def learn(self, lr=3e-4, **kw):
        """PPO по траекториям боя + подражание примерам. Возвращает награду за бой."""
        batch = process(self.buf, stack=self.E.stack_rows, limits=limits(self.net.arch if self.net else None))
        self.buf = []
        if batch is None or len(batch["a_type"]) < 4 or self.net is None:
            return None
        torch = _torch()
        self.E.ppo_step(self.net, torch.optim.Adam(self.net.parameters(), lr=lr), batch, **kw)
        self.changed()
        return batch["reward"]

    def clone_learn(self, epochs=6, lr=1e-3):
        """Чистое подражание (школа): учимся выбирать то же, что учитель."""
        batch = process(self.buf, stack=self.E.stack_rows, limits=limits(self.net.arch if self.net else None))
        self.buf = []
        if batch is None or self.net is None:
            return
        batch["demo"] = np.ones(len(batch["a_type"]), np.float32)
        torch = _torch()
        self.E.ppo_step(self.net, torch.optim.Adam(self.net.parameters(), lr=lr), batch, epochs=epochs, minibatch=256)
        self.changed()


def process(trajs, gamma=GAMMA, lam=LAM, rscale=1.0, stack=None, limits=None):
    """Траектории юнитов → пачка для PPO. Выгода (GAE) — по каждой траектории отдельно: насколько вышло лучше,
    чем сеть ожидала. Примеры (demo) не учат ценность и политику PPO — только подражание.
    Шаги разной длины (решения по событиям): дисконт шага — γ^(Δt / 0.5 с), не зависит от частоты решений.
    rscale — нормировка награды (ученик держит её так, чтобы разброс отдачи был ~1: так критику всё равно,
    какой пресет награды). stack/limits — сборщик и размеры полного наблюдения (full_obs)."""
    rows, at, ag, lp, advs, rets, demo, vals = [], [], [], [], [], [], [], []
    total = 0.0
    g_n = g_s = g_q = 0.0                            # отдача без нормировки: для оценки её разброса учеником
    for tr in trajs:
        if not tr:
            continue
        val = np.array([b[4] for b in tr], np.float32)
        raw = np.array([b[5] for b in tr], np.float32)
        rew = raw * rscale
        done = np.array([b[6] for b in tr], np.float32)
        gam = gamma ** (np.array([b[8] if len(b) > 8 else DISCOUNT_DT for b in tr], np.float32) / DISCOUNT_DT)
        adv = np.zeros_like(rew)
        last = 0.0
        g = 0.0
        is_demo = tr[0][7] > 0.5
        for t in range(len(rew) - 1, -1, -1):
            nv = 0.0 if done[t] or t == len(rew) - 1 else val[t + 1]
            delta = rew[t] + gam[t] * nv - val[t]
            last = delta + gam[t] * lam * (0.0 if done[t] else last)
            adv[t] = last
            if not is_demo:
                g = raw[t] + gam[t] * (0.0 if done[t] else g)
                g_n += 1
                g_s += g
                g_q += g * g
        for b in tr:
            rows.append(b[0])
            at.append(b[1])
            ag.append(b[2])
            lp.append(b[3])
            demo.append(b[7])
        advs.append(adv)
        rets.append(adv + val)
        vals.append(val)
        total += float(raw.sum())
    if not rows:
        return None
    return {"obs": (stack or E.stack_rows)(rows, **(limits or {})), "a_type": np.array(at, np.int64),
            "a_tgt": np.array(ag, np.int64),
            "logp": np.array(lp, np.float32), "adv": np.concatenate(advs), "ret": np.concatenate(rets),
            "val": np.concatenate(vals), "g": (g_n, g_s, g_q),
            "demo": np.array(demo, np.float32), "reward": total}


class Broker:
    """Решатель для нескольких боёв сразу: бои идут шаг в шаг и думают в одни и те же кадры (think_now), контроллеры
    сдают наблюдения (submit), flush() — одна пачка на сеть за все бои: у маленькой сети накладные расходы на вызов
    больше счёта, так 4 боя стоят почти как один."""

    def __init__(self):
        self.think_now = False
        self.pending = []

    def submit(self, ctl, groups):
        for agent, items in groups.items():
            self.pending.append((ctl, agent, items))

    def flush(self):
        by = {}
        for ctl, agent, items in self.pending:
            by.setdefault(id(agent), (agent, []))[1].append((ctl, items))
        self.pending = []
        for agent, lst in by.values():
            obs = [it[1] for _, items in lst for it in items]
            res = agent.act(obs, lst[0][0].greedy)
            k = 0
            for ctl, items in lst:
                ctl.apply_decisions(items, res[k:k + len(items)])
                k += len(items)


class NpAgent:
    """Агент без torch: та же сеть на numpy (sim/np_net.py) — бойцы лаборатории и её окно. Только решает и копит
    опыт (buf); учит его ученик лаборатории на видеокарте."""

    def __init__(self, key, state, stats=None, obs=None, np_net=None):
        self.key = key
        self.B = obs or B
        self.NP = np_net or NP
        self.P = state["net"]
        self.names = state["names"]
        self.arch = state["arch"]
        self.stats = dict(stats or {"battles": 0, "rewards": [], "wins": 0})
        self.buf = []
        self.rng = np.random.default_rng()

    def ensure(self, data):
        cur = self.B.names(self.B.schema(data))
        if cur != self.names:
            self.P = self.NP.adapt(self.P, self.names, cur)
            self.names = cur

    def act(self, obs_list, greedy=False):
        return self.NP.act(self.P, self.arch, obs_list, greedy, self.rng)

    def changed(self):
        pass


def merge(batches):
    """Несколько пачек process() → одна."""
    batches = [b for b in batches if b]
    if not batches:
        return None
    out = {"obs": {k: np.concatenate([b["obs"][k] for b in batches]) for k in batches[0]["obs"]},
           "reward": sum(b["reward"] for b in batches)}
    for k in ("a_type", "a_tgt", "logp", "adv", "ret", "demo", "val"):
        out[k] = np.concatenate([b[k] for b in batches])
    out["g"] = tuple(sum(b["g"][i] for b in batches) for i in range(3))
    return out


# ---------- контроллер боя ----------

class Controller:
    """Управляет юнитами команд teams сетями. factory(unit) → Agent или None (юнит остаётся правилам: призванные,
    объекты). Новые юниты (подмога, фазы босса) получают сеть сразу. learn — копить опыт (иначе только играть).
    teacher — вместо сети действует автопилот, а сеть записывает его решения как примеры (школа)."""

    def __init__(self, c, factory, teams=(PLAYER, ENEMY), learn=True, teacher=False, greedy=False, reward=None,
                 broker=None, obs=None, net=None, autocast=False, dagger=False):
        from .autocast import AutoCaster
        self.c = c
        self.B = obs or B
        self.E = net or E
        self.factory = factory
        self.teams = set(teams)
        self.agents = {}              # unit -> Agent
        self.learn = learn
        self.teacher = teacher
        self.greedy = greedy
        self.autocast = autocast      # оставить автоприменение навыков включённым и для сети
        self.dagger = dagger          # сеть играет, автопилот размечает те же состояния как примеры
        self.label_ai = None
        self.caster = AutoCaster(c, PLAYER, force=True)
        self.state = {}
        self.ref = max(1.0, float(np.mean([v.max_hp for v in c.units if not v.obj] or [100])))
        self.thinking = {}            # unit -> {"v", "top": [(p, текст)]} — для панели «что думает сеть»
        self.seen = set()
        self.keep_obs = False         # лаборатория: помнить последнее наблюдение юнита (панель «что видит сеть»)
        self.last_obs = {}
        self.mask_t = -1e9             # когда последний раз обновляли last_obs для панели
        self.rw = reward or RW.resolve()   # веса награды на этот момент обучения (sim/rewards.py)
        self.broker = broker          # общий решатель нескольких боёв (лаборатория): одна пачка на сеть за всех
        self.explain = True           # считать «что думает сеть» (панель боя); бойцам лаборатории не нужно
        self.planner = None           # {"k", "horizon", "margin"} — use_planner(): автопилот + поправки планировщика,
        self.planned = 0              # а сеть записывает его ходы как примеры
        self.improved = 0             # сколько раз планировщик поправил автопилот
        if teacher:
            from .ai import TeamAI
            self.rule_ai = {t: TeamAI(c, t) for t in self.teams}
        if dagger and not teacher:
            from .ai import TeamAI
            self.label_ai = TeamAI(c, PLAYER)
        c.ais = [ai for ai in c.ais if ai.team not in self.teams]    # правила этих команд молчат (учитель — свои)
        self._adopt()

    def _adopt(self):
        for u in self.c.units:
            if u.id in self.seen or u.team not in self.teams or u.obj:
                continue
            self.seen.add(u.id)
            ag = None if u.summon else self.factory(u)
            if ag is None:
                continue
            ag.ensure(self.c.data)
            self.agents[u] = ag
            if not self.teacher and not self.autocast:
                for st in u.autocast.values():
                    st["on"] = False
            self.state[u] = {"tally": dict(u.tally), "pending": None, "net_order": None, "alive": True, "traj": [],
                             "demos": [], "last": 0, "phi": RW.potential(self.c, u.team, self.rw), "parts": {},
                             "t": -1e9, "hp": u.hp, "ready": 0, "t_pending": 0.0, "danger": False, "cast": None,
                             "idle": False}

    def _reward(self, u, st, sparse=None):
        """Награда за отрезок: подсказка (личные заслуги + баланс сил, с затуханием) и разовые (смерть, итог).
        → {"s": подсказка, "p": разовые, "k": номер мысли} — командный дух смешивается в collect()."""
        rw = self.rw
        comp = RW.parts(u, st["tally"], self.ref, rw)
        st["tally"] = dict(u.tally)
        phi = RW.potential(self.c, u.team, rw)
        if rw["w"].get("team"):
            comp["team"] = rw["w"]["team"] * (phi - st["phi"])
        st["phi"] = phi
        shaped = rw["scale"] * sum(comp.values())
        pa = st["parts"]
        for k, v in comp.items():
            pa[k] = pa.get(k, 0.0) + rw["scale"] * v
        sp = 0.0
        for k, v in (sparse or {}).items():
            pa[k] = pa.get(k, 0.0) + v
            sp += v
        return {"s": shaped, "p": sp, "k": int(self.c.time / REWARD_DT)}   # командный дух — по отрезкам 0.5 с

    def _close(self, u, st, sparse=None, done=False):
        """Закрыть прошлое решение юнита: награда за отрезок до этого момента."""
        p = st["pending"]
        if p is None:
            return
        dt = max(0.05, self.c.time - st["t_pending"])
        r = self._reward(u, st, sparse)
        if self.rw.get("time"):                       # небольшой штраф за время: не тянуть бой без пользы
            penalty = self.rw["time"] * dt
            r["s"] -= penalty
            st["parts"]["time"] = st["parts"].get("time", 0.0) - penalty
        st["traj"].append((p[0], p[1], p[2], p[3], p[4], r, done, p[5], dt))
        st["pending"] = None

    def _refresh_obs(self):
        """Лаборатория: обновить наблюдения и маски для панели чаще, чем сеть принимает решения."""
        view = self.B.View(self.c)
        for u, st in self.state.items():
            if st["alive"] and u.alive:
                self.last_obs[u] = view.observe(u, st["last"])
        return view

    def tick(self, c, dt):
        if len(c.units) != len(self.seen):
            self._adopt()
        for u, st in self.state.items():
            if st["alive"] and not u.alive:
                st["alive"] = False
                if self.learn:
                    self._close(u, st, sparse={"death": self.rw["death"]}, done=True)
        if self.teacher:
            for ai in self.rule_ai.values():
                ai.update(dt)
        if self.broker is not None and not self.broker.think_now:
            return
        now = c.time
        view = None
        if self.keep_obs and now - self.mask_t >= MASK_REFRESH:
            self.mask_t = now
            view = self._refresh_obs()                    # панель видит свежие маски, даже если решений ещё нет
        due = []
        for u, st in self.state.items():                 # кто думает сейчас: прошло 0.1 с или случилось событие
            if not st["alive"] or u.cast or u.stun > 0:
                continue
            since = now - st["t"]
            if since >= THINK or (since >= MIN_GAP and self._event(u, st, since)):
                due.append(u)
        if not due:
            return
        for u in due:
            st = self.state[u]
            st["t"], st["hp"], st["ready"] = now, u.hp, self._ready(u)
        view = view or self.B.View(c)
        groups = {}
        for u in due:
            st = self.state[u]
            if not any(u.is_enemy(v) for v in view.units):
                continue
            obs, cands = view.observe(u, st["last"])
            if self.keep_obs:
                self.last_obs[u] = (obs, cands)
            o = u.order
            manual = o is not None and not o.get("by_net") and not self.teacher and o is not st["net_order"]
            if manual and o.get("manual"):            # приказ игрока: не мешаем, запоминаем как пример
                if self.learn:
                    self._close(u, st)
                    a = self.B.encode(u, o, obs, cands)
                    if a is not None:
                        st["pending"] = (self.E.sample_row(obs, *a), a[0], a[1], 0.0, 0.0, 1.0)
                        st["t_pending"] = c.time
                continue
            if self.teacher:                          # автопилот решает, сеть смотрит и учится
                ch = self.caster.choose(u) if not (u.order or {}).get("type") == "skill" else None
                if ch:
                    c.order_skill(u, ch[0], ch[1], auto=True)
                a = self.B.encode(u, u.order, obs, cands)
                if a is not None:
                    st["traj"].append((self.E.sample_row(obs, *a), a[0], a[1], 0.0, 0.0, 0.0, False, 1.0))
                    st["last"] = a[0]
                continue
            if self.planner is not None:              # автопилот игры + поправки планировщика; сеть — запоминает
                self._plan(u, obs, cands)
                a = self.B.encode(u, u.order, obs, cands)
                if a is not None and self.learn:
                    st["traj"].append((self.E.sample_row(obs, *a), a[0], a[1], 0.0, 0.0, 0.0, False, 1.0))
                    st["last"] = a[0]
                continue
            if self.dagger:                          # сеть играет, но автопилот даёт метку на этом же состоянии
                a = self._label(u, obs, cands)
                if a is not None:
                    st["demos"].append((self.E.sample_row(obs, *a), a[0], a[1], 0.0, 0.0, 0.0, False, 1.0))
            groups.setdefault(self.agents[u], []).append((u, obs, cands))
        if self.broker is not None:                   # решения — пачкой вместе с другими боями (Broker.flush)
            self.broker.submit(self, groups)
            return
        for agent, items in groups.items():
            self.apply_decisions(items, agent.act([it[1] for it in items], self.greedy))

    def apply_decisions(self, items, res):
        """Решения сети → приказы боя (и опыт, если учимся)."""
        c = self.c
        for (u, obs, cands), (a, tgt, lp, v, probs) in zip(items, res):
            st = self.state[u]
            cand = self.B.decode(cands, obs["ttype"], a, tgt)
            if self.explain:                          # «что думает сеть» — бойцам лаборатории не нужно
                self.thinking[u] = {"v": v, "top": self._top(u, obs, cands, probs)}
            if self.learn:
                self._close(u, st)
                st["pending"] = (self.E.sample_row(obs, a, tgt), a, tgt, lp, v, 0.0)
                st["t_pending"] = c.time
            st["last"] = a
            st["net_order"] = apply(c, u, cand)

    def use_planner(self, cfg=None):
        """Режим учителя-планировщика: своими командами правит автопилот игры (правила и автоприменение навыков —
        ровно как в копиях боя), а планировщик подменяет его ход, если копии показывают, что другой ход лучше."""
        from .ai import TeamAI
        self.planner = dict({"k": 5, "horizon": 4.0, "margin": 0.02}, **(cfg or {}))
        for team in self.teams:
            if not any(ai.team == team for ai in self.c.ais):
                self.c.ais.append(TeamAI(self.c, team))
        self.c.autocaster.force = True
        for u in self.state:
            for st in u.autocast.values():
                st["on"] = True
        return self

    def _plan(self, u, obs, cands):
        """Планировщик (sim/planner.py): копии боя проигрывают варианты — «как решил автопилот» и лучшие ходы по
        мнению сети; если какой-то ход заметно лучше автопилота, он заменяет приказ автопилота."""
        from . import planner as PL
        res = self.agents[u].act([obs], True)[0]
        best, scores = PL.plan(self.c, u, obs, cands, res[4], **self.planner)
        self.planned += 1
        if best is not None and scores[best] > scores.get(None, -1e9) + self.planner.get("margin", 0.02):
            apply(self.c, u, self.B.decode(cands, obs["ttype"], *best))
            self.improved += 1

    def _label(self, u, obs, cands):
        """DAgger: автопилот размечает то же состояние, что видит сеть. Приказы и очередь боя не меняются —
        метка только переводится в (тип, цель) и уходит в отдельную демонстрационную траекторию."""
        if self.label_ai is None or not self.learn:
            return None
        old_order, old_queue = u.order, list(u.queue)
        old_cast, old_last, old_timer, old_kite = u.cast, u.last_target, u.ai_timer, u.kite_cd
        try:
            u.order, u.queue, u.ai_timer = None, [], 0.0
            self.label_ai.think(u)
            order = u.order
            if not (order and order.get("type") == "skill"):
                ch = self.caster.choose(u)             # навык важнее шага, как в режиме учителя
                if ch:
                    order = {"type": "skill", "skill": ch[0], "target": ch[1]}
            return self.B.encode(u, order, obs, cands) if order is not None else None
        finally:
            u.order, u.queue, u.cast = old_order, old_queue, old_cast
            u.last_target, u.ai_timer, u.kite_cd = old_last, old_timer, old_kite

    @staticmethod
    def _ready(u):
        return sum(1 for s in u.skills if s in u.skill_defs and u.skill_ready(s, u.skill_defs[s]))

    def _event(self, u, st, since):
        """Повод решить раньше срока: кончился приказ, больно ударили, откатился навык, под нами опасность,
        враг начал каст по нам/союзнику или накрывает нашу клетку. Частые повторные срабатывания не нужны:
        обычный тик всё равно раз в THINK."""
        idle = u.order is None
        if idle and not st.get("idle"):                 # приказ только что кончился — не ждём тика
            st["idle"] = True
            return True
        st["idle"] = idle
        if not idle:
            if (st["hp"] - u.hp) >= HP_TRIGGER * u.max_hp:
                return True
            if self._ready(u) > st["ready"]:
                return True
        danger = u.cell in self.c.grid.cells and self.c._danger(u, u.cell) > 0   # лава, огонь, ловушка, яд
        if danger and not st.get("danger"):
            st["danger"] = True
            return True
        st["danger"] = danger
        cast = None
        for v in self.c.units:
            cs = v.cast
            if cs is None or not v.alive or v.team == u.team:
                continue
            tg = cs.get("target")
            threat = tg is u or getattr(tg, "team", None) == u.team
            p = getattr(tg, "cell", tg)
            if not threat and p is not None and not isinstance(p, str):
                rad = v.skill_defs.get(cs["skill"], {}).get("radius", 0)
                threat = max(abs(p[0] - u.cell[0]), abs(p[1] - u.cell[1])) <= rad + 1
            if not threat:
                continue
            cast = (v.id, cs["skill"], cs["total"])
            if st.get("cast") != cast:                   # новый каст — реагируем сразу, даже если он начался
                st["cast"] = cast                        # до прошлого решения (раньше такой каст терялся)
                return True
        st["cast"] = cast
        return False

    def _top(self, u, obs, cands, probs, k=3):
        """Три самых вероятных хода (тип × лучшая цель) — текстом."""
        pt, _, pu, pc = probs
        out = []
        for a in np.argsort(-pt)[:k]:
            if pt[a] < 0.005:
                break
            tt = obs["ttype"][a]
            tgt, pp = 0, 1.0
            if a != self.B.T_HOLD and tt != self.B.TGT_NONE:
                row = pu[a] if tt == self.B.TGT_UNIT else pc[a]
                tgt = int(np.argmax(row))
                pp = float(row[tgt])
            out.append((float(pt[a]) * pp,
                        self.B.describe(self.c, u, self.B.decode(cands, obs["ttype"], int(a), tgt))))
        return out

    def collect(self):
        """Бой окончен: последняя награда (победа/поражение) и траектории юнитов → в их сети (agent.buf)."""
        c = self.c
        rw = self.rw
        win = {PLAYER: c.result == "victory", ENEMY: c.result == "defeat"}
        terminal = {}                                  # павшим победа/поражение — в последний переход, а не теряется
        for u, st in self.state.items():
            if not self.learn or self.teacher:
                continue
            sp = {"win": rw["win"] if win.get(u.team) else -rw["win"]}
            if win.get(u.team) and rw["margin"]:
                sp["margin"] = rw["margin"] * max(0.0, RW.balance(c, u.team))
            if st["alive"]:
                self._close(u, st, sparse=sp, done=True)
            else:
                terminal[u] = sum(sp.values())
                for k, v in sp.items():               # для графиков вклада: победа видна и у павшего героя
                    st["parts"][k] = st["parts"].get(k, 0.0) + v
        # командный дух: доля τ подсказки — средняя по команде на том же шаге
        tau = rw["tau"]
        mean = {}
        for u, st in self.state.items():
            for b in st["traj"]:
                if isinstance(b[5], dict):
                    acc = mean.setdefault((u.team, b[5]["k"]), [0.0, 0])
                    acc[0] += b[5]["s"]
                    acc[1] += 1
        for u, st in self.state.items():
            out = []
            for b in st["traj"]:
                r = b[5]
                if isinstance(r, dict):
                    tot, n = mean[(u.team, r["k"])]
                    r = (1 - tau) * r["s"] + tau * tot / n + r["p"]
                out.append(b[:5] + (float(r),) + b[6:])
            extra = terminal.get(u, 0.0)
            if not st["alive"] and out and extra:
                out[-1] = out[-1][:5] + (out[-1][5] + extra,) + out[-1][6:]
                extra = 0.0
            st["reward"] = st.get("reward", 0.0) + sum(b[5] for b in out) + extra
            st["traj"] = []
            if out:
                self.agents[u].buf.append(out)
            demos = st.pop("demos", [])                # DAgger-примеры не смешиваются с PPO-траекторией
            if demos:
                self.agents[u].buf.append(demos)
        return win

    def finish(self):
        """Бой окончен: траектории — в сети, обучение. Возвращает {Agent: награда за бой}."""
        win = self.collect()
        out = {}
        if self.teacher:
            for ag in set(self.agents.values()):
                ag.clone_learn()
            return {}
        for ag in set(self.agents.values()):
            if not self.learn:
                continue
            team = next(u.team for u, a in self.agents.items() if a is ag)
            total = ag.learn()
            ag.stats["battles"] = ag.stats.get("battles", 0) + 1
            ag.stats["wins"] = ag.stats.get("wins", 0) + (1 if win.get(team) else 0)
            if total is not None:
                ag.stats["rewards"] = (ag.stats.get("rewards", []) + [round(total, 2)])[-60:]
            out[ag] = total
        return out


def apply(c, u, cand):
    """Вариант → приказ боя (тот же, что отдаёт игрок). Возвращает приказ (или None, если ждём)."""
    kind = cand[0]
    o = u.order or {}
    if kind == "hold":
        return u.order
    same = ((kind == "attack" and o.get("type") == "attack" and o.get("target") is cand[1]) or
            (kind == "move" and o.get("type") == "move" and o.get("cell") == cand[1]) or
            (kind == "skill" and o.get("type") == "skill" and o.get("skill") == cand[1]))
    if same:                                   # тот же приказ уже выполняется — не сбивать замах и путь
        return u.order
    if kind == "attack":
        c.order_attack(u, cand[1])
    elif kind == "move":
        c.order_move(u, cand[1])
    else:
        c.order_skill(u, cand[1], cand[2] if cand[2] is not None else u)
    if u.order is not None:
        u.order["by_net"] = True
    return u.order


def mark_manual(c, before):
    """Сцена боя: приказы, появившиеся после ввода игрока, помечаются как ручные (сеть им подражает)."""
    for u in c.units:
        if u.order is not None and before.get(u.id) is not u.order and not u.order.get("by_net"):
            u.order["manual"] = True


# ---------- хранение ----------

class Store:
    """Сети на диске: heroes/<uid>.pt (сеть героя), school/hero.pt (школа героев), enemies/enemy.pt (враги)."""

    def __init__(self, root, defaults=None):
        self.root = root
        self.defaults = defaults      # готовые школы (data/neural): с них начинает новый сейв
        self.cache = {}

    def _path(self, kind, key):
        return os.path.join(self.root, kind, f"{key}.pt")

    def load(self, kind, key, fallback=None):
        """Агент из файла; нет файла — копия fallback (школа) или новая сеть."""
        ck = (kind, key)
        if ck in self.cache:
            return self.cache[ck]
        p = self._path(kind, key)
        if not os.path.exists(p) and self.defaults:
            p = os.path.join(self.defaults, kind, f"{key}.pt")
        ag = None
        if os.path.exists(p):
            try:
                d = _torch().load(p, weights_only=False, map_location="cpu")
                if d.get("names"):                # старый формат (плоский вектор) — несовместим: начнём заново
                    ag = Agent(key, d, d.get("stats"))
            except Exception:                    # noqa: BLE001 — испорченный файл: начнём заново
                ag = None
        if ag is None:
            ag = Agent(key)
            if fallback is not None:
                ag.copy_from(fallback)
        self.cache[ck] = ag
        return ag

    def save(self, kind, key, ag):
        if ag.net is None and ag._state is None:
            return
        torch = _torch()
        p = self._path(kind, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        st = ag.state() if ag.net is not None else ag._state
        torch.save(dict(st, stats=ag.stats), p + ".tmp")
        os.replace(p + ".tmp", p)
        self.cache[(kind, key)] = ag

    def has(self, kind, key):
        return (kind, key) in self.cache or os.path.exists(self._path(kind, key))

    def hero(self, h):
        """Сеть героя: своя или копия школы героев."""
        return self.load("heroes", h.uid, self.school(h.cls))

    def school(self, cls=None):
        """Школа героев — одна на все классы (класс сеть видит в токене юнита)."""
        return self.load("school", HERO_KEY)

    def enemy(self, etype=None):
        """Сеть врагов — одна на все виды (вид — в токене юнита)."""
        return self.load("enemies", ENEMY_KEY)

    def blend_school(self, cls, ag, k=0.3):
        """Опыт героя — в школу (школа сдвигается к его сети на долю k)."""
        if ag.net is None:
            return
        sc = self.school(cls)
        sc.ensure_names(ag.names)
        sd, hd = sc.net.state_dict(), ag.net.state_dict()
        for name in sd:
            if sd[name].dtype.is_floating_point:
                sd[name] = sd[name] * (1 - k) + hd[name] * k
        sc.net.load_state_dict(sd)
        sc.changed()
        self.save("school", HERO_KEY, sc)
