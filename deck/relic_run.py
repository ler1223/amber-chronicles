"""Предметы, которые связывают события боя с наградами и следующим боем."""

from . import model as M
from .relic_choice import RelicChoice


TROPHIES = "trophy_book"
LABEL = "vest_label"
DEBT = "debtor_receipt"
MIRROR = "one_name_mirror"
CREST = "scraped_crest"
OATH = "oath_stone"
PACT = "void_pact"

RELICS = {
    TROPHIES: {
        "name": "Книга трофеев", "icon": "gift_word_power", "rarity": "rare",
        "about": "Запоминает тег добивающей карты. Если в следующем бою победишь другим тегом, "
                 "можешь заменить одну карту награды на карту с одним из двух записанных тегов.",
    },
    LABEL: {
        "name": "Бирка на жилете", "icon": "art_belt_common", "rarity": "uncommon",
        "about": "После победы можешь отметить карту [Сохранение] из руки. "
                 "Она ляжет наверх добора первого боя следующего этажа.",
    },
    DEBT: {
        "name": "Квитанция должника", "icon": "gift_word_power", "rarity": "rare",
        "about": "При первом срабатывании [Благословения] в бою можешь передать полученную защиту "
                 "союзной установке. В следующем бою первый платный [Удар] стоит на 1 дороже.",
    },
    MIRROR: {
        "name": "Зеркало одного имени", "icon": "unique_mirror_cloak", "rarity": "rare",
        "about": "Первая [Уникальная], сыгранная сразу после карты с таким же основным тегом, "
                 "запоминает предыдущую. В следующем бою можешь один раз создать её копию. "
                 "Ограничения уникальности сохраняются.",
    },
    CREST: {
        "name": "Счищенный герб", "icon": "art_belt_common", "rarity": "uncommon",
        "about": "Если за бой изгнал три обычные карты с общим тегом, можешь отложить одну из них. "
                 "В следующем бою она вернётся в добор при первой перетасовке.",
    },
    OATH: {
        "name": "Камень зарока", "icon": "mat_ember", "rarity": "rare",
        "about": "В начале боя выбери тег из стартовой руки, для которого есть награда. "
                 "Победа без розыгрыша карт этого тега добавит улучшенную карту с этим тегом.",
    },
    PACT: {
        "name": "Договор с пустотой", "icon": "unique_mirror_cloak", "rarity": "boss",
        "about": "Первый [Финал] за бой сохраняет одну выбранную карту и переносит оставшийся ресурс "
                 "на следующий ход. Другие карты [Финал] в том ходу стоят на 1 дороже.",
    },
}


def primary_tag(card):
    return next((tag for tag in card.tag_ids if tag not in M.card_rules(card.d) and tag != "unique"), None)


def tracked_key(run, card):
    if not getattr(card, "relic_key", None):
        number = run.relic_state.get("tracked_card", 0) + 1
        run.relic_state["tracked_card"] = number
        card.relic_key = number
    return card.relic_key


class RunRelics:
    def __init__(self, battle):
        self.b = battle
        self.run = battle.run
        self.owned = {item["id"] for item in getattr(self.run, "relics", ())} & RELICS.keys()
        self.state = self.run.relic_state
        self.killing_tag = None
        self.active_card = None
        self.last_card = None
        self.hidden = None
        self.exiled = []
        self.oath_tag = None
        self.oath_broken = False
        self.debt_pending = DEBT in self.owned and self.state.pop(DEBT, False)
        self.debt_used = False
        self.pact_used = False
        self.pact_turn = 0
        self.pact_card = None
        self.mirror_recorded = False

    def prepare_pile(self):
        pile = self.b.draw_pile
        if LABEL in self.owned and (label := self.state.get(LABEL)) and self.run.depth >= label["floor"]:
            self.state.pop(LABEL)
            if self.run.depth == label["floor"]:
                card = next((c for c in pile if getattr(c, "relic_key", None) == label["card"]), None)
                if card is not None:
                    pile.remove(card)
                    pile.append(card)
        if CREST in self.owned and (key := self.state.pop(CREST, None)):
            self.hidden = next((c for c in pile if getattr(c, "relic_key", None) == key), None)
            if self.hidden is not None:
                pile.remove(self.hidden)

    def release_held(self):
        hidden, self.hidden = self.hidden, None
        return [hidden] if hidden is not None else []

    def opening(self):
        b = self.b
        if OATH in self.owned:
            tags = sorted({tag for card in b.hand for tag in card.tag_ids
                           if tagged_candidates(self.run, tag, (), insight=True)}, key=M.tag_label)
            if tags:
                self.oath_tag = yield RelicChoice("Камень зарока. Выберите тег", [(M.tag_label(tag), tag) for tag in tags])
        if MIRROR in self.owned and (saved := self.state.pop(MIRROR, None)):
            from .save import card_from
            cid = saved["cid"]
            base = saved.get("definition") or self.run.defs.get(cid)
            if base is None:
                return
            card = card_from(saved, {cid: base}, self.run.data["gods"]["gods"])
            card.rank = saved.get("rank", 1)
            card.heat_payment = saved.get("heat_payment", False)
            if card.d.get("deck_unique") and any(c.cid == cid for c in self.run.deck):
                return
            if b.limits_unique_hand(card) and b.has_unique():
                return
            from .battle import HAND_MAX, PRIEST_HAND
            if len(b.hand) >= (PRIEST_HAND if b.idols is not None else HAND_MAX) and b.merge_partner(card) is None:
                return
            selected = yield RelicChoice("Зеркало одного имени. Создать копию?", [(card.name, card)])
            if selected is not None:
                b.receive_card(selected)
                b.fx("created", unit=b.hero, uid=selected.uid)
                b.queue.append(("create", selected))
                yield from b.react()

    def observe_play(self, card):
        if self.oath_tag and self.oath_tag in card.tag_ids:
            self.oath_broken = True
        if MIRROR not in self.owned:
            return
        prior, self.last_card = self.last_card, card
        if self.mirror_recorded or prior is None or "unique" not in M.card_rules(card.d):
            return
        tag = primary_tag(card)
        if tag and tag == primary_tag(prior):
            from .save import card_to
            self.mirror_recorded = True
            record = card_to(prior)
            record.pop("relic_key", None)
            record.update(rank=prior.rank, heat_payment=prior.heat_payment)
            if prior.cid not in self.run.data["cards"]["cards"]:
                record["definition"] = prior.base
            self.state[MIRROR] = record

    def price(self, card, price, consume):
        if self.pact_turn == self.b.turn and "finale" in M.card_rules(card.d):
            price += 1
        if self.debt_pending and price > 0 and "strike" in card.tag_ids:
            price += 1
            if consume:
                self.debt_pending = False
        return price

    def blessing_target(self, source):
        if source is not self.b.hero or DEBT not in self.owned or self.debt_used:
            return source
        self.debt_used = True
        options = [(u.name, u) for u in self.b.c.units if u.alive and u is not source
                   and u.team == source.team and u.obj]
        if options:
            selected = yield RelicChoice("Квитанция должника. Кому передать защиту?", options)
            if selected is not None:
                self.state[DEBT] = True
                return selected
        return source

    def finale(self):
        if PACT not in self.owned or self.pact_used:
            return
        b = self.b
        self.pact_used = True
        self.pact_turn = b.turn + 1
        # Жар сохраняется сам. У Жреца ресурс следующего хода расходуется как добор свитков.
        if b.mech != "heat":
            b.next_energy += b.energy
        options = [(card.name, card) for card in b.hand]
        if options:
            card = yield RelicChoice("Договор с пустотой. Какую карту сохранить?", options)
            if card is not None:
                self.pact_card = card
                b.temporary_retain.setdefault(card.uid, 0)

    def observe_exhaust(self, card):
        if CREST in self.owned and card in self.run.deck and not card.d.get("token") and card not in self.exiled:
            self.exiled.append(card)

    def observe_victory(self):
        if TROPHIES in self.owned and self.active_card is not None and not self.b.enemy_phase:
            self.killing_tag = primary_tag(self.active_card)

    def victory_choices(self):
        if LABEL in self.owned:
            cards = [card for card in self.b.hand if card in self.run.deck and "retain" in M.card_rules(card.d)]
            if cards:
                yield LABEL, cards
        if CREST in self.owned:
            tags = {tag for c in self.exiled for tag in c.tag_ids
                    if sum(tag in other.tag_ids for other in self.exiled) >= 3}
            cards = [card for card in self.exiled if tags.intersection(card.tag_ids)]
            if cards:
                yield CREST, cards

    def record_choice(self, relic, card):
        self.state[relic] = ({"card": tracked_key(self.run, card), "floor": self.run.depth + 1}
                             if relic == LABEL else tracked_key(self.run, card))

    def reward_tags(self):
        previous = self.state.get(TROPHIES)
        if TROPHIES in self.owned:
            self.state[TROPHIES] = self.killing_tag
        both = (previous, self.killing_tag) if previous and self.killing_tag and previous != self.killing_tag else ()
        return both, self.oath_tag if not self.oath_broken else None


def scroll_actions(definition):
    return definition.get("acts") or [{"m": definition["meaning"], "q": 1 + bool(definition.get("plus")),
                                       "n": 1 + definition.get("repeat", 0)}]


def tagged_candidates(run, tag, offer, *, insight=False):
    used = {card.cid for card in offer}
    if run.hero.get("mechanic") == "idols":
        pool = [cid for cid, d in run.defs.items() if d.get("meaning")]
    else:
        pool = [*run.hero.get("rewards", ()), *run.data["cards"].get("neutral", ())]
    candidates = []
    for cid in dict.fromkeys(pool):
        if cid in used or not run.rewardable(cid) or tag not in M.card_tag_ids(run.defs[cid]):
            continue
        definition = run.defs[cid]
        growth = definition.get("growth") or ()
        if (not insight or (growth and growth[0].get("options"))
                or (definition.get("meaning") and any(act.get("q", 1) < 4 for act in scroll_actions(definition)))):
            candidates.append(cid)
    return candidates


def tagged_card(run, tag, offer, *, insight=False):
    candidates = tagged_candidates(run, tag, offer, insight=insight)
    if not candidates and insight:
        # Награда зарока отдельная: в обычном предложении уже могут лежать все совпадения.
        candidates = tagged_candidates(run, tag, (), insight=True)
    cid = run.weighted_pick(candidates)
    if cid is None:
        return None
    card = M.Card(cid, run.defs)
    if insight:
        if card.growth_next():
            card.pick(run.rng.randrange(len(card.growth_next()["options"])))
        elif card.d.get("meaning"):
            from .idols import make_scroll, scroll_text
            definition = card.d
            acts = [dict(act) for act in scroll_actions(definition)]
            act = run.rng.choice([act for act in acts if act.get("q", 1) < 4])
            act["q"] = act.get("q", 1) + 1
            upgraded = make_scroll(run, acts)
            generated = run.defs[upgraded]
            run.defs[upgraded] = dict(definition, acts=acts, name=generated["name"],
                                      main=dict(definition["main"], say=scroll_text(acts)))
            card = M.Card(upgraded, run.defs)
    return card
