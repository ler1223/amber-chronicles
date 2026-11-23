"""«Сплав» — отдельная мини-игра: карты-цвета, парные силы и автослияния.

Это прототип без поля: рука, силы между соседними картами, автослияние,
бой 1 на 1 с HP, намерениями и пассивками врага. Запуск: python merge_duel.py
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field

import pygame

COLORS = ("red", "yellow", "blue")
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
HAND_MAX = 6
START_HP = 42


@dataclass
class Card:
    uid: int
    colors: tuple[str, ...]
    level: int = 1

    @property
    def threshold(self):
        return len(self.colors)

    @property
    def name(self):
        return f"{MIX_NAME.get(frozenset(self.colors), 'Сплав')} {self.level}"

    def effect_lines(self):
        out = []
        has = set(self.colors)
        power = 3 + self.level * 2
        if "red" in has:
            out.append(f"Урон {power}")
        if "blue" in has:
            out.append(f"Защита {power}")
        if "yellow" in has:
            out.append("Взять 1 карту")
        if {"red", "yellow"} <= has:
            out.append(f"Горение {self.level + 1}")
        if {"red", "blue"} <= has:
            out.append("Уязвимость 1")
        if {"yellow", "blue"} <= has:
            out.append("+1 энергия")
        if len(has) == 3:
            out.append("Тройной эффект")
        return out


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
        return {"attack": f"Атака {self.intent_value + self.strength}", "defend": f"Защита {self.intent_value}",
                "buff": f"Ярость +{self.intent_value}"}.get(self.intent, self.intent)

    def passive_text(self):
        return self.passive or "Без пассивки"


@dataclass
class MergeRun:
    seed: int | None = None
    player_hp: int = START_HP
    max_hp: int = START_HP
    energy: int = 3
    max_energy: int = 3
    block: int = 0
    hand: list[Card] = field(default_factory=list)
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
        for _ in range(HAND_MAX):
            self.hand.append(self.new_card((self.rng.choice(COLORS),)))
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
        wave = self.wave
        hp = 22 + wave * 9
        passive = ""
        if wave >= 2:
            passive = self.rng.choice(("Регенерация 2", "Шипы 2", "Броня 1", "Ярость 1"))
        return Enemy(names[(wave - 1) % len(names)], hp, hp, passive=passive)

    def new_card(self, colors, level=1):
        self._uid += 1
        return Card(self._uid, tuple(c for c in COLORS if c in colors), level)

    # ---------- силы и слияния ----------
    def force(self, a: Card, b: Card):
        vals = [self.affinity[tuple(sorted((x, y)))] for x in a.colors for y in b.colors]
        return sum(vals) / max(1, len(vals))

    def can_merge(self, a: Card, b: Card):
        return self.force(a, b) > max(a.threshold, b.threshold)

    def merge_cards(self, a: Card, b: Card):
        colors = tuple(c for c in COLORS if c in set(a.colors) | set(b.colors))
        return self.new_card(colors, max(a.level, b.level) + 1)

    def auto_merge(self):
        events = []
        for _ in range(100):
            best = None
            for i in range(len(self.hand) - 1):
                a, b = self.hand[i], self.hand[i + 1]
                if self.can_merge(a, b):
                    f = self.force(a, b)
                    if best is None or f > best[0]:
                        best = (f, i)
            if best is None:
                break
            _, i = best
            a, b = self.hand[i], self.hand[i + 1]
            merged = self.merge_cards(a, b)
            self.hand[i:i + 2] = [merged]
            events.append(f"{a.name} + {b.name} → {merged.name}")
            self.log.append(events[-1])
        return events

    def swap(self, i, j):
        if abs(i - j) != 1 or i < 0 or j < 0 or i >= len(self.hand) or j >= len(self.hand):
            return []
        self.hand[i], self.hand[j] = self.hand[j], self.hand[i]
        return self.auto_merge()

    # ---------- бой ----------
    def start_player_turn(self):
        if self.over:
            return []
        self.turn += 1
        self.energy = self.max_energy
        self.block = 0
        self.draw(HAND_MAX - len(self.hand))
        events = self.auto_merge()
        self.enemy.choose_intent(self)
        return events

    def _intent(self):
        e = self.enemy
        e.intent = self.rng.choice(("attack", "attack", "defend", "buff"))
        if e.intent == "attack":
            e.intent_value = 4 + self.wave * 2
        elif e.intent == "defend":
            e.intent_value = 4 + self.wave
        else:
            e.intent_value = 1 + self.wave // 2

    def draw(self, n):
        for _ in range(n):
            if len(self.hand) >= HAND_MAX:
                break
            self.hand.append(self.new_card((self.rng.choice(COLORS),)))

    def play(self, index):
        if self.over or index < 0 or index >= len(self.hand):
            return []
        if self.energy <= 0:
            return ["Нет энергии"]
        card = self.hand.pop(index)
        self.energy -= 1
        out = [f"Разыграно: {card.name}"]
        has = set(card.colors)
        level = card.level
        if "red" in has:
            dmg = 3 + level * 2
            if self.enemy.burn:
                dmg += 1
            if self.enemy.vulnerable:
                dmg = int(dmg * 1.5)
            if "броня" in self.enemy.passive.lower() or "armor" in self.enemy.passive.lower():
                dmg = max(0, dmg - 1)
            if self.enemy.shield:
                absorbed = min(self.enemy.shield, dmg)
                self.enemy.shield -= absorbed
                dmg -= absorbed
            self.enemy.hp -= dmg
            out.append(f"Урон {dmg}")
            if "thorns" in self.enemy.passive.lower() or "шипы" in self.enemy.passive.lower():
                self.player_hp -= 2
                out.append("Шипы: −2 HP")
        if "blue" in has:
            self.block += 3 + level * 2
            out.append(f"Защита {3 + level * 2}")
        if "yellow" in has:
            self.draw(1)
            out.append("Взята карта")
        if {"red", "yellow"} <= has:
            self.enemy.burn += level + 1
            out.append(f"Горение {level + 1}")
        if {"red", "blue"} <= has:
            self.enemy.vulnerable = max(self.enemy.vulnerable, 1)
            out.append("Уязвимость 1")
        if {"yellow", "blue"} <= has:
            self.energy = min(self.max_energy, self.energy + 1)
            out.append("+1 энергия")
        if len(has) == 3:
            self.draw(1)
            out.append("Тройной эффект")
        self.auto_merge()
        if self.player_hp <= 0:
            self.player_hp = 0
            self.over = True
            out.append("Поражение")
        elif self.enemy.hp <= 0:
            self._next_wave()
        self.log.extend(out)
        return out

    def end_turn(self):
        if self.over:
            return []
        out = []
        e = self.enemy
        if e.burn:
            e.hp -= e.burn
            out.append(f"Горение: {e.burn}")
            e.burn = max(0, e.burn - 1)
        if "регенерация" in e.passive.lower() or "regen" in e.passive.lower():
            e.hp = min(e.max_hp, e.hp + 2)
            out.append("Враг восстановил 2 HP")
        if "ярость" in e.passive.lower() or "rage" in e.passive.lower():
            e.strength += 1
            out.append("Враг разъярён: +1 сила")
        if e.intent == "attack":
            dmg = max(0, e.intent_value + e.strength - self.block)
            self.player_hp -= dmg
            out.append(f"Враг атакует: {dmg}")
        elif e.intent == "defend":
            e.shield += e.intent_value
            out.append(f"Враг защищается: {e.intent_value}")
        else:
            e.strength += e.intent_value
            out.append(f"Враг усиливается: +{e.intent_value}")
        if e.vulnerable:
            e.vulnerable = max(0, e.vulnerable - 1)
        if self.player_hp <= 0:
            self.player_hp = 0
            self.over = True
            out.append("Поражение")
            self.log.extend(out)
            return out
        if e.hp <= 0:
            self._next_wave()
        else:
            out.extend(self.start_player_turn())
        self.log.extend(out)
        return out

    def _next_wave(self):
        self.wave += 1
        self.player_hp = min(self.max_hp, self.player_hp + 7)
        self.enemy = self._make_enemy()
        self.log.append(f"Волна {self.wave}: {self.enemy.name}")
        self.start_player_turn()


# ---------- экран ----------
class MergeDuelApp:
    W, H = 1280, 800
    CARD_W, CARD_H = 156, 248

    def __init__(self, seed=None):
        pygame.init()
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("Сплав — карточный залив")
        self.clock = pygame.time.Clock()
        self._fonts = {}
        self.font = self._font(20)
        self.big = self._font(30)
        self.small = self._font(16)
        self.seed = seed
        self.run = MergeRun(seed)
        self.mouse = (0, 0)
        self.drag_index = None
        self.drag_start = None
        self.drag_moved = False
        self.toast = ""
        self.toast_t = 0
        self.card_rects = []
        self.end_rect = pygame.Rect(self.W - 230, self.H - 68, 200, 46)
        self.restart_rect = pygame.Rect(self.W - 230, 190, 200, 38)

    def card_at(self, pos):
        for i, r in enumerate(self.card_rects):
            if r.collidepoint(pos):
                return i
        return None

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return False
            if ev.key == pygame.K_SPACE:
                self.end_turn()
            if ev.key == pygame.K_r:
                self.run = MergeRun(self.seed)
                self.toast = ""
        elif ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            if self.drag_start is not None and pygame.math.Vector2(ev.pos).distance_to(self.drag_start) > 9:
                self.drag_moved = True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            if self.restart_rect.collidepoint(ev.pos):
                self.run = MergeRun(self.seed)
                return True
            if self.end_rect.collidepoint(ev.pos):
                self.end_turn()
                return True
            self.drag_index = self.card_at(ev.pos)
            self.drag_start = ev.pos
            self.drag_moved = False
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self.drag_index is None:
                return True
            target = self.card_at(ev.pos)
            if self.drag_moved and target is not None and abs(target - self.drag_index) == 1:
                events = self.run.swap(self.drag_index, target)
                self.flash(events)
            elif not self.drag_moved:
                out = self.run.play(self.drag_index)
                self.flash(out)
            self.drag_index = None
            self.drag_start = None
            self.drag_moved = False
        return True

    def flash(self, events):
        if events:
            self.toast = " · ".join(events[-2:])
            self.toast_t = 2.8

    def end_turn(self):
        events = self.run.end_turn()
        self.flash(events)
        if self.run.over:
            self.toast = "Поражение. R — новый забег"

    def draw(self):
        s = self.screen
        s.fill((13, 15, 20))
        # фон
        pygame.draw.rect(s, (20, 24, 31), (0, 0, self.W, 8))
        self.title()
        self.player_panel()
        self.enemy_panel()
        self.affinity_panel()
        self.hand_panel()
        self.bottom_panel()
        if self.toast_t > 0:
            self.toast_t -= 1 / 60
            f = self.font.render(self.toast, True, (255, 228, 150))
            s.blit(f, (self.W // 2 - f.get_width() // 2, 100))
        if self.run.over:
            shade = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 180))
            s.blit(shade, (0, 0))
            msg = self.big.render("Забег окончен", True, (255, 120, 100))
            s.blit(msg, (self.W // 2 - msg.get_width() // 2, 300))
            msg = self.font.render("R — начать новый забег", True, (240, 220, 180))
            s.blit(msg, (self.W // 2 - msg.get_width() // 2, 346))

    def title(self):
        s = self.screen
        f = self.big.render("СПЛАВ", True, (255, 205, 110))
        s.blit(f, (self.W // 2 - f.get_width() // 2, 24))
        sub = self.small.render(f"Волна {self.run.wave} · ход {self.run.turn}", True, (150, 155, 165))
        s.blit(sub, (self.W // 2 - sub.get_width() // 2, 58))

    def player_panel(self):
        s = self.screen
        r = pygame.Rect(24, 24, 290, 118)
        pygame.draw.rect(s, (28, 31, 38), r, border_radius=8)
        pygame.draw.rect(s, (90, 115, 155), r, 1, border_radius=8)
        self._text("Игрок", (r.x + 14, r.y + 10), (220, 225, 235), 20)
        self._text(f"HP {self.run.player_hp}/{self.run.max_hp}", (r.x + 14, r.y + 38), (235, 150, 140), 18)
        self._text(f"Энергия {self.run.energy}/{self.run.max_energy}", (r.x + 14, r.y + 62), (150, 195, 255), 16)
        self._text(f"Защита {self.run.block}", (r.x + 14, r.y + 84), (150, 190, 240), 16)

    def enemy_panel(self):
        s = self.screen
        e = self.run.enemy
        r = pygame.Rect(self.W - 330, 24, 306, 150)
        pygame.draw.rect(s, (36, 27, 30), r, border_radius=8)
        pygame.draw.rect(s, (170, 90, 85), r, 1, border_radius=8)
        self._text(e.name, (r.x + 14, r.y + 10), (245, 185, 165), 20)
        self._text(f"HP {max(0, e.hp)}/{e.max_hp}", (r.x + 14, r.y + 38), (235, 150, 140), 17)
        self._text(f"Намерение: {e.intent_text()}", (r.x + 14, r.y + 62), (255, 220, 135), 16)
        self._text(f"Пассивка: {e.passive_text()}", (r.x + 14, r.y + 84), (190, 195, 205), 14)
        if e.shield:
            self._text(f"Щит {e.shield}", (r.x + 14, r.y + 106), (150, 190, 240), 15)
        if e.burn:
            self._text(f"Горение {e.burn}", (r.x + 14, r.y + 126), (240, 140, 90), 15)
        if e.vulnerable:
            self._text(f"Уязвимость {e.vulnerable}", (r.x + 140, r.y + 126), (235, 140, 190), 15)

    def affinity_panel(self):
        s = self.screen
        r = pygame.Rect(24, 160, 290, 230)
        pygame.draw.rect(s, (25, 29, 36), r, border_radius=8)
        pygame.draw.rect(s, (80, 92, 110), r, 1, border_radius=8)
        self._text("Силы пар", (r.x + 14, r.y + 10), (205, 215, 230), 18)
        self._text("притяжение >", (r.x + 14, r.y + 34), (145, 155, 170), 12)
        step = 72
        x0, y0 = r.x + 92, r.y + 68
        for i, a in enumerate(COLORS):
            self._text(COLOR_NAME[a][:1], (x0 + i * step, y0 - 24), COLOR_RGB[a], 17)
            self._text(COLOR_NAME[a][:1], (r.x + 22, y0 + i * 44), COLOR_RGB[a], 17)
            for j, b in enumerate(COLORS):
                v = self.run.affinity[tuple(sorted((a, b)))]
                col = (160, 230, 160) if v > 1 else (220, 160, 130) if v < 0 else (185, 185, 195)
                self._text(f"{v:+d}", (x0 + j * step, y0 + i * 44), col, 17)
        self._text("Слияние: сила > числа цветов", (r.x + 14, r.bottom - 36), (145, 155, 170), 12)

    def hand_panel(self):
        s = self.screen
        n = len(self.run.hand)
        gap = 14
        total = n * self.CARD_W + max(0, n - 1) * gap
        x = (self.W - total) // 2
        y = 436
        self.card_rects = []
        for i, c in enumerate(self.run.hand):
            r = pygame.Rect(x + i * (self.CARD_W + gap), y, self.CARD_W, self.CARD_H)
            self.card_rects.append(r)
            self.draw_card(r, c, i)
        if n > 1:
            for i in range(n - 1):
                a, b = self.run.hand[i], self.run.hand[i + 1]
                f = self.run.force(a, b)
                col = (130, 240, 145) if self.run.can_merge(a, b) else (155, 160, 175)
                mid = (self.card_rects[i].right + self.card_rects[i + 1].left) // 2
                label = f"{f:+.1f}"
                img = self.small.render(label, True, col)
                s.blit(img, (mid - img.get_width() // 2, y + self.CARD_H + 8))
                if self.run.can_merge(a, b):
                    self._text("слить", (mid - 10, y + self.CARD_H + 26), (140, 240, 150), 12)
        if not n:
            self._text("Рука пуста — завершите ход", (self.W // 2 - 100, y + 80), (180, 180, 190), 18)

    def draw_card(self, r, c, i):
        s = self.screen
        col = COLOR_RGB[c.colors[0]]
        dark = COLOR_DARK[c.colors[0]]
        dragging = i == self.drag_index and self.drag_moved
        if dragging:
            r = r.move(0, -12)
        pygame.draw.rect(s, dark, r, border_radius=9)
        pygame.draw.rect(s, col, r, 3, border_radius=9)
        for k, cc in enumerate(c.colors):
            pygame.draw.rect(s, COLOR_RGB[cc], (r.x + 8 + k * 32, r.y + 8, 25, 8), border_radius=3)
        self._text(c.name, (r.x + 10, r.y + 26), (245, 235, 215), 17, bold=True)
        self._text(f"Порог {c.threshold} · ур. {c.level}", (r.x + 10, r.y + 50), (200, 190, 170), 13)
        yy = r.y + 78
        for line in c.effect_lines()[:6]:
            self._text(line, (r.x + 10, yy), (205, 210, 220), 14)
            yy += 19
        self._text("зажми и перетащи — сдвиг", (r.x + 10, r.bottom - 40), (150, 155, 170), 11)
        self._text("клик — сыграть", (r.x + 10, r.bottom - 24), (150, 155, 170), 11)

    def bottom_panel(self):
        s = self.screen
        self._text("ЛКМ: клик — сыграть · перетаскивание на соседнюю — сдвиг · Space — конец хода",
                   (24, self.H - 44), (150, 155, 170), 14)
        b = pygame.Rect(self.W - 230, self.H - 68, 200, 46)
        hot = b.collidepoint(self.mouse)
        pygame.draw.rect(s, (50, 44, 32) if hot else (34, 30, 24), b, border_radius=7)
        pygame.draw.rect(s, (230, 185, 100) if hot else (120, 100, 70), b, 1, border_radius=7)
        self._text("КОНЕЦ ХОДА", (b.centerx - 54, b.centery - 10), (245, 225, 180), 16, bold=True)
        b2 = self.restart_rect
        pygame.draw.rect(s, (32, 36, 44), b2, border_radius=6)
        pygame.draw.rect(s, (90, 100, 120), b2, 1, border_radius=6)
        self._text("Новый забег (R)", (b2.x + 34, b2.y + 10), (190, 195, 210), 15)

    def _font(self, size, bold=False):
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
            if len(self._fonts) > 40:
                self._fonts.clear()
            self._fonts[key] = f
        return f

    def _text(self, text, pos, col, size=16, bold=False):
        img = self._font(size, bold).render(text, True, col)
        self.screen.blit(img, pos)

    def run_loop(self):
        running = True
        while running:
            for ev in pygame.event.get():
                running = self.handle(ev)
                if not running:
                    break
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    MergeDuelApp(args.seed).run_loop()


if __name__ == "__main__":
    main()
