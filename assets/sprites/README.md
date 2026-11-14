# Спрайты юнитов

Положите PNG в эту папку — игра подхватит его при следующем запуске. Если файла нет, рисуется заглушка.

## Имена файлов
- Герои: `warrior.png`, `archer.png`, `mage.png`, `priest.png`, `assassin.png`, `druid.png`, `guardian.png`,
  `shaman.png`, `bard.png`, `alchemist.png`, `ram.png`, `trapper.png`, `cryo.png`, `necro.png`, `chrono.png`,
  `gravity.png`, `geomancer.png`, `brewer.png`, `bloodrager.png`, `tactician.png`, `binder.png`.
- Облики друида: `druid_bear.png` / `druid_wolf.png` (или общие `bear.png` / `wolf.png`).
- Призывы: `totem_storm.png`, `totem_thunder.png`, `totem_heal.png`, `totem_ward.png`, `spirit_tree.png`, `ent.png`,
  `skeleton_minion.png`, `decoy.png`. Без файла берётся спрайт родственника (`SPRITE_ALIAS` в `ui/battle_view.py`).
- Подклассы (необязательно; без файла берётся спрайт класса) — по id пути из `data/paths.json`: `berserker.png`,
  `paladin.png`, `ranger.png`, `sniper.png`, `warlock.png`, `cryomancer.png`, `inquisitor.png`, `lifekeeper.png`,
  `shadow.png`, `duelist.png`, `wild.png`, `grove.png`, `sentinel.png`, `dragoon.png`, `thunderlord.png`,
  `spiritwalker.png`, `skald.png`, `minstrel.png`, `demolitionist.png`, `poisoner.png`.
- Враги: все id из `data/enemies.json` (77 файлов) — болото и кузни гл. 1–2, нежить Склепа (`skeleton.png`,
  `lich.png`, …), Перевалы (`yeti.png`, `frost_giant.png`, …), Степь (`raider.png`, `storm_khan.png`, …), Гробницы
  (`mummy.png`, `pharaoh.png`, …), Лес фей (`sprite.png`, `fae_queen.png`, …), Затонувший город (`drowned.png`,
  `deep_lord.png`, …), Цитадель (`sky_knight.png`, `archon.png`, …). Элита и боссы — по флагам `elite`/`boss`
  в `data/enemies.json`.
- Объекты поля: id из `data/objects.json` (`barrel_powder.png`, `boulder.png`, `nest.png`, `hearth.png`,
  `raider_tent.png`, `cart.png`, `ward_torch.png`, `bell.png`, `bone_wall.png`, …).
- Имя = id юнита из `data/classes.json`, `data/enemies.json`, `data/paths.json`, `data/objects.json`.
- Окружение — в подпапке `env/`, см. ниже.

## Сад (`garden/`)
Спрайты растений: `garden/<вид>_<стадия>.png`, где стадия — `0` (росток), `1` (молодое), `2` (взрослое).
Виды: `sunleaf`, `moonroot`, `thornbud`, `starflower`, `emberfern`, `frostbell`. Если файла нет,
`ui/garden_sprites.py` рисует процедурный спрайт. Промпты — `prompts_garden.md`.



## Окружение (`env/`)
Билборды укрытий и декора поля: `env/<материал>_<вид>.png` (материал главы — `grass` болото, `ash` кузни, `dirt`
склеп, `snow` перевалы, `dry` степь, `sand` гробницы, `moss` лес фей, `wet` затонувший город, `marble` цитадель).
`block` — полное укрытие, `log` — половина укрытия, остальные виды (`tree`, `pine`, `bush`, `rock`, `column`,
`tombstone`, `deadtree`, `mushroom`) — декор вокруг поля. Холсты по виду: `tree` 32×46, `pine` 28×48, `block` 36×34,
`log` 34×18, `rock` 24×18, `column` 20×46, `bush` 24×16, `mushroom` 22×26, `tombstone` 16×20, `deadtree` 28×40;
в игре ×2, ноги (низ картинки) — в точку на земле. Без файла рисуется заглушка (`ui/ground.py`).

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
