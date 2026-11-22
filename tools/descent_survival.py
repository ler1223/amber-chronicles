"""Выживаемость Наёмника, Охотницы и Пиромантки (квиз 2026-11-21, балансировка): карты «ударить и не получить в
ответ» — удар с отходом, оборона (половина защиты на следующий ход), лечение; у каждой 5 прозрений. Плюс ресурс:
+10 HP, рука 6 (лечение 10% после боя — в deck/game.py).

Пишет в data/deck/cards.json и data/deck/heroes.json. Запуск: python tools/descent_survival.py
(после tools/descent_epiphanies.py, если он перезапускался).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from descent_epiphanies import IF, B, D, V, W, adj, enemy, ifs, me, op, step  # noqa: E402

D_ = os.path.join(ROOT, "data", "deck")


def shot(rng, *ops, **kw):
    return enemy(*ops, rng=rng, los=True, ranged=True, **kw)


def lv(*levels):
    """Уровни Пиромантки: [(жар, применение)]."""
    return [{"heat": h, "main": m} for h, m in levels]


def card(name, typ, ill, art, main=None, alt=None, cost=1, levels=None, variants=(), **kw):
    c = {"ill": [ill, 0.5, 0.5, 0.5], "art": art, "name": name, "cost": cost, "type": typ, "alt": alt}
    if levels:
        c["levels"] = levels
        c["main"] = levels[0]["main"]
    else:
        c["main"] = main
    c.update(kw)
    opts = []
    for v in variants:
        if "main" in v and main is not None and main.get("vfx"):
            v["main"].setdefault("vfx", main["vfx"])
        opts.append(v)
    assert len(opts) == 5, name
    c["growth"] = [{"uses": 3, "options": opts}]
    return c


def LV(label, name, levels):
    v = {"label": label, "levels": levels}
    if name:
        v["name"] = name
    return v


CARDS = {
    # ---------- Наёмник ----------
    "m_hit_back": card("Удар с отходом", "attack", "training", "item_blade",
                       main=enemy(D(6), op("retreat", 2), vfx="power_strike"), alt=step(1),
                       variants=[V("Сильнее", enemy(D(8), op("retreat", 2))),
                                 V("Дальше отскок", enemy(D(6), op("retreat", 3)), "Отскок"),
                                 V("С толчком", enemy(D(5), op("push", 1), op("retreat", 2)), "Удар и отход"),
                                 V("Под щитом", enemy(D(6), op("retreat", 2), B(4)), "Отход под щитом"),
                                 V("Набрать ход", enemy(D(6), op("retreat", 2), op("momentum", 2)), "Отход с разгоном")]),
    "m_bastion": card("Глухая оборона", "skill", "abandoned_camp", "fx_phoenix_shield",
                      main=me(B(8), op("fort", 1), vfx="shield_wall"), alt=me(B(2)),
                      variants=[V("Крепче", me(B(11), op("fort", 1))),
                                V("Колючая", me(B(8), op("fort", 1), op("thorns", 3)), "Колючая оборона"),
                                V("Передышка", me(B(8), op("fort", 1), op("draw", 1)), "Передышка"),
                                V("Перевязка", me(B(6), op("fort", 1), op("heal", 3)), "Перевязка"),
                                V("Стена", me(B(14)), "Стена")]),
    "m_leech": card("Жадный удар", "attack", "hungry_spirit", "item_blade",
                    main=enemy(D(6), op("heal", 4), vfx="blood_strike"), alt=enemy(D(2)),
                    variants=[V("Сильнее", enemy(D(8), op("heal", 5))),
                              V("Жажда", enemy(D(6), op("heal", 4), **ifs(IF(W("hurt"), plus=4))), "Жажда крови"),
                              V("Кровь за кровь", enemy(D(6), op("heal", 4), op("thorns", 2)), "Кровь за кровь"),
                              V("Кровавый круг", me(adj(D(5)), op("heal", 4)), "Кровавый круг"),
                              V("Пить досуха", enemy(D(6), op("heal", 6)), "Пить досуха")]),
    # ---------- Охотница ----------
    "h_shoot_roll": card("Выстрел с перекатом", "attack", "runaway_apprentice", "item_bow",
                         main=shot(4, D(5), op("retreat", 2), vfx="vault_shot"), alt=step(1),
                         variants=[V("Сильнее", shot(4, D(7), op("retreat", 2))),
                                   V("Длинный перекат", shot(5, D(5), op("retreat", 3)), "Длинный перекат"),
                                   V("Ядовитый", shot(4, D(4), op("poison", 2), op("retreat", 2)), "Ядовитый отход"),
                                   V("Прикрыться", shot(4, D(5), op("retreat", 2), B(4)), "Отход под прикрытием"),
                                   V("Метка", shot(4, D(5), op("mark", 3), op("retreat", 2)), "Метка и отход")]),
    "h_brush": card("Укрытие в зарослях", "skill", "witch_hut", "gift_heron_eye",
                    main=me(B(7), op("fort", 1), vfx="vanish"), alt=step(1),
                    variants=[V("Крепче", me(B(10), op("fort", 1))),
                              V("Затаиться", me(B(7), op("fort", 1), op("draw", 1)), "Затаиться"),
                              V("Колючие заросли", me(B(7), op("fort", 1), op("thorns", 3)), "Колючие заросли"),
                              V("Уйти в заросли", step(2, B(6)), "Уйти в заросли"),
                              V("Выжидать", me(B(7), op("focus")), "Выжидать")]),
    "h_herbs": card("Целебные травы", "skill", "hot_springs", "gift_heron_eye",
                    main=me(op("heal", 6), op("draw", 1), vfx="healing_potion"), alt=me(B(2)),
                    variants=[V("Сильнее", me(op("heal", 9), op("draw", 1))),
                              V("С повязкой", me(op("heal", 6), B(5)), "Травы и повязка"),
                              V("Отвар", me(op("heal", 5), op("draw", 2)), "Отвар"),
                              V("Очищение", me(op("heal", 6), op("cleanse"), op("draw", 1)), "Очищающий настой"),
                              V("Бодрость", me(op("heal", 5), op("energy", 1)), "Бодрящий настой")]),
    # ---------- Пиромантка (уровни за жар) ----------
    "p_barrier": card("Огненный барьер", "skill", "ghost_forge", "fx_phoenix_shield",
                      levels=lv((1, me(B(5), adj(op("burn", 1)), vfx="flame_wall")),
                                (2, me(B(8), adj(op("burn", 2)), vfx="flame_wall")),
                                (3, me(B(10), op("fort", 1), adj(op("burn", 3)), vfx="flame_wall"))),
                      alt=me(op("heat", 1)),
                      variants=[LV("Крепче", None, lv((1, me(B(7), adj(op("burn", 1)), vfx="flame_wall")),
                                                       (2, me(B(10), adj(op("burn", 2)), vfx="flame_wall")),
                                                       (3, me(B(13), op("fort", 1), adj(op("burn", 3)), vfx="flame_wall")))),
                                LV("Держать жар", "Тлеющий барьер",
                                   lv((1, me(B(5), op("fort", 1), adj(op("burn", 1)), vfx="flame_wall")),
                                      (2, me(B(8), op("fort", 1), adj(op("burn", 2)), vfx="flame_wall")),
                                      (3, me(B(10), op("fort", 1), adj(op("burn", 4)), vfx="flame_wall")))),
                                LV("Отбросить", "Взрывной барьер",
                                   lv((1, me(B(5), adj(op("push", 1)), vfx="flame_wall")),
                                      (2, me(B(7), adj(op("burn", 2), op("push", 1)), vfx="flame_wall")),
                                      (3, me(B(9), adj(op("burn", 3), op("push", 2)), vfx="flame_wall")))),
                                LV("Шипы пламени", "Пылающие шипы",
                                   lv((1, me(B(4), op("thorns", 3), vfx="flame_wall")),
                                      (2, me(B(7), op("thorns", 4), vfx="flame_wall")),
                                      (3, me(B(9), op("thorns", 6), op("fort", 1), vfx="flame_wall")))),
                                LV("Остыть", "Холодный барьер",
                                   lv((1, me(B(6), op("heat", -1), vfx="frost_guard")),
                                      (2, me(B(9), op("heat", -1), vfx="frost_guard")),
                                      (3, me(B(12), op("fort", 1), vfx="frost_guard"))))]),
    "p_ashstep": card("Пепельный шаг", "skill", "ash_nest", "fx_phoenix_shield",
                      levels=lv((1, step(2, B(3), vfx="blink")), (2, step(3, B(5), vfx="blink")),
                                (3, step(3, B(6), op("fort", 1), vfx="flashover"))),
                      alt=me(op("heat", 1)),
                      variants=[LV("Дальше", None, lv((1, step(3, B(3), vfx="blink")), (2, step(4, B(5), vfx="blink")),
                                                      (3, step(4, B(6), op("fort", 1), vfx="flashover")))),
                                LV("Крепче", "Пепельный покров", lv((1, step(2, B(5), vfx="blink")),
                                                                    (2, step(3, B(7), vfx="blink")),
                                                                    (3, step(3, B(9), op("fort", 1), vfx="flashover")))),
                                LV("Огненный след", "Огненный след",
                                   lv((1, step(2, B(3), op("ignite", 0), vfx="blink")),
                                      (2, step(3, B(5), op("ignite", 0), vfx="blink")),
                                      (3, step(3, B(6), op("ignite", 1), vfx="flashover")))),
                                LV("Добрать", "Пепел и знание", lv((1, step(2, op("draw", 1), vfx="blink")),
                                                                   (2, step(3, B(4), op("draw", 1), vfx="blink")),
                                                                   (3, step(3, B(6), op("draw", 2), vfx="flashover")))),
                                LV("Раздуть", "Шаг сквозь жар", lv((1, step(2, B(3), op("heat", 1), vfx="blink")),
                                                                    (2, step(3, B(5), op("heat", 1), vfx="blink")),
                                                                    (3, step(3, B(6), op("heat", 2), vfx="flashover"))))]),
    "p_breath": card("Дыхание феникса", "skill", "fire_ale", "fx_phoenix_shield",
                     levels=lv((1, me(op("heal", 3), vfx="phoenix")), (2, me(op("heal", 5), B(3), vfx="phoenix")),
                               (3, me(op("heal", 7), B(5), vfx="phoenix"))),
                     alt=me(op("heat", 1)),
                     variants=[LV("Сильнее", None, lv((1, me(op("heal", 4), vfx="phoenix")),
                                                      (2, me(op("heal", 7), B(3), vfx="phoenix")),
                                                      (3, me(op("heal", 9), B(6), vfx="phoenix")))),
                               LV("Пламя внутри", "Пламя внутри", lv((1, me(op("heal", 3), op("heat", 1), vfx="phoenix")),
                                                                    (2, me(op("heal", 5), op("heat", 1), vfx="phoenix")),
                                                                    (3, me(op("heal", 7), op("heat_regen", 1), vfx="phoenix")))),
                               LV("Очищение", "Очищающее пламя", lv((1, me(op("heal", 3), op("cleanse"), vfx="phoenix")),
                                                                     (2, me(op("heal", 5), op("cleanse"), vfx="phoenix")),
                                                                     (3, me(op("heal", 7), op("cleanse"), B(4), vfx="phoenix")))),
                               LV("Вспышка", "Вспышка феникса", lv((1, me(op("heal", 2), adj(op("burn", 2)), vfx="phoenix")),
                                                                    (2, me(op("heal", 4), adj(op("burn", 3)), vfx="phoenix")),
                                                                    (3, me(op("heal", 6), adj(op("burn", 4)), vfx="phoenix")))),
                               LV("Добрать", "Перерождение", lv((1, me(op("heal", 3), op("draw", 1), vfx="phoenix")),
                                                                (2, me(op("heal", 4), op("draw", 1), B(3), vfx="phoenix")),
                                                                (3, me(op("heal", 6), op("draw", 2), vfx="phoenix"))))]),
}
EXTRA = {"merc": {"energy": 4}, "pyro": {"heat_turn": 2}}      # ресурс: Наёмнику 4 энергии, Пиромантке +2 жара за ход
HERO = {"merc": (["m_hit_back", "m_bastion", "m_leech"], "m_hit_back", 80),
        "hunter": (["h_shoot_roll", "h_brush", "h_herbs"], "h_shoot_roll", 70),
        "pyro": (["p_barrier", "p_ashstep", "p_breath"], "p_ashstep", 72)}


def main():
    p = os.path.join(D_, "cards.json")
    c = json.load(open(p, encoding="utf-8"))
    c["cards"].update(CARDS)
    json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    p = os.path.join(D_, "heroes.json")
    h = json.load(open(p, encoding="utf-8"))
    for hid, (new, starter, hp) in HERO.items():
        hd = h["heroes"][hid]
        for cid in new:
            if cid not in hd["rewards"]:
                hd["rewards"].append(cid)
        if starter not in hd["starter"]:
            hd["starter"].append(starter)
        hd["hp"] = hp
        hd["hand"] = 6
        hd.update(EXTRA.get(hid, {}))
    json.dump(h, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok:", len(CARDS), "карт выживания")


if __name__ == "__main__":
    main()
