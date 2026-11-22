"""Сохранение забега «Спуска»: забег пишется сам, когда герой возвращается на карту этажа (после боя и наград,
костра, торговца, сундука, мастерской), и стирается, когда забег кончился. Продолжить — с выбора героя.

Файл — save/descent_run.json (рядом с настройками). Бой в процессе не сохраняется: продолжение — с карты этажа.
"""
import json
import os
import random

from . import model as M

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "save", "descent_run.json")
VERSION = 1


def card_to(c):
    d = {"cid": c.cid, "picks": list(c.picks), "uses": c.uses,
         "insight_ready": bool(c.ready), "insight_misses": c.insight_misses}
    if c.alt_up is not None:
        d["alt_up"] = c.alt_up
    if c.divine:
        d["divine"] = c.divine.get("id")
    return d


def card_from(d, defs, gods):
    c = M.Card(d["cid"], defs, uses=d.get("uses", 0), picks=d.get("picks", []),
               insight_ready=d.get("insight_ready", False), insight_misses=d.get("insight_misses", 0))
    if d.get("alt_up") is not None:
        c.alt_up = d["alt_up"]
    if d.get("divine") and d["divine"] in gods:
        c.divine = gods[d["divine"]]
    return c


def run_to(run, node=None):
    """Забег → словарь для JSON."""
    base = run.data["cards"]["cards"]
    extra = {c.cid: run.defs[c.cid] for c in run.deck if c.cid not in base and c.cid in run.defs}
    st = run.rng.getstate()
    fl = run.floor
    return {
        "version": VERSION,
        "hero": run.hero_id, "variant": run.variant,
        "hp": run.hp, "max_hp": run.max_hp, "gold": run.gold, "depth": run.depth, "fight": run.fight,
        "kills": run.kills, "remove_price": run.remove_price,
        "deck": [card_to(c) for c in run.deck], "defs": extra,
        "relics": [r["id"] for r in run.relics],
        "relic_state": getattr(run, "relic_state", {}),
        "god_xp": run.god_xp, "god_picks": {g: [list(p) for p in v] for g, v in run.god_picks.items()},
        "god_pending": [list(p) for p in run.god_pending],
        "rng": [st[0], list(st[1]), st[2]],
        "floor": {"depth": fl.depth, "nodes": fl.nodes, "node": fl.node, "path": fl.path} if fl else None,
        "node": node,
    }


def run_from(data, d):
    """Словарь → забег (данные игры — нынешние: правки карт и врагов подхватываются)."""
    from .floor import Floor
    run = M.Run.__new__(M.Run)
    run.data = data
    run.rng = random.Random()
    r = d["rng"]
    run.rng.setstate((r[0], tuple(r[1]), r[2]))
    run.defs = dict(data["cards"]["cards"])
    run.defs.update(d.get("defs", {}))
    h = data["heroes"]["heroes"][d["hero"]]
    run.hero_id, run.hero, run.hero_name, run.sprite = d["hero"], h, h["name"], h["sprite"]
    run.variant = d.get("variant")
    run.max_hp, run.hp = d["max_hp"], d["hp"]
    gods = data["gods"]["gods"]
    run.deck = [card_from(c, run.defs, gods) for c in d["deck"] if c["cid"] in run.defs]
    run.fight, run.result = d.get("fight", 0), None
    run.gold, run.depth, run.kills = d["gold"], d["depth"], d.get("kills", 0)
    run.remove_price = d.get("remove_price", data["enemies"]["shop"]["remove_price"])
    run.god_xp = d.get("god_xp", {})
    run.god_picks = {g: [tuple(p) for p in v] for g, v in d.get("god_picks", {}).items()}
    run.god_pending = [tuple(p) for p in d.get("god_pending", [])]
    rel = data["relics"]["relics"]
    run.relics = [dict(rel[i], id=i) for i in d.get("relics", []) if i in rel]
    run.relic_state = dict(d.get("relic_state", {}))
    f = d.get("floor")
    if f:
        fl = Floor.__new__(Floor)
        fl.depth, fl.nodes, fl.node, fl.path = f["depth"], f["nodes"], f["node"], f["path"]
        run.floor = fl
    else:
        run.floor = None
        run.next_floor()
    return run


def save(run, node=None, path=PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(run_to(run, node), f, ensure_ascii=False)
    os.replace(tmp, path)                                # не оставить полузаписанный файл


def load(data, path=PATH):
    """(забег, id узла) или None, если сохранения нет или оно не читается."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("version") != VERSION:
            return None
        return run_from(data, d), d.get("node")
    except (OSError, ValueError, KeyError, TypeError):
        return None


def exists(path=PATH):
    return bool(path) and os.path.exists(path)


def delete(path=PATH):
    try:
        os.remove(path)
    except OSError:
        pass
