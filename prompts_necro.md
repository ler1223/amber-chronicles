# Промпты Некроманта: скелеты и улучшения Алтаря

Два готовых запроса для генератора: лист спрайтов всех скелетов и лист иконок всех улучшений Алтаря.
Стиль — как в остальных листах игры: настоящий пиксель-арт, фон `#FF00FF`, без текста и рамок.

## 1. Спрайты скелетов

Один лист: **9 фигур** — 7 обычных скелетов и 2 элитных. «Легион» отдельного спрайта не имеет:
он поднимает обычных костяных воинов/стражей.

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark
outline (dark brown/navy, not black), light from top-left, 2-3 tone shading. Three-quarter view, full body,
every figure faces RIGHT, standing on an invisible ground line, no ground shadow, no text, no labels, no
frames. Dark fantasy tactics RPG, readable silhouettes like classic SNES / GBA tactics games.
9 figures in 3 rows of 3, in EXACTLY this order (left to right, top row first). Leave wide empty magenta
space between figures: nothing may touch or overlap. Normal skeletons are about 26-30 pixels tall;
the bone colossus is about 1.6x a human; the death knight is about 1.3x a human.

Row 1:
1. Skeleton warrior: yellowed bones, a rusty straight sword and a cracked round shield, tattered dark
   loincloth, faint teal glow in the eye sockets.
2. Skeleton archer: lean bones, a short bow held ready, a quiver of bone arrows on the hip, a torn leather
   hood, teal eye glow.
3. Skeleton mage: hooded dark robe over bones, a gnarled staff topped with a small green soul-flame,
   floating bone charms, teal-green glow in the eyes.

Row 2:
4. Bone guard: broad skeleton in a battered iron helmet, a heavy tower shield made of fused ribs and bone
   plates, thick arm bones, steady defensive stance, teal eye glow.
5. Skeleton bomber: small hunched skeleton with a leather satchel of round bone bombs, one lit bomb in its
   hand, a short burning fuse, orange-red glow in the eye sockets.
6. Skeleton assassin: crouched lean skeleton in a dark hood and torn scarf, two curved bone daggers,
   purple-green glow in the eye sockets, stealthy pose.

Row 3:
7. Skeleton captain: tall skeleton in a horned iron helm and a tattered dark cape, holding a bone standard
   with a small green soul-banner, a faint command aura around the shoulders, teal-green eye glow.
8. Bone colossus: a huge skeleton golem made of fused ribs, skulls and thick bone plates, massive arms,
   amber-green light burning inside the ribcage, slow heavy stance, about 1.6x human height.
9. Death knight: an elite skeleton knight in blackened plate armor, a horned great helm, a huge notched
   sword, green soul-fire leaking from the visor and joints, a dark aura around the blade, about 1.3x
   human height.
```

## 2. Иконки улучшений Алтаря

Один лист: **29 иконок** в сетке 6×5, последняя ячейка пустая. Каждая иконка — один крупный символ,
без рамки, подписей и фона-плитки.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art upgrade icons in the exact same style as the previous icon sheets: each icon is true pixel art
on a 32x32 grid, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel
dark outline, light from top-left, 2-3 tone shading. Each icon is ONE bold centered emblem, readable at
small size, with a subtle green/teal necromantic glow where noted. No text, no letters, no numbers, no
frames, no background plates, no UI. Dark fantasy tactics RPG.
29 icons in 5 rows of 6, in EXACTLY this order (left to right, top row first). The 30th cell is empty
magenta. Leave wide empty magenta space between icons: nothing may touch.

Row 1 — skeleton warrior:
1. Bone armor: a thick bone chest plate with a green soul-glow in the center.
2. Cleaving strike: a curved sword arc cutting through two small bone shards.
3. Last stand: a broken warrior skull with a shield-shaped aura behind it.

Row 2 — skeleton archer:
4. Keen eye: a single eye with a small arrowhead in the pupil.
5. Piercing arrow: an arrow passing through three stacked bone plates.
6. Arrow rain: three arrows falling diagonally from a small dark cloud.

Row 3 — skeleton mage:
7. Grave cold: a blue skull with a ring of pale frost around it.
8. Bone blast: a skull exploding into radiating bone shards.
9. Soul vortex: a green soul-wisp spiraling around a small skull.

Row 4 — bone guard:
10. Bone shield: a round shield made of ribs protecting two tiny skulls.
11. Taunt: a horned skull shouting, three short sound arcs.
12. Unbreakable bone: a ribcage with a green protective aura.

Row 5 — skeleton bomber:
13. Big charge: a round bomb with a large orange blast ring.
14. Shrapnel bomb: a bomb bursting into sharp bone splinters.
15. Bone storm: a swirling storm of bones and green sparks.

Row 6 — skeleton assassin:
16. Shadow: a hooded skull silhouette with a purple-green outline.
17. Backstab: a curved dagger behind a ribcage.
18. Bone blade: a long bone sword above a low-health skull.

Row 7 — skeleton captain:
19. Battle cry: a small bone banner with speed lines.
20. Bone order: a bone banner with a shield emblem.
21. Bone standard: a tall skull-topped standard radiating a green command aura.

Row 8 — rituals:
22. Bone watch: a guard skull rising from a small grave circle.
23. Bone supply: a neat pile of bones and a single skull.
24. Double harvest: two skeletal hands raising two small skulls.
25. Funeral blast: a skull bursting with green-white bone fire.
26. Necrotic link: a green thread connecting a skull to a small heart.
27. Bone retinue: six tiny skulls arranged around a crown.
28. Commander's voice: a captain skull with a wide radiating aura.

Row 9:
29. Gift of souls: a green soul-wisp rising from a bone pile.
30. EMPTY — plain magenta, no object.
```

## 3. Если генерировать по одному

Для отдельного спрайта или иконки использовать тот же стиль, заменив только описание:

```
Make ONE pixel art game sprite, 512x512, plain flat solid magenta background (#FF00FF).
True pixel art on a 32x32 logical grid, crisp square pixels, no anti-aliasing, no blur, no gradients,
limited palette, 1-pixel dark outline, light from top-left, 2-3 tone shading. Three-quarter view, full
body, facing RIGHT, standing on an invisible ground line, no shadow, no text, no frame.
Dark fantasy tactics RPG. Character: <ОПИСАНИЕ СКЕЛЕТА ИЗ СПИСКА ВЫШЕ>.
```

Для иконки:

```
Make ONE pixel art upgrade icon, 512x512, plain flat solid magenta background (#FF00FF).
True pixel art on a 32x32 logical grid, crisp square pixels, no anti-aliasing, no blur, no gradients,
limited palette, 1-pixel dark outline, light from top-left, one centered bold emblem, no text, no frame,
no background plate. Dark fantasy tactics RPG. Icon: <ОПИСАНИЕ УЛУЧШЕНИЯ ИЗ СПИСКА ВЫШЕ>.
```

## Куда сохранять

- Спрайты: `assets/art_src/sheet_necro_army.png`, затем нарезать своим набором `necro_army`.
- Иконки: `assets/art_src/sheet_icons_necro.png`, затем нарезать набором `icons_necro`.
- Если набор ещё не описан в `tools/import_sheet.py`, сначала добавить его туда: порядок фигур в промпте
  совпадает с порядком id в наборе.
