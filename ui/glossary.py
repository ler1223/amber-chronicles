"""Термины боя: ссылки в описаниях навыков и подсказки по эффектам."""
import re

import pygame

from ui import theme as T

_BUFFS = {
    "Уязвимость": ("exposed", "Получает больше урона от атак."),
    "Молчание": ("silence", "Не может применять навыки."),
    "Сон": ("sleep", "Не действует, пока его не ударят."),
    "Оглушение": ("stun", "Не может двигаться и действовать."),
    "Замедление": ("slow", "Двигается и атакует медленнее."),
    "Броня": ("armor", "Снижает входящий прямой урон."),
    "Щит": ("shield", "Поглощает урон до здоровья."),
    "Регенерация": ("regen", "Восстанавливает здоровье каждый тик."),
    "Провокация": ("taunt", "Вынуждает врагов атаковать носителя."),
    "Ускорение": ("atk_speed", "Уменьшает интервал между атаками."),
    "Ярость": ("atk_mult", "Увеличивает урон атак."),
    "Сила навыков": ("skill_mult", "Увеличивает силу применяемых навыков."),
    "Восстановление AP": ("ap_rate", "Ускоряет восстановление AP."),
    "Снижение брони": ("armor_shred", "Уменьшает броню цели."),
    "Получаемое лечение": ("heal_taken", "Изменяет эффективность лечения по цели."),
    "Получаемый урон": ("dmg_taken", "Изменяет входящий урон."),
    "Очищение": ("cleanse", "Снимает отрицательные эффекты."),
}

_STAT_TERMS = {
    "exposed": "Уязвимость", "silence": "Молчание", "sleep": "Сон", "stun": "Оглушение",
    "slow": "Замедление", "armor": "Броня", "regen": "Регенерация", "atk_speed": "Ускорение",
    "atk_mult": "Ярость", "skill_mult": "Сила навыков", "ap_rate": "Восстановление AP",
    "armor_shred": "Снижение брони", "heal_taken": "Получаемое лечение", "shield": "Щит",
    "dmg_taken": "Получаемый урон", "cleanse": "Очищение",
}

_MARKS = {
    "challenge": ("Вызов", "Цель вынуждена атаковать наложившего; он наносит ей больше урона."),
    "duel": ("Поединок", "Цель и наложивший бьют только друг друга; наложивший сильнее."),
    "cold": ("Холод", "Три стака замораживают цель."),
    "bomb": ("Липкая бомба", "Три стака взрываются при снятии."),
}


def build(data):
    """Словарь терминов: имя -> (короткое имя, описание, цвет)."""
    out = {}
    for tid, tag in getattr(data, "tags", {}).items():
        name = tag.get("name", tid)
        desc = tag.get("status") or tag.get("desc") or ""
        out[name] = (name, desc, tuple(tag.get("color", T.TEXT)))
    for reaction in getattr(data, "reactions", {}).get("unit", []):
        name = reaction.get("name", "")
        if not name:
            continue
        tags = ", ".join(data.tags.get(t, {}).get("name", t) for t in reaction.get("tags", []))
        desc = reaction.get("desc", "")
        if tags:
            desc = f"{desc} ({tags})" if desc else tags
        out[name] = (name, desc, (255, 190, 130))
    for mid, mark in (getattr(data, "config", {}).get("marks") or {}).items():
        name = mark.get("name", mid)
        desc = _MARKS.get(mid, ("", "Метка боя."))[1]
        out[name] = (name, desc, tuple(mark.get("color", T.AMBER)))
    for name, (stat, desc) in _BUFFS.items():
        out[name] = (name, desc, T.TEXT)
    return out


def _terms(text, glossary):
    """Непересекающиеся ссылки в тексте, длинные термины первыми."""
    used = []
    for name in sorted(glossary, key=len, reverse=True):
        for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.IGNORECASE):
            if any(a <= m.start() < b or a < m.end() <= b for a, b in used):
                continue
            used.append((m.start(), m.end()))
            yield m.start(), m.end(), name


def segments(text, glossary):
    """[(кусок текста, ключ эффекта или None)]."""
    marks = sorted(_terms(text, glossary), key=lambda x: x[0])
    out, pos = [], 0
    for a, b, key in marks:
        if a > pos:
            out.append((text[pos:a], None))
        out.append((text[a:b], key))
        pos = b
    if pos < len(text):
        out.append((text[pos:], None))
    return out


def draw(surf, text, pos, size, width, glossary, color=None, bold=False, max_lines=None):
    """Рисует текст с подсветкой терминов. Возвращает (высота, [(rect, key)])."""
    font = T.font(size, bold)
    base = color or T.TEXT
    rows, cur, cur_w = [], [], 0
    for line in str(text).split("\n"):
        for chunk, key in segments(line, glossary):
            # сохраняем пробелы, но переносим по словам
            for word in re.findall(r"\S+\s*", chunk):
                raw = word.rstrip()
                w = font.size(raw)[0]
                if cur and cur_w + w > width:
                    rows.append(cur)
                    cur, cur_w = [], 0
                cur.append((raw, key))
                cur_w += w + font.size(" ")[0]
        if cur:
            rows.append(cur)
            cur, cur_w = [], 0
    if max_lines is not None:
        rows = rows[:max_lines]
    links = []
    y = pos[1]
    for row in rows:
        x = pos[0]
        for raw, key in row:
            if not raw:
                continue
            col = T.AMBER if key else base
            r = T.text(surf, raw, (x, y), size, col, bold)
            if key:
                links.append((r, key))
                pygame.draw.line(surf, T.AMBER_DIM, (r.x, r.bottom - 2), (r.right, r.bottom - 2), 1)
            x += font.size(raw)[0] + font.size(" ")[0]
        y += size + 4
    return y - pos[1], links


def effect_tip(glossary, key):
    name, desc, col = glossary[key]
    return [(name, col), (desc, T.TEXT)]


def _pct(value, sign=True):
    return f"{value * 100:+.0f}%" if sign else f"{value * 100:.0f}%"


def _buff_detail(eff):
    stat, value = eff.get("stat"), eff.get("value", 1)
    if stat == "slow":
        return f"Замедление {(1 - 1 / max(1.01, value)) * 100:.0f}%"
    if stat == "atk_speed":
        return f"Ускорение атаки {(1 - value) * 100:.0f}%"
    if stat == "dmg_taken":
        return f"Входящий урон {_pct(value - 1)}"
    if stat == "exposed":
        return f"Уязвимость {_pct(value - 1)}"
    if stat == "armor":
        return f"+{value:g} брони"
    if stat == "armor_shred":
        return f"−{value:g} брони"
    if stat == "skill_mult":
        return f"Сила навыков {_pct(value - 1)}"
    if stat == "ap_rate":
        return f"Скорость AP {_pct(value - 1)}"
    if stat == "atk_mult":
        return f"Урон атак {_pct(value - 1)}"
    if stat == "heal_taken":
        return f"Получаемое лечение {_pct(value - 1)}"
    if stat == "regen":
        return f"Регенерация +{value:g} HP/сек"
    if stat in ("silence", "stun", "sleep"):
        return {"silence": "Молчание", "stun": "Оглушение", "sleep": "Сон"}[stat] + \
               f" {float(eff.get('duration', 0)):g} сек"
    return _STAT_TERMS.get(stat)


def skill_effect_terms(sk, data):
    """Названия эффектов навыка для строки «Эффекты: ...»."""
    out = []
    for eff in sk.get("effects", []):
        t = eff.get("type")
        names = []
        if eff.get("tag"):
            names.append(data.tags.get(eff["tag"], {}).get("name", eff["tag"]))
        if t == "buff":
            term = _STAT_TERMS.get(eff.get("stat"))
            if term:
                names.append(term)
        elif t in ("sleep", "stun", "cleanse"):
            names.append({"sleep": "Сон", "stun": "Оглушение", "cleanse": "Очищение"}[t])
        elif t == "status":
            names.append(data.tags.get(eff.get("tag"), {}).get("name", eff.get("tag", "эффект")))
        elif t == "mark":
            mark = (data.config.get("marks") or {}).get(eff.get("mark"), {})
            names.append(mark.get("name", eff.get("mark", "метка")))
        for name in names:
            if name and name not in out:
                out.append(name)
    return out


def effect_line(sk, data):
    details = []
    for eff in sk.get("effects", []):
        if eff.get("type") == "buff":
            detail = _buff_detail(eff)
        elif eff.get("type") in ("stun", "sleep"):
            detail = {"stun": "Оглушение", "sleep": "Сон"}[eff["type"]] + \
                     f" {float(eff.get('duration', 0)):g} сек"
        elif eff.get("type") == "silence":
            detail = f"Молчание {float(eff.get('duration', 0)):g} сек"
        elif eff.get("type") == "cleanse":
            detail = "Очищение"
        elif eff.get("type") == "mark":
            mark = (data.config.get("marks") or {}).get(eff.get("mark"), {})
            detail = mark.get("name")
        elif eff.get("tag"):
            detail = data.tags.get(eff["tag"], {}).get("name", eff["tag"])
        else:
            detail = None
        if detail and detail not in details:
            details.append(detail)
    return ("Эффекты: " + ", ".join(details)) if details else None
