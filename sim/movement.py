"""Перемещение: цена хода по клеткам, особенности юнитов и вынужденные сдвиги.

Цена хода (во сколько раз дольше шаг) — у рельефа и клеток-опасностей (config.terrain[*].move,
config.hazards[*].move). Особенности юнита (data/traits.json) меняют цену: «плавает» — вода как суша,
«любит жар» — лава как суша, «ловкий» — терновник и масло не мешают; «летает» — всё как суша.
Путь строится с учётом цены: юнит обходит воду, если обход не намного длиннее.

Двигать можно всё, кроме стен (ледяная и костяная стены, укрепления-источники, охраняемые объекты, юниты с
особенностью «недвижим»). «Тяжёлый» (боссы, валун, большая бочка) сдвигается на клетку меньше, невесомый — на
две дальше. Все толчки, притягивания и стягивания идут через forced_move: сдвиг по клеткам, пропасть — падение,
скользкий лёд — скольжение дальше, не хватило места — столкновение (урон обоим, бочка взрывается).
"""
from .grid import cheb, sign

PUSH_KINDS = ("knockback", "push", "rule", "wind")


def traits(c, u):
    t = set(u.proto.get("traits", ()))
    if u.flying:
        t.add("fly")
    if u.heat:
        t.add("heat")
    if u.ice_walker:
        t.add("ice_walk")
    if u.boss:
        t.add("heavy")
    return t


def step_cost(c, u, pos):
    """Во сколько раз дольше шаг на эту клетку (1 — обычная земля)."""
    if u.flying:
        return 1.0
    cell = c.grid.get(pos)
    if cell is None:
        return 1.0
    keys = [cell.terrain] + ([cell.hazard] if cell.hazard else [])
    if cell.hazard and c.cfg["hazards"].get(cell.hazard, {}).get("covers"):
        keys = [cell.hazard]                         # замёрзшая вода — это лёд, а не вода
    over = {}
    for t in traits(c, u):
        over.update(c.data.traits_def.get(t, {}).get("move", {}))
    cost = 1.0
    for k in keys:
        base = c.cfg["terrain"].get(k, {}).get("move") if k == cell.terrain else c.cfg["hazards"].get(k, {}).get("move")
        cost = max(cost, over.get(k, base or 1.0))
    return cost


def movable(c, u):
    """Можно ли сдвинуть юнита или объект: всё, кроме стен и того, что вне времени."""
    if not u.alive or u.stasis > 0 or u.merged > 0:
        return False
    if u.obj:
        return bool(u.obj.get("pushable"))
    return "unmovable" not in traits(c, u)


def heavy(c, u):
    return (u.obj and u.obj.get("heavy")) or "heavy" in traits(c, u)


def forced_move(c, u, cells, next_cell, mover=None, kind="knockback", slide=False):
    """Сдвинуть u на cells клеток; next_cell(клетка) → следующая клетка или None (дошёл до цели).
    Возвращает (сдвинулся ли, столкнулся ли)."""
    if not movable(c, u):
        return False, False
    if heavy(c, u):
        cells -= 1
    if u.levitate > 0:                                   # невесомый улетает дальше
        cells += 2
    p = mover.passive if mover is not None else None
    if p and p["kind"] == "momentum" and kind in PUSH_KINDS and mover.pp >= p["pp"]:
        c._use_passive(mover, f"+{p.get('cells', 1)} клетка толчка", u)
        cells += p.get("cells", 1)
    if cells <= 0:
        return False, False
    c._interrupt(u)
    start, dest, left, blocker, blocked = u.cell, u.cell, cells, None, False
    extra = 0
    while left > 0:
        n = next_cell(dest)
        if n is None:
            left = 0
            break
        if not c.is_free(n, flying=u.flying):
            cell = c.grid.get(n)
            if cell is not None and cell.terrain == "chasm" and not c.unit_at(n) and not u.flying:
                c.emit("knockback" if kind in PUSH_KINDS else "pull", unit=u, src=mover)
                c._place(u, n if u.obj else dest, 0.15)
                c._fall(u)
                return True, False
            blocker, blocked = c.unit_at(n), True
            break
        dest = n
        left -= 1
        # скользкий лёд: толчок проезжает дальше, пока впереди свободно
        if slide and left == 0 and extra < 6 and c.grid.get(dest).terrain == "ice_floor" \
                and "ice_walk" not in traits(c, u) and dest != start:
            nxt = next_cell(dest)
            if nxt is not None and c.is_free(nxt, flying=u.flying):
                left, extra = 1, extra + 1
    moved = dest != start
    c.emit("knockback" if kind in PUSH_KINDS else "pull", unit=u, src=mover)
    if moved:
        c._place(u, dest, 0.12 + 0.05 * cheb(dest, start))
        c.rules.fire("moved", {"forced", kind}, unit=u, source=mover)
        cell = c.grid.get(dest)
        if cell.portal:
            c._after_step(u, start)
    if blocked and left > 0:
        c._collide(u, blocker, left, mover)
    return moved, blocked and left > 0


def push_dir(src_cell, u):
    return sign(u.cell[0] - src_cell[0]), sign(u.cell[1] - src_cell[1])


def toward(target, stop_at=0):
    """next_cell для притягивания: шаг к target, остановка на расстоянии stop_at."""
    def nxt(p):
        if cheb(p, target) <= stop_at:
            return None
        return p[0] + sign(target[0] - p[0]), p[1] + sign(target[1] - p[1])
    return nxt


def straight(d):
    def nxt(p):
        return p[0] + d[0], p[1] + d[1]
    return nxt


def fill_path(c, u, points):
    """Маршрут игрока: точки (клетки) → непрерывная цепочка соседних клеток. Между точками, которые не соседи,
    достраивается кратчайший участок (стены и объекты обходятся). None — до какой-то точки не дойти."""
    walls = {o.cell for o in c.units if o.alive and o.obj}
    out, cur = [], u.cell
    for p in points:
        p = tuple(p)
        if p == cur:
            continue
        if not c.grid.passable(p, u.flying) or p in walls:
            return None
        if cheb(p, cur) == 1 and c.grid.passable(p, u.flying):
            out.append(p)
        else:
            seg = c.grid.find_path(cur, lambda q, p=p: q == p, lambda q, p=p: cheb(q, p), walls, u.flying,
                                   lambda q: step_cost(c, u, q) - 1.0)
            if seg is None:
                return None
            out += seg
        cur = p
    return out


def path_time(c, u, cells):
    """Сколько секунд займёт маршрут (без учёта ожиданий)."""
    base = u.move_time * u.slow_mult(c.tags) * u.buff("slow", 1.0)
    return sum(base * step_cost(c, u, p) for p in cells)
