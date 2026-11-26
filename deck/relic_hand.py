"""Предметы руки, стоек и последовательностей розыгрыша."""
from sim.grid import DIRS8, cheb

from . import model as M
from .relic_choice import RelicChoice


def relic(name, rarity, about, hero=None):
    item = {"name": name, "icon": "gift_word_power", "rarity": rarity, "about": about}
    return dict(item, hero=hero) if hero else item


RELICS = {
    "link_spool": relic("Катушка связного", "uncommon",
                       "Когда Связь сбрасывает две или больше карт, выбери одну. В начале следующего хода она ляжет наверх колоды без Связи."),
    "wax_pocket": relic("Восковой карман", "rare",
                        "Раз за бой можешь вернуть карту, изгнанную Мимолётной в конце хода, в руку в начале следующего."),
    "empty_binding": relic("Пустой переплёт", "uncommon",
                           "В конце хода можешь обменять Неактивируемую карту, которая провела весь ход в руке, на верхнюю карту сброса."),
    "edge_coin": relic("Монета на ребре", "uncommon",
                       "Если скидка Упреждения сгорела, в начале следующего хода можешь передать скидку 1 любой платной карте в руке."),
    "black_sealing_wax": relic("Чёрная сургучница", "rare",
                                "Раз за бой можешь отложить эффект вручную сброшенной карты с Затиханием до начала следующего хода и выбрать цель тогда."),
    "last_word_book": relic("Книга последнего слова", "uncommon",
                             "Перед завершением хода от Финала можешь дать одной карте в руке временное Сохранение."),
    "split_seal": relic("Расколотая печать", "rare",
                        "Первое ранение картой с Изгнанием 2 помечает цель. Если она снова ранена этой картой при втором розыгрыше, после изгнания забери карту из сброса."),
    "two_fates_binding": relic("Переплёт двух судеб", "rare",
                               "Раз за бой вместо слияния можешь оставить обе исходные карты. Они получают Мимолётную до конца хода."),
    "copper_spur": relic("Медная шпора", "uncommon",
                          "При смене стойки после Шага можешь вернуться на клетку, с которой сделал последний добровольный шаг.", "merc"),
    "chess_pendant": relic("Шахматная подвеска", "rare",
                            "В стойке Коня отметь клетку первого приземления. Вернись на неё прыжком и сможешь притянуть соседнего врага на клетку, с которой прыгнул.", "merc"),
    "glass_buckler": relic("Стеклянный щиток", "uncommon",
                            "Если сохранил Удар в защитной стойке, в начале следующего хода можешь сбросить эту карту ради одной контратаки.", "merc"),
    "tuning_fork": relic("Камертон", "rare",
                          "Раз за ход можешь направить повтор одиночной атаки Резонанса в другую допустимую цель."),
    "salt_fuse": relic("Солевой фитиль", "uncommon",
                        "Если Огонь попал по отравленному врагу, можешь снять с него 2 яда и положить ядовитое покрытие на соседнюю свободную клетку."),
    "two_faced_chime": relic("Двуликий колокольчик", "rare",
                              "После двух последовательных свитков через статуи разных богов можешь поменять их местами.", "priest"),
    "swap_bead": relic("Бусина перестановки", "uncommon",
                         "Когда Комбо срабатывает второй раз за ход, можешь обменять карту, не сыгранную в этом ходу, из руки на верхнюю карту добора."),
    "oblique_seal": relic("Косая печать", "uncommon",
                           "Раз за ход, если Область накрывает врага и твою установку, можешь сдвинуть её центр на одну клетку от установки."),
}


def cells_near(cell):
    x, y = cell
    return [(x + dx, y + dy) for dx, dy in DIRS8]


class HandRelics:
    def __init__(self, battle):
        self.b = battle
        self.spent = set()
        self.turn_spent = set()
        self.next_top = []
        self.next_hand = []
        self.fleeting = set()
        self.deferred_merge = set()
        self.untouched = set()
        self.guard_strikes = []
        self.lead_credit = False
        self.rolled_lead = set()
        self.delayed_quietus = None
        self.first_cuts = {}
        self.current_cuts = []
        self.previous_step = None
        self.step_card = False
        self.knight_mark = None
        self.last_statue = None
        self.combos = 0
        self.played = set()

    def has(self, item_id):
        return any(item.get("id") == item_id for item in self.b.items.list)

    def ready(self, item_id, *, turn=False):
        return self.has(item_id) and item_id not in (self.turn_spent if turn else self.spent)

    def choose(self, item_id, options, label=None):
        if not options:
            return None
        if label is None:
            label = lambda value: value.name if hasattr(value, "name") else f"{value[0] + 1}, {value[1] + 1}"
        return (yield RelicChoice(RELICS[item_id]["name"], [(label(value), value) for value in options]))

    def accept(self, item_id, label):
        return (yield from self.choose(item_id, [True], lambda _: label))

    def take_from_pile(self, card):
        b = self.b
        for pile in (b.discard, b.used, b.exhaust):
            if card in pile:
                pile.remove(card)
                return True
        return False

    def can_swap(self, incoming, outgoing=None):
        b = self.b
        return not b.ballista_locked(incoming) and (
            not b.limits_unique_hand(incoming)
            or not any(card is not outgoing and b.limits_unique_hand(card) for card in b.hand))

    def before_draw(self, hand_limit):
        b = self.b
        b.draw_pile.extend(self.next_top)
        self.next_top.clear()
        waiting, self.next_hand = self.next_hand, []
        for card in waiting:
            if len(b.hand) < hand_limit and self.can_swap(card):
                b.receive_card(card)
            else:
                b.draw_pile.append(card)

    def turn_start(self):
        b = self.b
        self.turn_spent.clear()
        self.played.clear()
        self.previous_step = None
        self.step_card = False
        self.combos = 0
        self.rolled_lead = set(b.lead_discounts)
        if self.has("empty_binding"):
            self.untouched = {c.uid for c in b.hand}
        if self.lead_credit:
            self.lead_credit = False
            paid = [c for c in b.hand if b.effective_cost(c) > 0 and not c.d.get("x_cost")]
            chosen = yield from self.choose("edge_coin", paid)
            if chosen is not None:
                b.lead_discounts.add(chosen.uid)
        waiting, self.guard_strikes = self.guard_strikes, []
        for card in waiting:
            if card in b.hand and (yield from self.accept("glass_buckler", f"Сбросить «{card.name}»")):
                b.hand.remove(card)
                b.place_discarded_card(card)
                yield from b.card_event("discarded", card)
                b.hero.ds["counter"] += 1
                b._icons(b.hero)
                break
        if self.delayed_quietus is not None:
            card, ops = self.delayed_quietus
            self.delayed_quietus = None
            targets = b.foes() if any(op["op"] in ("damage", "burn", "poison", "push", "pull", "weak",
                                                  "vulnerable", "bleed", "mark", "stun") for op in ops) else []
            target = yield from self.choose("black_sealing_wax", targets)
            if target is None and targets:
                target = targets[0]
            yield from b.apply(b.hero, ops, target, {"card": card})

    def lost_lead(self, played=None):
        b = self.b
        if self.has("edge_coin") and any(c.uid in self.rolled_lead and c.uid in b.lead_discounts
                                         for c in b.hand if c is not played):
            self.lead_credit = True

    def link(self, cards):
        if len(cards) >= 2 and self.has("link_spool"):
            chosen = yield from self.choose("link_spool", [c for c in cards if c in self.b.discard or c in self.b.used])
            if chosen is not None and self.take_from_pile(chosen):
                self.next_top.append(chosen)

    def manual_discard(self, card):
        b = self.b
        item = "black_sealing_wax"
        ops = M.card_reactions(card.d, "quietus") if "quietus" in M.card_rules(card.d) else ()
        if ops and self.ready(item) and (yield from self.accept(item, f"Отложить «{card.name}»")):
            self.spent.add(item)
            self.delayed_quietus = card, ops
            yield from b.apply(b.hero, tuple(op for op in b.card_event_ops("discarded", card)
                                            if not any(op is quiet for quiet in ops)), None, {"card": card})
        else:
            yield from b.card_event("discarded", card)

    def on_ephemeral(self, card):
        item = "wax_pocket"
        if self.ready(item) and card in self.b.exhaust and (yield from self.accept(item, f"Запечатать «{card.name}»")):
            self.spent.add(item)
            self.b.exhaust.remove(card)
            self.next_hand.append(card)

    def clear_fleeting(self):
        for card in self.fleeting:
            card.temporary_rules -= {"ephemeral"}
        self.fleeting.clear()

    def before_end(self, from_finale):
        b = self.b
        self.lost_lead()
        if from_finale and self.has("last_word_book"):
            card = yield from self.choose("last_word_book", b.hand)
            if card is not None:
                b.temporary_retain[card.uid] = max(0, b.temporary_retain.get(card.uid, 0))
        if self.has("empty_binding") and b.discard:
            candidates = [c for c in b.hand if c.uid in self.untouched and "unactivatable" in M.card_rules(c.d)
                          and self.can_swap(b.discard[-1], c)]
            card = yield from self.choose("empty_binding", candidates)
            if card is not None:
                top = b.discard.pop()
                b.hand.remove(card)
                b.receive_card(top)
                b.place_discarded_card(card)
                yield from b.card_event("discarded", card)

    def defer_merge(self, card, hand_limit):
        b = self.b
        if not self.ready("two_fates_binding") or b.merge_partner(card) is None:
            return False
        if len(b.hand) >= hand_limit:
            if not self.deferred_merge:
                self.spent.add("two_fates_binding")
            return False
        self.deferred_merge.add(card.uid)
        b.hand.append(card)
        b.queue.append(("relic_job", self.merge_choice(card)))
        return True

    def merge_choice(self, card):
        b = self.b
        item = "two_fates_binding"
        self.deferred_merge.discard(card.uid)
        if card not in b.hand:
            return
        b.hand.remove(card)
        partner = b.merge_partner(card)
        keep_both = False
        if partner is not None and self.ready(item):
            self.spent.add(item)
            keep_both = yield from self.accept(item, f"Оставить две карты «{card.name}»")
        if keep_both:
            self.fleeting.update((card, partner))
            for member in (card, partner):
                member.temporary_rules |= {"ephemeral"}
            b.hand.append(card)
            b.queue_card_event("entered_hand", card)
        else:
            b.receive_card(card, relic_offer=False)

    def retained(self, card):
        if self.b.stance == "guard" and self.has("glass_buckler") and "strike" in card.tag_ids:
            self.guard_strikes.append(card)

    def hit(self, card, target, hp, shield):
        b = self.b
        harmed = target.hp < hp or target.shield < shield
        if card is None or not harmed:
            return
        if target.hp < hp and self.has("split_seal") and "exhaust_2" in M.card_rules(card.d):
            self.current_cuts.append((card.uid, target))
        if (self.has("salt_fuse") and "fire" in card.tag_ids and target.alive and
                target.ds.get("poison", 0) >= 2):
            cell = yield from self.choose("salt_fuse", [p for p in cells_near(target.cell) if b.free(p)])
            if cell is not None:
                target.ds["poison"] -= 2
                b._icons(target)
                b.set_surface(cell, "poison")

    def exhaust_count(self, card, count):
        if not self.has("split_seal"):
            return
        if count == 1:
            target = next((f for uid, f in self.current_cuts if uid == card.uid), None)
            if target is not None:
                self.first_cuts[card.uid] = target
                self.b.fx("status", unit=target, el="mark")
                self.b.say(f"Расколотая печать: {target.name} помечен", (220, 190, 240))
        elif (card.uid, self.first_cuts.pop(card.uid, None)) in self.current_cuts and card in self.b.exhaust:
            chosen = yield from self.choose("split_seal", self.b.discard)
            if chosen is not None and self.take_from_pile(chosen):
                self.b.receive_card(chosen)
        self.current_cuts = [(uid, target) for uid, target in self.current_cuts if uid != card.uid]

    def stepped(self, old, knight_jump):
        b = self.b
        self.previous_step = old
        if not knight_jump or not self.has("chess_pendant"):
            return
        if self.knight_mark is None:
            self.knight_mark = b.hero.cell
        elif self.knight_mark == b.hero.cell and b.free(old):
            foes = [f for f in b.foes() if cheb(f.cell, b.hero.cell) <= 1]
            target = yield from self.choose("chess_pendant", foes)
            if target is not None:
                yield from self.relocate(target, old)

    def relocate(self, unit, cell):
        b = self.b
        b.c._place(unit, cell, 0.18)
        yield "move", 0.0, unit
        b._enter(unit, cell)
        yield from b.trigger_trap(unit, cell)

    def changed_stance(self):
        cell = self.previous_step
        if self.b.stance != "knight":
            self.knight_mark = None
        if self.b.stance and self.has("copper_spur") and self.step_card and cell is not None and self.b.free(cell):
            if (yield from self.choose("copper_spur", [cell])) is not None:
                self.step_card = False
                yield from self.relocate(self.b.hero, cell)

    def resonance_target(self, card, target, use):
        item = "tuning_fork"
        b = self.b
        if (not self.ready(item, turn=True) or target is None or card.d.get("type") != "attack"
                or use.get("target") not in ("enemy", "adj") or use.get("pierce")):
            return target
        h = b.hero
        radius = use.get("range", 1) if use["target"] != "adj" else 1
        candidates = [f for f in b.foes() if f is not target and cheb(h.cell, f.cell) <= radius
                      and (not use.get("line") or h.cell[0] == f.cell[0] or h.cell[1] == f.cell[1])
                      and (radius <= 1 or not use.get("los", radius > 1) or b.los(h.cell, f.cell))
                      and not (f.ds.get("veil") and cheb(h.cell, f.cell) > 1)]
        other = yield from self.choose(item, candidates)
        if other is not None:
            self.turn_spent.add(item)
        return other or target

    def after_card(self, card, condition_fired, stepped):
        self.step_card = "step" in card.tag_ids and stepped
        item = "swap_bead"
        if not self.has(item) or not condition_fired:
            return
        self.combos += 1
        b = self.b
        if self.combos == 2 and b.draw_pile:
            chosen = yield from self.choose(item, [c for c in b.hand if c.uid not in self.played
                                                   and self.can_swap(b.draw_pile[-1], c)])
            if chosen is not None:
                top = b.draw_pile.pop()
                b.hand.remove(chosen)
                b.receive_card(top)
                b.draw_pile.append(chosen)

    def after_scroll(self, statue):
        item = "two_faced_chime"
        first, self.last_statue = self.last_statue, statue
        if (self.has(item) and first is not None and first.statue != statue.statue
                and first.alive and statue.alive):
            if (yield from self.accept(item, "Поменять статуи местами")):
                origin = first.cell
                b = self.b
                b.c._place(first, statue.cell, 0.18)
                b.c._place(statue, origin, 0.18)
                yield "move", 0.0, statue

    def area_center(self, center, use):
        item = "oblique_seal"
        b = self.b
        if not self.ready(item, turn=True):
            return center
        radius = use.get("radius", 1)
        if not any(cheb(f.cell, center) <= radius for f in b.foes()):
            return center
        installs = [u for u in b.ballistas if cheb(u.cell, center) <= radius]
        if b.idols:
            installs.extend(u for u in b.idols.statues if u.alive and cheb(u.cell, center) <= radius)
        options = [p for p in cells_near(center) if b.c.grid.get(p) and b.c.grid.get(p).passable
                   and cheb(b.hero.cell, p) <= use.get("range", 5) and b.los(b.hero.cell, p)
                   and any(cheb(u.cell, p) > cheb(u.cell, center) for u in installs)]
        cell = yield from self.choose(item, options)
        if cell is not None:
            self.turn_spent.add(item)
        return cell or center
