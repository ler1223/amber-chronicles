# Промпты главы «Огненные кузни»

Каждый блок — готовый запрос целиком (лучше в тот же чат, где делали прошлые листы). Картинку сохранить в `assets/art_src/` и нарезать командой из таблицы. Пока картинок нет, игра рисует заглушки: врагов — спрайтом родственника (`sprite_fallback`), жерло — печью, иллюстрации — виньеткой, иконки — пиксельными значками.

| Что | Запрос | Команда | Куда ляжет |
|---|---|---|---|
| Враги, боссы и жерло (15) — готово | Лист K1 | `python tools/import_sheet.py assets/art_src/sheet_forge_events.png --set forge_events --preview p.png` (и `--res 2` для высокой детализации) | `assets/sprites` |
| Иконки: узлы, металлы, шедевры (12) — готово | Лист K2 | `python tools/import_sheet.py assets/art_src/sheet_icons_forge.png --set icons_forge --preview p.png` | `assets/icons` |
| Иллюстрации (52) — готово 44, ждут листы 24 и 27 | Листы 19–31 | `python tools/import_illustrations.py assets/art_src/ill_19.png --sheet 19 --preview p.png` | `assets/illustrations` |

---

## Лист K1 — враги, боссы и жерло Кузней (`--set forge_events`)

Вольный голем — союзник-гость (вставшие на вашу сторону големы). Безымянный кузнец и Пепельный змей — тайные боссы, Пробуждённый вулкан — финальный босс при Жаре на пределе. Жерло — объект поля.

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy underground forge enemies for a tactics
RPG (soot, iron, chains, molten metal, orange fire light). 15 figures in 3 rows of 5, in EXACTLY this order (left
to right, top row first). Wide empty magenta space between figures: nothing may touch. Elites (marked E) are about
1.3x a normal figure, bosses (marked B) about 1.7x.

Row 1:
1. Slag slave: a gaunt soot-covered human worker in rags, broken shackles on the wrists, a pickaxe, a burned brand on
   the forehead.
2. Ember hound: a lean dog-like beast made of black coal with glowing orange cracks, fiery eyes, smoke from the
   mouth, low and fast.
3. Bellows keeper: a stocky worker with a big leather bellows strapped to his back and a nozzle in his hands, goggles,
   leather apron.
4. Chain smith: a broad armored brute in a blacksmith apron over chain mail, a heavy chain with a hook swinging from
   one hand, an iron mask.
5. Ash wraith: a floating ghost made of grey ash and embers, empty glowing eyes, its lower half dissolving into
   drifting ash, floating above the ground line.

Row 2:
6. Cinder caster: a foundry woman in a scorched leather coat holding a small crucible of glowing metal, flicking
   molten drops, goggles on the forehead.
7. Flame zealot: a cultist in charred red robes with a burning brand on the chest, hands wrapped in fire, wild eyes.
8. (E) Crucible golem: a heavy golem with a big open crucible of molten metal in its chest, iron plates, glowing
   seams, metal dripping.
9. Free golem: a stone-and-iron golem with calm blue-white glowing eyes and a rune in its chest, chipped and dusty,
   friendly stance.
10. Magma vent (object, not a creature): a cracked rock mound on the ground with a glowing magma crack on top,
   smoke rising, about half a figure's height, wider than tall.

Row 3:
11. (B) Overseer Groh: a huge brutal overseer in spiked black armor with a long fire whip coiled in one hand and a
   hammer in the other, scarred bald head.
12. (B) Crucible titan: a colossal foundry golem made of cast iron and molten metal, a giant ladle for an arm,
   glowing furnace-mouth in its belly.
13. (B) Awakened volcano: a towering living volcano spirit, a body of black basalt rock with rivers of lava, a
   crater for a head spewing fire, arms of magma.
14. (B) Nameless smith (ghost): a tall translucent pale-blue ghost of a master smith in a leather apron with a
   spectral hammer and tongs, flowing beard of mist.
15. (B) Ash wyrm: a long serpent-dragon made of grey ash and smoldering coals, glowing ember eyes, rib bones
   visible through the ash, mouth full of embers, coiled.

```

---

## Лист K2 — иконки Кузней (`--set icons_forge`)

Иконки узлов (наковальня, пепелище) ложатся в медальон карты, металлы — на шкалу руды, шедевры — в карточку вещи.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left,
2-3 tone shading. Each icon is a single bold object seen from the front, filling most of its square, readable
when tiny. No text, no letters, no frames, no background plates, no circles behind the objects.
12 icons in 3 rows of 4, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
icons: nothing may touch.

Row 1:
1. Anvil: a heavy black anvil with a hammer resting on it, a few orange sparks.
2. Ash ruins: a pile of grey ash with a few glowing orange embers and a charred plank sticking out.
3. Ore: a chunk of brown-grey ore with rusty metal veins.
4. Obsidian: a sharp shard of glossy black-violet volcanic glass.

Row 2:
5. Star steel: a pale-blue glowing ingot of fallen-star metal with tiny sparkles.
6. Ember heart: a glowing orange heart-shaped coal with fire inside it.
7. Starforged blade: a straight sword with a pale-blue star-metal blade and a gold guard.
8. Obsidian aegis: a heavy black obsidian chest plate with violet glints.

Row 3:
9. Ember crown: a crown-shaped circlet of glowing coals and blackened gold.
10. Volcano maul: a huge two-handed hammer with a head of basalt cracked with lava.
11. Magma bow: a recurve bow of black wood with a glowing molten-metal string.
12. Forge heart ring: a thick iron ring with a small glowing ember set in it.

```

---

## Иллюстрации Кузней (`tools/import_illustrations.py`)

4 картинки на лист сеткой 2×2; героев на картинках нет — игра ставит фигурки отряда слева внизу.

### Лист 19 — forge_act_0, forge_act_1, forge_act_2, anvil (`--sheet 19`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. Act I, "Slag heaps": huge grey-black slag hills under a rust-red smoky sky inside a giant cavern, mine carts on rails, distant chained slaves carrying ore, an iron gate behind.
2. Act II, "Foundry halls": an enormous foundry hall, giant ladles of glowing molten metal hanging on chains overhead, half-cast golem bodies in molds, sparks everywhere.
3. Act III, "Heart of the furnace": a colossal furnace like a volcano mouth on the right, giant leather bellows breathing fire into it, rivers of lava converging, an obsidian throne far away.
4. A forge anvil station: a heavy black anvil in the center-right under a hanging lamp, a glowing forge hearth behind it, tongs and hammers on a rack, ingots of ore, obsidian and blue star-metal on a shelf.
```

### Лист 20 — slave_revolt, revolt_rising, revolt_end, golem_core (`--sheet 20`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. Slaves hiding under a slag heap: gaunt chained workers sharpening pickaxes on stones on the right, an old man with a burned brand on his forehead looking at the viewer, a whip-guard far away.
2. A burning foundry: freed slaves with pickaxes holding a narrow bridge against armored chain-smiths swinging chains, fire and smoke, on the right.
3. Near the great furnace: a crowd of freed slaves with torches and hammers, the branded old man in front, determined, on the right; the glow of the heart of the forge behind them.
4. A dusty dormant stone-and-iron golem standing in a wall niche on the right, an empty fist-sized hole in its chest where its rune-heart was, its fingers slightly twitching.
```

### Лист 21 — golem_awakening, cult_initiation, cult_ascension, cold_anvil (`--sheet 21`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A casting pit where dozens of golems rise, their eyes lighting up one by one with blue-white light, dust falling from them, on the right.
2. Fire cultists in charred robes dancing around a forge fire, a priestess on the right holding out a bowl of liquid fire, sparks swirling.
3. A fire choir of cultists singing around the heart of the forge, a huge armored figure of fire rising in the flames in the background, the priestess beckoning on the right.
4. In a red-hot workshop, a single anvil covered with white frost on the right, a lonely hammer lying beside it, faint carved runes on the anvil.
```

### Лист 22 — ghost_forge, ash_nest, chained_ifrit, volcano_whisper (`--sheet 22`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A ghostly forge with blue spectral fire, a tall transparent smith in a leather apron stepping out of the flames with a hammer on the right.
2. A cave buried knee-deep in grey ash, giant ribs sticking out of the ash, the ash slowly rising and falling as if something huge breathes beneath it, embers glowing.
3. A cage of blue star-steel bars on the right holding a furious fire spirit with a cruel grin, flames licking through the bars.
4. A cracked basalt floor glowing from within, fiery cracks forming the shape of a face, heat haze, the deep red glow of a volcano heart.
```

### Лист 23 — forge_herald, lava_dam, cooling_cistern, starsteel_vein (`--sheet 23`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A herald in a steel mask on the right holding a scroll with an anvil seal, two chain-smiths in the shadows behind him.
2. A stone dam holding back a lake of lava on the right, glowing cracks running across the masonry, a sluice wheel.
3. A huge iron vat of water for quenching on the right, clouds of steam, buckets and chains, a few thirsty slaves looking at it.
4. A mine tunnel wall with a glowing pale-blue vein of fallen-star metal on the right, cold light among the red heat, pickaxes leaning.
```

### Лист 24 (ещё не сделан) — molten_river, overseer_bribe, bellows_hall, slag_merchant (`--sheet 24`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A river of liquid metal crossing the cave, a chain bridge over it, and a guild ferryman on a stone raft at the right bank.
2. An overseer warming his hands over a brazier on the right, smirking, a whip on his belt, coins on a crate.
3. A hall of house-sized leather bellows pumping air into furnaces on the right, a big unguarded lever, gusts of sparks.
4. A hunchbacked guild trader selling from a mine cart on the right: ore, black obsidian chunks, rusty ingots, a lantern.
```

### Лист 25 — master_blueprints, fire_trial, trapped_miner, salamander_nest (`--sheet 25`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A burnt workshop with an iron chest standing open on the right, untouched rolled blueprints inside, soot everywhere.
2. A corridor of fire on the right with a guild altar at its far end holding a glowing reward, flames forming a tunnel.
3. A collapsed mine passage with a hand sticking out of the rubble on the right, a miner's sack and helmet lamp beside it.
4. A rock crevice with a nest of glowing ember-like eggs, a mother salamander sleeping coiled around them on the right.
```

### Лист 26 — hammer_duel, golem_parts, flame_preacher, ash_storm (`--sheet 26`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A guild master smith with a beard and leather apron on the right throwing a hammer to the ground as a challenge, two anvils ready side by side.
2. A guild market stall of golem parts on the right: stone arms, gears, and one warm glowing core on a velvet cloth, mechanics in goggles.
3. A preacher in charred robes standing on a barrel on the right shouting to a crowd of slaves, his arms raised, fire behind him.
4. A wall of grey ash pouring from a vent and sweeping across the cave, visibility of a few steps, faint shapes of pillars.
```

### Лист 27 (ещё не сделан) — broken_automaton, heat_altar, obsidian_mirror, runaway_apprentice (`--sheet 27`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A broken mechanical servant with a cracked boiler on the right trying to stand up, something glowing ticking in its chest.
2. An altar of hardened magma on the right, the air above it trembling with heat, a carved sun-like symbol, offerings of coal.
3. A tall slab of polished black obsidian on the right reflecting a burning hall that is not there, eerie orange light in the reflection.
4. A boy in a burned apron hiding behind an anvil on the right clutching a master's hammer, scared eyes.
```

### Лист 28 — quench_bath, smoke_signal, slave_cache, tribute_cart (`--sheet 28`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A quenching bath of oil and icy water on the right with blades hanging above it, steam rising, an abandoned workshop.
2. Above an old mine entrance three short columns of smoke rising into the dark cavern ceiling, a ruined headframe on the right.
3. A hidden cache under stones on the right: piles of ore and a small note pinned with a nail, candle light.
4. A line of mine carts loaded with ingots and black obsidian pulled by chained slaves under guard of chain-smiths, moving right.
```

### Лист 29 — hot_springs, master_contest, old_armory, fire_ale (`--sheet 29`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. An underground boiling sulfur spring on the right, steam and yellow crystals around it, warm light.
2. A guild showcase hall: masterworks displayed on stands, a one-eyed old judge smith inspecting a blade on the right.
3. A collapsed old armory with three intact weapon racks on the right, dust and cobwebs, a cracked banner of the previous lord.
4. A dwarf brewer with a big beard pouring glowing orange ale from a barrel into mugs on the right, cozy forge corner.
```

### Лист 30 — tunnel_collapse, guild_contract, contract_due, lava_raft (`--sheet 30`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. A cracking mine tunnel ceiling with falling rocks, an exit light ahead on the right, a mine cart of ore and slaves behind.
2. A guild master smith unrolling a parchment contract on a workbench on the right, measuring tape, ore sacks.
3. A guild workshop: the master smith holding out a finished item wrapped in leather on the right, proud.
4. A stone raft hanging on chains moving across a lake of lava toward distant workshops on the right.
```

### Лист 31 — ember_orphans, brass_oracle, guild_feast, guild_toll (`--sheet 31`)
```
Make ONE image, 1536x1024, split into a 2x2 grid of FOUR separate illustrations of equal size, each with a thin
black border, separated by wide black gutters. Pixel art scene illustrations, true pixel art on a 192x128 grid
per illustration, crisp square pixels, no anti-aliasing, limited palette of about 32 colors, dithering allowed.
Dark fantasy underground forge adventure: volcanic halls, rivers of molten metal, soot, chains, glowing furnaces,
painterly pixel art like classic adventure games (Loom, Darkest Dungeon mood), strong silhouettes, one clear
light source (usually orange fire light), moody but readable. No text, no UI, no letters anywhere.
IMPORTANT: these are EMPTY scenes. Do NOT draw any adventurers, heroes, party members, player characters or
their hands — the game places its own small hero sprites into the picture later. Keep the LOWER-LEFT third of
every illustration as a clear, flat, unobstructed patch of solid ground (stone floor, iron walkway, ash bank)
seen at eye level, where 2-4 small figures could stand side by side facing right; nothing important there.
Named creatures and non-player characters listed below (slaves, smiths, cultists, golems…) ARE allowed and
should stand in the middle or on the right side of the scene.
Order: top-left, top-right, bottom-left, bottom-right.
1. Soot-covered children collecting glowing coals into baskets with bare hands on the right, the smallest holding out a burning ember.
2. A mechanical brass head on a tripod with turning gears and glowing eyes on the right, coins in a dish.
3. A feast of the free guild: long table made of anvils, dwarves and smiths singing with mugs raised on the right, warm light.
4. Guild guards with halberds at a foundry gate on the right blocking the way, a toll table with scales.
```
