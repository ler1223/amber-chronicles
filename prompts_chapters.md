# Промпты изображений глав

Для карточек глав и фонов актов. Стиль — как у остальных иллюстраций экспедиции: пиксель-арт 192×128
(генерировать крупно, 1536×1024, затем уменьшать), без героев и текста. В левой нижней трети — чистая
площадка под фигурки отряда, если картинка используется как сцена.

## Общий стиль

Вставлять в начало каждого запроса:

```
Make ONE image, 1536x1024, one single scene, no grid, no panels.
Pixel art scene illustration, true pixel art on a 192x128 logical grid, crisp square pixels,
no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy tactics RPG, painterly pixel art like classic adventure games, strong silhouettes,
one clear light source, moody but readable. No text, no UI, no letters.
IMPORTANT: do NOT draw adventurers, heroes, party members, player characters or their hands.
Keep the LOWER-LEFT third as a clear, flat, unobstructed patch of ground where 2-5 small figures
could stand side by side facing right; nothing important there.
```

---

## 1. Болото — `swamp_act_0`

```
A misty swamp boardwalk at dusk, black water between reeds, crooked dead trees, a distant amber
glow over the mire, fireflies, a muddy bank in the lower-left foreground.
```

## 2. Огненные кузни — `forge_act_0`

```
A huge underground forge hall: rivers of orange lava, black anvils, chains, giant bellows, sparks
and heat haze, a stone bridge over the lava in the lower-left, a distant red furnace heart.
```

## 3. Склеп нежити — `crypt_act_0`

```
A dark crypt under a ruined monastery: rows of broken stone coffins, pale blue candles, fog
crawling over the floor, a narrow path between graves in the lower-left, a cold light from a
distant altar. Very dark, readable silhouettes.
```

## 4. Ледяные перевалы — `pass_act_0`

```
A narrow mountain pass above clouds: blue-white ice, a frozen waterfall, jagged peaks, snow
blowing sideways, a safe rocky ledge in the lower-left, a faint warm campfire glow far away.
```

## 5. Грозовая степь — `steppe_act_0`

```
An endless stormy steppe at dusk: tall grass bending in the wind, dark thunderclouds, distant
lightning, stone idols on the horizon, a flat patch of grass in the lower-left, cold blue light.
```

## 6. Пустынные гробницы — `tomb_act_0`

```
A desert necropolis at sunset: half-buried stone tombs, colossal broken sphinx heads, blowing
sand, deep shadows, a clear sandy patch in the lower-left, a golden tomb entrance far right.
```

## 7. Тёмный лес фей — `fae_act_0`

```
A dark enchanted forest: giant glowing mushrooms, twisted violet trees, floating pollen, a
circle of pale stones, a mossy clearing in the lower-left, faint fairy lights between roots.
```

## 8. Затонувший город — `sunken_act_0`

```
A flooded ancient city at low tide: half-submerged marble streets, a broken lighthouse, green
water in the canals, seaweed and shells, a dry stone pier in the lower-left, cold teal light.
```

## 9. Небесная цитадель — `citadel_act_0`

```
A floating sky citadel above clouds: white stone towers, broken bridges over an endless blue
abyss, banners in the wind, a safe platform in the lower-left, a distant golden throne room.
```

---

## Как подключить

Если генерируешь по одной картинке, сохраняй её как:

```
assets/illustrations/hd/pass_act_0.png
assets/illustrations/pass_act_0.png      # 192×128, уменьшенная копия
```

Для листа 2×2 (четыре главы на одном изображении):

```
python tools/import_illustrations.py assets/art_src/sheet_chapters_1.png --names pass_act_0,steppe_act_0,tomb_act_0,fae_act_0 --preview p.png
```

После этого в `data/expedition_<глава>.json` можно заменить `art` у актов и в `data/expedition.json` —
`art` у главы на новый id.
