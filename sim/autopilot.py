"""Умный автопилот: какой навык применить сейчас.

Для всех классов — порядок навыков, как у автокаста, но без навыков, которые сейчас не сработают (шкала, знамя,
условие ультимейта, облик): необычные классы больше не застревают. По желанию (scored) — выбор по оценке пользы:
урон по скольким врагам, сколько недостающего здоровья вылечит, щит при врагах рядом, контроль, призыв.
Цель подбирает тот же код, что и автокаст (sim/autocast.py).

Бард играет мелодиями: выбирает мелодию по обстановке (раненые союзники — Песнь жизни или Серенада, враг кастует —
Колыбельная, толпа рядом — Волна, иначе — Марш или Диссонанс) и нажимает её ноты по порядку, учитывая уже сыгранные;
Финал — когда мелодия сыграна и рядом враги.

Работает для отряда в демо и боте (AutoCaster(force=True)), для барда — и при включённом автокасте нот, и как
учитель нейросети в режиме обучения (sim/neural.py).
"""
from . import kit
from .autocast import flat_effects
from .grid import cheb

MIN_SCORE = 0.25


def _area(c, u, center, r, foes=True):
    group = c.foes_of(u) if foes else c.fighters(u.team)
    cell = center.cell if hasattr(center, "cell") else tuple(center)
    return [v for v in group if cheb(v.cell, cell) <= r and not v.obj]


def score(c, u, sid, sk, target):
    """Польза навыка по цели: ~1 — обычный удар по одному врагу."""
    if target is None:
        return 0.0
    effs = flat_effects(sk)
    types = {e["type"] for e in effs}
    r = sk.get("radius", 0)
    s = 0.0
    if types & {"damage", "line", "chain", "detonate", "shatter", "collapse", "push", "rush", "toss"}:
        n = len(_area(c, u, target, max(r, 0))) if (r or not hasattr(target, "team")) else 1
        s += 1.0 * max(1, n) if n else 0.0
    heal = [e for e in effs if e["type"] == "heal"]
    if heal:
        allies = _area(c, u, target, r, foes=False) if r else ([target] if hasattr(target, "hp") else [])
        missing = sum(1 - a.hp / a.max_hp for a in allies if a.alive)
        s += 2.2 * missing
    if types & {"shield", "buff"} and any(cheb(f.cell, u.cell) <= 3 for f in c.foes_of(u)):
        s += 0.6
    if types & {"stun", "sleep", "taunt", "silence"}:
        tgt = _area(c, u, target, r) if r else ([target] if hasattr(target, "cast") else [])
        s += sum(1.5 if v.cast else 0.6 for v in tgt)
    if types & {"summon", "corpse", "raise_all"}:
        mine = sum(1 for v in c.units if v.alive and v.owner is u)
        s += max(0.0, 1.2 - 0.4 * mine)
    if "form" in types:
        s += 0.5
    if not s:
        s = 0.4                                # прочее (рельеф, ловушки, метки) — понемногу
    if sk.get("ult"):
        s *= 1.6
    return s / max(1.0, 0.5 + 0.25 * sk["ap"])


def choose(caster, u, scored=False):
    """(навык, цель) или None. Бард — мелодиями. Остальные — по порядку навыков (как обычный автокаст), но навык,
    который сейчас не сработает (мало шкалы, нет знамени, ультимейт не набран, не та форма), пропускается — иначе
    необычные классы застревают на нём и не применяют остальные. scored — выбор по оценке пользы (score)."""
    c = caster.c
    if kit.notes_of_unit(c, u):
        return bard(caster, u)
    best, best_s = None, MIN_SCORE
    for sid in u.skills:
        sk = u.skill_defs[sid]
        if not u.skill_ready(sid, sk):
            continue
        if any(e["type"] == "form" and e.get("form") == u.form for e in sk["effects"]):
            continue
        target = caster._pick_target(u, sk, [])
        if target is None or not c.check_skill(u, sid, target)[0]:
            continue
        if not scored:
            return sid, target
        s = score(c, u, sid, sk, target)
        if s > best_s:
            best, best_s = (sid, target), s
    return best


# ---------- бард: мелодии ----------

def want_melody(c, u, known):
    """Какую мелодию играть сейчас."""
    allies = [a for a in c.fighters(u.team) if not a.obj]
    foes = c.foes_of(u)
    hurt = [a for a in allies if a.hp < a.max_hp * 0.55 and cheb(a.cell, u.cell) <= 3]
    order = []
    if hurt:
        order += ["mel_serenade", "mel_life"]
    if any(f.cast and cheb(f.cell, u.cell) <= 4 for f in foes):
        order.append("mel_lullaby")
    if sum(1 for f in foes if cheb(f.cell, u.cell) <= 3) >= 2:
        order.append("mel_wave")
    order += ["mel_march", "mel_discord", "mel_wave", "mel_life"]
    for sid in order:
        if sid in known:
            return sid
    return known[0] if known else None


def next_note(played, melody):
    """Следующая буква мелодии с учётом уже сыгранных нот (самый длинный хвост, совпадающий с началом)."""
    for k in range(min(len(played), len(melody) - 1), 0, -1):
        if played[-k:] == melody[:k]:
            return melody[k]
    return melody[0]


def bard(caster, u):
    c = caster.c
    notes = kit.notes_of_unit(c, u)
    known = kit.known_melodies(c, u)
    fin = next((s for s in u.skills if s not in notes and u.skill_defs[s].get("ult")), None)
    if fin and u.skill_ready(fin, u.skill_defs[fin]) and u.last_melody and \
            sum(1 for f in c.foes_of(u) if cheb(f.cell, u.cell) <= u.skill_defs[fin].get("radius", 3)) >= 2 and \
            c.check_skill(u, fin, u)[0]:
        return fin, u
    if not c.foes_of(u):
        return None
    mel = want_melody(c, u, known)
    if mel is None:
        return None
    letter = next_note("".join(u.notes), c.data.skills[mel]["melody"])
    sid = notes["QWE".index(letter)] if letter in "QWE" and "QWE".index(letter) < len(notes) else None
    if sid and u.skill_ready(sid, u.skill_defs[sid]) and c.check_skill(u, sid, u)[0]:
        return sid, u
    return None
