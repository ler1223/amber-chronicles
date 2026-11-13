# Промпты экспедиции: враги болота, иконки, иллюстрации

Каждый блок — **готовый запрос целиком**: скопировать в ChatGPT (лучше в тот же чат, где делали прошлые листы, —
стиль совпадёт). Картинку сохранить в `assets/art_src/` и нарезать:

| Что | Запрос | Команда | Куда ляжет |
|---|---|---|---|
| Новые враги и боссы болота (9) — готово | Лист A | `python tools/import_sheet.py assets/art_src/sheet_swamp_new.png --set swamp_new --preview p.png` | `assets/sprites` |
| Иконки вещей (23) — готово | Лист B | `python tools/import_sheet.py assets/art_src/sheet_icons_items.png --set icons_items --preview p.png` | `assets/icons` |
| Иконки даров (17) — готово | Лист C | `python tools/import_sheet.py assets/art_src/sheet_icons_gifts.png --set icons_gifts --preview p.png` | `assets/icons` |
| Иллюстрации (44, по 4 на лист) | Листы 0–10 | `python tools/import_illustrations.py assets/art_src/ill_3.png --sheet 3 --preview p.png` | `assets/illustrations` |
| Враги и союзники событий (10) — готово | Лист E | `python tools/import_sheet.py assets/art_src/sheet_swamp_events.png --set swamp_events --preview p.png` | `assets/sprites` |
| Иллюстрации событий с последствиями (32) — готово | Листы 11–18 | `python tools/import_illustrations.py assets/art_src/ill_11.png --sheet 11 --preview p.png` | `assets/illustrations` |
| Иконки узлов карты похода (7) — готово | Лист F | `python tools/import_sheet.py assets/art_src/sheet_icons_map.png --set icons_map --preview p.png` | `assets/icons` |
| Иконки: новые дары, часть 1 (22) — готово | Лист G1 | `python tools/import_sheet.py assets/art_src/sheet_icons_gifts2.png --set icons_gifts2 --preview p.png` | `assets/icons` |
| Иконки: новые дары, часть 2 (23) — готово | Лист G2 | `python tools/import_sheet.py assets/art_src/sheet_icons_gifts3.png --set icons_gifts3 --preview p.png` | `assets/icons` |
| Иконки: новые базы и уникальные вещи (16) — готово | Лист I1 | `python tools/import_sheet.py assets/art_src/sheet_icons_items2.png --set icons_items2 --preview p.png` | `assets/icons` |
| Тотемы шамана (5) — готово | Лист S | `python tools/import_sheet.py assets/art_src/sheet_totems_shaman.png --set totems_shaman --preview p.png` | `assets/sprites` |
| Иконки: стрелы колчанов лучника (10) — готово | Лист Q | `python tools/import_sheet.py assets/art_src/sheet_icons_arrows.png --set icons_arrows --preview p.png` | `assets/icons` |
| Иконки: новые уникальные вещи (16) — готово | Лист I2 | `python tools/import_sheet.py assets/art_src/sheet_icons_items3.png --set icons_items3 --preview p.png` | `assets/icons` |
| Новые боссы Склепа (2) | Лист CR1 | `python tools/import_sheet.py assets/art_src/sheet_crypt_bosses.png --set crypt_bosses --preview p.png` | `assets/sprites` |
| Иконки Склепа: трофей, костяная пыль, 6 уникальных вещей (8) | Лист CR2 | `python tools/import_sheet.py assets/art_src/sheet_icons_crypt.png --set icons_crypt --preview p.png` | `assets/icons` |
| Недостающие сцены Склепа (3) | Лист 38 | `python tools/import_illustrations.py assets/art_src/ill_38.png --names order_toll,final_vigil,lich_phylactery --preview p.png` | `assets/illustrations` |

Пока картинки нет, игра рисует заглушку: враг берёт спрайт родственника (`sprite_fallback` в
`data/expedition.json`), иллюстрация — процедурную виньетку главы, иконки просто не показываются.

Порядок на листе важен: ряды сверху вниз, в ряду слева направо. Если генератор нарисовал не столько фигур или
перепутал порядок — скрипт скажет «на листе N фигур» или превью покажет путаницу; проще перегенерировать.

---

## Лист A — новые враги и боссы болота (`--set swamp_new`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy swamp enemies for a tactics RPG.
9 figures in 2 rows (5, 4), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between figures: nothing may touch. Bosses (marked B) are about 1.7x a normal enemy.

Row 1:
1. Mosquito swarm: a dense cloud of a dozen fat swamp mosquitoes with glinting wings and red bellies, hovering
   in a loose ball shape, a few drops of green venom falling. About 3/4 of a human's height.
2. Bog crocodile: a long dark-green crocodile with mossy back plates, half-open jaws full of yellow teeth, low on
   four legs, swamp weed hanging from its snout. As long as a human is tall.
3. Spore mushroom: a walking giant toadstool with a purple spotted cap, short root legs, glowing lilac gills and
   a puff of pale spores rising from it, small angry eyes under the cap.
4. Toad spearman: an upright armored toad warrior with a shell-plate shield and a long bone-tipped spear, a
   reed helmet, olive warty skin.
5. Bog hag: a hunched swamp witch with grey-green skin, long wet hair full of duckweed, a crooked staff with a
   dangling frog skull, a sickly green curse glow in her free hand.

Row 2:
6. Will-o'-wisp: a floating pale-blue ball of light with a faint ghostly face, small electric sparks around it,
   a thin trail of mist below. About half a human's height, floating above the ground line.
7. Elder leech: a huge fat black-and-purple leech rearing up, a round toothy mouth ring, slime dripping, about
   2/3 of a human's height.
8. (B) Heart of the Mire: a towering swamp colossus made of black mud, roots and rotten logs, a pulsing amber
   heart glowing through cracks in its chest, huge dripping arms, eyes of swamp light.
9. (B) Toad Queen: an enormous regal toad sitting upright on a lily-pad throne, a crown of reeds and amber
   stones, a cloak of moss, a scepter with a glowing water orb.
```

---

## Лист B — иконки вещей (`--set icons_items`)

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art inventory icons in the same style as the previous sheets: each icon is true pixel art on a 32x32 grid,
crisp square pixels, no anti-aliasing, limited palette, 1-pixel dark outline, light from top-left. Each item
shown alone, centered, slightly tilted like a classic RPG inventory icon, no text, no frames, no background tiles.
23 icons in 4 rows (6, 6, 6, 5), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between icons: nothing may touch. All icons roughly the same size.

Row 1 (ordinary item bases):
1. Blade: a straight steel short sword with a leather grip.
2. Staff: a gnarled wooden staff with a small amber stone on top.
3. Axe: a heavy one-handed war axe with a dark iron head.
4. Crossbow: a small hand crossbow with a loaded bolt.
5. Chainmail: a chainmail shirt.
6. Robe: a folded mage robe with a hood, deep blue cloth with trim.

Row 2:
7. Plate armor: a steel breastplate with pauldrons.
8. Charm: a woven charm amulet with feathers and a bead.
9. Fang necklace: a big beast fang on a cord.
10. Totem: a small carved wooden totem figure on a string.
11. Signet band: a gold ring with a red gem.
12. Plain ring: a simple silver ring with a small blue stone.

Row 3:
13. Seal ring: a heavy bronze seal ring with an engraved rune.
14. Slime King's crown: a rusty iron crown dripping with green slime.
15. Toad staff: a staff topped with a dried toad and a water bead.
16. Witch's ice ring: a ring made of blue ice with a frozen white gem.
17. Bog horror hide: a folded mossy leathery hide armor with roots growing on it.
18. Drowned man's lantern: an old ship lantern with a cold blue flame inside.

Row 4:
19. Mire fang dagger: a curved blade made from a giant green fang, wet and glistening.
20. Amber beetle seal: a ring with a glowing amber beetle set in it.
21. Reed cloak: a cloak woven from dry cattail reeds.
22. Shaman drum: a small round hand drum with painted swirls and feathers.
23. Cattail bolt: a crossbow bolt fletched with cattail fluff, its tip green with poison.
```

---

## Лист C — иконки даров (`--set icons_gifts`)

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art ability icons in the same style as the previous sheets: each icon is true pixel art on a 32x32 grid,
crisp square pixels, no anti-aliasing, limited palette, 1-pixel dark outline. Each icon is a single bold
emblem (not a framed square), centered, readable at small size, glowing accents, no text.
17 icons in 3 rows (6, 6, 5), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between icons: nothing may touch.

Row 1:
1. Amber blood: a drop of glowing amber blood.
2. Master's hand: a gauntleted fist gripping a sword hilt, motion lines.
3. Word of power: an open book with a bright violet rune rising from it.
4. Second wind: a swirl of white wind around a small green heart.
5. Reaction expert: two colliding orbs, one fire-orange and one ice-blue, with a spark between them.
6. Mire hunter: a spear tip dripping with water drops.

Row 2:
7. Mire fury: a roaring red beast face with mud splashes.
8. Living wall: a stone tower shield with moss and a glowing crack.
9. Ash heart: a black heart with orange embers glowing inside.
10. Permafrost: a snowflake frozen inside a blue ice shard.
11. Holy spring: a small golden chalice overflowing with light.
12. Heron's eye: a sharp yellow heron eye with a crosshair glint.

Row 3:
13. Reed shadow: a hooded dark silhouette among reeds, with a dagger gleam.
14. Bog roots: green roots wrapped around a glowing seed.
15. Witch's gift: a pale hand holding an ice crown.
16. Amber heart: a large faceted amber heart pulsing with light.
17. Leech blood: a black leech curled around a red drop.
```

---

## Иллюстрации экспедиции (`tools/import_illustrations.py`)

Каждый лист — 4 иллюстрации сеткой 2×2; блок стиля уже вставлен в каждый запрос. **Героев на картинках нет:**
игра сама ставит фигурки текущего отряда на передний план (слева внизу, с тенью), поэтому картинка подходит
к любому составу. В запросе — пустая площадка под отряд в левой нижней трети; NPC (ведьма, кузнец, жабы,
торговец) остаются частью сцены и стоят в центре или справа.

Игра уменьшает картинку до 192×128 и даёт общую палитру листа, поэтому важны крупные формы, читаемый силуэт
и свет; мелкие детали пропадут. Многошаговые сцены имеют картинку на шаг (`sunken_chapel.belfry` и т.п.).

### Лист 0 — акты и таверна (`--sheet 0`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Act I, the edge of the swamp": a wooden boardwalk starting in the lower left and leading into misty marsh at
   dusk, dead trees, a far amber glow on the horizon.
2. "Act II, the deep mire": black water, giant mangrove roots, carved toad totems with eyes, fog, green swamp
   lights; a muddy bank in the lower left.
3. "Act III, the heart of the swamp": a huge living bog with roots like veins converging on a pulsing amber
   light in the distance, red-violet sky, ominous; a ridge of roots to stand on in the lower left.
4. "The Amber Mug tavern": a cozy empty timber tavern interior, a big hearth on the right, an amber lamp, mugs
   and an empty bench and table, a barkeeper behind the counter in the back; open floor in the lower left.
```

### Лист 1 — лагерь, торговец, итоги (`--sheet 1`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Camp": a small campfire on a dry hillock in the swamp at night, empty bedrolls and a pot over the fire on
   the right, fireflies, stars.
2. "Swamp merchant": a hooded merchant in a flat-bottomed boat with a lantern, a chest of goods and hanging
   trinkets, on the right side; a little wooden pier in the lower left.
3. "Victory": a hilltop at dawn with a glowing amber crystal on a stone pedestal on the right, the swamp below
   clearing in golden light.
4. "Defeat": a broken shield and a fallen banner sinking into dark water on the right, fog, a single cold light.
```

### Лист 2 — встречи (`--sheet 2`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Chest in the mud": an iron-bound chest half sunk in brown swamp mud in the middle, something with tentacles
   moving under the water nearby.
2. "Leech ford": the only ford across a stream, swarming with fat black leeches, the far bank on the right.
3. "Drowning traveler": a mercenary up to his chest in a bog in the middle-right, reaching out a hand, his sword
   on his back.
4. "Amber-eyed idol": a carved wooden idol on a tussock on the right, glowing amber eye sockets, offerings at
   its base.
```

### Лист 3 — встречи (`--sheet 3`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Abandoned camp": a cold campfire, a torn tent, scattered supplies, signs of a hasty escape.
2. "Bones in the mire": an old battlefield, bones and rusty blades sticking out of the water, one blade with
   glowing runes.
3. "Overgrown mushroom": a mushroom as tall as a man on the right, pulsing with pale light, sweet-looking
   spores.
4. "Toad money-changer": a fat toad in a waistcoat sitting on a lily pad on the right, shiny trinkets laid out
   on a leaf.
```

### Лист 4 — встречи и часовня (`--sheet 4`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Old palisade": an abandoned outpost with a wooden palisade and straw training dummies on the right.
2. "Voices in the fog": thick white fog with faint ghostly faces and reaching hands drifting on the right.
3. "Sunken chapel": the spire of a chapel rising from the water on the right, a candle burning in the belfry
   window.
4. "Belfry": inside a dry belfry, a candle before an icon of a drowned saint, an old bronze bell, a donation
   box; wooden floor in the lower left.
```

### Лист 5 — часовня и жабий базар (`--sheet 5`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Underwater door": murky underwater view of a sunken chapel door, a chain going down into darkness, bubbles;
   a stone ledge in the lower left.
2. "Chapel altar": a dry altar in a flooded chapel with a fist-sized glowing amber drop on it, on the right.
3. "Toad bazaar": a floating market on rafts, toad merchants with goods, toad guards with spears; a raft in the
   lower left.
4. "Market stalls": close-up of bazaar stalls with potions, nets and lanterns, a toad haggling behind them.
```

### Лист 6 — гадалка, пиявочник, кузнец (`--sheet 6`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Toad fortune-teller": an old toad seer on the right looking into a bowl of swamp water, glowing reflections.
2. "Leech master": a hermit sitting in a rusty cauldron full of leeches on the right, jars of leeches around
   him.
3. "Leech master talks": the hermit on the right pointing to a distant amber glow, by a smoky fire.
4. "Broken cart": an overturned blacksmith's cart, tools scattered, toad footprints leading into the reeds.
```

### Лист 7 — нить кузнеца и ведьмы (`--sheet 7`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Toad raiders' camp": a reed palisade on the right, toad raiders drinking swamp brew by a fire, a tied-up
   blacksmith.
2. "Blacksmith's debt": a forge smoking on a small island on the right, a burly blacksmith waving with a hammer.
3. "Hut on stilts": a witch's hut on thin stilts over the water on the right, blue smoke from the chimney, frost
   on the porch.
4. "Inside the hut": a grey-haired woman with an icicle crown stirring a cauldron that glows blue, on the right;
   plank floor in the lower left.
```

### Лист 8 — ведьма и янтарь (`--sheet 8`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Witch's envoy": a raven made of ice perched on a dead branch on the right, frost spreading from its claws.
2. "The price of the pact": the ice witch standing on an icy tussock in fog on the right, holding out her hand.
3. "Glowing mire": an amber light shining from under the dark water, warm and alive.
4. "Magpie nest": a huge nest on a dead tree on the right, magpies carrying shiny things, an amber glint inside.
```

### Лист 9 — грот и спутники (`--sheet 9`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Amber call": three amber shards glowing on a flat rock, light beams pulling towards a cave on the right that
   shines from inside.
2. "Wandering lights": blue wisps circling over the water on the right, cold and sorrowful.
3. "Rustle in the reeds": tall reeds on the right with hidden yellow eyes and spear tips of an ambush.
4. "Swamp gas": big bubbles of gas rising from the bog on the right, faint green haze.
```

### Лист 10 — спутники (`--sheet 10`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Rotten bridge": a rotten wooden bridge over a deep channel, its near end in the lower left.
2. "Talking heron": a giant heron standing on one leg on the right, an amber shard in its beak.
3. "Warm pond": a murky steaming pond on the right with a thin rim of ice at its edge.
4. "Stranger's purse": a fat purse hanging on a snag on the right as bait, a hidden net trap around it.
```


### Лист 11 — пленник, тайник, таможня, коронация (`--sheet 11`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Toad guards and a prisoner": two upright armored toad guards with shell helmets and spears drag a thin ragged human poacher on a rope along a boardwalk, on the right; the prisoner looks back over his shoulder.
2. "Poacher's cache": a crooked willow on the right, a lean hooded poacher with a longbow leaning on it, an open hidden sack of furs, arrows and coins in the roots.
3. "Toad customs": a heavy rusty chain stretched across a boardwalk on the right, a fat toad tax collector at a little table with a wet scroll and scales, two toad guards with spears behind him.
4. "Toad coronation": a mossy tussock throne in the middle-right, an old toad queen with a reed-and-amber crown and a young muscular toad pretender with a crude crown facing each other, crowds of toads with torches.
```

### Лист 12 — колокол, звонарь, деревня, пир (`--sheet 12`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Bell under the bog": black still water on the right with rings spreading and bubbles rising, the top of a green bronze bell barely visible below the surface, a dead tree with a hanging rope.
2. "The drowned bell-ringer" (secret boss): a leaning wooden bell tower in the middle of the bog on the right, a bloated drowned monk in a rotten cassock at the top, a bell rope wound around his arm, cold green light.
3. "Fever village": a village of huts on stilts on the right, boarded doors marked with chalk crosses, a sick old headman coughing on a ladder, smoke and a pale fever haze.
4. "Village gratitude": a cart loaded with pies, dried fish and a sword, villagers with pitchforks and lanterns smiling on the right, warm lantern light at dusk.
```

### Лист 13 — самосуд, заводь, дух, Ржавые (`--sheet 13`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Lynch mob": an angry crowd of swamp villagers with pitchforks and torches blocking a boardwalk on the right, the headman in front pointing, red torchlight.
2. "Mirror pool": a perfectly still pool like black glass on the right, in it the reflection of a lone figure that is NOT standing on the bank — the reflection smiles and beckons; moonlight.
3. "Hungry spirit": a translucent pale old man sitting on the path on the right, chewing on nothing, his body faintly glowing, empty bowls around him, fog.
4. "The Rust Company camp": five mercenaries in rusty chain mail around a campfire on the right, their scarred captain sharpening a big sword and squinting, a tattered rust-red banner.
```

### Лист 14 — лагерь у Сердца, лодочник, библиотека, книга (`--sheet 14`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Rivals at the Heart": the Rust Company camp on a ridge of roots on the right, the captain standing up, and far behind them a huge pulsing amber light of the swamp heart, red-violet sky.
2. "Silent ferryman": a narrow black boat without oars gliding on black water toward the bank, a tall cloaked ferryman with no face holding out an open empty palm, a single lantern on the bow.
3. "Sunken library": the roof of a stone tower sticking out of the water, inside a dry hall with leaning shelves and books in silt, a lectern on the right with a black book hanging on a chain.
4. "The forbidden tome": a close view of the black book on a chain above a lectern on the right, a silver witch-hunter sigil on its cover, faint whispering purple glow from its pages, candles bending away.
```

### Лист 15 — охотники, яйцо, вылупление, двойники (`--sheet 15`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Witch hunters": three tall figures in grey cloaks with silver blades and wide hats blocking the path on the right, one holding a lantern with a holy symbol, cold light.
2. "Leech egg": a nest of slime and weed on the right, in it a giant translucent egg the size of a barrel with something dark moving inside, purple glow.
3. "Hatchling": a broken giant eggshell on the right and a dog-sized baby leech, round toothless mouth, looking up cutely, a small campfire nearby at night.
4. "Fog doubles": in thick fog on the right, four grey featureless fog creatures shaped like armed travellers (fog monsters, NOT the player's party), blank watery eyes, mist trailing from their edges, eerie.
```

### Лист 16 — алтарь, беглец, огонёк, поляна (`--sheet 16`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Amber altar": a flat stone slab covered with thick hardened amber on the right, inside the amber flies, coins, teeth and fingers are trapped, a warm inner glow.
2. "Deserter shaman": an old toad shaman with a broken staff hiding under a snag on the right, frightened, torches of a search party far behind in the reeds.
3. "The wisp calls": a small pale-blue will-o'-wisp hovering above the path, leaving a thin glowing trail away into dark reeds on the right.
4. "Wisp hoard": a hidden glade where dozens of small wisps float over a pile of drowned treasure — rings, blades, bones, a crown — on the right, magical blue light.
```

### Лист 17 — сёстры, сделка, жаба-игрок, Старый Зуб (`--sheet 17`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Three sisters at the cauldron": three hunched swamp hags around one big bubbling cauldron on the right, green steam, frog skulls and herbs hanging.
2. "The sisters' bargain": a close view of the three hags on the right, one holding a long glowing thread, another with rusty shears about to cut it, ominous green light.
3. "Toad gambler": a toad in a tricorn hat sitting on a barrel on the right, shaking a dice cup, coins and small treasures stacked on a crate as stakes, a lantern.
4. "Lair of Old Tooth" (secret boss): a shore littered with hunters' bones and broken spears, a gigantic old crocodile the size of a boat dozing on a sandbar on the right, a scar across one eye.
```

### Лист 18 — плач в камышах, свадьба, караван, лунная жаба (`--sheet 18`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy swamp adventure, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood),
strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (bank, boardwalk, floor, hillock) seen
at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (witch, blacksmith, toads, merchant, hermit, heron…)
ARE allowed and should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Crying in the reeds": tall dark reeds on the right with a small pale shape of a child barely visible among them, no footprints in the mud, something watching from the water, cold mist.
2. "Toad wedding": a festive feast on lily pads on the right, toads with gourd drums and garlands, a toad bride with a duckweed veil, paper lanterns, warm joyful light.
3. "Sunken caravan": sides of sunken toad rafts sticking out of the water on the right, bundles and crates with a royal toad seal floating, an iron-bound chest half under water.
4. "Moon frog": a frog made of pure gold sitting on a lily pad on the right, the full moon reflected in its eyes, the water around it shining silver, magical stillness.
```
---

## Лист E — враги и союзники событий болота (`--set swamp_events`)

Браконьер, ополченцы и наёмники бывают и врагами, и союзниками-гостями (идут с отрядом несколько боёв). Звонарь,
Старый Зуб и Матка пиявок — тайные боссы, Квакс — новый финальный босс, если жабья корона досталась ему.

```
python tools/import_sheet.py assets/art_src/sheet_swamp_events.png --set swamp_events --preview p.png
```

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy swamp characters for a tactics RPG.
10 figures in 2 rows (5, 5), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between figures: nothing may touch. Elites (marked E) are about 1.3x a normal figure, bosses (marked B) about 1.7x.

Row 1:
1. Poacher: a lean ragged human hunter in a hooded fur cape, a longbow drawn, a knife on the belt, a rope burn
   on the wrists.
2. Village militiaman: a swamp villager in a padded jerkin and a reed hat, holding a pitchfork, a small lantern
   on the belt.
3. Rust mercenary: a human sell-sword in rusty chain mail and a dented helmet, a short sword and a round shield
   painted rust-red.
4. (E) Rust captain: a scarred broad mercenary captain in rusty plate, a big two-handed sword on his shoulder, a
   torn rust-red cloak.
5. Witch hunter: a tall figure in a grey cloak and a wide-brimmed hat, a silver blade in one hand and a hand
   crossbow in the other, a silver holy pendant.

Row 2:
6. Fog double: a grey featureless humanoid made of fog and water, shaped like an adventurer with a sword, blank
   watery eyes, mist trailing from its edges.
7. (B) The drowned bell-ringer: a bloated drowned monk in a rotten cassock, green skin, a heavy bronze bell
   hanging on a chain from his hand like a flail, a bell rope wound around his arm, seaweed in his hair.
8. (B) Old Tooth: a gigantic old crocodile, mossy dark back plates, a scar across one blind eye, broken spears
   stuck in its hide, jaws half open, low on four legs.
9. (B) Leech mother: an enormous bloated purple-black leech queen rearing up, a ring of teeth, clusters of small
   leeches clinging to her body, dripping slime.
10. (B) Kvaks, king of the Heart: a huge muscular toad king with a crude crown of reeds and amber, a glowing
   amber heart pulsing in his chest, a heavy club of bog oak, a cloak of moss.
```

---

## Лист F — иконки узлов карты похода (`--set icons_map`)

Иконка ложится в деревянный медальон узла на карте (кайма — цвет вида узла), поэтому фон у иконки не нужен:
только предмет, крупным силуэтом. Пока картинок нет, игра рисует пиксельные заглушки.

```
python tools/import_sheet.py assets/art_src/sheet_icons_map.png --set icons_map --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
7 icons in 2 rows (4, 3), in EXACTLY this order (left to right, top row first). Wide empty magenta space between
icons: nothing may touch.

Row 1:
1. Battle: two crossed steel swords with leather-wrapped hilts, blades up.
2. Elite: a horned beast skull with glowing orange eye sockets and cracked bone.
3. Boss: a menacing crowned skull, gold crown with red gems, dark eye sockets with violet glow.
4. Event: a rolled parchment scroll half open with a large dark question mark on it, wax seal hanging.

Row 2:
5. Camp: a small campfire with orange flames on crossed logs, a few sparks.
6. Merchant: a fat leather coin purse tied with string, gold coins spilling from it.
7. Story thread: a glowing amber gemstone star with a thin golden thread wound around it.
```

---

## Лист G1 — новые дары, часть 1 (`--set icons_gifts2`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_gifts2.png --set icons_gifts2 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
22 icons in 4 rows (6, 6, 6, 4), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. An iron heart wrapped in a chain, grey steel.
2. Two crossed gloved hands with motion streaks.
3. A sharp golden eye inside a crosshair.
4. A glowing blue gem with concentric calm rings.
5. Pale undead lips with a drop of blood.
6. A small spring of glowing blue water bubbling from a stone.
Row 2:
7. A cracked glass cannon glowing red inside.
8. A forearm covered with sharp thorns.
9. A battered shield with a golden aura behind it.
10. A soul-flame shaped like a heart, orange fire.
11. A soul-flame shaped like a heart, pale blue ice.
12. A soul-flame shaped like a heart, violet lightning.
Row 3:
13. A light boot leaving a ghostly afterimage.
14. A red snarling wolf mouth dripping.
15. An open glowing chest with three blue orbs.
16. A sword through a giant's broken horned helmet.
17. A battle axe dripping red blood.
18. A heavy riveted steel breastplate.
Row 4:
19. A brass spyglass with a sparkle.
20. Two arrows with leech-shaped heads.
21. A swirling violet ribbon of magic.
22. An open spellbook with a burst of sparks.
```

---

## Лист G2 — новые дары, часть 2 (`--set icons_gifts3`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_gifts3.png --set icons_gifts3 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
23 icons in 4 rows (6, 6, 6, 5), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. Two hands holding a small green glowing leaf.
2. A tall tower shield with a guardian rune.
3. Two crossed rapiers over a red ribbon.
4. A bowstring glowing orange hot.
5. A heart made of fire with an ember core.
6. A holy candle that never goes out.
Row 2:
7. A dagger in shadow with a red edge.
8. A wolf's head howling, leaf-green.
9. Three crossed spears like a palisade.
10. A carved totem pole head with glowing eyes.
11. A golden tuning fork with three notes.
12. Two powder barrels tied together with a fuse.
Row 3:
13. A ram's horned head charging.
14. A hunting trap with a red mark.
15. An ice fortress tower.
16. A crown made of bones.
17. An hourglass with extra golden sand.
18. A heavy dark star pulling small stones.
Row 4:
19. A mountain with stone roots.
20. A bubbling green potion bottle with three herbs.
21. A red goblet overflowing.
22. A marshal's baton with a gold tip.
23. Three glowing threads tied in a knot.
```

---

## Лист I1 — новые базы и уникальные вещи (`--set icons_items2`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_items2.png --set icons_items2 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
16 icons in 4 rows (4, 4, 4, 4), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. A short dagger.
2. A heavy war hammer.
3. A slim magic wand.
4. A leather jerkin.
Row 2:
5. A hooded cloak.
6. A small carved idol.
7. A signet ring with a seal.
8. A war hammer crackling with blue lightning.
Row 3:
9. A black dagger with a red widow spider.
10. A wand topped with an ice crystal.
11. A wand topped with a burning ember.
12. A cloak with shiny mirror patches.
Row 4:
13. A leather vest with leeches sewn on.
14. A mossy green hunter's cloak.
15. A crown of thorns.
16. A war drum with red stripes.
```

---

## Лист I2 — новые уникальные вещи (`--set icons_items3`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_items3.png --set icons_items3 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
16 icons in 4 rows (4, 4, 4, 4), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. A glowing orange phoenix feather.
2. A ring set with a dice.
3. A royal gold seal with a crown.
4. A ring shaped like an eel with sparks.
Row 2:
5. A swamp lantern with green light.
6. A small crown with a toad face.
7. A bow with lightning along the string.
8. A staff made of bones with a skull.
Row 3:
9. An executioner's broad axe.
10. Heavy plate armor with a shield emblem.
11. A ring shaped like a green snake.
12. A golden sun amulet.
Row 4:
13. A ring with a tiny hourglass.
14. A smoldering grey cloak of ash.
15. A wand with a swirling water orb.
16. A black glass knife.
```

---
## Лист D — некромант и хрономант (`--set necro_time`)

```
python tools/import_sheet.py assets/art_src/sheet_necro_time.png --set necro_time --preview p.png
```

Лежащие скелеты — трупы на поле (ресурс некроманта), поднятые скелеты — 4 вида вразнобой, песочные часы — стазис
(юнит виден сквозь стекло, поэтому середина колб пустая и прозрачная).

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art, crisp square pixels,
no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left, 2-3 tone shading.
No text, no labels, no frames. Wide empty magenta space between figures: nothing may touch.
9 figures in 3 rows of 3, in EXACTLY this order (left to right, top row first).

Row 1 — skeletons LYING on the ground, seen from three-quarter view above, wider than tall (about 40x24 pixels):
1. A skeleton lying on its back, arms spread, a rusty sword beside it.
2. A skeleton lying on its side, curled up, a few scattered bones and a cracked skull.
3. A collapsed pile of bones with a skull on top and a torn rag.

Row 2:
4. A skeleton lying face down with a broken shield on its back.
5. Raised skeleton servant: hunched, rusty short sword, teal glow in the eye sockets, faces RIGHT, standing.
6. Raised skeleton archer: bony, a small bow, a quiver, teal glow, faces RIGHT, standing.

Row 3:
7. Raised skeleton brute: big bones, a heavy bone club, a horned helmet, teal glow, faces RIGHT, standing.
8. Raised skeleton spearman: a rusty spear and a round shield, teal glow, faces RIGHT, standing.
9. A large magical hourglass standing upright, about 40x56 pixels: dark brass frame with two pillars and round
   caps, clear glass bulbs with golden sand, the middle of both bulbs mostly EMPTY so a small figure would be
   visible through the glass; soft golden glow on the glass edges.
```

---

## Лист Q — стрелы колчанов лучника (`--set icons_arrows`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_arrows.png --set icons_arrows --preview p.png
```

Иконки ложатся в `assets/icons/arrow_<вид>.png`; пока их нет, панель колчанов над навыками лучника рисует простую
стрелу цвета колчана.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is ONE arrow drawn diagonally from bottom-left to top-right (head at the top right),
filling most of its square, readable when tiny; the arrowhead and fletching show what kind of arrow it is.
No text, no letters, no frames, no background plates, no circles behind the objects.
10 icons in 2 rows (5, 5), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. Fire arrow: the arrowhead wrapped in a bright orange-yellow flame, a few embers trailing behind the shaft.
2. Frost arrow: a pale-blue ice-crystal arrowhead, a thin rime of frost along the shaft, two tiny snowflakes.
3. Poison arrow: a dark arrowhead dripping bright green venom, green-tinted fletching, one falling drop.
4. Bleeding arrow: a cruel barbed serrated steel arrowhead with dark red blood on the barbs, red fletching.
5. Storm arrow: a violet-blue arrowhead crackling with a small zigzag lightning bolt around it.

Row 2:
6. Blunt arrow: a heavy round wooden knob instead of a point, thick brown shaft, plain grey fletching.
7. Vampire arrow: a dark crimson fang-shaped arrowhead, purple-black bat-wing fletching, a small red glow.
8. Explosive arrow: a small black round bomb with a lit sparking fuse tied behind a short arrowhead.
9. Piercing arrow: a long narrow polished steel bodkin point, slightly gleaming, cracking a tiny armor plate.
10. Bouncing arrow: a golden arrowhead with a curved motion trail looping behind it, as if ricocheting.
```

---

## Лист S — тотемы шамана (`--set totems_shaman`)

```
python tools/import_sheet.py assets/art_src/sheet_totems_shaman.png --set totems_shaman --preview p.png
```

Пока моделей нет, новые тотемы рисуются спрайтом тотема грозы; варианты из веток (боевой, неистовства, мудрости,
силы, скалы, щитов, родники) берут модель своего тотема с этого листа.

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets (the existing storm totem and healing totem):
true pixel art on a 32x32 grid per figure, crisp square pixels, no anti-aliasing, no blur, no gradients, limited
palette, 1-pixel dark outline, light from top-left, 2-3 tone shading. Three-quarter view, every totem stands upright
on an invisible ground line, no ground shadow, no text, no labels. Carved wooden and stone shaman totem poles for a
dark fantasy tactics RPG, each about 3/4 of a human's height unless noted.
5 figures in 1 row, in EXACTLY this order (left to right). Wide empty magenta space between figures: nothing may touch.

1. Rage totem: a dark red wooden pole with a snarling carved boar face, two crossed bone axes tied on top, glowing
   orange-red eyes, a few red war paint stripes, small embers floating up.
2. Spirit totem: a pale grey-violet pole with three stacked serene carved faces, a ring of small floating violet
   spirit wisps around the top, glowing lavender runes.
3. Stoneskin totem: a squat totem of stacked grey boulders bound with rope, a carved bear face in the middle stone,
   a few glowing amber cracks, moss on the base.
4. Lightning rod totem: a tall thin dark wooden pole wrapped in copper bands with a copper spike on top, small blue
   sparks crackling around the spike, a carved eagle face.
5. (Big) Thunder idol: a large ancient stone idol about 1.4x a human's height, a stern carved thunder-god face,
   glowing blue-white eyes and runes, lightning arcs between two horn-like stone spikes on its head.
```


---

## Лист A1 — артефакты таверны (`--set icons_artifacts`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_artifacts.png --set icons_artifacts --preview p.png
```

Иконки ложатся в `assets/icons/art_<вид>_<редкость>.png`; пока их нет, хранилище и мастерские рисуют простой силуэт
вида в рамке цвета редкости. Ряд — редкость (обычный, редкий, эпический, легендарный), колонка — вид.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is ONE wearable artifact of a dark fantasy tactics RPG, filling most of its square,
readable when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
20 icons in 4 rows (5, 5, 5, 5), in EXACTLY this order (left to right, top row first).
Columns are always: 1. a pair of bracers, 2. a belt with a buckle, 3. a ring with a stone, 4. an amulet on a cord,
5. a talisman (a carved bone and leather charm with a feather).
Wide empty magenta space between icons: nothing may touch.

Row 1 (common): plain iron and brown leather, dull grey stone, simple and worn, no glow.
Row 2 (rare): polished steel with blue-teal trim, small pale-green pearls, a faint teal shine.
Row 3 (epic): dark bronze with amber inlays and violet runes, a soft violet glow on the stones.
Row 4 (legendary): ornate gold with a great orange-amber gem, beast fangs and ember accents, a warm golden glow.
```

## Лист A2 — самоцветы и материалы мастерских (`--set icons_workshop`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_workshop.png --set icons_workshop --preview p.png
```

Иконки: `assets/icons/gem_<камень>.png` (огранённые камни ювелирной) и `assets/icons/mat_<материал>.png`
(руда — уже есть, `mat_ore`).

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is ONE object filling most of its square, readable when tiny.
No text, no letters, no frames, no background plates, no circles behind the objects.
11 icons in 2 rows (5, 6), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1 (cut gems, faceted, with a small sparkle):
1. Ruby: deep red cushion-cut gem.
2. Sapphire: royal blue oval gem.
3. Emerald: green rectangular step-cut gem.
4. Topaz: golden-yellow pear-shaped gem.
5. Amethyst: violet hexagonal gem.

Row 2 (crafting materials):
6. Leather: a rolled brown hide tied with a cord.
7. Herbs: a small bundle of green swamp herbs and a purple flower tied with twine.
8. Raw gems: three rough uncut crystals (red, blue, green) on a lump of grey rock.
9. Toad pearl: a large lustrous pale-teal pearl with a greenish sheen, a drop of swamp water.
10. Embersteel: a small ingot of dark steel with glowing orange cracks and a wisp of smoke.
11. Stardust: a tiny cloth pouch spilling glittering pale-violet star dust with sparkles.
```

---

## Таверна из комнат: иллюстрации, объекты, значки вкладок

Таверна разбита на комнаты (полоса внизу: Зал, Сборы, Мастерская, Двор, Стройка, Зал славы). Пока картинок нет,
комнаты рисуются на фоне зала, двор — ночной улицей, объекты — простыми заглушками.

### Лист 32 — комнаты таверны, часть 1 (`--sheet 32`)

```
python tools/import_illustrations.py assets/art_src/ill_32.png --sheet 32 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), warm amber
lamplight and dark wood, one clear light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: EMPTY rooms — no people, no adventurers, no animals. The game draws its own heroes and objects on top,
so keep the central and lower areas calm and uncluttered (plain floor, plain walls), details at the edges.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Muster room": the armory by the tavern's back gate before an expedition — weapon racks and hanging cloaks on
   the side walls, a big wooden map table pushed against the back wall under a lantern, travel packs by the door,
   a wide empty plank floor in the middle and front.
2. "Masters' workshop": a long empty workshop hall with a stone wall and soot, shelves with tools, tongs and
   jars along the back wall, hanging herbs and leather strips, a chimney hood; the whole lower third is a clear
   empty stone floor (the game places four work stations along it).
3. "Tavern backyard at night": a cobbled courtyard under a starry night sky with a pale moon, a wooden fence and
   a crooked tree on the left, lantern on a post; the RIGHT HALF is an empty dark area of sky and cobbles (the
   game draws a tall timber dormitory building there).
4. "Hall of glory": a solemn stone hall with banners and candles, two tall arched passages in the back wall side
   by side — the left arch opens onto a misty moonlit graveyard, the right arch onto a warm candle-lit library;
   empty stone floor in front.
```

### Лист 33 — комнаты таверны, часть 2 (`--sheet 33`)

```
python tools/import_illustrations.py assets/art_src/ill_33.png --sheet 33 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy, painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), one clear light
source, moody but readable. No text, no UI, no letters anywhere. EMPTY scenes — no people, no animals.
Order: top-left, top-right, bottom-left, bottom-right.
1. "Building yard": the side of the tavern under construction at dusk — wooden scaffolding, stacks of timber and
   stone blocks, a hoist with a rope, buckets of mortar, warm light from the tavern windows; calm muted colors.
2. "Graveyard panorama": a WIDE misty swamp graveyard at night, seen from the side — dead trees, a crooked iron
   fence, distant crypt silhouettes, a big pale moon, fog banks; the LOWER THIRD is an empty dark earth path
   with NO gravestones (the game draws the graves itself). Calm, melancholic, cold blue light.
3. "Library of chronicles": a candle-lit archive room, tall shelves of old books and scrolls, a reading lectern
   with a huge open book, warm candle glow, dust in the light.
4. "Dormitory room": a small cozy timber bedroom at night — a simple bed with a red blanket on the LEFT, a small
   window with the moon above it, a wall lamp on the right; the RIGHT HALF of the floor is empty (the game puts
   a hero standing there).
```

### Лист O — объекты комнат (`--set room_objects`)

```
python tools/import_sheet.py assets/art_src/sheet_room_objects.png --set room_objects --preview p.png
```

Спрайты ложатся в `assets/sprites/obj_*.png` и `grave_*.png`; игра ставит их в комнаты крупно (×3–5).

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art, crisp square pixels,
no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left, 2-3 tone shading.
Three-quarter view, every object stands on an invisible ground line, no ground shadow, no text, no letters.
Furniture and props of a dark fantasy tavern. 10 objects in 2 rows (5, 5), in EXACTLY this order
(left to right, top row first). Wide empty magenta space between objects: nothing may touch.

Row 1:
1. Notice board: a big wooden board on two posts with a small shingle roof, several pinned parchment notes and
   one red wax seal, a lantern hanging from the corner.
2. Storage chest: a sturdy wooden chest with iron bands and a golden lock, lid closed, a faint glint (smaller
   than the others, about half their height).
3. Forge station: a stone forge with glowing coals and a chimney, bellows on the side, an anvil with a hammer
   in front.
4. Jeweler's bench: a small wooden table with a magnifying lens on a stand, tiny tools and three sparkling gems
   (red, blue, green), a candle.
5. Leatherworker's rack: a wooden frame with a stretched hide, a cutting table with a knife and rolled leather,
   a few hanging straps.

Row 2:
6. Alchemy table: a wooden table with three bubbling flasks (green, violet, blue), an alembic with a small
   flame under it, scattered herbs.
7. Bed: a simple timber bed with a red wool blanket and a white pillow, seen from the side (wide and low).
8. Gravestone 1: a weathered rounded headstone with a carved cross, moss at the base.
9. Gravestone 2: a leaning slab with a carved sword and a small candle at its foot.
10. Gravestone 3: a small stone obelisk with an iron wreath, a few wild flowers.
```

### Лист T — значки комнат для полосы вкладок (`--set icons_tabs`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_tabs.png --set icons_tabs --preview p.png
```

Иконки `assets/icons/tab_<комната>.png`; пока их нет, полоса берёт значки узлов карты.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading, warm amber and dark wood palette. Each icon is ONE object filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates.
6 icons in 1 row, in EXACTLY this order (left to right). Wide empty magenta space between icons.
1. Hall: a foaming amber ale mug.
2. Muster: two crossed swords over a small travel pack.
3. Workshop: a hammer resting on an anvil with a spark.
4. Yard: a parchment notice pinned with a red pin.
5. Building: a saw crossed with a hammer over a wooden plank.
6. Hall of glory: a laurel wreath around a small skull.
```

---

## Общежитие из модулей и двор слоями

Дом во дворе собирается снизу вверх: **основание со входом → этажи 1–6 (у каждого свой вид) → крыша**. Внутри
каждого этажа — проём, сквозь который видна комната (иллюстрации `room_dorm*`, у каждого этажа своя). Модули
ставятся друг на друга вплотную, поэтому у всех ОДИНАКОВАЯ ширина и стены продолжаются по вертикали без швов.
Задник двора — слоями, которые при листании вверх сдвигаются с разной скоростью (параллакс): небо из трёх
стыкующихся частей, дальние крыши города, кроны деревьев, передний план двора. Пока картинок нет — заглушки.

### Лист D — модули дома (`--set dorm_house`)

```
python tools/import_sheet.py assets/art_src/sheet_dorm_house.png --set dorm_house --preview p.png
```

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art, crisp square pixels,
no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left, 2-3 tone shading,
warm amber window light, night colors. STRAIGHT FRONT VIEW (orthographic, no perspective), no text, no letters.
These are stackable MODULES of ONE tall timber-and-stone dormitory house of a dark fantasy tavern.
CRITICAL: every module has EXACTLY THE SAME WIDTH and the same left and right outer wall edges (vertical corner
posts at the very left and right), so they can be stacked on top of each other seamlessly. Flat horizontal top and
bottom edges (except the top of the roof). Nothing sticks out of the wall edges except the roof eaves.
8 modules, in EXACTLY this order: left column top to bottom = 1, 2, 3, 4; right column top to bottom = 5, 6, 7, 8.
Each module is a wide horizontal strip about 3 times wider than tall (the roof and the base may be a bit taller).
Wide empty magenta space between modules: nothing may touch.

STOREYS (modules 2-7): each is one storey of the house facade with ONE LARGE RECTANGULAR CUT-AWAY OPENING in the
middle, about 84% of the width and 80% of the height, filled with FLAT SOLID MAGENTA (#FF00FF) - the game shows the
room inside through it. Around the opening: that storey's own facade frame (beams, stones, sill below, lintel
above). Each storey looks DIFFERENT, the house getting older and more patched-up toward the top:

1. Roof: a steep dark red shingle roof with wide eaves, a stone chimney with a wisp of smoke, a small round attic
   window glowing amber, a weather vane; flat bottom edge as wide as the walls plus the eaves.
2. Storey 1: heavy grey stone masonry frame, a carved wooden lintel, an iron lamp bracket on the left post.
3. Storey 2: half-timbered frame (dark oak beams, cream plaster), a flower box under the opening.
4. Storey 3: plank boards frame with diagonal braces, a small hanging sign with a moon, ivy climbing a post.
5. Storey 4: half-timbered with red-brown plaster, a little wooden balcony rail under the opening.
6. Storey 5: weathered planks patched with mismatched boards and metal plates, a bird nest on the lintel.
7. Storey 6: a low attic storey of dark beams under the eaves, cobwebs, a hanging lantern.
8. Base (ground floor): wide stone foundation with stone steps, a big arched oak door with iron hinges in the
   center, two small barred windows glowing amber at the sides, a lantern above the door, moss at the bottom.
```

### Лист L — слои двора для параллакса (`--set yard_layers`)

```
python tools/import_sheet.py assets/art_src/sheet_yard_layers.png --set yard_layers --preview p.png
```

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art in the same style as the previous tavern illustrations (night, warm amber lamp light, cold blue
moonlight), crisp square pixels, no anti-aliasing, no text. Three WIDE HORIZONTAL LAYERS for a parallax background;
each layer spans the FULL WIDTH of the image edge to edge, with magenta above it (that is sky, the game fills it).
Layers are placed one under another, separated by wide magenta gaps; nothing may touch.
Order from top to bottom:
1. Far layer: silhouettes of distant town rooftops at night - steep roofs, chimneys, a bell tower, a few tiny lit
   windows; dark blue-violet, low contrast, flat bottom edge.
2. Middle layer: dark tree crowns and bare branch silhouettes, a few lanterns hanging between the trees,
   deep blue-green, a little lighter than the far layer, flat bottom edge.
3. Near layer (the yard itself): a cobbled courtyard strip with a wooden fence, a big crooked oak at the far LEFT,
   barrels and a lamp post with a glowing lantern; the RIGHT third is just open cobbles (the game puts the dorm
   house there); flat bottom edge, cobbles reach the bottom.
```

### Лист 34 — комнаты общежития (`--sheet 34`)

```
python tools/import_illustrations.py assets/art_src/ill_34.png --sheet 34 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy, cozy, night, warm lamp light. No text, no UI. EMPTY rooms - no people, no animals.
Straight front view into the room (like a dollhouse cut-away); the RIGHT HALF of the floor is empty (the game puts a
hero standing there); furniture on the left and on the back wall. Every room is DIFFERENT.
Order: top-left, top-right, bottom-left, bottom-right.
1. Soldier room: a narrow cot, a weapon rack with a spear and a shield, a chest, a map pinned to the wall.
2. Scholar room: a bed under a slanted shelf of books, a writing desk with a candle and scrolls, a globe.
3. Hunter room: a fur-covered bed, antlers and pelts on the wall, a bow on hooks, drying herbs.
4. Healer room: a clean bed with white linen, shelves of jars and bandages, a basin and a pitcher, a lamp.
```

### Лист 35 — небо двора слоями и чердак (`--sheet 35`)

```
python tools/import_illustrations.py assets/art_src/ill_35.png --sheet 35 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art, true pixel art on a 192x128 grid per illustration,
crisp square pixels, no anti-aliasing, limited palette, dithering allowed. Night. No text, no UI.
The first three are parts of ONE TALL NIGHT SKY stacked vertically by the game (low part at the bottom, the middle
part repeated several times, the high part on top). Colors and gradients MUST MATCH at the joins: the TOP edge of
part 1 continues into the BOTTOM edge of part 2; the TOP edge of part 2 matches its own BOTTOM edge (it repeats)
and the BOTTOM edge of part 3. NO ground, NO buildings, NO trees in them - only sky.
Order: top-left, top-right, bottom-left, bottom-right.
1. Sky, low: the sky just above the horizon - a faint warm amber town glow at the very bottom fading up into deep
   blue, a few thin clouds.
2. Sky, middle (repeats seamlessly top-to-bottom): deep blue-violet night sky, scattered small stars, a couple of
   thin wispy clouds, the same color at the top and bottom edges.
3. Sky, high: the darkest sky with many stars and a big pale moon with a soft halo in the upper area; bottom edge
   matching part 2.
4. Attic room: a cozy attic bedroom under slanted roof beams, a small round window with the moon, a narrow bed and
   old trunks on the left; the right half of the floor empty.
```

---

## Огранка: станок и верстаки мастерских

Камень рисуется кодом (трассировка лучей), картинки нужны только для станка и фона. Пока их нет — рисуются
простые формы.

### Лист J — детали гранильного станка (`--set facet_machine`)

```
python tools/import_sheet.py assets/art_src/sheet_facet_machine.png --set facet_machine --preview p.png
```

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art, crisp square pixels,
no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left, 2-3 tone shading.
Parts of an old-world gem FACETING MACHINE (a jeweler's lapidary), brass, steel and dark wood, STRAIGHT SIDE
VIEW (orthographic, no perspective), no text, no letters, no numbers. 7 parts in 2 rows (4, 3), in EXACTLY this
order (left to right, top row first). Wide empty magenta space between parts: nothing may touch.

Row 1:
1. Lap disk seen exactly edge-on: a very wide flat horizontal grinding disk (about 7 times wider than tall),
   dark grey cast iron rim with a fine diamond-grit top surface (light speckles), a thin bright edge on top.
2. Lap stand: a squat cast-iron pedestal with a wooden base plate and a little water drip can, wider at the
   bottom, flat top (the disk sits on it).
3. Mast: a TALL thin vertical steel column (about 7 times taller than wide) with a brass height-adjust screw
   and a few ring marks, flat bottom.
4. Quadrant head: a round brass protractor dial with an engraved 0-90 quarter-circle scale (only tick marks,
   NO numbers), a pivot knob in the center.

Row 2:
5. Index gear: a round brass gear wheel seen face-on with many small teeth around the rim and a hole in the center.
6. Loupe ring: a round brass magnifier frame seen face-on, thick ornate rim with rivets; the INSIDE of the ring is
   FLAT SOLID MAGENTA (#FF00FF) - empty, the game shows the gem through it.
7. Diagram plate: a round dark slate disc with a thin brass bezel and faint engraved concentric guide rings and
   radial lines (no numbers).
```

### Лист 36 — верстаки мини-игр мастерских (`--sheet 36`)

```
python tools/import_illustrations.py assets/art_src/ill_36.png --sheet 36 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy, warm lamp light, close-up views of craftsmen's workbenches. No text, no UI, no people.
The CENTER and LOWER-LEFT of every picture must be calm and fairly dark (the game draws its machine and UI there),
details on the far edges and the back wall. Order: top-left, top-right, bottom-left, bottom-right.
1. Jeweler's bench: a dark wooden workbench close-up, velvet cloth, tweezers, a candle and a hanging lamp,
   small boxes of gems on a shelf on the back wall, a window with night outside.
2. Blacksmith's forge corner: glowing forge on the right edge, tongs and hammers on the back wall, a quench
   barrel with water, warm orange light, empty dark anvil area in the center.
3. Alchemist's table: shelves of colored flasks and jars on the back wall, hanging dried herbs, a small brazier
   on the side, an empty dark table surface in the center.
4. Leatherworker's bench: hides stretched on frames on the back wall, rolls of leather, awls and thread on hooks,
   a large empty work table surface in the center.
```

---

## Рынок

Седьмая комната таверны. Камни рисуются кодом; нужны фон и значок вкладки (пока — значок рубина и затемнённый зал).

### Лист 37 — рынок (`--sheet 37`)

```
python tools/import_illustrations.py assets/art_src/ill_37.png --sheet 37 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy town at dusk, warm lanterns, no text, no letters, no signs with writing. No people in the foreground;
the CENTER of every picture is calm and darker (the game draws trade panels there), details at the edges.
Order: top-left, top-right, bottom-left, bottom-right.
1. Market square next to the tavern: wooden stalls with striped awnings around a cobbled square, lanterns on
   strings, a well, crates and barrels, warm dusk light.
2. Gem merchant's stall close-up: a dark velvet-covered counter, small glass cases and trays with sparkling rough
   crystals and cut gems, a brass balance scale, a jeweler's loupe, a hanging lantern.
3. General goods stall close-up: sacks, baskets of herbs, rolls of leather, ingots of ore, jars, a hanging lamp.
4. The market square at night: closed stalls under covers, puddles reflecting lanterns, moonlight.
```

### Лист T2 — значок вкладки «Рынок» (`--set icons_tabs2`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_tabs2.png --set icons_tabs2 --preview p.png
```

```
Make ONE icon sheet image, 1024x1024, plain flat solid magenta background (#FF00FF) everywhere.
One pixel art game icon in the exact same style as the previous tab icons (32x32 grid, crisp pixels, 1-pixel dark
outline, warm amber palette), centered: a small market stall awning with a coin purse and a red gem in front.
No text, no frame, no background plate.
```


---

## Кузня (Горн мастера): спрайты этапов

Металл рисуется кодом (слои, блеск, каление); картинки нужны для инструментов и мебели кузни. Пока их нет —
простые формы. Фон — верстак кузнеца (лист 36, уже есть).

### Лист K — инструменты кузни (`--set forge_props`)

```
python tools/import_sheet.py assets/art_src/sheet_forge_props.png --set forge_props --preview p.png
```

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Detailed pixel art game sprites in the exact same style as the previous sheets (the gem faceting machine parts):
crisp square pixels, no anti-aliasing, no blur, rich but limited palette, 1-pixel dark outline, light from the
top-left, 3-4 tone shading, worn iron, soot, warm forge light. STRAIGHT SIDE VIEW (orthographic), no text.
Blacksmith's workshop equipment of a dark fantasy tavern. 12 objects in 3 rows (4, 4, 4), in EXACTLY this order
(left to right, top row first). Wide empty magenta space between objects: nothing may touch.

Row 1:
1. Anvil: a heavy black iron anvil with a pointed horn on the LEFT, flat polished face, hardy hole, standing on a
   thick wooden stump with iron bands. Wide (about twice wider than tall).
2. Forge hearth: a stone and brick forge with a glowing coal bed, an OPEN FIRE MOUTH in the lower middle where a
   bar can be put in, a sooty chimney hood on top.
3. Crucible on a stand: a thick clay-and-iron crucible pot, OPEN TOP (seen slightly from above, the rim is an
   empty dark oval — the game draws the molten metal), iron tripod legs, coals under it.
4. Quench barrel: a wooden barrel full of dark water with a little steam, iron hoops.

Row 2:
5. Bellows: big leather forge bellows with wooden boards and a brass nozzle pointing RIGHT.
6. Hot-cut chisel: a vertical blacksmith's chisel with a wooden handle on top and a sharp wedge tip at the bottom.
7. Tongs: long blacksmith's tongs, horizontal, jaws on the RIGHT.
8. Hand hammer: a blacksmith's hand hammer, head on top, handle down, slightly tilted.

Row 3:
9. Sledgehammer: a big two-handed sledgehammer, heavy square head on top, long handle down.
10. Cross-peen hammer: a hammer with a narrow wedge-shaped peen on one side of the head.
11. Flatter: a set hammer with a wide flat square face (a flatter), wooden handle.
12. Work table: a sturdy wooden workbench with an iron-plated top (seen from the side), a few scattered metal
    scraps.
```

---

## Огранка: инструменты, диски, бродячий ювелир

Камень по-прежнему рисует код (трассировка лучей, рельеф граней от зерна диска — тоже кодом). Картинки нужны для
рычага подачи, оправы лупы, значков дисков и книги огранок, фигуры бродячего ювелира — и **текстуры дисков
высокого разрешения** для лупы (под ×15 видно зерно). Пока картинок нет — рисуются простые формы.

### Лист JT — инструменты ювелира (`--set jewel_tools`)

```
python tools/import_sheet.py assets/art_src/sheet_jewel_tools.png --set jewel_tools --preview p.png
```

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets (the gem faceting machine parts): true pixel
art, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from the top-left,
2-3 tone shading, brass, steel, dark wood. No text, no letters, no numbers. 8 objects in 2 rows (3, 5), in EXACTLY
this order (left to right, top row first). Wide empty magenta space between objects: nothing may touch.

Row 1 (large objects):
1. Feed lever plate: a TALL narrow vertical brass plate (about 3.5 times taller than wide) bolted with 4 rivets,
   with a long vertical dark slot in the middle and 5 small horizontal notches along the slot, evenly spaced.
   NO lever handle and NO knob in the slot (the game draws the moving knob). Straight front view.
2. Magnifier: a big jeweler's hand magnifier seen face-on. A round thick ornate brass ring in the UPPER-RIGHT part
   of a square area, and a turned dark-wood handle with a brass ferrule going straight DOWN-LEFT at exactly 45
   degrees to the lower-left corner. The ring's inner opening is about 62% of the whole width, its center is at
   about 62% from the left and 38% from the top. The INSIDE of the ring is FLAT SOLID MAGENTA (#FF00FF) - empty,
   the game shows the magnified view there.
3. Wandering jeweler: a full-body standing character, front 3/4 view, an old travelling gem merchant with a long
   coat of dark velvet, a wide-brimmed hat, a magnifying loupe on one eye, a small wooden case of gems under the
   arm and a stack of old books on a strap; gold rings on the fingers. Calm, mysterious, friendly.

Row 2 (small square icons, each fills a square of equal size):
4. Coarse grinding disc icon: a round lapidary lap disc seen from above, dark rusty-brown surface with big rough
   visible grit grains and a dark steel rim, a center hole.
5. Medium grinding disc icon: the same disc, grey surface with medium fine grit.
6. Fine grinding disc icon: the same disc, light silver smooth satin surface with very fine grit.
7. Diamond grinding disc icon: the same disc, pale blue-steel surface with tiny sparkling diamond specks.
8. Book of cuts icon: an old thick leather-bound book, the cover embossed with a golden diagram of a faceted gem
   (seen from above, star of facet lines), brass corners, a ribbon bookmark.
```

### Лист JD — поверхности шлифовальных дисков (4 картинки, высокое разрешение)

Эти — **не пиксель-арт**: их видно в лупе с увеличением до ×15. Каждая — отдельная картинка, затем:

```
python tools/import_texture.py assets/art_src/lap_coarse.png --name lap_tex_coarse
python tools/import_texture.py assets/art_src/lap_medium.png --name lap_tex_medium
python tools/import_texture.py assets/art_src/lap_fine.png --name lap_tex_fine
python tools/import_texture.py assets/art_src/lap_diamond.png --name lap_tex_diamond
```

Общая часть промпта (одинаковая для всех четырёх, меняется только последняя строка):

```
Make ONE image, 2048x512, a highly detailed photorealistic macro texture (NOT pixel art), seamless and tileable
HORIZONTALLY (the left and right edges must continue each other perfectly). It shows the EDGE of a spinning
lapidary grinding disc seen exactly from the side at eye level, filling the whole image: the top 20% of the image
is the flat working top surface of the disc seen at a very low grazing angle (a thin bright band where the grit
catches the light from a warm lamp above), the lower 80% is the vertical outer rim of the disc. Even, soft studio
light from above, no shadows of objects, no stone, no machine parts, no background, no text, no vignette, no
perspective convergence — perfectly straight horizontal lines across the whole width. Fine motion streaks along
the horizontal direction are allowed (the disc spins), but keep the grit grains crisp.
```

Последняя строка для каждого диска:

```
1 (lap_coarse): COARSE 260-grit disc: rough dark rusty-brown cast iron, large irregular grit grains and pits,
  visible deep circular scratches along the rim, a little grey slurry of water and stone dust on the top band.
2 (lap_medium): MEDIUM 600-grit disc: grey steel with an even medium grit, fine circular scratches, a wet sheen
  on the top band.
3 (lap_fine): FINE 1200-grit disc: light silver satin finish, very fine almost invisible grit, smooth soft
  reflections, a clean wet top band.
4 (lap_diamond): DIAMOND disc: pale blue-steel plate with an even layer of tiny sparkling diamond grains that
  glint like stars, very fine regular texture, crisp bright highlights on the top band.
```

### Лист JM — лупа в высоком разрешении (`--set jewel_magnifier_hd`)

Лупа на станке занимает до трети экрана, а на листе JT она маленькая. Отдельная картинка высокого разрешения
заменит её сама (игра измеряет, где стекло, и поворачивает ручку от края экрана зеркально — рисуйте как ниже).

```
python tools/import_sheet.py assets/art_src/jewel_magnifier_hd.png --set jewel_magnifier_hd --preview p.png
```

```
Make ONE image, 2048x2048, plain flat solid magenta background (#FF00FF) everywhere around the object.
A single large jeweler's hand magnifier, seen exactly face-on (front view, no perspective), as a HIGH-RESOLUTION
finely detailed game asset: crisp clean edges, rich but smooth shading, hand-painted look in the same warm brass
and dark wood colors as a pixel-art fantasy game, but NOT chunky pixel art (no visible pixel grid).
The round ornate brass ring sits in the UPPER-RIGHT part of the image; a turned dark-wood handle with brass
ferrules goes straight DOWN-LEFT at exactly 45 degrees and ends near the lower-left corner. The ring's opening
is a perfect circle about 52% of the image width, its center at about 64% from the left and 36% from the top.
The ring is thick (about 7% of the image width), with engraved leaves, small rivets and a polished highlight from
the top-left. The INSIDE of the ring is FLAT SOLID MAGENTA (#FF00FF) — empty, no glass, no reflections, the game
draws the magnified view there. Nothing else in the image, no shadow, no text.
```

---

## Интерфейс: украшения (без пикселей)

Интерфейс сейчас — тёмные плашки с янтарной каймой. Нужны **небольшие** украшения, передающие фэнтези, но не
перегружающие экран: уголки рамок, разделитель под заголовками, завиток у заголовка окна, ползунок прокрутки и
кнопка «закрыть». Всё — **высокое разрешение, не пиксель-арт** (как HD-монокль). Игра сама ставит их на все
панели и окна; пока картинок нет — остаются ромбики и линии.

### Лист UI — украшения интерфейса (`--set ui_kit`)

```
python tools/import_sheet.py assets/art_src/sheet_ui_kit.png --set ui_kit --preview p.png
```

```
Make ONE image, 2048x2048, plain flat solid magenta background (#FF00FF) everywhere around the objects.
A small set of ELEGANT fantasy UI ornaments for a dark tavern game interface, as HIGH-RESOLUTION finely detailed
game assets: crisp clean edges, smooth shading, hand-painted look (NOT pixel art, no visible pixel grid).
Material: aged warm brass / old gold filigree with tiny amber gems, subtle dark-bronze shadows. Restrained and
thin — they decorate the corners and edges of dark wooden panels, they must not be bulky or busy.
No text, no letters. 6 objects in 3 rows (2, 2, 2), in EXACTLY this order (left to right, top row first),
with wide empty magenta space between them (nothing may touch).

Row 1:
1. Corner ornament (large): an L-shaped filigree corner piece for the TOP-LEFT corner of a panel — two thin
   brass strips meeting at a right angle with a small curling leaf flourish and one tiny round amber gem at the
   corner. The two arms point RIGHT and DOWN. Fits in a square, mostly empty inside the L.
2. Corner ornament (small): a simpler, thinner version of the same top-left corner (no leaves, just a tiny
   curl and a dot), for small buttons and cards.

Row 2:
3. Horizontal divider: a very long thin line ornament (about 12 times wider than tall) — a fine brass rule that
   fades out to both ends, with a small symmetric filigree knot and a tiny oval amber gem in the center.
4. Title flourish: a small horizontal scroll/curl ornament (about 4 times wider than tall) that follows a title
   on its right side, curling out to the right.

Row 3:
5. Scrollbar thumb: a VERTICAL slim capsule (about 5 times taller than wide) of polished brass with a thin
   engraved groove along its length and tiny rounded caps at both ends.
6. Close button: a round brass coin-like button with a thin raised rim and a small engraved X cross in the
   middle (the X is an ornament, not a letter).
```

## Огранка без пикселей: станок и фон в высоком разрешении

Камень, лупа, диски, линии уже без пикселей; детали станка (лист J) и фон верстака (лист 36) — ещё пиксельные и
при крупном масштабе мылятся. Перегенерация в высоком разрешении:

### Лист J-HD — детали гранильного станка (`--set facet_machine_hd`)

```
python tools/import_sheet.py assets/art_src/sheet_facet_machine_hd.png assets/sprites --set facet_machine_hd --preview p.png
```

```
Make ONE image, 2048x2048, plain flat solid magenta background (#FF00FF) everywhere around the objects.
Parts of an old-world gem FACETING MACHINE (a jeweler's lapidary), polished brass, blued steel and dark wood,
as HIGH-RESOLUTION finely detailed game assets: crisp clean edges, smooth realistic shading, warm lamp light from
the top-left, hand-painted look (NOT pixel art). STRAIGHT SIDE VIEW (orthographic, no perspective), no text, no
letters, no numbers. 7 parts in 2 rows (4, 3), in EXACTLY this order (left to right, top row first). Wide empty
magenta space between parts: nothing may touch.

Row 1:
1. Lap disk seen exactly edge-on: a very wide flat horizontal grinding disk (about 7 times wider than tall),
   dark grey cast iron rim with a fine grit top surface, a thin bright edge on top.
2. Lap stand: a squat cast-iron pedestal with a wooden base plate and a little brass water drip can, wider at
   the bottom, flat top (the disk sits on it).
3. Mast: a TALL thin vertical steel column (about 7 times taller than wide) with a brass height-adjust screw and
   a few ring marks, flat bottom.
4. Quadrant head: a round brass protractor dial with an engraved 0-90 quarter-circle scale (only tick marks, NO
   numbers), a pivot knob in the center.

Row 2:
5. Index gear: a round brass gear wheel seen face-on with many fine teeth around the rim and a hole in the center.
6. Loupe ring: a round thick ornate brass porthole frame seen face-on with rivets; the INSIDE of the ring is FLAT
   SOLID MAGENTA (#FF00FF) - empty, the game shows the gem through it.
7. Diagram plate: a round dark slate disc with a thin brass bezel and faint engraved concentric guide rings and
   radial lines (no numbers).
```

### Фон верстака ювелира (одна картинка, сразу в игру)

Сохраните как `assets/illustrations/hd/ws_bench_jewel.png` (заменит пиксельный фон огранки).

```
Make ONE image, 2400x1600, a painterly high-resolution fantasy illustration (NOT pixel art): a close-up of an old
jeweler's workbench in a dark cozy tavern workshop at night. Dark wooden bench with green velvet cloth,
tweezers, small open boxes of rough gems on a shelf on the back wall, a brass oil lamp giving a warm pool of
light, a window with night sky on the upper left. No people, no text. The CENTER and LOWER-LEFT of the picture
must be calm, dark and empty (the game draws a faceting machine there), details only near the edges and the back
wall. Soft depth of field on the background.
```

---

## Кузня v2 и шахта (без пикселей, высокое разрешение)

Кузня теперь: тигель → слиток → примитивы → изделие с закалкой. Сейчас этапы рисуются формами и старыми
пиксельными спрайтами (лист K). Для единого вида с ювелиркой — всё в высоком разрешении, не пиксель-арт, импорт
HD-путём (`--set ... ` как у листа J-HD). Шахта — новая комната (8): нужна иллюстрация и спрайты рабочих.

### Лист K-HD — оборудование кузни (`--set forge_props_hd`)

```
python tools/import_sheet.py assets/art_src/sheet_forge_hd.png assets/sprites --set forge_props_hd --preview p.png
```

```
Make ONE image, 2048x2048, plain flat solid magenta background (#FF00FF) everywhere around the objects.
Blacksmith's workshop equipment of a dark fantasy tavern as HIGH-RESOLUTION finely detailed game assets: crisp
clean edges, smooth realistic shading, warm forge light from the left, hand-painted look (NOT pixel art), STRAIGHT
SIDE VIEW (orthographic), no text. 12 objects in 3 rows (4, 4, 4), in EXACTLY this order, wide magenta gaps:

Row 1:
1. Anvil: heavy black iron anvil, horn on the LEFT, flat polished face, on a wooden stump with iron bands
   (about twice wider than tall).
2. Forge hearth: stone and brick forge with glowing coals, an open fire mouth in the lower middle, sooty hood.
3. Crucible: a thick clay-and-graphite crucible pot, OPEN TOP (the rim is an empty dark oval), on its own.
4. Quench barrel: wooden barrel with dark water and a little steam, iron hoops.
Row 2:
5. Bellows: big leather bellows with wooden boards, brass nozzle pointing RIGHT.
6. Tongs: long blacksmith's tongs, horizontal, jaws on the RIGHT.
7. Hand hammer, head on top, handle down.
8. Sledgehammer, heavy square head on top, long handle down.
Row 3:
9. Flatter: a set hammer with a wide flat square face.
10. Ingot mold: a cast-iron open mold with an empty ingot-shaped cavity, seen slightly from above.
11. Pyrometer: a brass dial instrument with a needle and a long probe (no numbers, only tick marks).
12. Magnet on a handle: a horseshoe magnet on a short wooden handle.
```

Набор `forge_props_hd` уже в `tools/import_sheet.py`: те же имена `frg_*` (заменят пиксельные), холст ×4.

### Иллюстрация шахты (одна картинка, сразу в игру)

Сохраните как `assets/illustrations/hd/room_mine.png`.

```
Make ONE image, 2400x1500, a painterly high-resolution fantasy illustration (NOT pixel art): a cross-section of
a small mine under a tavern hill — four horizontal tunnels (levels) one under another, timber supports, lanterns,
rails with an empty mine cart, a wooden lift shaft on the right side connecting all levels, rock layers getting
darker and more crystalline deeper down (the deepest level has faint glowing blue meteoric veins and gem
crystals). No people, no text. The LEFT two thirds of each tunnel must be calm and fairly empty (the game draws
miners there); keep the right third for the lift and details. Warm lantern light, cool deep shadows.
```

## Кузня: значки

Два листа. KI — значки внутри кузни (слитки по сплавам, примитивы, приборы, жидкости, формы, книга) в высоком
разрешении, как оборудование K-HD. KM — недостающие значки руд и металлов для полосы ресурсов, в пиксель-арте,
как прежние `mat_*`. Пока значков нет, игра рисует простые формы, так что их можно добавлять по одному листу.

### Лист KI — значки кузни (`--set icons_forge_hd`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_forge_hd.png assets/sprites --set icons_forge_hd --preview p.png
```

Файлы — `assets/sprites/fic_*.png` (холст 256×256). Примитивы рисуются серой сталью: игра сама окрашивает их
в цвет сплава.

```
Make ONE image, 2048x2048, plain flat solid magenta background (#FF00FF) everywhere around the objects.
Fantasy blacksmith inventory icons as HIGH-RESOLUTION finely detailed game assets: crisp clean edges, smooth
realistic shading, warm light from the top-left, hand-painted look (NOT pixel art), no text, no letters, no
frames, no background plates, no glow halos, no separate sparkles or smoke puffs (every icon is ONE connected
silhouette). Each object fills most of its square cell and reads well when small (40-60 px).
32 icons in 4 rows of 8, in EXACTLY this order (left to right, top row first), wide magenta gaps, nothing touches.

Row 1 — metal ingots, all the SAME trapezoid ingot shape, three-quarter view, only the metal differs:
1. Bloomery iron: dark grey rough iron with pitted surface.
2. Copper: warm reddish-orange copper, slightly polished.
3. Bronze: golden-brown bronze with a faint green patina on one edge.
4. Sterling silver: bright cool silver, polished.
5. 18-carat gold: rich yellow gold, polished.
6. Steel: clean blue-grey steel with a fine brushed finish.
7. Spring steel: dark blue-tinted steel with a faint temper-blue sheen.
8. High-carbon steel: very dark, almost black steel with a sharp bright edge.
Row 2:
9. Star steel: deep blue-black metal with tiny glittering silver specks like a night sky.
10. Ember steel: dark steel with glowing orange cracks inside (glow stays inside the silhouette).
11. Rod: a single round forged bar, horizontal, plain grey steel.
12. Strip: a flat forged strip, horizontal, plain grey steel.
13. Sheet: a thin square metal plate seen at an angle, plain grey steel.
14. Wire: a small neat coil of wire, plain grey steel.
15. Recipe book: a thick leather smithing book with an iron hammer emblem on the cover.
16. Wire drawing plate: a steel plate with a row of holes of decreasing size, a bit of wire through one hole.
Row 3 — tools and instruments:
17. Bellows: leather bellows with wooden boards and a brass nozzle.
18. Pyrometer: a brass dial gauge with a needle and a long thin probe (tick marks only).
19. Magnet: a red horseshoe magnet on a short wooden handle.
20. Hourglass: a wooden-framed hourglass with pale sand.
21. Hardness tester: a small steel punch with a diamond-shaped tip on a little brass stand.
22. Sledgehammer: heavy square head, long handle, diagonal.
23. Flatter: a set hammer with a wide flat square face, diagonal.
24. Steel anvil: a clean bright steel anvil, horn on the left.
Row 4 — anvil, quench liquids, molds:
25. Master's anvil: an ornate dark anvil with engraved runes and gold inlay, horn on the left.
26. Quench oil: a squat clay jug of dark amber oil with a cork.
27. Brine: a glass jar of cloudy salt water with salt crystals at the bottom.
28. Salamander blood: a small glass flask of glowing red liquid, a salamander shape etched on the glass.
29. Glacier meltwater: a frosted glass flask of pale blue icy water with a tiny ice chunk inside.
30. Rod mold: a cast-iron open mold with a long narrow round groove, seen slightly from above.
31. Strip mold: a cast-iron open mold with a long flat rectangular groove, seen slightly from above.
32. Sheet mold: a cast-iron open mold with a wide square shallow cavity, seen slightly from above.
```

### Лист KM — руды и металлы для полосы ресурсов (`--set icons_forge_mats`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_forge_mats.png --set icons_forge_mats --preview p.png
```

Файлы — `assets/icons/mat_<материал>.png`, 32×32, тот же стиль, что у листа A2.

```
Make ONE icon sheet image, 1536x512, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is ONE object filling most of its square, readable when tiny.
No text, no letters, no frames, no background plates, no circles behind the objects.
6 icons in 1 row, in EXACTLY this order, wide empty magenta space between icons: nothing may touch.

1. Coal: a small heap of black glossy coal lumps.
2. Copper ore: a rough grey rock with bright orange-copper veins and a green patina spot.
3. Tin ore: a rough dark rock with pale silvery-white tin crystals.
4. Silver ore: a grey rock with bright white-silver metallic veins.
5. Gold nugget: a lumpy rich-yellow gold nugget with a small highlight.
6. Meteoric iron: a dark pitted black-blue meteorite chunk with a faint metallic sheen.
```

---

## Недостающая графика — сводка (ревизия 2026-11-12)

Ревизия по данным игры: у всех врагов, героев, баз вещей, даров, артефактов, самоцветов и объектов комнат картинки
есть. Не хватает того, что ниже. Сначала — листы, промпты к которым уже были написаны раньше:

| Что | Лист | Промпт | Импорт |
|---|---|---|---|
| События Кузней: река расплава, надсмотрщик, меха, шлаковщик | 24 | `prompts_forge.md`, «Лист 24» | `python tools/import_illustrations.py assets/art_src/ill_24.png --sheet 24 --preview p.png` |
| События Кузней: механоид, алтарь Жара, зеркало, подмастерье | 27 | `prompts_forge.md`, «Лист 27» | `python tools/import_illustrations.py assets/art_src/ill_27.png --sheet 27 --preview p.png` |
| Рынок: площадь, лоток камней, товары, ночь | 37 | этот файл, «Лист 37» | `python tools/import_illustrations.py assets/art_src/ill_37.png --sheet 37 --preview p.png` |

Лист T2 (значок «Рынок») больше не нужен — значок вошёл в лист T3 ниже.

Новые листы — дальше по порядку. Варианты тотемов шамана берут спрайт своего тотема, иллюзия и отражение
рисуются по описанию, ледяная стена — эффект: им отдельные картинки не нужны.

### Лист I3 — уникальные вещи, часть 3 (`--set icons_items4`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_items4.png --set icons_items4 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
14 icons in 2 rows (7, 7), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. A small duelist's pennant on a short pole with two crossed rapiers on the cloth.
2. A red-stained leather gauntlet with a blood-red gem on the knuckles.
3. A leather quiver with three arrows, one arrow split into two identical heads.
4. A ring made of a coiled bowstring with a pale blue wind swirl around it.
5. An amulet: a charcoal-black heart with glowing orange cracks, on a short chain.
6. A wooden staff topped with a crackling orange ember spark.
7. A loop of wooden prayer beads with a small silver holy symbol.
Row 2:
8. A gold signet ring with a sun-cross holy symbol on the face.
9. A dagger whose blade is made of black shadow smoke with a violet edge.
10. A dark navy hooded cloak sprinkled with tiny pale star dots.
11. A large wolf fang on a leather cord with three claw-mark notches.
12. A wreath of green leaves with small white flowers.
13. A long sentinel spear with a red tassel under the spearhead.
14. A heavy square tower shield, dented and muddy, with a spike at the bottom.
```

### Лист I4 — уникальные вещи, часть 4 (`--set icons_items5`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_items5.png --set icons_items5 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
14 icons in 2 rows (7, 7), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. A small carved wooden totem pole with three stacked painted faces.
2. A ring with a tiny dreamcatcher web and a single feather hanging from it.
3. A minstrel's lute with a carved wooden body.
4. A silver tuning fork with two short vibration arcs attached to the prongs.
5. A curved horn powder flask with a brass cap and a strap.
6. A ring whose stone is a small black bomb with a short lit fuse.
7. A ram's horn bound with iron bands, used as a war club.
Row 2:
8. A heavy shaggy brown bison-hide armor with short horns on the shoulders.
9. A short flintlock musket with a brass-bound stock.
10. A leather satchel with steel bear-trap jaws sticking out.
11. An amulet: a heart-shaped pale blue ice crystal in a silver frame.
12. A staff topped with a big swirling snowflake crystal.
13. A horned beast skull on a cord with faint violet light in the eye sockets.
14. A large black scythe with a ghostly pale green blade edge.
```

### Лист I5 — уникальные вещи, часть 5 (`--set icons_items6`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_items6.png --set icons_items6 --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
14 icons in 2 rows (7, 7), in EXACTLY this order (left to right, top row first).
Wide empty magenta space between icons: nothing may touch.

Row 1:
1. An ornate golden hourglass with glowing blue sand.
2. A ring with a tiny pendulum weight hanging below it on a thin rod.
3. A dark heavy stone with a violet spiral carved into it.
4. A ring with a thin outer hoop and two tiny spheres orbiting on it.
5. A gnarled tree root grown through a chunk of grey rock.
6. A black obsidian staff topped with a molten orange lava orb.
7. A small glass alembic still with bubbling green liquid.
Row 2:
8. A leather belt with four small colored potion flasks (red, green, blue, yellow).
9. A jagged notched battle axe with a red-stained blade and a broken chain on the haft.
10. A bracelet made of linked black leeches with one red drop.
11. A red and gold marshal's baton with an eagle-shaped cap.
12. A small red regimental flag on a pole with a gold emblem.
13. A spindle wound with a glowing golden thread, one loose end.
14. A signet ring with a glowing pale blue endless-knot symbol.
```

### Лист T3 — вкладки «Рынок» и «Шахта», трофеи глав (`--set icons_tabs3`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_tabs3.png --set icons_tabs3 --preview p.png
```

Файлы: `assets/icons/tab_market.png`, `tab_mine.png` (полоса вкладок), `mat_amber.png`, `mat_ember.png`
(трофеи глав в цене построек — сейчас там цветные ромбики).

```
Make ONE icon sheet image, 1536x512, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous tab icons: true pixel art on a 32x32 grid per icon,
crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading, warm amber and dark wood palette. Each icon is ONE object filling most of its square,
readable when tiny. No text, no letters, no frames, no background plates.
4 icons in 1 row, in EXACTLY this order (left to right). Wide empty magenta space between icons.
1. Market: a small market stall awning with a coin purse and a red gem in front.
2. Mine: a pickaxe crossed with a hanging mining lantern over a lump of ore.
3. Swamp amber: a glossy honey-orange amber chunk with a tiny insect trapped inside.
4. Forge heart: a fist-sized glowing ember-red crystal shaped like a heart, with dark iron bands around it.
```

### Лист MH — горняки и вагонетка шахты (`--set mine_hd`)

```
python tools/import_sheet.py assets/art_src/sheet_mine_hd.png assets/sprites --set mine_hd --preview p.png
python tools/align_miners.py
```

Второй шаг обязателен: он перерезает три кадра горняка на общий холст (один масштаб, одна линия земли).

Высокое разрешение, как иллюстрация шахты (`room_mine`). Три кадра одного горняка — игра чередует их (замах,
середина, удар) и зеркалит каждого второго; вагонетка стоит у подъёмника на каждом уровне. Пока листа нет —
горняки рисуются палочками.

```
Make ONE image, 2048x1024, plain flat solid magenta background (#FF00FF) everywhere around the figures.
Painterly HIGH-RESOLUTION game sprites matching a dark fantasy mine illustration: crisp clean edges, smooth
realistic shading, warm lantern light from the left, hand-painted look (NOT pixel art), STRAIGHT SIDE VIEW,
no text. 4 objects in 1 row, in EXACTLY this order, wide magenta gaps, nothing touches, all figures standing
on the same invisible ground line.

1. A stocky miner facing RIGHT, full body, leather cap with a small candle lantern, rolled sleeves, apron,
   heavy boots; holding a pickaxe with both hands RAISED HIGH behind the head (wind-up).
2. The SAME miner, the SAME size and the same legs, the pickaxe swung FORWARD level with the shoulders.
3. The SAME miner, the SAME size, the pickaxe STRIKING DOWN, its head touching the ground in front of him,
   a few rock chips attached to the silhouette (not floating far away).
4. A wooden mine cart on four iron wheels, side view, filled with lumps of grey ore and a few glinting
   crystals, iron corner plates.
```

### Лист NS — бродячий кузнец (`--set npc_smith`)

```
python tools/import_sheet.py assets/art_src/sheet_npc_smith.png --set npc_smith --preview p.png
```

Портрет в окне бродячего кузнеца на рынке — в пару к бродячему ювелиру с листа JT.

```
Make ONE sprite sheet image, 1024x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprite in the exact same style as the wandering jeweler sprite: true pixel art, crisp square
pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from the top-left, 2-3 tone
shading. No text, no letters. ONE object, centered:
A wandering blacksmith, full-body standing character, front 3/4 view: a broad-shouldered travelling smith with
a soot-stained leather apron over a rough shirt, thick gloves, a short beard, a heavy hammer hanging from the
belt, a big leather pack on the back with tongs, a small anvil and rolled books strapped to it, a pouch of
ingots. Gruff and friendly.
```

---

## Глава 3 «Склеп нежити» — недостающая графика

Основной бестиарий Склепа уже нарисован листом 2 в `prompts_more.md` (`--set crypt_pass`): скелеты, упырь,
некромант, банши, костяной голем, призрак, рыцарь смерти и лич. События `sunken_chapel`, `sunken_library`,
`room_cemetery`, `old_armory` и другие тоже уже есть в `assets/illustrations`. Ниже — только то, чего не хватает
главе 3: два новых босса, иконки трофея/материала/уникальных вещей и три сцены событий.

### Лист CR1 — новые боссы Склепа (`--set crypt_bosses`)

```
python tools/import_sheet.py assets/art_src/sheet_crypt_bosses.png --set crypt_bosses --preview p.png
```

Аббат и Хранитель колодца — боссы актов I и II. Лич уже есть на листе `crypt_pass`; здесь его не дублируем.

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the crypt enemies sheet: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy undead crypt bosses for a tactics RPG:
bone, tarnished silver, amber, cold blue soul-fire and grave dust. Two bosses side by side in ONE row, in EXACTLY
this order (left to right). Wide empty magenta space between them: nothing may touch. Bosses (marked B) are about
1.7x a normal enemy.

1. (B) Crypt abbot: a tall gaunt undead abbot in rotted violet-and-gold vestments, a tall mitre set with a dull
   amber stone, an amber seal burning in the middle of his chest, a bone rosary hanging from his belt, one
   skeletal hand raised with green necrotic flame, the other holding a crooked staff crowned with an amber skull.
   Cold, patient, almost gentle expression.
2. (B) Well warden: a drowned spectral guardian in tattered dark-blue robes over rusted mail, a hood hiding a
   face made of pale blue light, a heavy iron lantern with a soul-flame in one hand, a long rusted chain and hook
   dragging from the other, water dripping from the hem, faint spectral mist around the feet.
```

### Лист CR2 — иконки Склепа (`--set icons_crypt`)

```
python tools/import_sheet.py assets/art_src/sheet_icons_crypt.png --set icons_crypt --preview p.png
```

Иконки ложатся в карточки вещей, в цену построек и на шкалу материалов. Пока листа нет, уникальные вещи берут
иконку своей базы, а трофей и костяная пыль рисуются цветными ромбиками.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects. Dark fantasy
crypt palette: bone ivory, tarnished silver, black iron, amber, cold blue soul-fire.
8 icons in 2 rows of 4, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
icons: nothing may touch.

Row 1:
1. Soul shard: a jagged pale-blue crystal shard of a soul, wrapped in a thin silver wire, a faint ghost-light
   inside, small sparks around it.
2. Bone dust: a small open leather pouch spilling fine ivory bone dust, a few tiny bone chips and a finger bone
   resting on the pile.
3. Soulflame blade: a straight knight's sword with a bone grip, its blade edged in pale blue ghost-fire, a thin
   trail of soul-smoke rising from the tip.
4. Grave ward: a heavy dark-iron breastplate with a gravestone-shaped rune in the centre, a pale blue ward-light
   glowing in the cracks, moss and bone dust in the seams.

Row 2:
5. Bone bow: a recurve bow made of lashed ribs and a long leg bone, a pale sinew string, one bone-tipped arrow
   nocked, a faint cold gleam on the arrowhead.
6. Lich crown: a tall jagged crown of black iron and bone, a green-violet gem in the centre, cold blue flames
   rising from the points.
7. Crypt grail: a tarnished silver chalice with a bone stem and a skull-shaped base, filled with pale blue
   glowing liquid, a thin wisp of soul-light above the rim.
8. Bone idol: a small idol built from stacked bones and a horned skull, two dull coins in the eye sockets, a
   dark amber bead on its chest, faint grave mist around the base.
```

### Лист 38 — недостающие сцены Склепа (`--names ...`)

```
python tools/import_illustrations.py assets/art_src/ill_38.png --names order_toll,final_vigil,lich_phylactery --preview p.png
```

Три недостающие иллюстрации событий. Четвёртая ячейка остаётся пустой (чёрной): сетка всё равно 2×2, скрипт
возьмёт только три имени.

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR equal cells, each with a thin black border, separated
by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid per illustration, crisp
square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed. Dark fantasy crypt
adventure: bone, black stone, tarnished silver, amber, cold blue soul-light, fog. Strong silhouettes, one clear
light source, moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, grave slab, chapel step)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (Order patrol, ghostly hand, distant lich silhouette)
ARE allowed and should stay in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.

1. (top-left) "Order toll": a crypt corridor with bone niches, three tall patrolmen of the Order of Light in
   white tabards over silver mail, a sun-and-bone emblem on the chest, one holding a lantern and a small iron
   toll box, another resting a hand on a sword hilt; their faces are calm and tired, not hostile. A clear stone
   floor in the lower left.
2. (top-right) "Final vigil": a small camp before the lich's throne room, a ring of candles and a low brazier on
   the right, an empty bedroll and a folded banner on a grave slab, fog pressing against a black doorway in the
   distance, a single pale star visible through a crack in the vault. No people. Clear floor in the lower left.
3. (bottom-left) "Lich phylactery": a narrow silver-sealed niche in a throne-room wall, the silver plates warped
   and rune-etched, a small green-violet gem beating behind them like a heart, a skeletal hand hanging limply
   from a broken chain beside the niche, cold blue light spilling on the floor. No player characters. Clear
   floor in the lower left.
4. (bottom-right) EMPTY: fill this cell with flat solid black, no objects, no border inside the cell.
```

### Если хочется отдельные фоны актов

Фоны актов Склепа уже сгенерированы и подключены: `crypt_act_0` (ограда кладбища), `crypt_act_1`
(затонувшая часовня) и `crypt_act_2` (тронный зал лича) прописаны в `acts[].art` в
`data/expedition_crypt.json`. Промпт ниже оставлен на случай перегенерации.

```
python tools/import_illustrations.py assets/art_src/ill_crypt_acts.png --names crypt_act_0,crypt_act_1,crypt_act_2 --preview p.png
```

```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR equal cells, each with a thin black border, separated
by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid per illustration, crisp
square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed. Dark fantasy crypt
adventure, painterly pixel art like classic adventure games: black stone, bone, tarnished silver, amber, cold
blue soul-light, fog. Strong silhouettes, one clear light source, moody but readable. No text, no UI, no letters.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone flags, grave slab, throne-room
step) seen at eye level; nothing important there. Named creatures and NPCs below may stand in the middle or on
the right. Order: top-left, top-right, bottom-left, bottom-right.

1. (top-left) "Act I, the graveyard gate": a rusted iron gate half-sunk in bone-littered earth under a vaulted
   stone ceiling, rows of crooked graves fading into fog, a single amber lamp burning on a post, distant
   chapel silhouette. Clear stone path in the lower left.
2. (top-right) "Act II, the sunken chapel": a half-flooded chapel interior, pews under black water, a huge cracked
   bell hanging above a broken altar, silver reliquary glinting on the right, cold blue light through a hole in
   the roof. Clear stone step in the lower left.
3. (bottom-left) "Act III, the lich's throne": a vast black throne room with columns of bone and iron, a pale
   green-violet throne on a raised dais in the middle-right, soul-fire braziers, a long red-violet carpet
   leading to it, fog pooling on the floor. Clear flagstones in the lower left.
4. (bottom-right) EMPTY: fill this cell with flat solid black, no objects, no border inside the cell.
```
