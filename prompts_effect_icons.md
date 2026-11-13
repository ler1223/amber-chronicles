# Промпты иконок эффектов

Лист рассчитан на `tools/import_sheet.py --set icons_effects`: 16 иконок 32×32 в сетке 4×4.
Стиль — как у иконок даров и предметов: настоящий пиксель-арт, один читаемый символ, без рамки и текста.

## Лист эффектов (`--set icons_effects`)

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art status-effect icons in the exact same style as the previous icon sheets: each icon is true pixel art
on a 32x32 grid, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark
outline, light from top-left, 2-3 tone shading. Each icon is a single bold emblem (not a framed square),
centered, readable at small size, glowing accents, no text, no letters, no UI. Dark fantasy tactics RPG.
16 icons in 4 rows of 4, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
icons: nothing may touch.

Row 1:
1. Fog: a dense gray-green cloud with a faint closed eye inside, two thin wisps curling away.
2. Evasion: a cyan afterimage of a small human silhouette with three motion streaks behind it.
3. Blind: a single eye with a black cloth band across it and a small purple spark at the corner.
4. Increased healing: a warm golden heart with a green plus above it and two rising light motes.

Row 2:
5. Damage reduction: a thick stone-like hide plate with a soft golden rim, no shield shape.
6. Debuff resistance: a broken iron chain around a small white rune, the broken link glowing.
7. Heal over time: a small hourglass with a green healing droplet falling through it, golden sand.
8. Cleanse: a white cleansing flame washing over a purple curse rune, the rune dissolving into sparks.

Row 3:
9. Prayer: two open hands under a narrow column of golden light, tiny motes rising.
10. Meteor: a flaming black rock with a long orange-white trail, three small embers behind it.
11. Flame wall: three tall orange flame tongues in a row on a black scorched line.
12. Phoenix shield: a round fiery sphere-shield with a small white phoenix feather inside, orange rim.

Row 4:
13. Sanctuary: a golden circular rune on dark ground with four short light rays rising from it.
14. Spirit guardian: a small translucent blue-white healer ghost with a gentle face and a lantern.
15. Holy water: a small glass flask spilling bright water and golden sparks, a thin steam wisp.
16. Vow: a golden thread tied in a knot around a small red heart, one loose end glowing.
```

Сохранить лист в `assets/art_src/` и импортировать:

```
python tools/import_sheet.py assets/art_src/sheet_icons_effects.png --set icons_effects --preview p.png
```

## Отдельные иконки, если нужен не лист

Для одной иконки заменить размер и сетку:

```
Make ONE pixel art status icon, 512x512, plain flat solid magenta background (#FF00FF).
True pixel art on a 32x32 logical grid, crisp square pixels, no anti-aliasing, no blur, no gradients,
limited palette, 1-pixel dark outline, light from top-left, centered single bold emblem, no text, no frame.
Dark fantasy tactics RPG. Icon: <ОПИСАНИЕ ИЗ СПИСКА ВЫШЕ>.
```

## Куда это ляжет

- `assets/icons/fx_fog.png` — туман / ослепление.
- `assets/icons/fx_evasion.png` — уклонение союзников в тумане.
- `assets/icons/fx_blind.png` — ослепление.
- `assets/icons/fx_heal_taken.png` — усиление входящего лечения.
- `assets/icons/fx_tough.png` — снижение входящего урона.
- `assets/icons/fx_debuff_resist.png` — сокращение длительности дебаффов.
- `assets/icons/fx_heal_over_time.png` — постепенное лечение.
- `assets/icons/fx_cleanse.png` — очищение тегов.
- `assets/icons/fx_prayer.png` — канал «Молитва».
- `assets/icons/fx_meteor.png` — метеорный дождь.
- `assets/icons/fx_fire_wall.png` — стена пламени.
- `assets/icons/fx_phoenix_shield.png` — круглый щит Феникса.
- `assets/icons/fx_sanctuary.png` — святилище.
- `assets/icons/fx_spirit.png` — дух-хранитель.
- `assets/icons/fx_holy_water.png` — святая вода.
- `assets/icons/fx_vow.png` — обет.

Пока иконок нет, игра использует процедурные значки из `ui/icons.py`; после импорта их можно подключить
к `BUFF_NAMES` / `buff_icon` без изменения логики боя.
