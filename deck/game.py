"""Забег «Спуска»: карта этажа → узел (бой, элита, костёр, торговец, страж) → награда, прозрения → карта →
… страж лестницы → следующий этаж (враги сильнее). Конец — гибель героя: итог — глубина."""
from sim import expedition as X
from sim.data import GameData

from . import model as M
from .battle import Battle
from .ui import BattleScreen, ChoiceScreen, DeckScreen, EndScreen, HeroSelect, MapScreen, ShopScreen

CAMP_HEAL = 0.3


class DescentGame:
    def __init__(self, seed=None, gd=None, save_path=None):
        """save_path — куда сохранять забег (descent.py: save/descent_run.json); None — не сохранять (тесты)."""
        self.save_path = save_path
        from .terrain import warm_up
        warm_up()                                         # материалы земли — в фоне, к первому бою готовы
        self.gd = gd or X.expedition_data(GameData())     # поля боёв, фигурки и враги нынешней игры
        self.seed = seed
        self.frame = None                                 # последний кадр боя — фон под выбором
        self._imgs = {}
        self.data = M.load()
        self.run = None
        self.new_run()

    def new_run(self):
        """Новый забег — с выбора героя."""
        self.scene = HeroSelect(self)

    def start_run(self, hero="merc", variant=None):
        self.run = M.Run(data=self.data, seed=self.seed, hero=hero, variant=variant)
        self.node = None
        self.to_map()

    # ---------- сохранение забега ----------

    def autosave(self):
        """Забег — в файл, когда герой на карте этажа (после каждого узла)."""
        if not self.save_path or self.run is None or self.run.hp <= 0:
            return
        from . import save as SV
        try:
            SV.save(self.run, self.node["id"] if self.node else None, self.save_path)
        except OSError:
            pass

    def has_save(self):
        from . import save as SV
        return SV.exists(self.save_path)

    def continue_run(self):
        """Продолжить сохранённый забег — с карты этажа."""
        from . import save as SV
        got = SV.load(self.data, self.save_path) if self.save_path else None
        if got is None:
            return False
        self.run, nid = got
        self.node = self.run.floor.nodes.get(nid) if nid and self.run.floor else None
        self.to_map(f"Забег продолжен: {self.run.hero_name}, этаж {self.run.depth}")
        return True

    def end_run(self):
        """Забег кончился (гибель или победа) — сохранение стирается."""
        if self.save_path:
            from . import save as SV
            SV.delete(self.save_path)

    def run_defs(self):
        return self.data["cards"]["cards"]

    def to_map(self, toast=None):
        self.autosave()
        self.scene = MapScreen(self)
        if toast:
            self.scene.toast = (toast, 3.0)

    def hero_img(self, sprite=None, k=0.7):
        sprite = sprite or self.run.sprite
        if (sprite, k) not in self._imgs:
            from game.expedition_scenes import hero_sprite
            self._imgs[(sprite, k)] = hero_sprite(self.gd, sprite, k)
        return self._imgs[(sprite, k)]

    # ---------- узлы ----------

    def enter_node(self, nid):
        n = self.run.floor.enter(nid)
        self.node = n
        if n["type"] in ("battle", "elite", "boss"):
            self.start_battle(n["fight"])
        elif n["type"] == "camp":
            heal = int(self.run.max_hp * CAMP_HEAL)
            from .items import mod
            rest = [] if mod(self.run, "no_camp_heal") else [(f"Отдохнуть: +{heal} HP", None, "rest")]
            self.scene = ChoiceScreen(self, "Костёр", f"HP {self.run.hp}/{self.run.max_hp}. " +
                                      ("Отдохнуть или избавиться от слабой карты?" if rest else
                                       "Котелок бодрости не даёт уснуть — можно только избавиться от карты."),
                                      rest + [("Удалить карту", None, "remove")], self._camp)
        elif n["type"] == "shop":
            self.scene = ShopScreen(self)
        elif n["type"] == "workshop":                     # мастерская: улучшить простое применение карты
            self.offer_workshop()
        elif n["type"] in ("chest", "altar"):            # сундук: предмет на выбор (1 из 3)
            self.offer_relics(3, "Сундук", lambda toast=None: self.to_map(toast), source="chest")

    def offer_workshop(self):
        """Мастерская: выбрать карту, затем 1 из 3 улучшений её простого применения (одно на карту)."""
        run = self.run
        fit = sorted([c for c in run.deck if c.alt_options(run.hero_id)], key=lambda c: (c.cid, c.tier))
        if not fit:
            self.to_map("Мастерская: улучшать нечего")
            return

        def picked(card):
            opts = card.alt_options(run.hero_id)

            def done(k):
                card.upgrade_alt(opts[k][1].alt_up)
                self.to_map(f"Мастерская: «{card.name}» — {opts[k][0]}")
            self.scene = ChoiceScreen(self, f"Мастерская: {card.name}",
                                      "Простое применение (бесплатное, вверх ногами) станет таким — одно улучшение на "
                                      "карту", [(label, c, k) for k, (label, c) in enumerate(opts)], done,
                                      skip=self.offer_workshop)
        self.scene = DeckScreen(self, "Мастерская", fit, lambda: self.to_map(None), on_pick=picked,
                                sub="Выберите карту: мастер улучшит её простое применение")

    def start_battle(self, fight):
        run = self.run
        b = Battle(self.gd, run, fight, seed=(self.seed or 0) * 1000 + run.depth * 50 + len(run.floor.path))
        self.scene = BattleScreen(self, b)

    def _camp(self, what):
        run = self.run
        if what == "rest":
            run.hp = min(run.max_hp, run.hp + int(run.max_hp * CAMP_HEAL))
            self.to_map("Отдохнули у костра")
        else:
            self.pick_remove(back=None, paid=False)

    def pick_remove(self, back=None, paid=False):
        """Удалить карту: у торговца — за золото (цена растёт), у костра — даром. back — экран, куда вернуться."""
        run = self.run

        def done(card):
            run.deck.remove(card)
            if paid:
                run.gold -= run.remove_price
                run.remove_price += run.data["enemies"]["shop"]["remove_step"]
            if back is not None:
                self.scene = back
            else:
                self.to_map(f"«{card.name}» убрана из колоды")

        def cancel():
            if back is not None:
                self.scene = back
            else:                                          # у костра передумали — снова выбор
                self.enter_again_camp()

        self.scene = DeckScreen(self, "Удалить карту", sorted(run.deck, key=lambda c: (c.cid, c.tier)), cancel,
                                on_pick=done, sub="Какую карту убрать из колоды навсегда?" +
                                (f" Цена: {run.remove_price} золота" if paid else ""))

    def enter_again_camp(self):
        heal = int(self.run.max_hp * CAMP_HEAL)
        self.scene = ChoiceScreen(self, "Костёр", "Отдохнуть или избавиться от слабой карты?",
                                  [(f"Отдохнуть: +{heal} HP", None, "rest"), ("Удалить карту", None, "remove")],
                                  self._camp)

    def show_deck(self):
        back = self.scene
        self.scene = DeckScreen(self, f"Колода ({len(self.run.deck)})", sorted(self.run.deck, key=lambda c: (c.cid, c.tier)),
                                lambda: setattr(self, "scene", back),
                                sub="Полоска внизу карты — путь к прозрению (основные применения)")

    # ---------- после боя ----------

    def battle_over(self, b):
        b.finish_into_run()
        run = self.run
        if b.result != "victory":
            self.end_run()
            self.scene = EndScreen(self, False, [f"Пал на этаже {run.depth} в бою «{b.fight['name']}».",
                                                 f"Выиграно боёв: {run.fight} · убито врагов: {run.kills}",
                                                 f"Колода: {len(run.deck)} карт · прозрений: "
                                                 f"{sum(c.tier for c in run.deck)}"])
            return
        run.fight += 1
        if run.hero.get("mechanic") != "idols":           # отдышаться после боя: +10% HP (кроме Жреца)
            run.hp = min(run.max_hp, run.hp + max(1, round(run.max_hp * 0.1)))
        kind = self.node["type"] if self.node else "battle"
        gold = run.gold_for(kind)
        run.gold += gold
        self._boss = kind == "boss"
        self._elite = kind == "elite"
        self._gold = gold
        self._branches()

    def _branches(self):
        """Жрец: боги, выросшие в бою, — ветка 1 из 2 (переделка смысла или аура), по одному уровню за экран."""
        from .idols import Idols
        run = self.run
        while getattr(run, "god_pending", None):
            god, level = run.god_pending.pop(0)
            opts = Idols.branch_offer(run, god, level)
            if not opts:
                continue
            gdef = dict(run.data["gods"]["gods"][god], id=god)

            def pick(v, god=god):
                run.god_picks.setdefault(god, []).append(v)
                self._branches()
            from .ui import GodBranchScreen
            self.scene = GodBranchScreen(self, gdef, level, opts, pick, back=self.frame)
            return
        self._card_reward()

    def _card_reward(self):
        run = self.run
        offer = run.reward_offer()
        self.scene = ChoiceScreen(self, "Победа!", f"+{self._gold} золота · HP {run.hp}/{run.max_hp} (между боями "
                                  "не восстанавливается). Возьмите карту в колоду:", [("", c, c) for c in offer],
                                  self._took, skip=lambda: self._took(None), back=self.frame)

    def _took(self, card):
        if card is not None:
            self.run.take(card)
        self._next_insight()

    def _next_insight(self):
        ready = self.run.insights()
        if not ready:
            self._after_rewards()
            return
        card = ready[0]
        opts = card.options()                              # 3 случайных из 5 вариантов (как эпифании)
        self.scene = ChoiceScreen(self, f"Прозрение: {card.name}",
                                  f"Прозрение сработало за {card.uses} основных применений — какой она станет? "
                                  "(цена не меняется)",
                                  [(label, c, k) for k, (label, c) in enumerate(opts)],
                                  lambda k: (card.choose(k), self._next_insight()), back=self.frame)

    def _after_rewards(self):
        run = self.run
        if getattr(self, "_elite", False):                 # элита — реликвия: 1 из 2
            self._elite = False
            self.offer_relics(2, "Трофей элиты", lambda toast=None: self.to_map(toast), source="elite")
            return
        if getattr(self, "_boss", False):                  # страж повержен — реликвия, дар бога, затем вниз
            self._boss = False
            if run.last_floor:                             # последний босс — спуск пройден
                n = len(run.chapters)
                self.end_run()
                self.scene = EndScreen(self, True, [
                    f"Пройдено глав: {n} — до «{run.chapter_name}» включительно. {run.hero_name} у самого дна.",
                    f"Выиграно боёв: {run.fight} · убито врагов: {run.kills} · реликвий: {len(run.relics)}",
                    f"Колода: {len(run.deck)} карт · прозрений: {sum(c.tier for c in run.deck)}",
                    f"Глава {n + 1} — когда будет готова."])
                return
            new_chapter = run.chapter_end

            def down(toast=None):
                k = 1.0 if new_chapter else run.floor_cfg["boss_heal"]          # между главами — полный отдых
                heal = int((run.max_hp - run.hp) * k)
                run.hp += heal
                run.next_floor()
                if new_chapter:
                    i = run.chapter_at()[0] + 1
                    self.to_map(f"Глава {i}: {run.chapter_name}. Этаж {run.depth} — {run.floor_name}. +{heal} HP")
                else:
                    self.to_map(f"Спуск: этаж {run.depth} — {run.floor_name}. +{heal} HP")
            self.offer_relics(3, "Сокровище стража", down, source="boss")
            return
        self.to_map()

    # ---------- реликвии ----------

    def offer_relics(self, n, title, then, source="chest"):
        """Предмет на выбор (n штук); then(toast) — дальше (пропуск — тоже). source — редкость: сундук, элита, страж."""
        run = self.run
        offer = run.relic_offer(n, source)
        if not offer:
            then(None)
            return

        def took(r):
            run.relics.append(r)
            then(f"Предмет: {r['name']}")
        from .items import RARITY_NAME, about
        sub =("Сильный предмет с минусом — до конца забега" if source == "boss" else
               "Предмет лежит в сумке до конца забега и срабатывает при условии · I — сумка")
        self.scene = ChoiceScreen(self, title, sub,
                                  [(f"{r['name']} · {RARITY_NAME.get(r.get('rarity'), '')}\n{about(r, run)}", None, r)
                                   for r in offer], took, skip=lambda: then(None), back=self.frame)

    # ---------- цикл ----------

    def handle(self, ev):
        self.scene.handle(ev)

    def update(self, dt):
        self.scene.update(dt)

    def draw(self, surf):
        self.scene.draw(surf)
        if isinstance(self.scene, BattleScreen) and (self.scene.b.result or self.frame is None):
            self.frame = surf.copy()                        # фон под наградой — кадр конца боя
