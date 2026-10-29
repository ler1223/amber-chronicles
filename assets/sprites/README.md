# Спрайты юнитов

Положите PNG в эту папку — игра подхватит его при следующем запуске. Если файла нет, рисуется заглушка.

## Имена файлов
- Герои: `warrior.png`, `archer.png`, `mage.png`, `priest.png`, `assassin.png`, `druid.png`, `guardian.png`,
  `shaman.png`, `bard.png`, `alchemist.png`.
- Облики друида: `druid_bear.png` / `druid_wolf.png` (или общие `bear.png` / `wolf.png`).
- Призывы: `totem_storm.png`, `totem_thunder.png`, `totem_heal.png`, `totem_ward.png`, `spirit_tree.png`, `ent.png`.
- Подклассы (необязательно; без файла берётся спрайт класса) — по id пути из `data/paths.json`: `berserker.png`,
  `paladin.png`, `ranger.png`, `sniper.png`, `warlock.png`, `cryomancer.png`, `inquisitor.png`, `lifekeeper.png`,
  `shadow.png`, `duelist.png`, `wild.png`, `grove.png`, `sentinel.png`, `dragoon.png`, `thunderlord.png`,
  `spiritwalker.png`, `skald.png`, `minstrel.png`, `demolitionist.png`, `poisoner.png`.
- Враги: `slime.png`, `beetle.png`, `bog_archer.png`, `frog_shaman.png`, `slime_king.png` (элита), `ice_witch.png` (босс).
- Имя = id юнита из `data/classes.json`, `data/enemies.json`, `data/paths.json`.

## Как рисовать
- Холст **32×32** (можно другой — см. масштаб). Прозрачный фон.
- Персонаж **смотрит вправо** — влево игра отражает сама.
- **Ноги на нижнем ряду пикселей, по центру** холста: эта точка ставится в клетку.
- Тёмный контур в 1 пиксель хорошо читается на траве и воде.
- Не рисуйте тень, кольцо команды, полоску HP — это делает игра.
- Анимация процедурная (дыхание, шаг, выпад, вздрагивание, вспышка от удара) — нужен один кадр.

## Масштаб
Целочисленный, чтобы пиксели оставались чёткими: обычный юнит ≈ 64 px в высоту, босс ≈ 96 px.
Множитель = `round(64 / высота)` (у босса `round(96 / высота)`), минимум 1. Холст 32×32 → ×2 (босс ×3).

## Шаблоны
`python tools/export_placeholders.py` выгружает текущие заглушки в `_templates/` — их можно открыть в
Aseprite/LibreSprite и перерисовать поверх, а готовый файл положить сюда же (не в `_templates`).

## Модельки предметов (`props/`)
Стрелы, сеть, склянка, капкан и обломки в эффектах — тоже пиксель-арт; заглушки нарисованы ASCII-сетками
в `ui/props.py`. Свой рисунок: `assets/sprites/props/<имя>.png`, смотрит **вправо** (стрела — наконечником
вправо), прозрачный фон, контур в 1 пиксель. В игре масштаб ×2, ячейка атласа до 64×64.
Имена: `arrow`, `arrow_heavy`, `arrow_ice`, `arrow_fire`, `stake`, `net_ball` (сеть в полёте), `net` (раскрытая),
`bottle`, `mud`, `trap_open`, `trap_closed`, `smoke_bomb`, `rock`, `pebble`, `ice_chunk`, `glass`, `splinter`,
`mud_bit`, `dart`, `grapple`, `bomb`, `oil_bottle`, `potion_red`, `potion_green`, `mine`, `barrel`. Воткнутая в землю стрела делается из той же картинки: наконечник срезается, древко ставится под углом.
