"""Таблица «когда навык попадает» для симуляции (data/config.json → hit) из описаний визуала (data/vfx.json).

  python tools/hit_timing.py

Бой применяет урон и эффекты навыка не в момент каста, а в момент попадания: снаряд долетел, метеор упал,
площадь вспыхнула после метки. Время считает sim/combat.py (Combat.hit_delay) по этой таблице:
  fly  — снаряд от героя: время = расстояние / speed (клеток в секунду), в пределах min..max;
  fall — падает с неба: фиксированное time;
  time — удар по таймлайну визуала (стрелы ещё падают): фиксированное time;
  instant — рывок героя: сразу;
остальные навыки — по общим правилам (config.hit: area, swing, ally). Ключ «навык:ветка» — у ветки свой вид.
Визуал (ui/battle_view.py) растягивает полёт снаряда и метку площади ровно на это время.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOW = 0.55          # снаряды медленнее прежнего визуала: полёт видно, бой читается
PX_PER_CELL = 80.0
NL = "\n"


def entry(spec):
    tr = spec.get("travel")
    if tr:
        if tr.get("from") == "sky":
            return {"mode": "fall", "time": round(max(0.55, tr.get("time", 0.45) * 1.4), 2)}
        if tr.get("time") and tr["time"] < 0.2:          # рывок героя, а не снаряд
            return {"mode": "instant"}
        return {"mode": "fly", "speed": round(tr.get("speed", 800) / PX_PER_CELL * SLOW, 2)}
    if spec.get("delay"):
        return {"mode": "time", "time": spec["delay"]}
    return None


def build():
    vfx = json.load(open(os.path.join(ROOT, "data", "vfx.json"), encoding="utf-8"))
    out = {}
    for sid, spec in vfx["skills"].items():
        e = entry(spec)
        if e:
            out[sid] = e
        for b, over in (spec.get("branches") or {}).items():
            e2 = entry(dict(spec, **over))
            if e2 and e2 != out.get(sid):
                out[f"{sid}:{b}"] = e2
            elif not e2 and sid in out:
                out[f"{sid}:{b}"] = {"mode": "rule"}
    out["blizzard"] = {"mode": "fall", "time": 0.7}       # шквал с неба (ui/pix_battle.py, _blizzard)
    # оружие (ui/pix_weapons.py): замах и удар, прыжок драгуна — дуга и приземление
    for sid, e in (("power_strike", {"mode": "time", "time": 0.3}), ("jump_strike", {"mode": "time", "time": 0.62})):
        for key in (sid, f"{sid}:A", f"{sid}:B"):
            out[key] = dict(e)
    for key in ("power_strike:A", "power_strike:B"):          # усиленный: длинный замах двумя руками
        out[key] = {"mode": "time", "time": 0.45}
    # остальное оружие воина и стража: замах, рывок, удар щитом (ui/pix_weapons.py)
    for sid, t in (("whirlwind", 0.4), ("lunge", 0.3), ("guard_ally", 0.45), ("taunt", 0.25), ("shield_wall", 0.3),
                   ("brace", 0.25), ("consecrate", 0.45)):
        for key in (sid, f"{sid}:A", f"{sid}:B"):
            out[key] = {"mode": "time", "time": t}
    out["hook:B"] = {"mode": "time", "time": 0.3}             # подсечка: без цепи, удар по ногам
    # свет жреца (ui/pix_light.py): луч очищения, копьё приговора с неба; святая вода — склянка (из vfx.json)
    for sid, e in (("purify", {"mode": "time", "time": 0.35}), ("judgment", {"mode": "fall", "time": 0.4})):
        for key in (sid, f"{sid}:A", f"{sid}:B"):
            out[key] = dict(e)
    # лучник — стрелы навыков быстрее; ловчий — пуля, ещё быстрее (и в обычной атаке: attack_speed.trapper)
    for sid, sp in (("aimed_shot", 20.0), ("headshot", 24.0)):
        for key in (sid, f"{sid}:A", f"{sid}:B"):
            out[key] = {"mode": "fly", "speed": sp, "min": 0.12}
    for sid in TRAPPER_SHOTS:
        for key in (sid, f"{sid}:A", f"{sid}:B"):
            out[key] = {"mode": "fly", "speed": 45.0, "min": 0.06}
    out.update(EXTRA)
    return out


TRAPPER_SHOTS = ("hunter_mark", "slug_shot")
EXTRA = {                                                  # навыки характеров (sim/kit.py)
    "ice_shard": {"mode": "fly", "speed": 12.0}, "ignite": {"mode": "fly", "speed": 10.0},
    "sticky_bomb": {"mode": "fly", "speed": 8.0},
}


def main():
    path = os.path.join(ROOT, "data", "config.json")
    text = open(path, encoding="utf-8").read()
    cfg = json.loads(text)
    hit = {"_note": "Время попадания навыков — tools/hit_timing.py", "min": 0.3, "max": 1.1, "area": 0.55,
           "swing": 0.2, "ally": 0.35, "attack_speed": {"ranged": 13.0, "spell": 9.0, "trapper": 45.0}, "attack_melee": 0.08}
    rows = ("," + NL).join(f"    {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}"
                           for k, v in build().items())
    head = json.dumps(hit, ensure_ascii=False)[:-1]
    block = '  "hit": ' + head + ', "skills": {' + NL + rows + NL + "  }}"
    if "hit" in cfg:                                   # заменить старый раздел (он всегда последний)
        text = text[:text.index(NL + '  "hit": ')].rstrip().rstrip(",") + NL + "}" + NL
    body = text.rstrip()
    assert body.endswith("}")
    text = body[:-1].rstrip() + "," + NL + block + NL + "}" + NL
    n = len(json.loads(text)["hit"]["skills"])
    open(path, "w", encoding="utf-8").write(text)
    print(n, "навыков")


if __name__ == "__main__":
    main()
