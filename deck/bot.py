"""Простой бот «Спуска» — для тестов и замеров баланса (tools/deck_bench.py): уходит из зон, бьёт слабейшего,
закрывается от ожидаемого урона, добирает простыми действиями."""
from sim.grid import cheb

from .battle import BallistaShot, finish
from .model import BALLISTA_CARD


def incoming(b):
    return sum(b.intent_damage(u) for u in b.foes()
               if (u.intent or {}).get("kind") != "zone" or b.hero.cell in u.intent.get("cells", []))


def danger_cells(b):
    out = set()
    for u in b.foes():
        it = u.intent or {}
        if it.get("kind") == "zone":
            out.update(b.zone_hit_cells(it))
        elif it.get("kind") == "charge":                     # линии рывка
            out |= set(it["cells"])
    e = getattr(b, "env_now", None)
    if e and e.get("kind") == "lava_rain":                       # лава с потолка
        out |= set(e["cells"])
    return out


def ops(card, mode):
    return [o["op"] for o in card.d[mode].get("do", [])]


def deals(card, mode):
    return any(o in ("damage", "body_slam", "aoe_adjacent", "ballista_fire") for o in ops(card, mode))


def best_target(b, card, mode, ts):
    """Цель: область — где больше врагов, юнит — слабейший."""
    u = card.d[mode]
    if u["target"] == "area":
        r = u.get("radius", 1)
        return max(ts, key=lambda p: sum(1 for f in b.foes() if cheb(f.cell, p) <= r))
    if u["target"] == "ballista_fire":
        op = next(op for op in u["do"] if op["op"] == "ballista_fire")
        shots = [BallistaShot(ballista, foe) for foe in ts for ballista in b.ballista_shooters(foe, u.get("range", 6))]
        return max(shots, key=lambda shot: min(shot.victim.hp + shot.victim.shield,
                                                b.ballista_damage(op, shot.victim, shot.ballista)))
    return min(ts, key=lambda t: getattr(t, "hp", 0))


def area_hits(b, card, mode, p):
    r = card.d[mode].get("radius", 1)
    return sum(1 for f in b.foes() if cheb(f.cell, p) <= r)


def block_target(b, card):
    if "block" not in ops(card, "main"):
        return None
    targets = b.targets(card, "main")
    if card.d["main"]["target"] == "ballista_load" and targets:
        return targets[-1]                                 # защититься и одновременно зарядить
    return b.hero if b.hero in targets else None


def threat(b, p):
    """Сколько врагов дотянется до клетки p в их ход (грубо): ближние — по ходу+1, стрелки — по дальности."""
    n = 0
    for f in b.foes():
        it = f.intent or {}
        reach = (it.get("range", 5) if it.get("kind") in ("shot", "pull") else f.speed + 1)
        if cheb(f.cell, p) <= reach:
            n += 1
    return n


def priest_step(b):
    """Жрец: свитки — по статуям, где богу есть что делать (атаки — тем, кто ближе к врагам; защита — когда
    грозит удар); потом — шаги в самое безопасное место."""
    from .idols import IdolCast, SKIP
    idols = b.idols
    h = b.hero
    order = {"attack": 0, "curse": 1, "summon": 2, "move": 3, "defense": 4, "gift": 5}
    if any(idols.silenced(s) for s in idols.statues):        # статую глушат — сперва отогнать
        order["move"] = -1
    for c in sorted(b.hand, key=lambda c: order.get(c.d.get("meaning"), 9)):
        if not c.d.get("meaning"):                              # не свиток («Тина» от предмета) — мимо
            continue
        sts = b.targets(c, "main")
        if c.d.get("meaning") == "move" and any(idols.silenced(s) for s in sts):
            sts = [s for s in sts if idols.silenced(s)] + [s for s in sts if not idols.silenced(s)]
        if not sts:
            continue
        m = c.d["meaning"]
        if m == "defense" and incoming(b) <= h.shield:
            continue
        best = None
        for st in sts:
            t = idols.target_for(st, m, None)
            if t is SKIP:
                continue
            ch = idols.choices(st, m)
            if ch is not None and t not in ch:
                continue
            foes = b.foes()
            score = -min((cheb(st.cell, f.cell) for f in foes), default=0) + idols.level(st)
            if best is None or score > best[0]:
                best = (score, st, t)
        if best is not None:
            finish(b.play(c, "main", IdolCast(best[1], best[2])))
            return True
    cells = b.walk_cells()
    if cells:
        zone = danger_cells(b)
        cur = (h.cell in zone, threat(b, h.cell))
        p = min(cells, key=lambda p: (p in zone, threat(b, p), -min((cheb(p, f.cell) for f in b.foes()), default=0)))
        if (p in zone, threat(b, p)) < cur:
            finish(b.hero_walk(p))
            return True
    return False


def step_once(b):
    """Один розыгрыш; False — больше нечего делать."""
    if getattr(b, "idols", None) is not None:
        return priest_step(b)
    h = b.hero
    zone = danger_cells(b)
    hand = list(b.hand)
    if h.cell in zone:                                        # 1. уйти из зоны
        for c in hand:
            for mode in ("alt", "main"):
                if c.d[mode]["target"] in ("cell_step", "cell_dash"):
                    safe = [p for p in b.targets(c, mode) if p not in zone]
                    if safe:
                        foes = b.foes()
                        p = min(safe, key=lambda p: min((cheb(p, f.cell) for f in foes), default=0))
                        finish(b.play(c, mode, p))
                        return True
    foes = b.foes()
    if not foes:
        return False
    for c in hand:
        use = c.d["main"]
        if use["target"] == "copy_hand":
            options = [target for target in b.targets(c, "main") if not target.d.get("status")]
            if options:
                target = max(options, key=lambda x: (x.cid == BALLISTA_CARD, x.cost))
                finish(b.play(c, "main", target))
                return True
        elif use["target"] in ("hand_retain", "hand_other"):
            options = b.targets(c, "main")
            if options:
                count = use.get("count", 1)
                finish(b.play(c, "main", tuple(options[:count]) if count > 1 else options[0]))
                return True
    for c in hand:                                            # 1б. Силы до конца боя — сразу
        if c.d["main"].get("power") and b.targets(c, "main"):
            finish(b.play(c, "main", h))
            return True
    hit = lambda c: sum(o.get("n", 0) for o in c.d["main"].get("do", []) if o["op"] == "damage")
    for c in hand:                                            # 2а. добить того, кто сейчас ударит
        if hit(c) and c.d["main"]["target"] == "enemy":
            ts = [t for t in b.targets(c, "main") if getattr(t, "hp", 99) <= hit(c) and b.intent_damage(t) > 0]
            if ts:
                finish(b.play(c, "main", max(ts, key=b.intent_damage)))
                return True
    if incoming(b) - h.shield >= 6:                           # 2б. больно — сперва закрыться
        for c in hand:
            t = block_target(b, c)
            if t is not None:
                finish(b.play(c, "main", t))
                return True
    best = None
    for c in hand:                                            # 2. урон основным применением
        if deals(c, "main") or "detonate" in ops(c, "main") or "burn" in ops(c, "main"):
            ts = b.targets(c, "main")
            if ts:
                t = best_target(b, c, "main", ts)
                if c.d["main"]["target"] == "area" and not area_hits(b, c, "main", t):
                    continue
                if "detonate" in ops(c, "main") and not any(f.ds["burn"] for f in b.foes()):
                    continue
                if best is None or c.cost < best[0].cost:
                    best = (c, "main", t)
    if best:
        finish(b.play(*best))
        return True
    if incoming(b) > h.shield:                                # 3. защита основным
        for c in hand:
            t = block_target(b, c)
            if t is not None:
                finish(b.play(c, "main", t))
                return True
    for c in hand:                                            # установка с прострелом, зарядка к следующему залпу
        t = c.d["main"]["target"]
        if t == "ballista_place":
            positions = b.targets(c, "main")
            shots = {p: sum(victim is not None for _, victim in b.ballista_lines(origin=p)) for p in positions}
            if any(shots.values()):
                pos = max((p for p in positions if shots[p]), key=lambda p: (p not in zone, shots[p], -cheb(p, h.cell)))
                finish(b.play(c, "main", pos))
                return True
        elif t == "ballista_load":
            units = b.targets(c, "main")[1:]
            target = next((unit for unit in units if any(
                victim is not None for _, victim in b.ballista_lines(ballista=unit))), None)
            if target is not None:
                finish(b.play(c, "main", target))
                return True
    if b.energy <= 0 and any(cheb(f.cell, h.cell) <= 1 for f in foes):   # 4а. всё сыграно, враг рядом — отойти
        for c in hand:
            for mode in ("alt", "main"):
                if c.d[mode]["target"] in ("cell_step", "cell_dash") and b.targets(c, mode) and                         (mode == "alt" or c.cost == 0):
                    ts = [p for p in b.targets(c, mode) if p not in zone]
                    if ts:
                        p = min(ts, key=lambda p: (threat(b, p), -min(cheb(p, f.cell) for f in foes)))
                        if threat(b, p) < threat(b, h.cell):
                            finish(b.play(c, mode, p))
                            return True
    if not any(cheb(f.cell, h.cell) <= 1 for f in foes):      # 4. подойти простым шагом
        for c in hand:
            if c.d["alt"]["target"] in ("cell_step", "cell_dash") and b.targets(c, "alt"):
                ts = [p for p in b.targets(c, "alt") if p not in zone]
                if ts:
                    p = min(ts, key=lambda p: min(cheb(p, f.cell) for f in foes))
                    if min(cheb(p, f.cell) for f in foes) < min(cheb(h.cell, f.cell) for f in foes):
                        finish(b.play(c, "alt", p))
                        return True
    if b.mech == "heat":                                      # Пиромантка: раздуть жар картами, что не по карману
        for c in hand:
            if "heat" in ops(c, "alt") and not b.can_afford(c) and b.targets(c, "alt"):
                finish(b.play(c, "alt", h))
                return True
    for c in hand:                                            # 5. остальное — простыми действиями
        if deals(c, "alt") and b.targets(c, "alt"):
            ts = b.targets(c, "alt")
            finish(b.play(c, "alt", min(ts, key=lambda t: getattr(t, "hp", 0))))
            return True
    for c in hand:                                            # 6. основные на себя: мощь, контратака, ножи, добор
        u = c.d["main"]
        if u["target"] == "self" and set(ops(c, "main")) - {"heat"} and b.targets(c, "main"):
            finish(b.play(c, "main", h))
            return True
    for c in hand:
        if "block" in ops(c, "alt") and b.targets(c, "alt"):
            finish(b.play(c, "alt", h))
            return True
    return False


def play_turn(b, limit=20):
    for _ in range(limit):
        if b.result or not step_once(b):
            break
    if not b.result:
        finish(b.end_turn())


def play_battle(b, turns=40):
    for _ in range(turns):
        if b.result:
            break
        play_turn(b)
    return b.result
