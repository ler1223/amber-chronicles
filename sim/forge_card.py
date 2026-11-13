"""Кузня по техкартам (квиз 2026-11-13, вариант 4 «гибрид»): у каждой вещи и примитива — техкарта, короткая
последовательность операций; внутри этапа брусок формуют «в двух видах» (sim/forge_bar.py: вид сверху — ширина,
сбоку — толщина; объём сохраняется). У этапа — своя цель (призрак промежуточной формы) и окно жара; перейти к
следующему можно когда угодно, но недочёт остаётся в металле (не дотянул — дальше не хватит длины).

Операции: протяжка и разгонка (удары по виду сверху — уже, по виду сбоку — тоньше; кувалда раздаёт вширь),
осадка (удар в торец — короче и толще), скругление (обжимка — сечение в круг; без неё — удары «на угол»),
гибка на роге (тянуть свободный конец вокруг рога; подать дальше — колесо), пробивка (пробойник; без него —
бородком, грубее). Итог ковки: 75% — готовая форма (последняя форма + гибка + отверстия), 25% — аккуратность
этапов; трещины (удары по холодному) и окалина (перегрев) снижают.

Вещи кузни куются только по техкарте: базовая (потолок 100%) знакома сразу, техкарта мастера — книга бродячего
кузнеца (лишний этап, потолок 130% и шанс свойства)."""
import math

import numpy as np

from . import forge_bar as FB

OPS = {   # операция: (название, что делать, окно жара в долях рабочего диапазона металла, нужный инструмент)
    "draw": ("Протяжка", "вытянуть в длину: по виду сверху — уже, по виду сбоку — тоньше", (0.0, 1.0), None),
    "spread": ("Разгонка", "раздать вширь: удары по виду сбоку гонят металл вбок; по виду сверху — уже и длиннее",
               (0.1, 1.0), None),
    "upset": ("Осадка", "удар в торец: конец короче и толще", (0.35, 1.05), None),
    "round": ("Скругление", "сечение в круг: обжимка (без неё — удары «на угол»)", (0.0, 1.0), "swage"),
    "bend": ("Гибка", "тяните свободный конец вокруг рога; колесо — подать по рогу", (-0.25, 0.6), None),
    "punch": ("Пробивка", "отверстия по меткам: пробойник (без него — бородок, грубее)", (0.2, 1.0), "punch"),
}
BOOK_CARDS = {"bracers": "c_bracers", "belt": "c_belt", "ring": "c_ring", "amulet": "c_amulet"}


def _uni(aspect, r=0.0):
    return [(0.0, 1.0, aspect, r, 1.0)]


# техкарты: этапы (операция, название, длина цели мм | None — как раньше, профиль, доп.)
CARDS = {
    # --- примитивы (из слитка) ---
    "rod": {"name": "Прут", "stages": [
        {"op": "draw", "name": "Вытянуть брусок", "length": 150, "parts": _uni(1.0)},
        {"op": "round", "name": "Скруглить", "length": 160, "parts": _uni(1.0, 1.0)}]},
    "wire": {"name": "Проволока", "stages": [
        {"op": "draw", "name": "Вытянуть тонкий брусок", "length": 300, "parts": _uni(1.0)},
        {"op": "round", "name": "Скруглить", "length": 340, "parts": _uni(1.0, 1.0)}]},
    "strip": {"name": "Полоса", "stages": [
        {"op": "draw", "name": "Вытянуть брусок", "length": 200, "parts": _uni(1.4)},
        {"op": "spread", "name": "Раздать в полосу", "length": 260, "parts": _uni(2.0)}]},
    "sheet": {"name": "Лист", "stages": [
        {"op": "draw", "name": "Вытянуть плиту", "length": 180, "parts": _uni(2.5)},
        {"op": "spread", "name": "Разогнать в лист", "length": 300, "parts": _uni(12.0)}]},
    # --- вещи: базовые техкарты (потолок 100%) ---
    "bracers": {"name": "Наручи", "item": True, "cap": 1.0, "stages": [
        {"op": "draw", "name": "Вытянуть в полосу", "length": 130, "parts": _uni(3.0)},
        {"op": "spread", "name": "Разогнать пластину с раструбом", "length": 200,
         "parts": [(0.0, 0.7, 22.0, 0.0, 0.95), (0.7, 1.0, 26.0, 0.0, 1.12)]},
        {"op": "punch", "name": "Пробить отверстия под ремни", "holes": [(0.12, 6.0), (0.88, 6.0)]},
        {"op": "bend", "name": "Выгнуть по руке", "bend": (0.0, 1.0, 150.0)}]},
    "belt": {"name": "Пояс", "item": True, "cap": 1.0, "stages": [
        {"op": "draw", "name": "Вытянуть полосу", "length": 330, "parts": _uni(3.0)},
        {"op": "spread", "name": "Раздать полосу и пряжку", "length": 420,
         "parts": [(0.0, 0.88, 3.0, 0.0, 0.85), (0.88, 1.0, 1.2, 0.0, 2.1)]},
        {"op": "punch", "name": "Пробить дырки под язычок", "holes": [(0.55, 4.0), (0.63, 4.0), (0.71, 4.0)]},
        {"op": "bend", "name": "Загнуть пряжку", "bend": (0.88, 1.0, 180.0)}]},
    "ring": {"name": "Кольцо", "item": True, "cap": 1.0, "stages": [
        {"op": "draw", "name": "Вытянуть прутик", "length": 70, "parts": _uni(1.0)},
        {"op": "round", "name": "Скруглить", "length": 80, "parts": _uni(1.0, 1.0)},
        {"op": "bend", "name": "Свернуть в кольцо", "bend": (0.0, 1.0, 360.0)}]},
    "amulet": {"name": "Амулет", "item": True, "cap": 1.0, "stages": [
        {"op": "upset", "name": "Осадить конец под диск", "length": 120,
         "parts": [(0.0, 0.45, 1.0, 0.0, 0.5), (0.45, 1.0, 1.0, 0.0, 1.4)]},
        {"op": "spread", "name": "Разогнать диск, вытянуть хвост", "length": 150,
         "parts": [(0.0, 0.3, 1.0, 1.0, 0.35), (0.3, 1.0, 5.0, 0.0, 1.28)]},
        {"op": "punch", "name": "Пробить глазок", "holes": [(0.65, 5.0)]},
        {"op": "bend", "name": "Свернуть петлю", "bend": (0.0, 0.3, 300.0)}]},
}
# техкарты мастера (книги): лишний этап на чистоту формы, потолок 130%
for _k, _b in BOOK_CARDS.items():
    _st = [dict(s) for s in CARDS[_k]["stages"]]
    _shape = max(i for i, s in enumerate(_st) if s.get("parts"))
    _st.insert(_shape + 1, {"op": "spread" if _st[_shape]["op"] != "round" else "round",
                            "name": "Доводка формы (гладилка)", "length": None, "parts": _st[_shape]["parts"],
                            "length_of": _shape})
    CARDS[_k + "_master"] = {"name": CARDS[_k]["name"] + " — техкарта мастера", "item": True, "cap": 1.3,
                             "book": _b, "stages": _st}
    CARDS[_k]["master"] = _k + "_master"


def card_for(kind, tools=()):
    """Техкарта вещи/примитива: мастерская — если есть книга."""
    c = CARDS[kind]
    m = c.get("master")
    return m if m and CARDS[m]["book"] in tools else kind


def heat_window(op, alloy):
    """Окно жара этапа (°C) по рабочему диапазону металла."""
    lo, hi = alloy["work"]
    a, b = OPS[op][2]
    span = hi - lo
    return lo + a * span, lo + b * span


class StageTarget(FB.Target):
    """Цель этапа: профиль (как у FB.Target), объём — по бруску."""

    def __init__(self, length, parts, volume):
        self.kind, self.item, self.mass = "stage", False, volume / FB.MM3_PER_G
        self.length, self.parts = float(length), parts
        self.a0 = volume / self.length / sum((u1 - u0) * k for u0, u1, _, _, k in parts)


# ---------- брусок с гибкой и отверстиями ----------

class CardBar(FB.Bar):
    """Брусок техкарты: + угол гибки на станции (градусы), отверстия (по доле объёма от левого конца — так они
    едут вместе с металлом при протяжке)."""

    def __init__(self, mass_g, n=12):
        super().__init__(mass_g, n)
        self.ang = np.zeros(n)
        self.holes = []                          # [{"m": доля объёма, "d": мм, "depth": 0–1, "rough": бородком}]

    def refine(self):
        for _ in range(6):
            long = np.nonzero(self.dx > FB.DXMAX)[0]
            if not len(long) or len(self.dx) > 400:
                return
            for arr in ("w", "t", "r"):
                a = getattr(self, arr)
                setattr(self, arr, np.insert(a, long + 1, a[long]))
            self.ang[long] /= 2
            self.ang = np.insert(self.ang, long + 1, self.ang[long])
            self.dx[long] /= 2
            self.dx = np.insert(self.dx, long + 1, self.dx[long])

    def x_of_m(self, m):
        """Координата (мм) по доле объёма от левого конца."""
        cv = np.concatenate([[0.0], np.cumsum(self.area() * self.dx)])
        cx = np.concatenate([[0.0], np.cumsum(self.dx)])
        return float(np.interp(m * cv[-1], cv, cx))

    def m_of_x(self, x):
        cv = np.concatenate([[0.0], np.cumsum(self.area() * self.dx)])
        cx = np.concatenate([[0.0], np.cumsum(self.dx)])
        return float(np.interp(x, cx, cv) / cv[-1])

    # ----- разгонка -----

    def spread(self, x, power, hammer="hand"):
        """Разгонка (удар плашмя, клином/бойком поперёк): металл уходит вширь, длина почти не растёт.
        → доля сжатия."""
        c0, hx = FB.HAMMERS[hammer]
        hx = max(hx, 8.0)
        cen = self.centers()
        c = np.clip(c0 * power * np.exp(-(np.abs(cen - x) / hx) ** 4), 0, 0.5)
        if not (c > 0.005).any():
            return 0.0
        a0 = self.area()
        self.t = self.t * (1 - c)
        self.w = self.w * (1 - c) ** -0.85                      # 85% — вширь, остальное — в длину
        self.r = self.r * (1 - 2.5 * c)
        self.dx *= a0 / self.area()
        self.refine()
        return float(c.max())

    # ----- осадка -----

    def upset(self, end, power):
        """Удар в торец (end: 0 — левый, 1 — правый): металл у конца садится — короче и толще (объём тот же).
        → доля осадки."""
        cen = self.centers()
        L = self.length()
        d = cen if end == 0 else L - cen
        reach = 2.2 * float(np.sqrt(self.w * self.t).mean())
        k = np.clip(0.22 * power * np.exp(-(d / reach) ** 2), 0, 0.4)
        if not (k > 0.003).any():
            return 0.0
        s = 1 / np.sqrt(1 - k)                   # длина ×(1−k) — сечение ×1/(1−k)
        self.dx *= (1 - k)
        self.w *= s
        self.t *= s
        self.r *= (1 - 0.5 * k)
        return float(k.max())

    # ----- гибка -----

    def bend(self, x, dang, reach):
        """Догнуть на dang градусов у рога в точке x (мм): угол раскладывается на станции в пределах reach."""
        cen = self.centers()
        wgt = np.exp(-((cen - x) / max(1.0, reach)) ** 2)
        if wgt.sum() < 1e-6:
            return
        self.ang += dang * wgt / wgt.sum()

    def path(self):
        """Средняя линия согнутого бруска (вид сбоку): точки станций (x, y) от левого конца, вдоль — x."""
        h = np.cumsum(np.radians(self.ang)) - np.radians(self.ang) / 2
        dx = self.dx
        x = np.cumsum(dx * np.cos(h)) - dx * np.cos(h) / 2
        y = np.cumsum(dx * np.sin(h)) - dx * np.sin(h) / 2
        return x, y, h

    # ----- пробивка -----

    def punch(self, x, d, power, rough=False):
        """Удар пробойником в точку x: отверстие углубляется; сквозное — металл чуть раздаётся вокруг.
        → глубина отверстия."""
        m = self.m_of_x(x)
        tol = d / max(1.0, self.length())
        h = next((h for h in self.holes if abs(h["m"] - m) < tol * 0.6), None)
        if h is None:
            h = {"m": m, "d": d, "depth": 0.0, "rough": rough}
            self.holes.append(h)
        th = float(np.interp(x, self.centers(), self.t))
        h["depth"] = min(1.0, h["depth"] + 0.45 * power * 6.0 / max(3.0, th))
        if rough:                                  # бородком: отверстие гуляет и рвётся
            h["d"] = max(h["d"], d * (1.0 + 0.25 * power))
        return h["depth"]


# ---------- оценка этапов ----------

def stage_target(stage, bar, card_stages=None):
    """Цель этапа формы (StageTarget) или None (гибка, пробивка)."""
    if not stage.get("parts"):
        return None
    L = stage.get("length")
    if L is None and card_stages is not None:
        L = card_stages[stage["length_of"]]["length"]
    return StageTarget(L, stage["parts"], bar.volume())


def holes_score(bar, holes):
    """Отверстия по меткам: сквозные, на месте (доля длины), нужного диаметра; лишние — минус."""
    if not holes:
        return 1.0
    L = bar.length()
    made = [h for h in bar.holes if h["depth"] >= 1.0]
    got = 0.0
    used = set()
    for u, d in holes:
        best, bi = 0.0, None
        for i, h in enumerate(made):
            if i in used:
                continue
            err = abs(bar.x_of_m(h["m"]) / L - u) * L                     # мм
            s = max(0.0, 1 - err / 8.0) * max(0.0, 1 - abs(h["d"] - d) / d) * (0.8 if h["rough"] else 1.0)
            if s > best:
                best, bi = s, i
        if bi is not None:
            used.add(bi)
        got += best
    extra = len(made) - len(used)
    return max(0.0, got / len(holes) - 0.15 * extra)


def bend_score(bar, bend):
    """Гибка: угол на нужном участке (доли длины), ровность дуги и прямота остального."""
    if not bend:
        return 1.0
    u0, u1, deg = bend
    u = bar.centers() / max(1e-6, bar.length())
    inside = (u >= u0 - 0.02) & (u <= u1 + 0.02)
    total = float(bar.ang[inside].sum())
    s_ang = max(0.0, 1 - abs(total - deg) / deg)
    seg = bar.ang[inside] / np.maximum(bar.dx[inside], 1e-6)          # кривизна: ровная дуга — одинаковая
    even = 1.0 - min(1.0, float(np.std(seg) / (abs(np.mean(seg)) + 1e-6)) * 0.5) if inside.sum() > 2 else 1.0
    out = float(np.abs(bar.ang[~inside]).sum())
    s_out = max(0.0, 1 - out / max(30.0, deg))
    return max(0.0, s_ang * (0.8 + 0.2 * even) * s_out) if total > 0 else 0.0     # гнули не там — мимо


def stage_score(stage, bar, card_stages=None):
    """Оценка этапа 0–1 по его цели."""
    if stage["op"] == "punch":
        return holes_score(bar, stage["holes"])
    if stage["op"] == "bend":
        return bend_score(bar, stage["bend"])
    tgt = stage_target(stage, bar, card_stages)
    return bar.score(tgt) if tgt is not None else 1.0


def final_score(card_key, bar, stage_scores, cracks=0, burn=0.0):
    """Итог ковки 0–1: 75% — готовая форма (последняя форма, гибка, отверстия), 25% — аккуратность этапов."""
    st = CARDS[card_key]["stages"]
    parts = []
    shape = [s for s in st if s.get("parts")]
    if shape:
        parts.append(FB.forged_score(bar.score(stage_target(shape[-1], bar, st))))
    for s in st:
        if s["op"] == "punch":
            parts.append(holes_score(bar, s["holes"]))
        elif s["op"] == "bend":
            parts.append(bend_score(bar, s["bend"]))
    form = sum(parts) / len(parts) if parts else 0.0
    neat = sum(stage_scores) / len(stage_scores) if stage_scores else form
    return round(max(0.0, min(1.0, 0.75 * form + 0.25 * neat)) * (0.85 ** cracks) * (1 - burn), 3)
