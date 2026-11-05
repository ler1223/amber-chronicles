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
| Иконки: новые уникальные вещи (16) — готово | Лист I2 | `python tools/import_sheet.py assets/art_src/sheet_icons_items3.png --set icons_items3 --preview p.png` | `assets/icons` |

Пока картинки нет, игра рисует заглушку: враг берёт спрайт родственника (`sprite_fallback` в
`data/expedition.json`), иллюстрация — процедурную виньетку болота, иконки просто не показываются.

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
