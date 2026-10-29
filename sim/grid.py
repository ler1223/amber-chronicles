"""Сетка поля: клетки, соседство (8 направлений), A*."""
import heapq

DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
PERMANENT = -1.0


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def sign(v):
    return (v > 0) - (v < 0)


class Cell:
    __slots__ = ("pos", "terrain", "passable", "cover", "hazard", "hazard_time", "hazard_team", "base_terrain",
                 "portal", "deco", "hazard_owner")

    def __init__(self, pos, terrain="grass", passable=True, cover=None, hazard=None):
        self.pos = pos
        self.terrain = terrain
        self.passable = passable
        self.cover = cover
        self.hazard = hazard
        self.hazard_time = PERMANENT if hazard else 0.0
        self.hazard_team = None    # чья ловушка: срабатывает только на чужих
        self.hazard_owner = None   # кто поставил капкан (ему — шкала за пойманного)
        self.base_terrain = None   # прилив: настоящий рельеф под временной водой
        self.portal = False
        self.deco = None           # дерево и т.п. — только для отрисовки


class Grid:
    def __init__(self, rows, legend):
        self.h = len(rows)
        self.w = len(rows[0])
        self.cells = {}
        portals = []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                d = legend[ch]
                c = self.cells[(x, y)] = Cell((x, y), d.get("terrain", "grass"), d.get("passable", True),
                                              d.get("cover"), d.get("hazard"))
                c.deco = d.get("deco")
                if d.get("portal"):
                    c.portal = True
                    portals.append((x, y))
        # порталы связаны парами по порядку на карте (сверху вниз, слева направо)
        self.portal_pair = {}
        for a, b in zip(portals[::2], portals[1::2]):
            self.portal_pair[a], self.portal_pair[b] = b, a

    def in_bounds(self, p):
        return 0 <= p[0] < self.w and 0 <= p[1] < self.h

    def get(self, p):
        return self.cells.get(tuple(p))

    def passable(self, p, flying=False):
        c = self.cells.get(p)
        return c is not None and (c.passable or (flying and c.terrain == "chasm"))

    def neighbors(self, p, flying=False):
        x, y = p
        for dx, dy in DIRS8:
            n = (x + dx, y + dy)
            if not self.passable(n, flying):
                continue
            # по диагонали нельзя срезать угол препятствия
            if dx and dy and not (self.passable((x + dx, y), flying) and self.passable((x, y + dy), flying)):
                continue
            yield n, (1.001 if dx and dy else 1.0)

    def in_radius(self, center, r):
        cx, cy = center
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if self.in_bounds((x, y)):
                    yield (x, y)

    def find_path(self, start, goal, heuristic, blocked=frozenset(), flying=False, penalty=None):
        """penalty(p) — доплата за шаг на опасную клетку (лава, огонь): обходим, если есть путь не намного длиннее."""
        """A*: goal(p)->bool, heuristic(p)->float. Возвращает список клеток без start или None."""
        if goal(start):
            return []
        open_heap = [(heuristic(start), 0.0, start)]
        came = {start: None}
        cost = {start: 0.0}
        while open_heap:
            _, g, cur = heapq.heappop(open_heap)
            if g > cost[cur]:
                continue
            if goal(cur):
                path = []
                while cur != start:
                    path.append(cur)
                    cur = came[cur]
                return path[::-1]
            for n, step in self.neighbors(cur, flying):
                if n in blocked:
                    continue
                ng = g + step + (penalty(n) if penalty else 0.0)
                if ng < cost.get(n, 1e9):
                    cost[n] = ng
                    came[n] = cur
                    heapq.heappush(open_heap, (ng + heuristic(n), ng, n))
        return None

    def cover_between(self, shooter, target):
        """Укрытие, стоящее вплотную к цели со стороны стрелка."""
        dx, dy = sign(shooter[0] - target[0]), sign(shooter[1] - target[1])
        if (dx, dy) == (0, 0):
            return None
        c = self.get((target[0] + dx, target[1] + dy))
        if c is None or tuple(shooter) == c.pos:
            return None
        return c.cover
