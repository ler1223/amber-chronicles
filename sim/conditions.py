"""Состояния юнита как набор тегов.

Всё, что висит на юните, — тег стихии, оглушение (корни, лёд, сеть…), очарование, провокация, бафф или дебафф,
щит, привязь — это «состояние» со своими тегами. Через теги состояния ищут (условия автокаста, правила),
снимают (очищение снимает «control», «debuff» и стихии; святая вода — только «fire») и показывают.

Теги состояния:
  вид:        element, control, buff, debuff, shield, link
  чем именно: fire, water, ice, storm, poison, oil (стихии); stun, root, net, trap, freeze, shock, blind, sleep,
              stasis, levitate (контроль); charm, taunt (разум); stat:<имя> (бафф)
  свойства:   dot, slow, movement, mind, physical, nature, time, gravity, mark, heal, unremovable
Теги вида контроля и стихий берутся из data/tags.json (groups) и config.control_tags — новые виды добавляются
данными, без кода.
"""
from dataclasses import dataclass, field

DEFAULT_CLEANSE = ("element", "control", "debuff")      # очищение по умолчанию: стихии, контроль, дебаффы


@dataclass
class Cond:
    kind: str                      # status | control | charm | taunt | buff | shield | link
    key: str                       # тег стихии, вид контроля или стат баффа
    tags: frozenset = field(default_factory=frozenset)
    left: float = 0.0
    total: float = 0.0
    name: str = ""


def _buff_good(stat, value):
    if stat in ("armor", "atk_mult"):
        return value > (0 if stat == "armor" else 1)
    if stat in ("slow", "atk_speed"):
        return value < 1
    if stat in ("dmg_taken", "exposed"):
        return value < 1
    if stat == "heal_taken":
        return value >= 1
    return True


def conditions(c, u):
    """Все состояния юнита с тегами."""
    out = []
    tags_cfg = c.tags
    dur = c.cfg["status_duration"]
    for tag, left in u.statuses.items():
        t = tags_cfg.get(tag, {})
        out.append(Cond("status", tag, frozenset({"element", tag, *t.get("groups", [])}), left, dur,
                        t.get("name", tag)))
    if u.stun > 0:
        look = "sleep" if u.asleep else u.stun_look
        extra = c.cfg.get("control_tags", {}).get(look, [])
        out.append(Cond("control", look, frozenset({"control", look, *extra}), u.stun, u.stun_total, look))
    if u.charm_time > 0:
        out.append(Cond("charm", "charm", frozenset({"control", "charm", "mind"}), u.charm_time, u.charm_time,
                        "очарование"))
    if u.taunted_by is not None and u.taunt_time > 0:
        out.append(Cond("taunt", "taunt", frozenset({"control", "taunt", "mind"}), u.taunt_time, u.taunt_time,
                        "провокация"))
    for stat, (value, left) in u.buffs.items():
        good = _buff_good(stat, value)
        tags = {"buff" if good else "debuff", f"stat:{stat}"}
        if stat == "slow" and not good:
            tags |= {"slow", "movement"}
        if stat == "regen":
            tags.add("heal")
        if stat == "exposed":
            tags.add("mark")
        if stat in ("undying", "trance", "stealth"):
            tags.add("unremovable")              # часть собственной механики героя
        out.append(Cond("buff", stat, frozenset(tags), left, u.buff_total.get(stat, left), stat))
    if u.shield > 0:
        out.append(Cond("shield", "shield", frozenset({"buff", "shield"}), u.shield_time, u.shield_time, "щит"))
    if u.tethered_by is not None or u.guarded_by is not None:
        out.append(Cond("link", "link", frozenset({"link", "buff"}), max(u.tether_time, u.guard_time), 0, "связь"))
    return out


def unit_tags(c, u):
    """Объединение тегов всех состояний юнита (для условий и правил)."""
    out = set()
    for cond in conditions(c, u):
        out |= cond.tags
    return out


def has(c, u, tag):
    return tag in unit_tags(c, u)


def removable(c, u, tags=DEFAULT_CLEANSE):
    """Состояния, которые снимет очищение с этими тегами (любой из тегов; «unremovable» не снимается)."""
    want = set(tags)
    return [cond for cond in conditions(c, u) if cond.tags & want and "unremovable" not in cond.tags]


def remove(c, u, tags=DEFAULT_CLEANSE, limit=None):
    """Снять состояния с любым из тегов. Возвращает снятые состояния."""
    gone = removable(c, u, tags)
    if limit is not None:
        gone = gone[:limit]
    for cond in gone:
        k = cond.kind
        if k == "status":
            u.statuses.pop(cond.key, None)
        elif k == "control":
            u.stun, u.asleep = 0.0, False
            if cond.key == "levitate":
                u.levitate = 0.0             # снятая невесомость — мягкая посадка, без урона
            if cond.key == "stasis":
                u.stasis = 0.0
        elif k == "charm":
            u.charm_time = 0.0
            u.order, u.last_target = None, None
        elif k == "taunt":
            u.taunted_by, u.taunt_time = None, 0.0
        elif k == "buff":
            u.buffs.pop(cond.key, None)
        elif k == "shield":
            u.shield, u.shield_time = 0, 0.0
        elif k == "link":
            u.tethered_by, u.tether_time = None, 0.0
            u.guarded_by, u.guard_time = None, 0.0
    return gone
