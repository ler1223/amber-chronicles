"""Лаборатория обучения: много процессов-бойцов на процессоре, один ученик на видеокарте.

Пайплайн (actor–learner, как IMPALA/распределённый PPO):

  бойцы (worker_main, N процессов)              ученик (Trainer, главный процесс, поток train_loop)
  ──────────────────────────────────            ───────────────────────────────────────────────────
  1. берут свежие веса (weights.pt)       ◄──── 4. публикует веса каждые publish_sec секунд
  2. играют случайный бой: глава, акт,          3. копит опыт героев; набралось batch
     узел, отряд из 3 случайных классов            образцов — PPO на видеокарте (эпохи, мини-пачки),
     и уровней; герои — школа героев,              у школы свой Adam (шаги не сбрасываются)
     враги — обычный автопилот игры
  2a. считают выгоду (GAE) по каждому           5. каждые eval_every боёв — контроль: одни и те же
      юниту и шлют пачки ученику  ─────────►       бои сетью (без случайности) и автопилотом

Пока учится одна сеть — школа героев (одна на все классы; класс она видит в токене юнита). Врагами управляет
обычный автопилот игры, сеть врагов остаётся замороженной для совместимости старых точек. Бойцы считают решения
той же сетью на numpy (процессор, 1 поток, одна пачка решений на сеть раз в 0.1 с боя, событие — сразу, но не
чаще кадра);
ученик — на видеокарте. Опыт передаётся пачками массивов одной формы (float16, карта в uint8) и разом уходит
на видеокарту, мини-пачки режутся уже там.

Лаборатория работает в своей папке (save/lab): точки сохранения, метрики; «Опубликовать» копирует школу героев в
data/neural (school/hero.pt) — с неё начинают новые герои режима обучения. Сеть врагов при этом не публикуется.
"""
import collections
import json
import os
import queue
import random
import subprocess
import threading
import time

import numpy as np

from . import battle_obs as B
from . import entity_net as E
from . import full_obs as F
from . import neural as NN
from . import np_net as NP
from . import rewards as RW

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = os.path.join(ROOT, "data", "neural")
DEFAULTS_FULL = os.path.join(ROOT, "data", "neural_full")

CONFIG = {
    "full": False,             # полное наблюдение (full_obs) и новая сеть; старая реализация не меняется
    "workers": None,           # None — по ядрам и свободной памяти (auto_workers)
    "batch": 8192,             # образцов на сеть до шага PPO
    "epochs": 4,               # больше проходов по пачке: полное наблюдение дорого, но опыт переиспользуется
    "minibatch": 1024,         # меньше памяти на полной карте; больше шагов оптимизации
    "lr": 2e-4,
    "lr_final": 1e-4,          # линейное затухание скорости обучения к lr_anneal боям
    "lr_anneal": 200_000,
    "clip": 0.2,
    "entropy": 0.01,           # стартовая премия за разнообразие ходов; дальше подстраивается к ent_target
    "ent_target": 0.5,         # желаемая энтропия (тип + цель): ниже — сеть «застыла» и не ищет нового, премия растёт
    "ent_range": (0.002, 0.1),
    "balance": True,           # баланс матчей: сила врагов подстраивается под balance_target (60 %) —
                               # иначе исход решён заранее (проверено: «ничего не делать» выигрывает почти столько же)
    "balance_every": 40,       # подстройка — раз в столько боёв группы, по их доле побед (иначе сила скачет)
    "balance_gain": 0.6,       # шаг: логарифм силы += gain · (доля побед − balance_target)
    "balance_target": 0.6,     # цель баланса: герои выигрывают ~60 %, а не 50 % — с запасом на контроль
    "power_jitter": 0.15,      # разброс силы врагов вокруг баланса: сеть не привыкает к одной сложности
    "act_weights": (0.50, 0.32, 0.18),   # учебная программа: чаще ранние акты, реже поздние
    "focus": 0,                # >0 — учиться на N одних и тех же боях по кругу (проверка, что обучение работает)
    "bc": 0.5,                 # вес подражания примерам учителя (планировщика)
    "teacher_share": 0.1,      # доля боёв, где героями и врагами правит автопилот, а сети записывают примеры
    "dagger_share": 0.1,       # доля боёв DAgger: сеть играет, автопилот размечает те же состояния
    "planner_workers": 8,      # бойцов-учителей: автопилот + поправки планировщика (копии боя на horizon с вперёд);
                               # он сильнее автопилота, сеть героев учится подражать его ходам
    "planner": {"k": 5, "horizon": 3.0, "margin": 0.02},
    "opponents": {"rules": 1.0, "latest": 0.0, "past": 0.0},   # пока учим только героев: враги — обычный
                                                               # автопилот игры. latest/past — для будущих опытов
    "pool_every": 20,          # шагов обучения сети врагов между снимками в пул прошлых версий
    "pool_size": 8,
    "vclip": 0.2,              # обрезка изменения ценности за шаг
    "critic_warmup": 15,       # первые шаги после подражания учим только критика: иначе выгоды — шум
    "gamma": 0.99,
    "lam": 0.95,
    "publish_sec": 1.0,        # как часто бойцы получают новые веса (реже — опыт сильнее отстаёт от сети)
    "eval_every": 1000,        # боёв между контрольными сериями
    "eval_size": 100,          # боёв в серии; автопилот на них считается один раз и запоминается
    "eval_power": None,        # None — сила контроля замораживается при первом прогоне; число — фиксировать
    "max_time": 150.0,         # лимит боя, сек (не уложились — поражение)
    "boss_share": 0.15,
    "learn_heroes": True,
    "learn_enemies": False,    # враги — правила игры; сеть врагов пока не учим и в боях не используем
    "net_autocast": False,     # сеть героев тоже пользуется автоприменением навыков (честное сравнение с ботом)
    "autosave_sec": 600,       # точка сохранения раз в 10 минут (на случай сбоя ночью)
    "parallel": 4,             # боёв одновременно в каждом бойце: решения всех — одной пачкой (быстрее в разы)
    "reward": RW.DEFAULT,      # пресет награды (sim/rewards.py): команда / командный / роли / урон / победа
    "allow_reward_switch": False,   # не менять пресет на ходу: критик и нормировка привыкли к прежней шкале
    "hero_gear": "auto",       # снаряжение героев в лаборатории: auto / none (см. equip_lab_heroes)
}
SIDES = ((NN.HERO_KEY, "school"), (NN.ENEMY_KEY, "enemies"))
WORKER_GB = 0.45               # память одного бойца: данные игры, бой, сеть на numpy (torch бойцу не нужен)
CPU_SHARE = 0.85               # бойцов — 85 % логических ядер (по одному потоку на бойца): остальное — ученику, окну


def auto_workers():
    """Бойцов — 85 % логических ядер, но не больше, чем помещается в свободную память с запасом 3 ГБ."""
    cores = max(1, int(round((os.cpu_count() or 4) * CPU_SHARE)))
    try:
        import psutil
        free = psutil.virtual_memory().available / 2 ** 30
    except Exception:                                # noqa: BLE001
        return min(cores, 8)
    return max(1, min(cores, int((free - 3) / WORKER_GB)))


def model_mods(cfg=None):
    """(наблюдение, сеть, numpy-сеть): старое battle_obs или полное full_obs. Формулы сети общие."""
    if (cfg or {}).get("full"):
        return F, E, NP
    return B, E, NP


# ---------- сценарии боёв ----------

def scenario(ed, seed, act_weights=None, boss_share=None, gear=None):
    """Случайный бой: глава, акт, узел, отряд (3 случайных класса, уровни по акту).
    act_weights — учебная программа (чаще ранние акты); None — равномерно, как в испытаниях.
    gear — снаряжение героев: auto (по акту) или none; None — значение из CONFIG."""
    rng = random.Random(seed)
    classes = sorted(ed.classes)
    chapter = rng.choice(sorted(ed.expedition.get("chapters", {"swamp": 1})))
    act = rng.choices(range(3), weights=act_weights, k=1)[0] if act_weights else rng.randrange(3)
    squad = rng.sample(classes, 3)
    lv = [(1, 6), (4, 11), (8, 16)][act]
    share = CONFIG["boss_share"] if boss_share is None else boss_share
    return {"seed": seed, "chapter": chapter, "act": act, "squad": squad,
            "levels": [rng.randint(*lv) for _ in squad], "boss": rng.random() < share,
            "gear": CONFIG["hero_gear"] if gear is None else gear}


# Снаряжение героев в лаборатории. В настоящем походе герой начинает с одной вещью и получает
# новые за бои, элиту и боссов; к третьему акту слоты обычно заполнены. Без вещей лабораторные
# герои заметно слабее своих же прототипов из игры, поэтому бои кажутся неоправданно сложными.
# Пары (слот, редкость) подобраны по акту, а не по случайному узлу: сценарий должен быть
# воспроизводимым, а сила отряда — сравнимой между прогонами.
LAB_GEAR = (
    (("weapon", "common"), ("armor", "common")),
    (("weapon", "rare"), ("armor", "rare"), ("amulet", "rare")),
    (("weapon", "epic"), ("armor", "epic"), ("amulet", "rare"), ("ring", "rare")),
)


def equip_lab_heroes(run, sc):
    """Выдать героям снаряжение, которое у них было бы к этому акту похода.

    Генератор отдельный и привязан к seed сценария: добавление вещей не сдвигает карту,
    награды и остальные случайные решения похода. ``gear="none"`` оставляет героев
    «голыми» для сравнения с прежними прогонами.
    """
    from . import expedition as X
    mode = sc.get("gear", CONFIG["hero_gear"])
    if mode == "none":
        return
    act = max(0, min(len(LAB_GEAR) - 1, int(sc.get("act", 0))))
    plan = LAB_GEAR[act]
    rng = random.Random(f"{sc['seed']}:lab-gear")
    for i, h in enumerate(run.heroes):
        for slot, rarity in plan:
            item = X.make_item(run.xd, rng, run.item_tier(), rarity, slot,
                               uid=f"lab{sc['seed']}_{i}_{slot}", allow_tags=False)
            h.gear[slot] = item


def prepare(ed, sc):
    """Поход под сценарий: отряд нужных уровней с картами веток, узел боя. → (run, узел, номер боя)."""
    from . import expedition as X
    heroes = [X.Hero({"uid": f"lab{sc['seed']}_{i}", "name": ed.classes[c]["name"], "cls": c, "skills": []})
              for i, c in enumerate(sc["squad"])]
    run = X.Expedition(ed, heroes, seed=sc["seed"], chapter=sc["chapter"])
    if sc["act"]:
        run.act = sc["act"]
        run.new_map()
    for h, lv in zip(run.heroes, sc["levels"]):
        while h.level < lv:
            run.gain_xp(h, run.xp_next(h))
        while h.sp > 0 and run.take_card(h, 0):
            pass
    equip_lab_heroes(run, sc)
    rng = random.Random(sc["seed"] * 7 + 1)
    kinds = ("boss",) if sc["boss"] else ("battle", "elite")
    nodes = [n for n in run.nodes.values() if n["type"] in kinds and n["encounter"] is not None]
    node = rng.choice(nodes)
    run.node = node["id"]
    enc = run.boss_encounter() if node["type"] == "boss" else node["encounter"]
    return run, node, enc


def bucket(sc):
    """Группа сложности сценария для баланса матчей: акт, босс отдельно."""
    return "boss" if sc["boss"] else f"a{sc['act']}"


def build_battle(ed, sc):
    from .combat import Combat, ENEMY
    run, node, enc = prepare(ed, sc)
    scale = dict(run.enemy_scale(node))
    k = sc.get("power", 1.0)                         # баланс матчей: враги сильнее или слабее обычного
    if k != 1.0:
        for f in ("hp", "damage", "power"):
            if f in scale:
                scale[f] = scale[f] * k
    c = Combat(run.data, enc, seed=sc["seed"], squad=run.combat_squad(), enemy_scale=scale, ai_teams=(ENEMY,))
    return run, c


# ---------- боец ----------

def set_priority(high):
    """Приоритет процесса: ученику — выше обычного (он кормит видеокарту, без него бойцы ждут), бойцам — ниже."""
    try:
        import psutil
        p = psutil.Process()
        if os.name == "nt":
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS if high else psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(-5 if high else 10)
    except Exception:                                # noqa: BLE001 — нет прав — работаем как есть
        pass


def weights_path(wdir, version):
    """Веса версии v — свой файл: на Windows открытый бойцом файл нельзя заменить, новая версия пишется рядом."""
    return os.path.join(wdir, f"weights_{version}.npz")


def make_agents(states, cfg=None):
    """{ключ: состояние сети (numpy)} → {ключ: NpAgent} — решения на numpy, без torch."""
    obs, _, np_net = model_mods(cfg)
    return {k: NN.NpAgent(k, st, obs=obs, np_net=np_net) for k, st in states.items()}


def latest_agents(wdir, ed, cfg=None):
    """Агенты с последних опубликованных весов (окно лаборатории). → (агенты, версия, награда) или None."""
    try:
        v = int(open(os.path.join(wdir, "version.txt")).read().strip())
        states, extra = NP.load(weights_path(wdir, v))
    except (OSError, ValueError, KeyError):
        return None
    ags = make_agents(states, cfg)
    for ag in ags.values():
        ag.ensure(ed)
    return ags, v, extra.get("reward")


def factory(c, agents):
    """Герои отряда — школа героев; враги — сеть врагов только при явном self-play; призванные — правилам."""
    from .combat import PLAYER
    heroes = c.heroes(PLAYER)

    def make(u):
        if u.team == PLAYER:
            return agents[NN.HERO_KEY] if u in heroes else None
        return agents[NN.ENEMY_KEY]
    return make


def play(ed, sc, agents, cfg, learn=True, teacher=False, greedy=False, teams=None, reward=None, autocast=False):
    """Один бой сценария: по умолчанию сеть управляет только героями, враги — автопилот.
    teams=(PLAYER, ENEMY) — явный self-play. → (run, бой, контроллер)."""
    from .combat import PLAYER
    obs, net, _ = model_mods(cfg)
    run, c = build_battle(ed, sc)
    ctl = NN.Controller(c, factory(c, agents), teams=teams or (PLAYER,), learn=learn, teacher=teacher,
                        greedy=greedy, reward=reward, obs=obs, net=net, autocast=autocast)
    c.controllers.append(ctl)
    while not c.result and c.time < cfg["max_time"]:
        c.step()
    c.result = c.result or "defeat"
    return run, c, ctl


def battle_report(run, c, ctl, agents, cfg, rscale=None, learn_keys=None):
    """Опыт боя → пачки по сетям, награды по сетям, классам героев и видам врагов. rscale — нормировка награды
    по сетям, learn_keys — чей опыт отдавать ученику (сеть врагов учится только в боях с текущими героями)."""
    from .combat import PLAYER
    ctl.collect()
    heroes = c.heroes(PLAYER)
    cls_r, en_r = {}, {}
    for u, st in ctl.state.items():
        if u.team == PLAYER and u in heroes:
            cls_r[run.heroes[heroes.index(u)].cls] = st.get("reward", 0.0)
        elif u.team != PLAYER:
            en_r.setdefault(u.proto_id, []).append(st.get("reward", 0.0))
    parts = {}                                       # вклад компонентов награды: {сеть: {компонент: на юнита}}
    for u, st in ctl.state.items():
        side = parts.setdefault(ctl.agents[u].key, {"_n": 0})
        side["_n"] += 1
        for k, v in st.get("parts", {}).items():
            side[k] = side.get(k, 0.0) + v
    for side in parts.values():
        n = side.pop("_n")
        for k in side:
            side[k] /= max(1, n)
    batches, rewards = {}, {}
    for ag in agents.values():
        arch = getattr(getattr(ag, "net", None), "arch", None) or getattr(ag, "arch", None)
        b = NN.process(ag.buf, cfg["gamma"], cfg["lam"], (rscale or {}).get(ag.key, 1.0),
                       stack=E.stack_rows, limits=NN.limits(arch))
        ag.buf = []
        if b is None:
            continue
        units = sum(1 for a in ctl.agents.values() if a is ag)
        rewards[ag.key] = b["reward"] / max(1, units)
        if cfg["learn_heroes" if ag.key == NN.HERO_KEY else "learn_enemies"] and \
                (learn_keys is None or ag.key in learn_keys):
            batches[ag.key] = b
    return batches, rewards, cls_r, {k: float(np.mean(v)) for k, v in en_r.items()}, parts


def worker_main(wid, wdir, out_q, task_q, cfg, parent=None):
    """Процесс-боец: несколько боёв сразу (cfg["parallel"]) шаг в шаг — все думают в одни и те же кадры, и решения
    всех боёв считаются одной пачкой на сеть (NN.Broker). Опыт — ученику; task_q — контрольные бои. Без torch."""
    import traceback
    import psutil
    set_priority(False)                              # бойцы уступают ученику и окну
    from .data import GameData
    from . import expedition as X
    from .combat import ENEMY, PLAYER
    ed = X.expedition_data(GameData())
    obs_mod, net_mod, _ = model_mods(cfg)
    agents, version, reward, rscale, power = None, -1, None, {}, {}
    vpath = os.path.join(wdir, "version.txt")
    pool_dir = os.path.join(wdir, "pool")
    pool, pool_cache = [], {}                        # прошлые версии сети врагов (файлы) и загруженные из них
    broker = NN.Broker()
    slots = []
    n = frame = 0
    planner = wid < cfg.get("planner_workers", 0)   # этот боец — учитель-планировщик (по одному бою за раз)

    def send(msg):                                   # очередь полна, а ученика нет — не висеть вечно
        while True:
            try:
                out_q.put(msg, timeout=5)
                return
            except queue.Full:
                if parent is not None and not psutil.pid_exists(parent):
                    raise SystemExit

    def reload():
        nonlocal agents, version, reward, rscale, power
        try:
            v = int(open(vpath).read().strip())
        except (OSError, ValueError):
            return
        wpath = weights_path(wdir, v)
        if v != version and os.path.exists(wpath):
            try:
                states, extra = NP.load(wpath)
                new = make_agents(states, cfg)
                for ag in new.values():
                    ag.ensure(ed)
                agents, version, reward, rscale = new, v, extra.get("reward"), extra.get("rscale") or {}
                power = extra.get("power") or {}
            except Exception:                        # noqa: BLE001 — файл пишется: в следующий раз
                pass
        try:
            pool[:] = sorted(f for f in os.listdir(pool_dir) if f.endswith(".npz"))
        except OSError:
            pool[:] = []

    def past_enemy():
        """Случайная прошлая версия сети врагов (держим в памяти три последних загруженных)."""
        if not pool:
            return None
        name = random.choice(pool)
        if name not in pool_cache:
            try:
                st, _ = NP.load(os.path.join(pool_dir, name))
                ag = make_agents(st, cfg)[NN.ENEMY_KEY]
                ag.ensure(ed)
            except Exception:                        # noqa: BLE001 — файл удалён или пишется
                return None
            if len(pool_cache) >= 3:
                pool_cache.pop(next(iter(pool_cache)))
            pool_cache[name] = ag
        return pool_cache[name]

    def pick_opponent():
        r = random.random()
        opp = cfg["opponents"]
        if r < opp.get("rules", 0):
            return "rules", None
        if r < opp.get("rules", 0) + opp.get("past", 0):
            ag = past_enemy()
            if ag is not None:
                return "past", ag
        return "latest", agents[NN.ENEMY_KEY]

    def evaluate(task):                              # контроль: тот же бой героями-сетями (без случайности) и
        sc = task["scenario"]                        # автопилотом; враги в обоих случаях — правила игры
        res = {}
        for mode in ("net", "teacher") if task.get("need_base") else ("net",):   # автопилот — один раз на сценарий
            try:
                _, c, _ = play(ed, sc, agents, cfg, learn=False, greedy=True, teacher=mode == "teacher",
                               teams=(PLAYER,), autocast=(mode == "net" and cfg.get("net_autocast", False)))
            except Exception:                        # noqa: BLE001
                res[mode] = {"win": False, "time": 0.0, "hp": 0.0}
                continue
            hs = c.heroes(PLAYER)
            hp = sum(max(0, u.hp) for u in hs) / max(1, sum(u.max_hp for u in hs))
            res[mode] = {"win": c.result == "victory", "time": round(c.time, 1),
                         "hp": hp if c.result == "victory" else 0.0}
        send({"kind": "eval", "eval_id": task["eval_id"], "res": res, "scenario": sc})

    def new_slot():
        nonlocal n
        n += 1
        if cfg.get("focus"):
            sc = scenario(ed, 20_000 + random.randrange(cfg["focus"]), cfg.get("act_weights"),
                          cfg.get("boss_share"), cfg.get("hero_gear"))
        else:
            sc = scenario(ed, (wid * 1_000_003 + n * 7919 + int(time.time() * 1000)) % 2 ** 31,
                          cfg.get("act_weights"), cfg.get("boss_share"), cfg.get("hero_gear"))
        base = power.get(bucket(sc), 1.0)
        jitter = cfg.get("power_jitter", 0.0)
        sc["power"] = max(0.1, base * (1.0 + random.uniform(-jitter, jitter)) if jitter else base)
        if planner:
            try:
                run, c = build_battle(ed, sc)
                ctl = NN.Controller(c, factory(c, agents), teams=(PLAYER,), learn=True, reward=reward,
                                    obs=obs_mod, net=net_mod)
                ctl.use_planner(cfg["planner"])
                ctl.explain = False
                c.controllers.append(ctl)
            except Exception:                        # noqa: BLE001
                send({"kind": "error", "worker": wid, "scenario": sc, "trace": traceback.format_exc()[-1500:]})
                return None
            return {"sc": sc, "run": run, "c": c, "ctl": ctl, "agents": {NN.HERO_KEY: agents[NN.HERO_KEY]},
                    "teacher": True, "t0": time.time(), "version": version, "opp": "planner", "learn": {NN.HERO_KEY}}
        teacher = random.random() < cfg["teacher_share"]
        dagger = (not teacher) and random.random() < cfg.get("dagger_share", 0.0)
        opp, enemy = ("teacher", None) if teacher else pick_opponent()   # учитель тоже играет против правил
        used = {NN.HERO_KEY: agents[NN.HERO_KEY]}
        if enemy is not None:
            used[NN.ENEMY_KEY] = enemy
        try:
            run, c = build_battle(ed, sc)
            ctl = NN.Controller(c, factory(c, used), teams=(PLAYER,) if opp in ("rules", "teacher")
                                else (PLAYER, ENEMY), learn=True, teacher=teacher, reward=reward, broker=broker,
                                obs=obs_mod, net=net_mod, autocast=cfg.get("net_autocast", False), dagger=dagger)
            ctl.explain = False
            c.controllers.append(ctl)
        except Exception:                            # noqa: BLE001
            send({"kind": "error", "worker": wid, "scenario": sc, "trace": traceback.format_exc()[-1500:]})
            return None
        learn = {NN.HERO_KEY} | ({NN.ENEMY_KEY} if opp == "latest" else set())
        return {"sc": sc, "run": run, "c": c, "ctl": ctl, "agents": used, "teacher": teacher, "t0": time.time(),
                "version": version, "opp": opp, "learn": learn}

    def finish(slot):
        run, c, ctl, ags, sc = slot["run"], slot["c"], slot["ctl"], slot["agents"], slot["sc"]
        c.result = c.result or "defeat"
        try:
            batches, rewards, cls_r, en_r, parts = battle_report(run, c, ctl, ags, cfg, rscale, slot["learn"])
        except Exception:                            # noqa: BLE001
            for ag in ags.values():
                ag.buf = []
            send({"kind": "error", "worker": wid, "scenario": sc, "trace": traceback.format_exc()[-1500:]})
            return
        send({"kind": "battle", "worker": wid, "version": slot["version"], "win": c.result == "victory",
              "teacher": slot["teacher"], "opp": slot["opp"], "time": round(c.time, 1),
              "wall": time.time() - slot["t0"],
              "squad": sc["squad"], "act": sc["act"], "chapter": sc["chapter"], "boss": sc["boss"],
              "bucket": bucket(sc), "power": sc.get("power", 1.0),
              "rewards": rewards, "cls_reward": cls_r, "enemy_reward": en_r, "batches": batches, "parts": parts,
              "samples": sum(len(b["a_type"]) for b in batches.values())})

    while True:
        if frame % 100 == 0:                         # раз в 5 боевых секунд: ученик жив? новые веса? задания?
            if parent is not None and not psutil.pid_exists(parent):
                return
            reload()
            try:
                task = task_q.get_nowait()
            except queue.Empty:
                task = None
            if task == "stop":
                return
            if agents is None:
                time.sleep(0.5)
                continue
            if task is not None:
                evaluate(task)
        while len(slots) < (1 if planner else cfg["parallel"]):
            s = new_slot()
            if s is None:
                break
            slots.append(s)
        broker.think_now = True                      # событие будит каждый кадр; обычное решение — раз в 0.1 с
        for s in list(slots):
            try:
                s["c"].step()
            except Exception:                        # noqa: BLE001 — сломанный бой не роняет бойца
                for ag in s["agents"].values():
                    ag.buf = []
                send({"kind": "error", "worker": wid, "scenario": s["sc"], "trace": traceback.format_exc()[-1500:]})
                slots.remove(s)
                broker.pending = [p for p in broker.pending if p[0] is not s["ctl"]]
        broker.flush()
        for s in list(slots):
            if s["c"].result or s["c"].time >= cfg["max_time"]:
                slots.remove(s)
                finish(s)
        frame += 1


# ---------- ученик ----------

class Trainer:
    """Сети на видеокарте, процессы-бойцы, метрики. start() — запустить, stop() — остановить."""

    def __init__(self, lab_dir=None, cfg=None, fresh=False):
        import torch
        self.torch = torch
        self._cfg_given = dict(cfg or {})       # что задал пользователь: это важнее метрик старой точки
        self.cfg = dict(CONFIG, **self._cfg_given)
        if not self.cfg["workers"]:
            self.cfg["workers"] = auto_workers()
        self.obs_mod, self.net_mod, self.np_mod = model_mods(self.cfg)
        self.defaults = DEFAULTS_FULL if self.cfg.get("full") else DEFAULTS
        self.arch = dict(F.ARCH) if self.cfg.get("full") else None
        self.dir = lab_dir or os.path.join(ROOT, "save", "lab" + ("_full" if self.cfg.get("full") else ""))
        self.wdir = os.path.join(self.dir, "live")
        os.makedirs(self.wdir, exist_ok=True)
        self.device = self.cfg.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.device == "cuda":
            torch.backends.cudnn.benchmark = True
            torch.set_float32_matmul_precision("high")
        self.agents, self.opts, self.pending, self.net_stats = {}, {}, {}, {}
        self.lock = threading.Lock()
        self.version = 0
        self.running = False
        self.paused = False
        self.procs, self.out_q, self.task_q = [], None, None
        self.t_start = time.time()
        self.battles = 0
        self.teacher_battles = 0
        self.net_battles = 0
        self.samples = 0
        self.updates = 0
        self.recent = collections.deque(maxlen=400)              # последние бои
        self.arrivals = collections.deque()                      # время прихода боёв (скорость)
        self.history = collections.defaultdict(list)             # ряды графиков: [(бой, значение)]
        self.class_reward = collections.defaultdict(lambda: collections.deque(maxlen=200))
        self.enemy_reward = collections.defaultdict(lambda: collections.deque(maxlen=200))
        self.last_update = {}
        self.evals = []        # [(бой, побед сетей, побед автопилота, n, здоровья у сетей, у автопилота)]
        self.eval_pending = {}
        self.eval_id = 0
        self.next_eval = self.cfg["eval_every"]
        self.res = {"cpu": 0.0, "gpu": 0.0, "gpu_mem": 0.0}
        self.errors = []                                         # упавшие бои: сценарий и трассировка
        self.reward_battles = 0                                  # боёв с этим пресетом награды (затухание)
        self.parts = collections.deque(maxlen=200)               # вклад компонентов награды героев по боям
        self.rstat = {k: [0.0, 0.0, 0.0] for k, _ in SIDES}      # отдача без нормировки: n, сумма, сумма квадратов
        self.ent = {k: self.cfg["entropy"] for k, _ in SIDES}    # премия за энтропию — своя у каждой сети
        self.warm = {k: 0 for k, _ in SIDES}                     # осталось шагов «только критик»
        self.enemy_updates = 0
        self.eval_base = {}                                      # результаты автопилота по сценариям контроля
        self.lpower = {b: 0.0 for b in ("a0", "a1", "a2", "boss")}  # баланс матчей: логарифм силы врагов
        self.eval_power = None                                   # сила врагов в контроле (заморожена)
        self.bal = {}                                            # победы и бои группы с прошлой подстройки
        self.planner_wins = collections.deque(maxlen=60)         # победы учителя-планировщика
        from .data import GameData
        from . import expedition as X
        self.ed = X.expedition_data(GameData())
        self._load(fresh)

    @property
    def nets(self):
        return {k: ag.net for k, ag in self.agents.items()}

    @property
    def elapsed(self):
        return time.time() - self.t_start

    @property
    def workers(self):
        return len(self.procs)

    @property
    def alive(self):
        return sum(1 for p in self.procs if p.is_alive())

    # --- сети ---
    def _load(self, fresh=False):
        """Сети: точка лаборатории (save/lab/ckpt) или школы игры (data/neural), иначе — новые. fresh — новые."""
        torch = self.torch
        ck = os.path.join(self.dir, "ckpt")
        for key, kind in SIDES:
            st = None if fresh else (self._read(ck, kind, key) or self._read(self.defaults, kind, key))
            ag = NN.Agent(key, st, obs=self.obs_mod, net=self.net_mod, arch=self.arch)
            ag.ensure(self.ed)
            ag.net.to(self.device)
            self.agents[key] = ag
            self.opts[key] = torch.optim.Adam(ag.net.parameters(), lr=self.cfg["lr"])
            self.pending[key] = []
            self.net_stats[key] = {"updates": 0, "samples": 0}
            if not ((st or {}).get("stats") or {}).get("critic_ready"):
                self.warm[key] = self.cfg["critic_warmup"]
        meta = os.path.join(self.dir, "metrics.json")
        if os.path.exists(meta) and not fresh:
            try:
                m = json.load(open(meta, encoding="utf-8"))
                self.battles = m.get("battles", 0)
                self.reward_battles = m.get("reward_battles", self.battles)
                old_reward = m.get("reward")
                if "reward" not in self._cfg_given:
                    self.cfg["reward"] = old_reward or self.cfg["reward"]
                elif old_reward and old_reward != self.cfg["reward"]:
                    self.reward_battles = 0            # явная смена пресета: затухание начинается заново
                self.history.update({k: [tuple(x) for x in v] for k, v in m.get("history", {}).items()})
                self.evals = [tuple(e) + (0.0, 0.0)[:6 - len(e)] for e in m.get("evals", [])]
                self.next_eval = self.battles + self.cfg["eval_every"]
                self.rstat.update({k: list(v) for k, v in m.get("rstat", {}).items()})
                self.ent.update(m.get("ent", {}))
                self.eval_base = {int(k): v for k, v in m.get("eval_base", {}).items()}
                self.lpower.update(m.get("lpower", {}))
                if "eval_power" not in self._cfg_given:
                    self.eval_power = m.get("eval_power")
            except (OSError, ValueError):
                pass

    def power(self):
        """Сила врагов по группам сложности (баланс матчей)."""
        import math
        return {b: round(math.exp(v), 3) for b, v in self.lpower.items()}

    def rscale(self):
        """Нормировка награды по сетям: 1 / разброс отдачи (Engstrom и др. 2020) — критику всё равно, какой пресет."""
        out = {}
        for k, (n, sm, sq) in self.rstat.items():
            if n < 500:
                out[k] = 1.0
                continue
            var = max(1e-6, sq / n - (sm / n) ** 2)
            out[k] = float(1.0 / max(0.05, var ** 0.5))
        return out

    def _read(self, root, kind, key):
        p = os.path.join(root, kind, f"{key}.pt")
        if not os.path.exists(p):
            return None
        try:
            d = self.torch.load(p, map_location="cpu", weights_only=False)
            return d if d.get("names") else None
        except Exception:                            # noqa: BLE001
            return None

    def snapshot(self):
        """Состояния сетей на процессоре: {ключ: {"net", "names", "arch"}}."""
        with self.lock:
            return {k: {"net": {n: v.detach().cpu().clone() for n, v in ag.net.state_dict().items()},
                        "names": ag.names, "arch": ag.net.arch} for k, ag in self.agents.items()}

    def reward(self):
        """Веса награды на этот момент: пресет, затухание подсказок и командный дух — по числу боёв."""
        return RW.resolve(self.cfg["reward"], self.reward_battles)

    def set_reward(self, name):
        """Сменить пресет награды можно до первого боя. На ходу это ломает критика и нормировку награды,
        поэтому по умолчанию запрещено; для эксперимента — CONFIG["allow_reward_switch"] = True."""
        if name not in RW.PRESETS:
            return False
        if self.battles > 0 and not self.cfg.get("allow_reward_switch", False):
            self.history["reward_blocked"].append((self.battles, list(RW.PRESETS).index(name)))
            return False
        self.cfg["reward"] = name
        self.reward_battles = 0
        self.history["reward_switch"].append((self.battles, list(RW.PRESETS).index(name)))
        return True

    def publish_weights(self):
        """Веса сетей → weights_<версия>.npz (numpy, + награда), номер — в version.txt; старые версии удаляются."""
        v = self.version + 1
        tmp = weights_path(self.wdir, v) + ".tmp"
        NP.save(tmp, self.snapshot(), {"reward": self.reward(), "rscale": self.rscale(),
                                       "power": self.power() if self.cfg["balance"] else {}})
        os.replace(tmp, weights_path(self.wdir, v))
        for _ in range(20):
            try:
                with open(os.path.join(self.wdir, "version.txt"), "w") as f:
                    f.write(str(v))
                break
            except OSError:                          # боец как раз читает номер
                time.sleep(0.01)
        self.version = v
        for name in os.listdir(self.wdir):           # старше трёх версий — уже никто не читает
            if name.startswith("weights_") and name.endswith(".npz"):
                try:
                    if int(name[8:-4]) < v - 3:
                        os.remove(os.path.join(self.wdir, name))
                except (ValueError, OSError):
                    pass

    def showcase_agents(self):
        """Агенты на процессоре с текущими весами — для показательного боя."""
        snap = {k: dict(st, net={n: w.numpy() for n, w in st["net"].items()}) for k, st in self.snapshot().items()}
        ags = make_agents(snap, self.cfg)
        for ag in ags.values():
            ag.ensure(self.ed)
            ag.stats = {"battles": self.battles}
        return ags

    # --- процессы ---
    def start(self):
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        set_priority(True)
        for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):   # бойцу — одно ядро
            os.environ[var] = "1"
        self.out_q, self.task_q = ctx.Queue(maxsize=2000), ctx.Queue()
        self.publish_weights()
        for wid in range(self.cfg["workers"]):
            p = ctx.Process(target=worker_main, args=(wid, self.wdir, self.out_q, self.task_q, self.cfg, os.getpid()),
                            daemon=True)
            p.start()
            self.procs.append(p)
        self.running = True
        threading.Thread(target=self.train_loop, daemon=True).start()
        threading.Thread(target=self._monitor, daemon=True).start()

    def stop(self):
        self.running = False
        for _ in self.procs:
            try:
                self.task_q.put("stop")
            except Exception:                        # noqa: BLE001
                pass
        end = time.time() + 8                        # общий срок на всех: бойцы доигрывают кадр и выходят
        for p in self.procs:
            p.join(timeout=max(0.1, end - time.time()))
        for p in self.procs:
            if p.is_alive():
                p.terminate()
        self.procs = []
        self.save()

    # --- цикл ученика ---
    def train_loop(self):
        while self.running:
            try:
                self._train_loop()
            except Exception:                        # noqa: BLE001 — показать в окне и продолжить
                import traceback
                self.errors.append({"worker": "ученик", "scenario": None, "trace": traceback.format_exc()[-1500:]})
                time.sleep(1.0)

    def _train_loop(self):
        last_pub = last_save = time.time()
        while self.running:
            if time.time() - last_save > self.cfg["autosave_sec"]:
                self.save()
                last_save = time.time()
            got = 0
            while got < 64:
                try:
                    msg = self.out_q.get(timeout=0.05)
                except queue.Empty:
                    break
                got += 1
                if msg["kind"] == "battle":
                    self._on_battle(msg)
                elif msg["kind"] == "eval":
                    self._on_eval(msg)
                elif msg["kind"] == "error":
                    self.errors.append(msg)
                    del self.errors[:-20]
            if not self.paused:
                for key in list(self.pending):
                    if sum(len(b["a_type"]) for b in self.pending[key]) >= self.cfg["batch"]:
                        self._update(key)
            if time.time() - last_pub > self.cfg["publish_sec"]:
                self.publish_weights()
                last_pub = time.time()
            if self.battles >= self.next_eval:
                self.start_eval()

    def _on_battle(self, m):
        self.battles += 1
        self.arrivals.append(time.time())
        if not self.paused:
            for key, b in m["batches"].items():
                if key in self.pending:
                    self.pending[key].append(b)
                    self.samples += len(b["a_type"])
                    st = self.rstat[key]                 # разброс отдачи — с медленным забыванием (пресет мог смениться)
                    for i in range(3):
                        st[i] = float(st[i] * 0.995 + b["g"][i])
        if m["teacher"]:                             # бой учителя: только примеры, в метрики сетей не идёт
            self.teacher_battles += 1
            if m.get("opp") == "planner":            # уровень учителя-планировщика — для сравнения на графике
                self.planner_wins.append(m["win"])
                if len(self.planner_wins) % 10 == 0:
                    g = list(self.planner_wins)
                    self.history["win_planner"].append((self.battles, sum(g) / len(g)))
            return
        b = m.get("bucket")
        if self.cfg["balance"] and b in self.lpower:    # чаще выигрывают — враги сильнее, реже — слабее
            import math
            acc = self.bal.setdefault(b, [0, 0])
            acc[0] += 1 if m["win"] else 0
            acc[1] += 1
            if acc[1] >= self.cfg["balance_every"]:
                lp = self.lpower[b] + self.cfg["balance_gain"] * (acc[0] / acc[1] -
                                                                  self.cfg.get("balance_target", 0.5))
                self.lpower[b] = max(math.log(0.25), min(math.log(4.0), lp))
                self.bal[b] = [0, 0]
        self.recent.append(m)
        self.net_battles += 1
        self.reward_battles += 1
        if NN.HERO_KEY in m.get("parts", {}):
            self.parts.append(m["parts"][NN.HERO_KEY])
        for cls, r in m["cls_reward"].items():
            self.class_reward[cls].append(r)
        for et, r in m["enemy_reward"].items():
            self.enemy_reward[et].append(r)
        if self.net_battles % 20 == 0:
            rec = list(self.recent)[-200:]
            self.history["win"].append((self.battles, sum(x["win"] for x in rec) / len(rec)))
            for opp in ("rules", "latest", "past"):      # победы по соперникам: против правил — неподвижная мерка
                g = [x["win"] for x in list(self.recent) if x.get("opp") == opp][-150:]
                if len(g) >= 10:
                    self.history["win_" + opp].append((self.battles, sum(g) / len(g)))
            self.history["time"].append((self.battles, float(np.median([x["time"] for x in rec]))))
            hr = [x["rewards"][NN.HERO_KEY] for x in rec if NN.HERO_KEY in x["rewards"]]
            er = [x["rewards"][NN.ENEMY_KEY] for x in rec if NN.ENEMY_KEY in x["rewards"]]
            self.history["hero_reward"].append((self.battles, float(np.mean(hr)) if hr else 0.0))
            self.history["enemy_reward"].append((self.battles, float(np.mean(er)) if er else 0.0))
            self.history["bps"].append((self.battles, self.battles_per_sec()))
            self.history["cpu"].append((self.battles, self.res["cpu"]))
            self.history["gpu"].append((self.battles, self.res["gpu"]))
            comps = {k for p in self.parts for k in p}
            for k in comps:
                self.history["rp:" + k].append((self.battles, float(np.mean([p.get(k, 0.0) for p in self.parts]))))
            for b, v in self.power().items():
                self.history["power:" + b].append((self.battles, v))
            rw = self.reward()
            self.history["tau"].append((self.battles, rw["tau"]))
            self.history["scale"].append((self.battles, rw["scale"]))
            for k, v in self.history.items():
                if len(v) > 3000:
                    del v[:-3000]

    def battles_per_sec(self):
        """Боёв в секунду за последние 30 с (по приходу к ученику)."""
        now = time.time()
        while self.arrivals and now - self.arrivals[0] > 30:
            self.arrivals.popleft()
        if len(self.arrivals) < 2:
            return 0.0
        return len(self.arrivals) / max(1.0, min(30.0, now - self.t_start))

    def _update(self, key):
        batch = NN.merge(self.pending[key])
        self.pending[key] = []
        ag, opt = self.agents[key], self.opts[key]
        lr = self.cfg["lr"]
        final = self.cfg.get("lr_final")
        anneal = self.cfg.get("lr_anneal") or 0
        if final is not None and anneal:
            lr += (final - lr) * min(1.0, self.battles / anneal)
        for g in opt.param_groups:
            g["lr"] = lr
        warm = self.warm[key] > 0
        with self.lock:
            st = E.ppo_step(ag.net, opt, batch, device=self.device, epochs=self.cfg["epochs"],
                            minibatch=self.cfg["minibatch"], clip=self.cfg["clip"], ent=self.ent[key],
                            bc=self.cfg["bc"], vclip=self.cfg["vclip"], pi=0.0 if warm else 1.0)
        if warm:
            self.warm[key] -= 1
        else:                                        # премия за энтропию тянет её к ent_target
            lo, hi = self.cfg["ent_range"]
            self.ent[key] = min(hi, max(lo, self.ent[key] * (1.1 if st["ent"] < self.cfg["ent_target"] else 0.92)))
        st["ent_coef"] = self.ent[key]
        if key == NN.ENEMY_KEY:
            self.enemy_updates += 1
            if self.enemy_updates % self.cfg["pool_every"] == 0:
                self._snapshot_pool()
        self.updates += 1
        ns = self.net_stats[key]
        ns["updates"] += 1
        ns["samples"] += len(batch["a_type"])
        self.last_update[key] = st
        for k in ("pi", "v", "ent", "kl", "clip", "bc", "ent_coef"):
            h = self.history[f"loss_{k}:{key}"]
            h.append((self.battles, st.get(k, 0.0)))
            if len(h) > 2000:
                del h[:-2000]

    def _snapshot_pool(self):
        """Снимок сети врагов — в пул прошлых версий (с ними герои тоже бьются: не забывать старые приёмы)."""
        d = os.path.join(self.wdir, "pool")
        os.makedirs(d, exist_ok=True)
        snap = self.snapshot()
        NP.save(os.path.join(d, f"enemy_{self.enemy_updates:07d}.npz"), {NN.ENEMY_KEY: snap[NN.ENEMY_KEY]})
        files = sorted(f for f in os.listdir(d) if f.endswith(".npz"))
        for f in files[:-self.cfg["pool_size"]]:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass

    # --- контроль ---
    def start_eval(self):
        """Серия контрольных боёв: одни и те же сценарии — сетями (без случайности); автопилот на них считается
        один раз и запоминается (он не меняется)."""
        self.eval_id += 1
        self.eval_pending[self.eval_id] = {"at": self.battles, "res": []}
        fixed = self.cfg.get("eval_power")
        if fixed is not None:                               # фиксированная сила контроля (честная мерка)
            fixed = float(fixed)
            if not self.eval_power or any(abs(v - fixed) > 1e-9 for v in self.eval_power.values()):
                self.eval_power = {b: fixed for b in ("a0", "a1", "a2", "boss")}
                self.eval_base = {}
        elif self.eval_power is None or not self.eval_base:   # иначе замораживаем силу первого прогона
            self.eval_power = self.power() if self.cfg["balance"] else {}
            self.eval_base = {}
        for k in range(self.cfg["eval_size"]):
            seed = 10_000 + k
            sc = scenario(self.ed, seed, gear=self.cfg.get("hero_gear"))
            sc["power"] = self.eval_power.get(bucket(sc), 1.0)
            self.task_q.put({"eval_id": self.eval_id, "scenario": sc, "need_base": seed not in self.eval_base})
        self.next_eval = self.battles + self.cfg["eval_every"]

    def _on_eval(self, m):
        e = self.eval_pending.get(m["eval_id"])
        if e is None:
            return
        res = dict(m["res"])
        seed = m["scenario"]["seed"]
        if "teacher" in res:
            self.eval_base[seed] = res["teacher"]
        res["teacher"] = self.eval_base.get(seed, {"win": False, "hp": 0.0, "time": 0.0})
        e["res"].append(res)
        if len(e["res"]) >= self.cfg["eval_size"]:
            nw = sum(r["net"]["win"] for r in e["res"])
            tw = sum(r["teacher"]["win"] for r in e["res"])
            nhp = float(np.mean([r["net"]["hp"] for r in e["res"]]))
            thp = float(np.mean([r["teacher"]["hp"] for r in e["res"]]))
            self.evals.append((e["at"], nw, tw, len(e["res"]), nhp, thp))
            del self.eval_pending[m["eval_id"]]

    # --- ресурсы ---
    def _monitor(self):
        import psutil
        while self.running:
            self.res["cpu"] = psutil.cpu_percent(interval=1.0)
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                                      "--format=csv,noheader,nounits"], capture_output=True, text=True,
                                     timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                g, mem = out.strip().split("\n")[0].split(",")
                self.res["gpu"], self.res["gpu_mem"] = float(g), float(mem)
            except Exception:                        # noqa: BLE001
                pass
            time.sleep(1.0)

    # --- сохранение ---
    def _write(self, root, keys=None):
        snap = self.snapshot()
        for key, kind in SIDES:
            if keys is not None and key not in keys:
                continue
            p = os.path.join(root, kind, f"{key}.pt")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            self.torch.save(dict(snap[key], stats={"battles": self.battles, "rewards": [], "wins": 0,
                                                   "updates": self.net_stats[key]["updates"],
                                                   "critic_ready": self.warm[key] <= 0}), p)

    def save(self):
        """Точка лаборатории: сети (save/lab/ckpt) и метрики."""
        self._write(os.path.join(self.dir, "ckpt"))
        path = os.path.join(self.dir, "metrics.json")
        with open(path + ".tmp", "w", encoding="utf-8") as f:       # сначала во временный: сбой не портит метрики
            json.dump({"battles": self.battles, "reward": self.cfg["reward"], "reward_battles": self.reward_battles,
                       "rstat": self.rstat, "ent": self.ent, "lpower": self.lpower, "eval_power": self.eval_power,
                       "eval_base": {str(k): v for k, v in self.eval_base.items()},
                       "history": {k: v[-2000:] for k, v in self.history.items()}, "evals": self.evals},
                      f, default=float)
        os.replace(path + ".tmp", path)

    def publish(self):
        """Школа героев — в data/neural: с неё начнут новые герои режима обучения. Сеть врагов не трогаем."""
        keys = None if self.cfg["learn_enemies"] else {NN.HERO_KEY}
        self._write(self.defaults, keys)

    # --- сводка для окна (окно — в другом процессе) ---
    def status(self):
        """Всё, что показывает окно лаборатории: метрики, ряды графиков, контроль, сети. Только простые типы."""
        ag = self.agents[NN.HERO_KEY]
        rec = list(self.recent)
        classes = {}
        for cls in sorted(self.ed.classes):
            rw = self.class_reward.get(cls)
            games = [x for x in rec if cls in x["squad"]]
            classes[cls] = (float(np.mean(rw)) if rw else None,
                            sum(x["win"] for x in games) / len(games) if games else None, len(games))
        pend = list(self.eval_pending.values())
        return {"battles": self.battles, "teacher_battles": self.teacher_battles, "samples": self.samples,
                "updates": self.updates, "version": self.version, "device": self.device, "paused": self.paused,
                "res": dict(self.res), "workers": len(self.procs), "alive": self.alive, "cfg": dict(self.cfg),
                "history": {k: list(v) for k, v in self.history.items()}, "evals": list(self.evals),
                "eval_progress": (sum(len(e["res"]) for e in pend), self.cfg["eval_size"] * len(pend)),
                "classes": classes, "net_stats": {k: dict(v) for k, v in self.net_stats.items()},
                "net": {"names": {k: len(v) for k, v in ag.names.items()}, "arch": dict(ag.net.arch),
                        "params": sum(p.numel() for p in ag.net.parameters())},
                "reward": self.reward(), "bps": self.battles_per_sec(), "elapsed": time.time() - self.t_start,
                "ent_coef": dict(self.ent), "rscale": self.rscale(), "warm": dict(self.warm), "power": self.power(),
                "errors": len(self.errors), "last_error": self.errors[-1]["trace"] if self.errors else None,
                "wdir": self.wdir}

    def command(self, cmd, arg=None):
        if cmd == "pause":
            self.paused = bool(arg)
        elif cmd == "save":
            self.save()
        elif cmd == "publish":
            self.publish()
        elif cmd == "reward":
            self.set_reward(arg)
        elif cmd == "eval":
            self.start_eval()


def learner_main(lab_dir, cfg, fresh, cmd_q, stat_q):
    """Процесс ученика (окно лаборатории запускает его отдельно): сети на видеокарте, бойцы, метрики.
    Окну раз в секунду — сводка (stat_q), от окна — команды (cmd_q). Отдельный процесс, чтобы отрисовка окна не
    отнимала у ученика интерпретатор (GIL): иначе опыт от бойцов не успевает разбираться и они простаивают."""
    tr = Trainer(lab_dir, cfg, fresh)
    stat_q.cancel_join_thread()                      # выход не ждёт, пока окно дочитает сводки
    tr.start()
    try:
        while True:
            try:
                cmd = cmd_q.get(timeout=1.0)
            except queue.Empty:
                cmd = None
            if cmd is not None:
                if cmd[0] == "stop":
                    break
                tr.command(*cmd)
            try:
                while stat_q.qsize() > 1:
                    stat_q.get_nowait()
                stat_q.put_nowait(tr.status())
            except (queue.Full, queue.Empty, NotImplementedError):
                pass
    finally:
        tr.stop()
        try:
            stat_q.put({"stopped": True}, timeout=1)
        except queue.Full:
            pass


class RemoteTrainer:
    """Окно ↔ процесс ученика: те же поля и команды, что у Trainer, но сводка приходит по очереди раз в секунду.
    Окно не грузит torch: показательный бой берёт веса из файла (numpy)."""

    def __init__(self, lab_dir=None, cfg=None, fresh=False):
        import multiprocessing as mp
        from .data import GameData
        from . import expedition as X
        self.cfg = dict(CONFIG, **(cfg or {}))
        self.dir = lab_dir or os.path.join(ROOT, "save", "lab" + ("_full" if self.cfg.get("full") else ""))
        self.wdir = os.path.join(self.dir, "live")
        self.ed = X.expedition_data(GameData())
        ctx = mp.get_context("spawn")
        self.cmd_q, self.stat_q = ctx.Queue(), ctx.Queue(maxsize=3)
        self.proc = ctx.Process(target=learner_main, args=(self.dir, cfg, fresh, self.cmd_q, self.stat_q))
        self.s = {"battles": 0, "teacher_battles": 0, "samples": 0, "updates": 0, "version": 0, "device": "…",
                  "paused": False, "res": {"cpu": 0.0, "gpu": 0.0, "gpu_mem": 0.0}, "workers": 0, "alive": 0,
                  "cfg": dict(CONFIG, **(cfg or {})), "history": {}, "evals": [], "eval_progress": (0, 0),
                  "classes": {}, "net_stats": {}, "net": None, "reward": RW.resolve(), "bps": 0.0, "elapsed": 0.0,
                  "errors": 0, "last_error": None}
        self.paused_local = None

    def start(self):
        self.proc.start()

    def poll(self):
        """Забрать свежую сводку (вызывать каждый кадр — дёшево)."""
        got = None
        while True:
            try:
                got = self.stat_q.get_nowait()
            except (queue.Empty, OSError):
                break
        if got and not got.get("stopped"):
            self.s = got
        return self.s

    def __getattr__(self, name):
        s = self.__dict__.get("s")
        if s is not None and name in s:
            return s[name]
        raise AttributeError(name)

    @property
    def paused(self):
        return self.s["paused"] if self.paused_local is None else self.paused_local

    @paused.setter
    def paused(self, v):
        self.paused_local = bool(v)
        self.s["paused"] = bool(v)
        self.cmd_q.put(("pause", bool(v)))

    def reward(self):
        return self.s["reward"]

    def battles_per_sec(self):
        return self.s["bps"]

    def save(self):
        self.cmd_q.put(("save",))

    def publish(self):
        self.cmd_q.put(("publish",))

    def start_eval(self):
        self.cmd_q.put(("eval",))

    def set_reward(self, name):
        self.cmd_q.put(("reward", name))
        self.s["reward"] = RW.resolve(name)

    def showcase_agents(self):
        """Агенты с последних опубликованных весов (numpy). Весов ещё нет — новые случайные сети."""
        got = latest_agents(self.wdir, self.ed, self.cfg)
        if got is None:
            return None
        ags, _, _ = got
        for ag in ags.values():
            ag.stats = {"battles": self.s["battles"]}
        return ags

    def stop(self, timeout=60):
        """Остановить ученика: он сам остановит бойцов и сохранит точку."""
        try:
            self.cmd_q.put(("stop",))
        except Exception:                            # noqa: BLE001
            pass
        end = time.time() + timeout
        while self.proc.is_alive() and time.time() < end:   # ученик сохраняет точку; сводки дочитываем
            self.poll()
            self.proc.join(0.2)
        if self.proc.is_alive():
            self.proc.terminate()
