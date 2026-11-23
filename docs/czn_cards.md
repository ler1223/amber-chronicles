# Архив карт Chaos Zero Nightmare

Полный машинный каталог: **`data/czn/cards.json`**.

- Источник: GachaData, `https://gacha-data.com/chaos-zero-nightmare/cards/`
- Строк: **979** — базовые карты и эпифании.
- Уникальных базовых карт: **341**.
- Персонажей/источников: **73**.
- Вариантов: Base 341, Epiphany 1–5 — 638.

## Поля

| Поле | Смысл |
|---|---|
| `character` | персонаж/источник CZN |
| `name` | название карты |
| `variant` | `Base` или `Epiphany N` |
| `slot` | Basic Card / Signature Cards / Ego Skill / Partners |
| `type` | Attack / Skill / Upgrade |
| `rarity` | Normal / Rare / Legendary / Mythic |
| `cost` | стоимость в AP |
| `traits` | теги/ключевые слова |
| `effect` | полный текст эффекта |

## Адаптация в «Спуск»

Перенесены не все 979 строк: CZN использует AP, Ego, Bullet, Futility, Archetype и другие системы,
которых в «Спуске» нет. В `tools/descent_czn_pack.py` добавлены **34 базовые карты**, а
`tools/descent_hunter_ranger.py` расширяет Охотницу ещё **30 картами** CZN Ranger/Hunter
(Хильда, Селена, Люк, Диана, Реноа, Серениэль, Берил, Хайдемари, Вероника, Лукас), а
`tools/descent_hunter_upgrade.py` добавляет улучшение Lucas «Extended Magazine»,
`tools/descent_hunter_sniper.py` — линейные карты и усилители по мотивам Luke/Lucas. Всего
**66 игровых карт** с источником CZN. Каждая игровая карта хранит `source`:

```json
"source": {
  "game": "CZN",
  "character": "Hilde",
  "name": "Multishot",
  "effect": "60% Damage to all enemies"
}
```

Это позволяет позже найти исходник карты и сделать более точную версию.

## Запуск импорта

```text
python tools/import_czn_catalog.py      # скачать полный каталог
python tools/descent_tiers.py           # тиры/базовые/нейтральные
python tools/descent_czn_pack.py        # 34 базовые карты + adapted_as
python tools/descent_hunter_ranger.py   # +30 Ranger/Hunter карт + adapted_as
python tools/descent_hunter_upgrade.py  # +улучшение колчана + auto-стрела
python tools/descent_hunter_sniper.py   # линейные выстрелы и заряжающиеся стрелы
python tools/consolidate_hunter.py       # слияние похожих карт в прозрения
```

## Что перенесено

- Охотница: Hilde — мультивыстрел, перезарядка колчана, плазменный дождь, натянуть и отпустить;
  Selena — оптика, замеченная цель, бомбардировка дронами, владения снайпера.
- Охотница, расширение Ranger/Hunter: Хильда — вихревая стрела, большая дичь, матричное наложение;
  Селена — тактический манёвр, финальный выстрел; Люк — теневая перезарядка, танец демона,
  смертельный замысел, последний патрон; Диана — цветущая любовь, освобождённые чувства;
  Реноа — мгновенный приговор, баллада тьмы, последний штурм; Серениэль — плазменная ракета,
  кобальтовый свет, бледная звезда; Берил — заряженный выстрел, порочное удовольствие,
  неограниченная мощь, максимальная мощность; Хайдемари — герой для всех, нить света, элизиум клинков;
  Вероника — покой, сэр Ковальски, время охоты; Лукас — огнемёт, светошумовая, полный залп.
- Наёмник: Maribell — удар/укрытие/удар щитом/волчий купол;
  Khalipe — пересилить/сплочение; Magna — морозный заряд/ледяная стена.
- Пиромантка: Fei — танец души/монолог; Kayron — чёрная дыра/клеймо/эхо бездны;
  Mei Lin — восходящий дракон/единство; Tenebria — зов и ответ/на бис.
- Нейтральные: Quick Shelling, Reorganize, Rally, Protective Shout, Precision Aim, Pulverize,
  Pierce, Adagio, Soul Riff.

## Что делать дальше

1. Для каждой карты из `data/czn/cards.json` добавить поле `adapted_as` (id игровой карты), когда
   она будет перенесена.
2. Разобрать эпифании как варианты прозрений, а не как отдельные карты.
3. Для неподдерживаемых систем (Futility, Bullet, Rhythm, Archetype, Decibel) сначала добавлять
   движковую механику, потом карты.
4. Перепроверить редкость/тир после переноса: CZN Normal/Rare/Legendary/Mythic → 1–4 тир.
