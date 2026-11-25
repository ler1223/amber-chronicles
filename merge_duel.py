"""«Сплав» — мини-игра: карточные соты 6×6, силы и слияния.

Игрок выкладывает карты из руки на свободные соты. Перемещать уже
выложенные карты нельзя. Конец хода — одна итерация движения по силам;
после неё срабатывают эффекты карт и ход врага. Слитые карты сохраняют
цвета и части обеих карт.

Запуск: python merge_duel.py
"""
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field

import pygame

BOARD = 6
HAND_MAX = 5
START_HP = 42
COLORS = ("red", "yellow", "blue")
# Направления в осевых координатах для шестиугольной доски.
HEX_DIRS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
COLOR_NAME = {"red": "Красный", "yellow": "Жёлтый", "blue": "Синий"}
COLOR_RGB = {"red": (206, 72, 64), "yellow": (226, 184, 66), "blue": (72, 126, 210)}
COLOR_DARK = {"red": (70, 24, 22), "yellow": (74, 58, 20), "blue": (24, 42, 76)}
MIX_NAME = {
    frozenset(("red",)): "Алая искра",
    frozenset(("yellow",)): "Жёлтая искра",
    frozenset(("blue",)): "Синяя искра",
    frozenset(("red", "yellow")): "Огненный сплав",
    frozenset(("red", "blue")): "Пурпурный сплав",
    frozenset(("yellow", "blue")): "Зелёный сплав",
    frozenset(COLORS): "Радужный сплав",
}


@dataclass
class Card:
    uid: int
    colors: tuple[str, ...]
    level: int = 1
    parts: tuple[str, ...] = ()

    @property
    def name(self):
        return f"{MIX_NAME.get(frozenset(self.colors), 'Сплав')} {self.level}"

    def effect_lines(self):
        out, has = [], set(self.colors)
        p = 3 + self.level * 2
        if "red" in has:
            out.append(f"Урон {p}")
        if "blue" in has:
            out.append(f"Защита {p}")
        if "yellow" in has:
            out.append("Взять 1 карту")
        if {"red", "yellow"} <= has:
            out.append(f"Горение {self.level + 1}")
        if {"red", "blue"} <= has:
            out.append("Уязвимость 1")
        if {"yellow", "blue"} <= has:
            out.append("+1 карта")
        if len(has) == 3:
            out.append("Тройной эффект")
        return out

    def force_threshold(self):
        return len(self.colors)


@dataclass
class Enemy:
    name: str
    max_hp: int
    hp: int
    intent: str = "attack"
    intent_value: int = 4
    passive: str = ""
    strength: int = 0
    shield: int = 0
    burn: int = 0
    vulnerable: int = 0

    def choose_intent(self, run):
        run._intent()

    def intent_text(self):
        return {"attack": f"Атака {self.intent_value + self.strength}",
                "defend": f"Защита {self.intent_value}",
                "buff": f"Ярость +{self.intent_value}"}.get(self.intent, self.intent)

    def passive_text(self):
        return self.passive or "Без пассивки"


@dataclass
class ShiftAnimation:
    """Визуальный сдвиг: старые карты едут к целям, модель пока не меняется."""
    cards: list[tuple[Card, tuple[int, int], tuple[int, int]]]
    duration: float = 0.42
    elapsed: float = 0.0

    @property
    def progress(self):
        return min(1.0, max(0.0, self.elapsed / self.duration))

    @property
    def finished(self):
        return self.elapsed >= self.duration


@dataclass
class MergeAnimation:
    """Схождение двух соседних карт в одну с золотой вспышкой."""
    groups: list[tuple[list[tuple[Card, tuple[int, int]]], Card, tuple[int, int]]]
    duration: float = 0.55
    elapsed: float = 0.0

    @property
    def progress(self):
        return min(1.0, max(0.0, self.elapsed / self.duration))

    @property
    def finished(self):
        return self.elapsed >= self.duration


@dataclass
class MergeRun:
    seed: int | None = None
    player_hp: int = START_HP
    max_hp: int = START_HP
    block: int = 0
    hand: list[Card] = field(default_factory=list)
    board: dict[tuple[int, int], Card] = field(default_factory=dict)
    wave: int = 1
    turn: int = 0
    rng: random.Random = field(init=False)
    affinity: dict[tuple[str, str], int] = field(init=False)
    enemy: Enemy = field(init=False)
    log: list[str] = field(default_factory=list)
    over: bool = False
    _uid: int = 0

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        self.affinity = self._make_affinity()
        self.enemy = self._make_enemy()
        self.draw(HAND_MAX)
        self.start_player_turn()

    def _make_affinity(self):
        out = {}
        for i, a in enumerate(COLORS):
            for b in COLORS[i:]:
                out[tuple(sorted((a, b)))] = self.rng.choice([-2, -1, 0, 1, 2, 3])
        if not any(v > 1 for v in out.values()):
            out[("red", "red")] = 2
        return out

    def _make_enemy(self):
        names = ("Слизень", "Пепельный пёс", "Страж развилки", "Красный мим", "Багровый жрец")
        hp = 22 + self.wave * 9
        passive = ""
        if self.wave >= 2:
            passive = self.rng.choice(("Регенерация 2", "Шипы 2", "Броня 1", "Ярость 1"))
        return Enemy(names[(self.wave - 1) % len(names)], hp, hp, passive=passive)

    def new_card(self, colors, level=1, parts=()):
        self._uid += 1
        return Card(self._uid, tuple(c for c in COLORS if c in colors), level, tuple(parts))

    def draw(self, n):
        for _ in range(n):
            if len(self.hand) >= HAND_MAX:
                return
            self.hand.append(self.new_card((self.rng.choice(COLORS),)))

    # ---------- размещение ----------
    def place(self, hand_index, cell):
        if self.over or not (0 <= cell[0] < BOARD and 0 <= cell[1] < BOARD):
            return ["Нельзя поставить сюда"]
        if hand_index < 0 or hand_index >= len(self.hand):
            return ["Нет такой карты"]
        if cell in self.board:
            return ["Клетка занята"]
        card = self.hand.pop(hand_index)
        self.board[cell] = card
        self.log.append(f"Выложена: {card.name} → {cell}")
        return [f"Выложена: {card.name}"]

    # ---------- силы и шестиугольная геометрия ----------
    @staticmethod
    def to_axial(cell):
        """Смещённые координаты (col,row) → осевые (q,row)."""
        col, row = cell
        return col - (row - (row & 1)) // 2, row

    @staticmethod
    def from_axial(q, row):
        """Осевые (q,row) → смещённые координаты (col,row)."""
        return q + (row - (row & 1)) // 2, row

    def distance(self, a, b):
        """Расстояние между сотами по шести направлениям."""
        aq, ar = self.to_axial(a)
        bq, br = self.to_axial(b)
        dq, dr = bq - aq, br - ar
        ds = -dq - dr
        return (abs(dq) + abs(dr) + abs(ds)) // 2

    def pair_force(self, a: Card, b: Card):
        """Базовая сила пары: среднее по цветам плюс уровни обеих карт."""
        vals = [self.affinity[tuple(sorted((x, y)))] for x in a.colors for y in b.colors]
        return sum(vals) / max(1, len(vals)) + a.level + b.level

    def force_at(self, pos_a, pos_b):
        """Влияние на расстоянии: каждая сота пути стоит 1 единицу силы.

        Положительная сила (притяжение) и отрицательная (отталкивание)
        ослабевают по модулю. За пределами дальности влияния силы нет.
        """
        a, b = self.board[pos_a], self.board[pos_b]
        base = self.pair_force(a, b)
        d = self.distance(pos_a, pos_b)
        if base > 0:
            return max(0.0, base - d)
        if base < 0:
            return min(0.0, base + d)
        return 0.0

    def merge(self, pos_a, pos_b):
        a, b = self.board[pos_a], self.board[pos_b]
        colors = tuple(c for c in COLORS if c in set(a.colors) | set(b.colors))
        parts = a.parts + b.parts + (a.name, b.name)
        merged = self.new_card(colors, max(a.level, b.level) + 1, parts)
        self.board[pos_a] = merged
        self.board.pop(pos_b, None)
        self.log.append(f"{a.name} + {b.name} → {merged.name}")
        return merged

    # ---------- ход ----------
    def start_player_turn(self):
        if self.over:
            return []
        self.turn += 1
        self.block = 0
        self.draw(HAND_MAX - len(self.hand))
        self.enemy.choose_intent(self)
        return []

    def movement_intents(self):
        """Куда каждая карта хочет шагнуть по итоговой силе (без занятости)."""
        intents = {}
        for pos, card in self.board.items():
            q, r = self.to_axial(pos)
            vx = vy = 0.0
            for other_pos, other in self.board.items():
                if other_pos == pos:
                    continue
                f = self.force_at(pos, other_pos)
                if f == 0:
                    continue
                oq, orow = self.to_axial(other_pos)
                dx = (oq - q) + (orow - r) * 0.5
                dy = (orow - r) * (math.sqrt(3) / 2)
                length = math.hypot(dx, dy)
                if length == 0:
                    continue
                sign = 1.0 if f > 0 else -1.0
                vx += sign * dx / length
                vy += sign * dy / length
            if vx == 0 and vy == 0:
                continue
            best = None
            for dq, dr in HEX_DIRS:
                # Вектор направления в тех же «пиксельных» осях, что и dx/dy.
                nx = dq + dr * 0.5
                ny = dr * (math.sqrt(3) / 2)
                score = vx * nx + vy * ny
                if best is None or score > best[0]:
                    best = (score, dq, dr)
            if best is None:
                continue
            _, dq, dr = best
            target = self.from_axial(q + dq, r + dr)
            if target != pos:
                intents[pos] = target
        return intents

    def movement_targets(self, intents=None):
        """Куда сдвинется каждая карта за одну итерацию (без применения)."""
        intents = intents if intents is not None else self.movement_intents()
        occupied = set(self.board)
        moves = {}
        for pos, target in intents.items():
            if target == pos:
                continue
            if not (0 <= target[0] < BOARD and 0 <= target[1] < BOARD):
                continue
            if target in occupied:
                continue
            moves[pos] = target
            occupied.discard(pos)
            occupied.add(target)
        return moves

    def move_iteration(self):
        """Одна итерация: каждая карта делает не больше одного шага."""
        moves = self.movement_targets()
        for src, dst in moves.items():
            self.board[dst] = self.board.pop(src)
        return bool(moves)

    def neighbor_cells(self, cell):
        q, r = self.to_axial(cell)
        out = []
        for dq, dr in HEX_DIRS:
            nb = self.from_axial(q + dq, r + dr)
            if 0 <= nb[0] < BOARD and 0 <= nb[1] < BOARD:
                out.append(nb)
        return out

    def adjacent_merge_preview(self):
        """Соседние пары, которые сольются: взаимные намерения и сила."""
        return self.merge_candidates()

    def merge_candidates(self, intents=None, old_positions=None):
        """Какие соседние пары сольются; возвращает пары без мутации доски."""
        if not self.board:
            return []
        intents = intents if intents is not None else self.movement_intents()
        if old_positions is None:
            old_positions = {id(card): pos for pos, card in self.board.items()}

        candidates = []
        seen = set()
        for pos, card in self.board.items():
            for other_pos in self.neighbor_cells(pos):
                other = self.board.get(other_pos)
                if other is None:
                    continue
                pair = tuple(sorted((pos, other_pos)))
                if pair in seen:
                    continue
                seen.add(pair)
                old_a = old_positions.get(id(card))
                old_b = old_positions.get(id(other))
                if old_a is None or old_b is None:
                    continue
                target_a = intents.get(old_a)
                target_b = intents.get(old_b)
                if target_a is None or target_b is None:
                    continue
                # Обе хотят сократить дистанцию до другой карты.
                if not (self.distance(target_a, old_b) < self.distance(old_a, old_b)):
                    continue
                if not (self.distance(target_b, old_a) < self.distance(old_b, old_a)):
                    continue
                force = self.force_at(pos, other_pos)
                if force > max(card.force_threshold(), other.force_threshold()):
                    candidates.append((force, pos, other_pos))

        # Пары могут делить карту — сначала самые сильные.
        selected = []
        used = set()
        for force, pos_a, pos_b in sorted(candidates, key=lambda x: x[0], reverse=True):
            a = self.board.get(pos_a)
            b = self.board.get(pos_b)
            if a is None or b is None or id(a) in used or id(b) in used:
                continue
            selected.append((pos_a, pos_b))
            used.add(id(a))
            used.add(id(b))
        return selected

    def apply_merges(self, pairs):
        events = []
        for pos_a, pos_b in pairs:
            if pos_a not in self.board or pos_b not in self.board:
                continue
            merged = self.merge(pos_a, pos_b)
            events.append(merged.name)
        return events

    def merge_moving(self, intents=None, old_positions=None):
        """Слить соседние карты, намеренные двигаться друг в друга."""
        return self.apply_merges(self.merge_candidates(intents, old_positions))

    def apply_moves(self, moves):
        for src, dst in moves.items():
            self.board[dst] = self.board.pop(src)
        return bool(moves)

    def move_and_merge(self):
        """Фаза движения: один шаг и слияния соседних встречных карт."""
        if not self.board:
            return []
        intents = self.movement_intents()
        old_positions = {id(card): pos for pos, card in self.board.items()}
        moves = self.movement_targets(intents)
        if self.apply_moves(moves):
            events = ["Одна итерация движения"]
        else:
            events = []
        events += self.merge_moving(intents, old_positions)
        return events

    def pulse_card(self, card):
        """Срабатывание одной карты; возвращает события для журнала."""
        events = []
        has = set(card.colors)
        lv = card.level
        if "red" in has:
            dmg = 3 + lv * 2
            if self.enemy.vulnerable:
                dmg = int(dmg * 1.5)
            if "броня" in self.enemy.passive.lower():
                dmg = max(0, dmg - 1)
            if self.enemy.shield:
                a = min(self.enemy.shield, dmg)
                self.enemy.shield -= a
                dmg -= a
            self.enemy.hp -= dmg
            events.append(f"Урон {dmg}")
            if "шипы" in self.enemy.passive.lower():
                self.player_hp -= 2
                events.append("Шипы −2")
        if "blue" in has:
            self.block += 3 + lv * 2
        if "yellow" in has:
            self.draw(1)
        if {"red", "yellow"} <= has:
            self.enemy.burn += lv + 1
        if {"red", "blue"} <= has:
            self.enemy.vulnerable = max(self.enemy.vulnerable, 1)
        if len(has) == 3:
            self.draw(1)
        return events

    def pulse(self):
        """Все карты на доске срабатывают один раз."""
        events = []
        for pos in list(self.board):
            c = self.board.get(pos)
            if c is not None:
                events += self.pulse_card(c)
        return events

    def play_order(self):
        """Порядок разыгрывания: сверху вниз, затем слева направо."""
        return sorted(self.board, key=lambda cell: (cell[1], cell[0]))

    def play_card_at(self, pos):
        """Разыграть одну карту из конкретной соты."""
        if self.over:
            return []
        card = self.board.get(pos)
        if card is None:
            return []
        events = [f"Разыграна: {card.name}"]
        events += self.pulse_card(card)
        if self.player_hp <= 0:
            self.player_hp = 0
            self.over = True
            events.append("Поражение")
            return events
        if self.enemy.hp <= 0:
            events.append(f"{self.enemy.name} повержен")
            self._next_wave()
        return events

    def play_cards(self):
        """Фаза разыгрывания: карты срабатывают по одной в порядке доски."""
        if self.over:
            return []
        events = []
        wave_before = self.wave
        for pos in self.play_order():
            if self.over or self.wave != wave_before:
                break
            events += self.play_card_at(pos)
        return events

    def enemy_turn(self):
        """Фаза врага: горение, пассивка, намерение и новая волна при победе."""
        if self.over:
            return []
        events = []
        e = self.enemy
        if e.hp <= 0:
            self._next_wave()
            return events
        if e.burn:
            e.hp -= e.burn
            events.append(f"Горение: {e.burn}")
            e.burn = max(0, e.burn - 1)
        if "регенерация" in e.passive.lower():
            e.hp = min(e.max_hp, e.hp + 2)
        if "ярость" in e.passive.lower():
            e.strength += 1
        if e.hp <= 0:
            self._next_wave()
            return events
        if e.intent == "attack":
            dmg = max(0, e.intent_value + e.strength - self.block)
            self.player_hp -= dmg
            events.append(f"Враг атакует: {dmg}")
        elif e.intent == "defend":
            e.shield += e.intent_value
        else:
            e.strength += e.intent_value
        if e.vulnerable:
            e.vulnerable = max(0, e.vulnerable - 1)
        if self.player_hp <= 0:
            self.player_hp = 0
            self.over = True
            events.append("Поражение")
        elif e.hp <= 0:
            self._next_wave()
        else:
            self.start_player_turn()
        return events

    def end_turn(self):
        """Полный ход: движение → слияния → разыгрывание карт → враг."""
        if self.over:
            return []
        events = self.move_and_merge()
        wave_before = self.wave
        events += self.play_cards()
        if self.over or self.wave != wave_before:
            self.log.extend(events)
            return events
        events += self.enemy_turn()
        self.log.extend(events)
        return events

    def _intent(self):
        e = self.enemy
        e.intent = self.rng.choice(("attack", "attack", "defend", "buff"))
        e.intent_value = 4 + self.wave * 2 if e.intent == "attack" else \
            4 + self.wave if e.intent == "defend" else 1 + self.wave // 2

    def _next_wave(self):
        self.wave += 1
        self.player_hp = min(self.max_hp, self.player_hp + 7)
        self.enemy = self._make_enemy()
        self.log.append(f"Волна {self.wave}: {self.enemy.name}")
        self.start_player_turn()


# ---------- экран ----------
class MergeDuelApp:
    W, H = 1280, 800
    HEX_SIZE = 40
    HEX_W = math.sqrt(3) * HEX_SIZE
    HEX_H = 1.5 * HEX_SIZE
    CARD_W, CARD_H = 126, 188

    def __init__(self, seed=None):
        pygame.init()
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("Сплав — карточные соты")
        self.clock = pygame.time.Clock()
        self._fonts = {}
        self.seed = seed
        self.run = MergeRun(seed)
        self.mouse = (0, 0)
        self.selected = None
        self.anim: ShiftAnimation | None = None
        self.merge_anim: MergeAnimation | None = None
        self.phase = "place"
        self.phase_timer = 0.0
        self._wave_before_play = 0
        self._pending_intents = {}
        self._pending_old_positions = {}
        self._pending_moves = {}
        self.play_queue: list[tuple[int, int]] = []
        self.play_index = 0
        self.play_active = None
        self.play_stopped = False
        self.play_wave_before = 0
        self.toast, self.toast_t = "", 0.0
        self.end_rect = pygame.Rect(self.W - 230, self.H - 68, 200, 46)
        self.restart_rect = pygame.Rect(self.W - 230, self.H - 118, 200, 38)
        self.board_x = int((self.W - (BOARD * self.HEX_W + self.HEX_W / 2)) // 2)
        self.board_y = 150

    def _font(self, size, bold=False):
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
            self._fonts[key] = f
        return f

    def text(self, s, pos, col=(220, 225, 235), size=16, bold=False, center=False):
        img = self._font(size, bold).render(s, True, col)
        if center:
            pos = (pos[0] - img.get_width() // 2, pos[1] - img.get_height() // 2)
        self.screen.blit(img, pos)

    def hex_center(self, cell):
        col, row = cell
        return (self.board_x + col * self.HEX_W + (row & 1) * self.HEX_W / 2,
                self.board_y + row * self.HEX_H)

    def hex_points_at(self, center, radius):
        cx, cy = center
        return [
            (cx + math.cos(math.radians(a)) * radius,
             cy + math.sin(math.radians(a)) * radius)
            for a in (-90, -30, 30, 90, 150, 210)
        ]

    def hex_points(self, cell, inset=0):
        return self.hex_points_at(self.hex_center(cell), self.HEX_SIZE - inset)

    @staticmethod
    def point_in_polygon(point, polygon):
        x, y = point
        inside = False
        j = len(polygon) - 1
        for i, (xi, yi) in enumerate(polygon):
            xj, yj = polygon[j]
            if (yi > y) != (yj > y):
                if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    inside = not inside
            j = i
        return inside

    def board_cell_at(self, pos):
        for row in range(BOARD):
            for col in range(BOARD):
                if self.point_in_polygon(pos, self.hex_points((col, row))):
                    return col, row
        return None

    def hand_rects(self):
        n = len(self.run.hand)
        gap = 8
        total = n * self.CARD_W + max(0, n - 1) * gap
        x = (self.W - total) // 2
        y = 548
        return [(pygame.Rect(x + i * (self.CARD_W + gap), y, self.CARD_W, self.CARD_H), c, i)
                for i, c in enumerate(self.run.hand)]

    def hand_at(self, pos):
        for r, c, i in self.hand_rects():
            if r.collidepoint(pos):
                return i
        return None

    def flash(self, events):
        if events:
            self.toast = " · ".join(events[-2:])
            self.toast_t = 2.8

    def start_turn_resolution(self):
        """Начать ход: сдвиг, слияние, поочерёдное разыгрывание, враг."""
        if self.anim is not None or self.merge_anim is not None or self.run.over or self.phase != "place":
            return
        if not self.run.board:
            self.flash(["Сначала выложите карты в соты"])
            return
        self.selected = None
        self.phase = "move"
        self._pending_intents = self.run.movement_intents()
        self._pending_old_positions = {id(card): pos for pos, card in self.run.board.items()}
        self._pending_moves = self.run.movement_targets(self._pending_intents)
        if self._pending_moves:
            self.anim = ShiftAnimation([
                (card, pos, self._pending_moves.get(pos, pos))
                for pos, card in self.run.board.items()
            ])
        else:
            self.finish_move_phase()

    def finish_move_phase(self):
        """Закончить сдвиг: применить его и запустить анимацию слияний."""
        self.anim = None
        moved = self.run.apply_moves(self._pending_moves)
        if moved:
            self.run.log.append("Одна итерация движения")
        self._pending_moves = {}
        pairs = self.run.merge_candidates(self._pending_intents, self._pending_old_positions)
        if pairs:
            groups = []
            for pos_a, pos_b in pairs:
                a = self.run.board.get(pos_a)
                b = self.run.board.get(pos_b)
                if a is None or b is None:
                    continue
                sources = [(a, pos_a), (b, pos_b)]
                merged = self.run.merge(pos_a, pos_b)
                groups.append((sources, merged, pos_a))
            if groups:
                self.merge_anim = MergeAnimation(groups)
                self.phase = "merge"
                self.phase_timer = 0.0
                return
        self.start_play_phase()

    def finish_merge_phase(self):
        self.merge_anim = None
        self.start_play_phase()

    def start_play_phase(self):
        """Фаза 3: карты разыгрываются по одной, а не одновременно."""
        self.phase = "effects"
        self.play_queue = self.run.play_order()
        self.play_index = 0
        self.play_active = None
        self.play_stopped = False
        self.play_wave_before = self.run.wave
        self.phase_timer = 0.0
        self.next_play_card()

    def next_play_card(self):
        if self.run.over or self.play_stopped or self.run.wave != self.play_wave_before:
            self.phase = "place"
            self.phase_timer = 0.0
            return
        while self.play_index < len(self.play_queue):
            pos = self.play_queue[self.play_index]
            self.play_index += 1
            if pos not in self.run.board:
                continue
            self.play_active = pos
            events = self.run.play_card_at(pos)
            self.run.log.extend(events)
            self.flash(events)
            if self.run.over or self.run.wave != self.play_wave_before:
                self.play_stopped = True
            self.phase_timer = 0.45
            return
        self.start_enemy_phase()

    def start_enemy_phase(self):
        self.play_active = None
        self.phase = "enemy"
        self.phase_timer = 0.55
        events = self.run.enemy_turn()
        self.run.log.extend(events)
        self.flash(events)

    def advance_phase(self):
        if self.phase == "effects":
            if self.play_stopped or self.run.over or self.run.wave != self.play_wave_before:
                self.phase = "place"
                self.phase_timer = 0.0
                self.play_active = None
            else:
                self.next_play_card()
        elif self.phase == "enemy":
            self.phase = "place"
            self.phase_timer = 0.0

    def update(self, dt):
        if self.anim is not None:
            self.anim.elapsed += dt
            if self.anim.finished:
                self.finish_move_phase()
            return
        if self.merge_anim is not None:
            self.merge_anim.elapsed += dt
            if self.merge_anim.finished:
                self.finish_merge_phase()
            return
        if self.phase_timer > 0:
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.phase_timer = 0.0
                self.advance_phase()

    def reset_run(self):
        self.anim = None
        self.merge_anim = None
        self.phase = "place"
        self.phase_timer = 0.0
        self._pending_intents = {}
        self._pending_old_positions = {}
        self._pending_moves = {}
        self.play_queue = []
        self.play_index = 0
        self.play_active = None
        self.play_stopped = False
        self.run = MergeRun(self.seed)
        self.selected = None
        self.toast, self.toast_t = "", 0.0

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            return False
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_r:
            self.reset_run()
            return True
        if self.anim is not None:
            return True
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_SPACE:
                self.start_turn_resolution()
            return True
        if self.phase != "place":
            return True
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            return True
        if ev.type != pygame.MOUSEBUTTONDOWN or ev.button != 1:
            return True
        self.mouse = ev.pos
        if self.restart_rect.collidepoint(ev.pos):
            self.reset_run()
            return True
        if self.end_rect.collidepoint(ev.pos):
            self.start_turn_resolution()
            return True
        i = self.hand_at(ev.pos)
        if i is not None:
            self.selected = i if self.selected != i else None
            return True
        cell = self.board_cell_at(ev.pos)
        if cell is not None:
            if self.selected is None:
                self.flash(["Сначала выберите карту в руке"])
            else:
                events = self.run.place(self.selected, cell)
                self.flash(events)
                self.selected = None
        return True

    def draw(self, dt=1 / 60):
        s = self.screen
        s.fill((13, 15, 20))
        self.text("СПЛАВ · 6×6 СОТЫ", (self.W // 2, 27), (255, 205, 110), 30, True, True)
        self.text(f"Волна {self.run.wave} · ход {self.run.turn}", (self.W // 2, 57), (150, 155, 165), 14, center=True)
        self.player_panel()
        self.enemy_panel()
        self.affinity_panel()
        self.phase_panel()
        self.log_view()
        self.board_view()
        self.hand_view()
        self.bottom_view()
        self.card_tooltip()
        if self.toast_t > 0:
            self.toast_t -= dt
            self.text(self.toast, (self.W // 2, 92), (255, 225, 150), 16, center=True)
        if self.run.over:
            shade = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 180))
            s.blit(shade, (0, 0))
            self.text("Забег окончен", (self.W // 2, 300), (255, 120, 100), 30, True, True)
            self.text("R — новый забег", (self.W // 2, 346), (240, 220, 180), 17, center=True)

    def player_panel(self):
        r = pygame.Rect(24, 24, 290, 116)
        pygame.draw.rect(self.screen, (28, 31, 38), r, border_radius=8)
        pygame.draw.rect(self.screen, (90, 115, 155), r, 1, border_radius=8)
        self.text("Игрок", (r.x + 14, r.y + 10), (220, 225, 235), 20)
        self.text(f"HP {self.run.player_hp}/{self.run.max_hp}", (r.x + 14, r.y + 38), (235, 150, 140), 18)
        self.text(f"Защита {self.run.block}", (r.x + 14, r.y + 64), (150, 190, 240), 16)
        self.text("Клик по карте → клик по соте", (r.x + 14, r.y + 88), (160, 165, 180), 13)

    def enemy_panel(self):
        e = self.run.enemy
        r = pygame.Rect(self.W - 330, 24, 306, 150)
        pygame.draw.rect(self.screen, (36, 27, 30), r, border_radius=8)
        pygame.draw.rect(self.screen, (170, 90, 85), r, 1, border_radius=8)
        self.text(e.name, (r.x + 14, r.y + 10), (245, 185, 165), 20)
        self.text(f"HP {max(0, e.hp)}/{e.max_hp}", (r.x + 14, r.y + 38), (235, 150, 140), 17)
        self.text(f"Намерение: {e.intent_text()}", (r.x + 14, r.y + 62), (255, 220, 135), 16)
        self.text(f"Пассивка: {e.passive_text()}", (r.x + 14, r.y + 84), (190, 195, 205), 14)
        if e.shield:
            self.text(f"Щит {e.shield}", (r.x + 14, r.y + 106), (150, 190, 240), 15)
        if e.burn:
            self.text(f"Горение {e.burn}", (r.x + 14, r.y + 126), (240, 140, 90), 15)

    def affinity_panel(self):
        r = pygame.Rect(24, 160, 290, 224)
        pygame.draw.rect(self.screen, (25, 29, 36), r, border_radius=8)
        pygame.draw.rect(self.screen, (80, 92, 110), r, 1, border_radius=8)
        self.text("Силы цветов", (r.x + 14, r.y + 10), (205, 215, 230), 18)
        self.text("сила слабеет на 1 за каждую соту", (r.x + 14, r.y + 34), (145, 155, 170), 12)
        step = 72
        x0, y0 = r.x + 90, r.y + 68
        for i, a in enumerate(COLORS):
            self.text(COLOR_NAME[a][0], (x0 + i * step, y0 - 24), COLOR_RGB[a], 17, bold=True)
            self.text(COLOR_NAME[a][0], (r.x + 22, y0 + i * 44), COLOR_RGB[a], 17, bold=True)
            for j, b in enumerate(COLORS):
                v = self.run.affinity[tuple(sorted((a, b)))]
                col = (160, 230, 160) if v > 1 else (220, 160, 130) if v < 0 else (185, 185, 195)
                self.text(f"{v:+d}", (x0 + j * step, y0 + i * 44), col, 17)
        self.text("Слияние: сила > числа цветов", (r.x + 14, r.bottom - 32), (145, 155, 170), 12)

    def phase_panel(self):
        r = pygame.Rect(24, 396, 290, 142)
        pygame.draw.rect(self.screen, (25, 29, 36), r, border_radius=8)
        pygame.draw.rect(self.screen, (95, 85, 60), r, 1, border_radius=8)
        info = {
            "place": ("1. Выкладка", "Выложите карты и нажмите «Разыграть»."),
            "move": ("2. Движение", "Одна итерация по сотам."),
            "merge": ("3. Слияние", "Соседние встречные карты соединяются."),
            "effects": ("4. Разыгрывание карт", "Карты срабатывают по одной."),
            "enemy": ("5. Ход врага", "Враг выполняет намерение."),
        }
        title, desc = info.get(self.phase, info["place"])
        if self.phase == "effects" and self.play_queue:
            desc = f"По очереди: {min(self.play_index, len(self.play_queue))}/{len(self.play_queue)}"
        self.text(title, (r.x + 14, r.y + 10), (245, 210, 130), 19, True)
        self.text(desc, (r.x + 14, r.y + 36), (180, 188, 200), 12)
        steps = (("1", "Выкладка"), ("2", "Движение"), ("3", "Слияние"),
                 ("4", "Разыгрывание"), ("5", "Враг"))
        active = {"place": 0, "move": 1, "merge": 2,
                  "effects": 3, "enemy": 4}.get(self.phase, 0)
        for i, (num, label) in enumerate(steps):
            col = (255, 225, 150) if i == active else (125, 132, 145)
            x = r.x + 14 + (i % 2) * 138
            y = r.y + 64 + (i // 2) * 24
            self.text(f"{num}. {label}", (x, y), col, 13, i == active)

    def log_view(self):
        r = pygame.Rect(self.W - 330, 190, 306, 340)
        pygame.draw.rect(self.screen, (22, 25, 32), r, border_radius=8)
        pygame.draw.rect(self.screen, (70, 78, 92), r, 1, border_radius=8)
        self.text("Журнал", (r.x + 14, r.y + 10), (200, 210, 225), 18)
        yy = r.y + 38
        for line in self.run.log[-13:]:
            if len(line) > 42:
                line = line[:39] + "…"
            self.text(line, (r.x + 14, yy), (165, 172, 185), 12)
            yy += 20

    def draw_board_card(self, card, center, radius=None):
        radius = self.HEX_SIZE if radius is None else radius
        pts = self.hex_points_at(center, radius - 5)
        col = COLOR_RGB[card.colors[0]]
        dark = COLOR_DARK[card.colors[0]]
        pygame.draw.polygon(self.screen, dark, pts)
        pygame.draw.polygon(self.screen, col, pts, 2)
        n = len(card.colors)
        start = center[0] - (n - 1) * 7
        for k, cc in enumerate(card.colors):
            pygame.draw.circle(self.screen, COLOR_RGB[cc],
                               (round(start + k * 14), round(center[1] - radius * 0.42)), 3)
        self.text(str(card.level), (center[0], center[1] + 3), (255, 235, 200), 18, True, True)

    @staticmethod
    def lerp_point(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    @staticmethod
    def dashed_line(surface, color, start, end, width=2, dash=8, gap=5):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        d = 0.0
        while d < length:
            e = min(length, d + dash)
            pygame.draw.line(surface, color,
                             (start[0] + ux * d, start[1] + uy * d),
                             (start[0] + ux * e, start[1] + uy * e), width)
            d += dash + gap

    @staticmethod
    def arrow_head(surface, color, start, end, fraction=0.72, size=6):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        cx = start[0] + dx * fraction
        cy = start[1] + dy * fraction
        tip = (cx + ux * size, cy + uy * size)
        left = (cx - ux * size + px * size, cy - uy * size + py * size)
        right = (cx - ux * size - px * size, cy - uy * size - py * size)
        pygame.draw.polygon(surface, color, (tip, left, right))

    def draw_hex(self, surface, cell, fill, border, width=1, inset=0):
        pts = self.hex_points(cell, inset)
        pygame.draw.polygon(surface, fill, pts)
        pygame.draw.polygon(surface, border, pts, width)

    def movement_preview(self):
        """Следки-подсказки: куда карты сдвинутся после нажатия Space."""
        moves = self.run.movement_targets()
        merges = self.run.adjacent_merge_preview()
        if not moves and not merges:
            return
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for src, dst in moves.items():
            card = self.run.board[src]
            col = COLOR_RGB[card.colors[0]]
            a = self.hex_center(src)
            b = self.hex_center(dst)
            self.dashed_line(overlay, (*col, 120), a, b, 2, 7, 5)
            target = self.hex_points(dst, 7)
            pygame.draw.polygon(overlay, (*col, 45), target)
            pygame.draw.polygon(overlay, (*col, 155), target, 1)
            pygame.draw.circle(overlay, (*col, 190), b, 3)
            self.arrow_head(overlay, (*col, 180), a, b)
        for a_cell, b_cell in merges:
            a = self.hex_center(a_cell)
            b = self.hex_center(b_cell)
            self.dashed_line(overlay, (255, 215, 100, 190), a, b, 3, 6, 4)
            for cell in (a_cell, b_cell):
                pygame.draw.polygon(overlay, (255, 225, 145, 190),
                                    self.hex_points(cell, 3), 2)
            mid = self.lerp_point(a, b, 0.5)
            pygame.draw.circle(overlay, (255, 235, 160, 220), mid, 4)
        self.screen.blit(overlay, (0, 0))

    def draw_merge_animation(self):
        anim = self.merge_anim
        if anim is None:
            return
        p = anim.progress
        eased = 1 - (1 - p) ** 2
        target_cells = {target for _, _, target in anim.groups}

        # Финальные карты, которые не участвуют в слиянии, уже на своих местах.
        for cell, card in self.run.board.items():
            if cell not in target_cells:
                self.draw_board_card(card, self.hex_center(cell))

        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for sources, result, target in anim.groups:
            target_center = self.hex_center(target)
            for card, src in sources:
                a = self.hex_center(src)
                color = COLOR_RGB[card.colors[0]]
                self.dashed_line(overlay, (*color, 110), a, target_center, 2, 7, 5)
                for i in range(1, 4):
                    t = max(0.0, eased - i * 0.12)
                    if t <= 0:
                        continue
                    ghost_center = self.lerp_point(a, target_center, t)
                    pts = self.hex_points_at(ghost_center, self.HEX_SIZE - 6)
                    pygame.draw.polygon(overlay, (*color, 22), pts)
                    pygame.draw.polygon(overlay, (*color, 60), pts, 1)
            # Золотая вспышка-кольцо в целевой соте.
            alpha = 80 + int(120 * eased)
            pygame.draw.polygon(overlay, (255, 225, 140, alpha),
                                self.hex_points(target, 2), 3)
            pygame.draw.circle(overlay, (255, 235, 165, alpha), target_center, 4)
            self.arrow_head(overlay, (255, 225, 140, 150),
                            self.hex_center(sources[0][1]), target_center)

        self.screen.blit(overlay, (0, 0))
        # Карты сходятся в центр целевой соты; в конце появится результат.
        for sources, result, target in anim.groups:
            target_center = self.hex_center(target)
            for card, src in sources:
                center = self.lerp_point(self.hex_center(src), target_center, eased)
                self.draw_board_card(card, center)
            if eased > 0.62:
                ring = self.hex_points(target, 1)
                pygame.draw.polygon(self.screen, (255, 235, 165), ring, 2)
            if eased > 0.86:
                self.draw_board_card(result, target_center)

    def board_view(self):
        for row in range(BOARD):
            for col in range(BOARD):
                self.draw_hex(self.screen, (col, row), (25, 29, 36), (57, 64, 76))

        if self.anim is not None:
            overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            p = self.anim.progress
            eased = 1 - (1 - p) ** 2
            for card, src, dst in self.anim.cards:
                a = self.hex_center(src)
                b = self.hex_center(dst)
                color = COLOR_RGB[card.colors[0]]
                if src != dst:
                    for i in range(1, 4):
                        t = max(0.0, eased - i * 0.13)
                        if t <= 0:
                            continue
                        ghost_center = self.lerp_point(a, b, t)
                        pts = self.hex_points_at(ghost_center, self.HEX_SIZE - 5)
                        pygame.draw.polygon(overlay, (*color, 18), pts)
                        pygame.draw.polygon(overlay, (*color, 45), pts, 1)
                    self.dashed_line(overlay, (*color, 95), a, b, 2, 7, 5)
                    target = self.hex_points(dst, 7)
                    pygame.draw.polygon(overlay, (*color, 60), target)
                    pygame.draw.polygon(overlay, (*color, 170), target, 1)
                    self.arrow_head(overlay, (*color, 160), a, b)
            self.screen.blit(overlay, (0, 0))
            for card, src, dst in self.anim.cards:
                center = self.lerp_point(self.hex_center(src), self.hex_center(dst), eased)
                self.draw_board_card(card, center)
        elif self.merge_anim is not None:
            self.draw_merge_animation()
        else:
            if self.phase == "place":
                self.movement_preview()
            for cell, card in self.run.board.items():
                self.draw_board_card(card, self.hex_center(cell))
            if self.phase == "effects" and self.play_active in self.run.board:
                glow = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
                alpha = 100 + int(80 * abs(math.sin(self.phase_timer * 10)))
                pygame.draw.polygon(glow, (255, 215, 100, alpha),
                                    self.hex_points(self.play_active, -5), 3)
                self.screen.blit(glow, (0, 0))

        bottom = self.board_y + (BOARD - 1) * self.HEX_H + self.HEX_SIZE + 8
        self.text("Соты: золотая связь = слияние; карты играются по очереди",
                  (self.board_x, bottom), (140, 145, 160), 12)

    def hand_view(self):
        for r, c, i in self.hand_rects():
            col = COLOR_RGB[c.colors[0]]
            dark = COLOR_DARK[c.colors[0]]
            if i == self.selected:
                pygame.draw.rect(self.screen, (255, 235, 160), r.inflate(8, 8), 3, border_radius=9)
            pygame.draw.rect(self.screen, dark, r, border_radius=8)
            pygame.draw.rect(self.screen, col, r, 2, border_radius=8)
            for k, cc in enumerate(c.colors):
                pygame.draw.rect(self.screen, COLOR_RGB[cc], (r.x + 8 + k * 25, r.y + 8, 20, 6), border_radius=2)
            self.text(c.name, (r.x + 8, r.y + 26), (245, 235, 215), 15, True)
            self.text(f"Порог {len(c.colors)} · ур. {c.level}", (r.x + 8, r.y + 48), (200, 190, 170), 12)
            yy = r.y + 72
            for line in c.effect_lines()[:5]:
                self.text(line, (r.x + 8, yy), (205, 210, 220), 12)
                yy += 16

    def bottom_view(self):
        self.text("1. Выложите карты в соты. 2. Space / «Разыграть»: сдвиг → слияние → эффекты → враг.",
                  (24, self.H - 42), (150, 155, 170), 14)
        b = self.end_rect
        idle = self.phase == "place" and self.anim is None and not self.run.over
        hot = idle and b.collidepoint(self.mouse)
        label = {
            "place": "РАЗЫГРАТЬ КАРТЫ",
            "move": "ДВИЖЕНИЕ…",
            "merge": "СЛИЯНИЕ…",
            "effects": "РАЗЫГРЫВАЮ…",
            "enemy": "ХОД ВРАГА…",
        }.get(self.phase, "РАЗЫГРАТЬ КАРТЫ")
        pygame.draw.rect(self.screen, (50, 44, 32) if hot else (34, 30, 24), b, border_radius=7)
        pygame.draw.rect(self.screen, (230, 185, 100) if hot else (120, 100, 70), b, 1, border_radius=7)
        self.text(label, b.center, (245, 225, 180) if idle else (150, 140, 120), 16, True, True)
        b2 = self.restart_rect
        pygame.draw.rect(self.screen, (32, 36, 44), b2, border_radius=6)
        pygame.draw.rect(self.screen, (90, 100, 120), b2, 1, border_radius=6)
        self.text("Новый забег (R)", (b2.x + 34, b2.y + 10), (190, 195, 210), 15)

    def card_tooltip(self):
        if self.anim is not None or self.phase != "place":
            return
        cell = self.board_cell_at(self.mouse)
        if cell is None or cell not in self.run.board:
            return
        card = self.run.board[cell]
        parts = list(card.parts)
        shown = ", ".join(parts[:4]) + ("…" if len(parts) > 4 else "")
        lines = [card.name, "Цвета: " + ", ".join(COLOR_NAME[c] for c in card.colors)]
        if shown:
            lines.append("Части: " + shown)
        lines.extend(card.effect_lines())
        width = max(270, max(self._font(14).size(s)[0] for s in lines) + 24)
        height = 16 + len(lines) * 19 + (18 if card.parts else 0)
        x = min(self.mouse[0] + 16, self.W - width - 8)
        y = min(self.mouse[1] + 16, self.H - height - 8)
        box = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, (18, 21, 28), box, border_radius=7)
        pygame.draw.rect(self.screen, (150, 130, 90), box, 1, border_radius=7)
        yy = y + 8
        for i, line in enumerate(lines):
            col = (255, 228, 170) if i == 0 else (195, 200, 210)
            self.text(line, (x + 12, yy), col, 14 if i == 0 else 13, i == 0)
            yy += 19
        if card.parts:
            self.text("Обе исходные части сохранены", (x + 12, yy), (140, 155, 150), 11)

    def run_loop(self):
        running = True
        while running:
            for ev in pygame.event.get():
                running = self.handle(ev)
                if not running:
                    break
            dt = self.clock.tick(60) / 1000
            self.update(dt)
            self.draw(dt)
            pygame.display.flip()
        pygame.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    MergeDuelApp(args.seed).run_loop()


if __name__ == "__main__":
    main()
