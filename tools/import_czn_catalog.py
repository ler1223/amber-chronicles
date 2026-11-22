"""Импорт полного каталога карт Chaos Zero Nightmare (CZN) в data/czn/cards.json.

Источник — публичная таблица GachaData (979 строк: базовые карты + эпифании).
Скрипт сохраняет ВСЮ карточную информацию для будущих доработок, ничего не фильтруя.
Запуск:
    python tools/import_czn_catalog.py
"""
import html
import json
import os
import re
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "czn")
OUT = os.path.join(OUT_DIR, "cards.json")
URL = "https://gacha-data.com/chaos-zero-nightmare/cards/"


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).replace("\xa0", " ").strip()


def parse(html_text):
    body = html_text.split('id="dsrows"', 1)[-1]
    rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
    out = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 9:
            continue
        vals = [strip_tags(c) for c in cells[:9]]
        out.append({
            "character": vals[0],
            "name": vals[1],
            "variant": vals[2],
            "slot": vals[3],
            "type": vals[4],
            "rarity": vals[5],
            "cost": vals[6],
            "traits": vals[7],
            "effect": vals[8],
        })
    return out


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as f:
        text = f.read().decode("utf-8", "replace")
    cards = parse(text)
    os.makedirs(OUT_DIR, exist_ok=True)
    data = {
        "source": URL,
        "note": "Полный каталог CZN: базовые карты и эпифании. Для будущих переносов.",
        "count": len(cards),
        "cards": cards,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("карт:", len(cards))
    print("персонажей:", len({c["character"] for c in cards}))
    print("варианты:", dict(Counter(c["variant"] for c in cards)))
    print("типы:", dict(Counter(c["type"] for c in cards)))


if __name__ == "__main__":
    main()
