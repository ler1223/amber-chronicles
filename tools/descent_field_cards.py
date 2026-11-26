"""Стойки Наёмника, баллиста Охотницы, духи Пиромантки и нейтральный Слепок.

Запускать после генераторов карт и тиров:
    python tools/descent_field_cards.py
"""
import json
from pathlib import Path

from descent_cards_czn import cell, lv, make, per, token
from descent_epiphanies import IF, W, enemy, ifs, step
from descent_hunter_more import B, V, add_op, me, op


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "deck"


def card(name, owner, cost, art, ill, main, tags, options=None, *, battle_only=False, deck_unique=False):
    definition = {
        "ill": ill,
        "art": art,
        "name": name,
        "cost": cost,
        "type": "skill",
        "main": main,
        "alt": {"target": "none", "do": []},
        "tags": tags,
        "category": "token" if battle_only else ("hero" if owner else "neutral"),
        "rarity": 0 if battle_only else 1,
    }
    if battle_only:
        definition["battle_only"] = True
    else:
        definition["growth"] = [{"uses": 3, "options": options}]
    if owner:
        definition["owner"] = owner
    if deck_unique:
        definition.update(unique=True, deck_unique=True)
    return definition


def stances():
    ready_stance = op("stance", id="ready")
    ready = me(B(2), ready_stance)
    knight_stance = op("stance", id="knight")
    knight = me(knight_stance)
    guard_stance = op("stance", id="guard")
    guard = me(guard_stance, B(3))
    return {
        "m_stance_ready": card(
            "Боевая стойка", "merc", 1, "stance_ready", ["bellows_hall", 0.472, 0.421, 0.70],
            ready, ["Защита"], [
                V("Начальная защита 4", me(B(4), ready_stance)),
                V("С добором", add_op(ready, op("draw", 1))),
                V("С контратакой", add_op(ready, op("counter", 1))),
                V("С обороной", add_op(ready, op("fort", 1))),
                V("Сохранение", retain=True),
            ],
        ),
        "m_stance_knight": card(
            "Стойка коня", "merc", 1, "stance_knight", ["guard_bridge", 0.563, 0.421, 0.68],
            knight, [], [
                V("С начальной защитой", add_op(knight, B(2))),
                V("С разгоном", add_op(knight, op("momentum", 1))),
                V("С добором", add_op(knight, op("draw", 1))),
                V("С контратакой", add_op(knight, op("counter", 1))),
                V("Сохранение", retain=True),
            ],
        ),
        "m_stance_guard": card(
            "Глухая оборона", "merc", 1, "stance_guard", ["guild_toll", 0.633, 0.439, 0.70],
            guard, ["Защита"], [
                V("Начальная защита 4", me(guard_stance, B(4))),
                V("С обороной", add_op(guard, op("fort", 1))),
                V("С контратакой", add_op(guard, op("counter", 1))),
                V("С добором", add_op(guard, op("draw", 1))),
                V("Сохранение", retain=True),
            ],
        ),
    }


def ballista_cards():
    place = {"target": "ballista_place", "range": 2, "do": [op("ballista_place")]}
    load = {"target": "ballista_load", "range": 2, "do": [B(3), op("ballista_load", 2)]}
    fire = {"target": "ballista_fire", "range": 6, "do": [op("ballista_fire", 5, per_charge=3)]}
    return {
        "h_ballista": card(
            "Баллиста", "hunter", 2, "ballista_card", ["smith_cart", 0.563, 0.436, 0.65],
            place, [], [
                V("Дальность установки 3", dict(place, range=3)),
                V("Подготовленный заряд", dict(place, do=[op("ballista_place", charge=1)])),
                V("Прочность 17", dict(place, do=[op("ballista_place", hp=17)])),
                V("С защитой", add_op(place, B(4))),
                V("Сохранение", retain=True),
            ], deck_unique=True,
        ),
        "h_ballista_load": card(
            "Зарядить баллисту", "hunter", 0, "ballista_load", ["witch_hunters", 0.573, 0.478, 0.67],
            load, ["Защита"], battle_only=True,
        ),
        "h_ballista_fire": card(
            "Залп баллисты", "hunter", 0, "ballista_fire", ["archer_ambush", 0.652, 0.451, 0.64],
            fire, ["Выстрел"], battle_only=True,
        ),
    }


def hand_copy_card():
    use = {"target": "copy_hand", "do": [op("copy_hand")]}
    return card(
        "Слепок", None, 0, "unique_mirror_cloak", ["obsidian_mirror", 0.582, 0.441, 0.67],
        use, [], [
            V("С защитой", add_op(use, B(2))),
            V("С добором", add_op(use, op("draw", 1))),
            V("С контратакой", add_op(use, op("counter", 1))),
            V("С обороной", add_op(use, op("fort", 1))),
            V("Сохранение", retain=True),
        ], deck_unique=True,
    )


def spirit_token(name, art, ill, use):
    return dict(token(name, art, use, ill[0]), type="skill", ill=ill, tags=["spirit"], category="token", rarity=0,
                alt={"target": "none", "do": []})


def ranked_spirit(name, art, ill, *ranks, **properties):
    ranked_uses = [{"main": use, "reactions": {"retained": [retain]}} for use, retain in ranks]
    return dict(spirit_token(name, art, ill, ranks[0][0]), rules=["retain", "merge"],
                ranks=ranked_uses, **properties)


def spirit_tokens():
    ember_aim = {"rng": 3, "los": True, "ranged": True, "vfx": "e_fireball"}
    draft_aim = {"rng": 3, "los": True}
    draft_buffs = [op("card_damage_buff", n, tag="fire", type="attack") for n in (2, 3, 4)]
    return {
        "t_spirit_ember": ranked_spirit(
            "Дух угля", "mat_coal", ["ember_orphans", 0.464, 0.396, 0.64],
            (enemy(op("damage", 4), **ember_aim), op("temper_card", 2)),
            (enemy(op("damage", 7), op("spirit_ignite", 0), **ember_aim), op("temper_card", 3)),
            (enemy(op("damage", 11), op("spirit_ignite", 1), **ember_aim), op("temper_card", 5)),
            type="attack", element="fire",
        ),
        "t_spirit_draft": ranked_spirit(
            "Дух тяги", "unique_spirit_catcher", ["bellows_hall", 0.581, 0.395, 0.62],
            (enemy(op("pull", 1), **draft_aim), draft_buffs[0]),
            (enemy(op("pull", 2), **draft_aim), draft_buffs[1]),
            (enemy(op("pull", 2, burn_on_move=2), **draft_aim), draft_buffs[2]),
        ),
        "t_spirit_ash": ranked_spirit(
            "Дух пепла", "gift_ash_heart", ["ash_storm", 0.587, 0.421, 0.63],
            (me(B(3)), op("heal", 2)),
            (me(B(5), op("reduce_burn", 1)), op("heal", 3)),
            (step(1, B(6), op("reduce_burn", 1), allow_stay=True), op("heal", 4)),
        ),
        "t_elemental_forge": spirit_token(
            "Кузнечный элементаль", "mat_embersteel", ["ghost_forge", 0.614, 0.431, 0.68], cell(4, op("ignite", 1)),
        ),
        "t_elemental_ash": spirit_token(
            "Пепельный элементаль", "unique_ash_cloak", ["ash_nest", 0.621, 0.451, 0.67], step(2, B(6)),
        ),
    }


def pyro_card(name, heat, art, ill, use, options, *, rarity=1):
    choices = [V(label, levels=lv((heat, upgraded))) for label, upgraded in options]
    choices.append(V("Сохранение", retain=True))
    definition = card(name, "pyro", heat, art, ill, use, [], choices)
    return dict(definition, levels=lv((heat, use)), rarity=rarity)


def pyro_levels(name, art, ill, uses, options=()):
    levels = lv(*enumerate(uses, 1))
    choices = [V(label, levels=lv(*enumerate(upgraded, 1))) for label, upgraded in options]
    choices.append(V("Сохранение", retain=True))
    return dict(card(name, "pyro", 1, art, ill, uses[0], [], choices), levels=levels)


def retain_insights(uses):
    return [(label, [add_op(use, effect) for use in uses]) for label, effect in (
        ("С прикрытием", B(2)),
        ("С добором", op("draw", 1)),
        ("С запасом", op("next_draw", 1)),
        ("С обороной", op("fort", 1)),
    )]


def retain_cards():
    activate = op("trigger_retain", 1)
    stoke = (
        {"target": "hand_retain", "do": [B(2), activate]},
        {"target": "hand_retain", "count": 2, "do": [B(4), activate]},
        {"target": "hand_retain", "do": [B(4), op("trigger_retain", 2), op("create_retain", 1)]},
    )
    ash = (
        {"target": "hand_other", "do": [B(4), op("grant_retain", 0)]},
        {"target": "hand_other", "count": 2, "do": [B(6), op("grant_retain", 0)]},
        {"target": "hand_other", "do": [B(8), op("grant_retain", 1)]},
    )
    forge = (me(B(4), op("retain_rewards", 1)),
             me(B(5), op("retain_rewards", 0, block=2)),
             me(B(6), op("retain_rewards", 1, block=2)))
    return {
        "p_stoke_embers": pyro_levels("Раздуть угли", "mat_emberheart", ["ember_orphans", 0.62, 0.46, 0.69],
                                     stoke, retain_insights(stoke)),
        "p_ash_cover": pyro_levels("Под слоем пепла", "gift_ash_heart", ["ash_storm", 0.59, 0.42, 0.63],
                                  ash, retain_insights(ash)),
        "p_forge_patience": pyro_levels("Выдержка горна", "mat_embersteel", ["ghost_forge", 0.61, 0.43, 0.68],
                                       forge, retain_insights(forge)),
    }


def spirit_cards():
    summon = op("add_card", 1, pool=["t_spirit_ember", "t_spirit_draft", "t_spirit_ash"], pool_name="Огненные духи")
    elemental = op("add_card", 1, pool=["t_elemental_forge", "t_elemental_ash"], pool_name="Огненные элементали")
    after_spirit = W("after", tag="spirit")
    evoke_elemental = ifs(IF(after_spirit, do=[elemental]))
    living = (me(summon), me(dict(summon, n=2, distinct=True)), me(dict(summon, n=2, same=True)))
    coal = make("t_spirit_ember", 1, "Дух угля")
    circle = me(B(6), **evoke_elemental)
    spirit_count = per("tag:spirit", 1)
    pull = op("pull", 1, per=spirit_count)
    draft = enemy(pull, rng=4, los=True)
    return {
        "p_living_embers": pyro_levels(
            "Живые угли", "mat_emberheart", ["ember_orphans", 0.623, 0.459, 0.69], living, [
                ("Под прикрытием", [add_op(use, B(2)) for use in living]),
                ("Зов угля", [me(coal), me(dict(summon, n=2, distinct=True, first="t_spirit_ember")),
                             me(dict(coal, n=2))]),
                ("С шагом", [step(1, *use["do"]) for use in living]),
                ("С добором", [add_op(use, op("draw", 1)) for use in living]),
            ],
        ),
        "p_spirit_circle": pyro_card(
            "Круг призыва", 2, "fx_spirit", ["hungry_spirit", 0.589, 0.451, 0.64], circle, [
                ("Защита 9", me(B(9), **evoke_elemental)),
                ("Шаг к кругу", step(1, B(6), **evoke_elemental)),
                ("Зов кузни", me(B(6), **ifs(IF(after_spirit, do=[
                    make("t_elemental_forge", 1, "Кузнечный элементаль"),
                ])))),
                ("С обороной", add_op(circle, op("fort", 1))),
            ], rarity=2,
        ),
        "p_furnace_draft": pyro_card(
            "Тяга горна", 1, "gift_fire_soul", ["bellows_hall", 0.647, 0.453, 0.66], draft, [
                ("Дальность 5", dict(draft, range=5)),
                ("Поджечь клетку", add_op(draft, op("ignite", 0))),
                ("Сильнее притянуть", enemy(op("pull", 2, per=spirit_count), rng=4, los=True)),
                ("Ослабить", add_op(draft, op("weak", 1))),
            ],
        ),
    }


def main():
    cards_path = DATA_DIR / "cards.json"
    heroes_path = DATA_DIR / "heroes.json"
    cards_data = json.loads(cards_path.read_text(encoding="utf-8"))
    heroes_data = json.loads(heroes_path.read_text(encoding="utf-8"))
    cards_data["cards"]["n_hand_copy"] = hand_copy_card()
    cards_data["neutral"] = sorted(set(cards_data["neutral"]) | {"n_hand_copy"})
    cards_data["cards"].update(spirit_tokens())
    ballista = ballista_cards()
    commands = {cid for cid, definition in ballista.items() if definition.get("battle_only")}
    for hero in heroes_data["heroes"].values():
        pools = [hero.get("starter", []), hero.get("rewards", [])]
        for key in ("starter_by_variant", "rewards_by_variant", "reward_guarantee"):
            pools.extend(hero.get(key, {}).values())
        for pool in pools:
            pool[:] = [cid for cid in pool if cid not in commands]

    groups = (
        ("merc", ("press",), stances()),
        ("hunter", ("range", "quiver"), ballista),
        ("pyro", ("ash",), {**spirit_cards(), **retain_cards()}),
    )
    for hero_id, variants, cards in groups:
        cards_data["cards"].update(cards)
        hero = heroes_data["heroes"][hero_id]
        pools = [hero["rewards"], *(hero["rewards_by_variant"][variant] for variant in variants)]
        reward_cards = [cid for cid in cards if cid not in commands]
        for pool in pools:
            pool[:] = list(dict.fromkeys([*pool, *reward_cards]))
    cards_path.write_text(json.dumps(cards_data, ensure_ascii=False, indent=1), encoding="utf-8")
    heroes_path.write_text(json.dumps(heroes_data, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
