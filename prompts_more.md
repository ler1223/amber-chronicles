# Листы для остальных персонажей и окружения

Каждый блок ниже — **готовый запрос целиком**: скопировать и вставить в ChatGPT (лучше каждый лист в новом
сообщении того же чата, где делали первый лист, — так стиль совпадёт). Картинку сохранить в `assets/art_src/` и
нарезать своим набором:

```
python tools/import_sheet.py assets/art_src/<лист>.png --set <набор> --preview preview.png
```

Исходники уже лежат в `assets/art_src/sheet_<набор>.png` (sheet_heroes2.png, sheet_crypt_pass.png, …) — нарезка
уже сделана, запросы ниже нужны, чтобы перегенерировать лист или добавить новый.

| Лист | `--set` | Фигур | Куда ляжет |
|---|---|---|---|
| Герои 2 + призывы | `heroes2` | 20 | `assets/sprites` |
| Остатки гл. 1–2, Склеп, Перевалы | `crypt_pass` | 21 | `assets/sprites` |
| Степь, Гробницы | `steppe_tomb` | 17 | `assets/sprites` |
| Лес фей, Затонувший город | `fae_sunken` | 17 | `assets/sprites` |
| Небесная цитадель | `citadel` | 9 | `assets/sprites` |
| Объекты поля | `objects` | 21 | `assets/sprites` |
| Окружение 1 (болото, кузни, склеп, перевалы) | `env1` | 18 | `assets/sprites/env` |
| Окружение 2 (степь, гробницы, лес фей, город, цитадель) | `env2` | 20 | `assets/sprites/env` |

Важно для нарезки: фигуры не касаются друг друга, порядок — строго как в списке (ряды сверху вниз, слева
направо). Если генератор нарисовал другое число фигур или перепутал порядок — скрипт скажет «на листе N фигур»
или превью покажет путаницу; проще перегенерировать лист, чем чинить. Число фигур в ряду — подсказка
генератору, скрипт сам находит ряды.

Варианты призывов без своей картинки берут спрайт родственника (`SPRITE_ALIAS` в `ui/battle_view.py`): тотем грома
→ тотем грозы, оберег → тотем исцеления, колючее чучело → чучело, поднятые мертвецы → скелет-прислужник, мумия
фараона → мумия. Саркофаг — один файл и для врага, и для объекта поля.

Окружение подменяет заглушки укрытий и декора (`ui/ground.py`): `env/<материал>_<вид>.png`, материал главы — grass
(болото), ash (кузни), dirt (склеп), snow (перевалы), dry (степь), sand (гробницы), moss (лес фей), wet (затонувший
город), marble (цитадель). `block` — полное укрытие на клетке, `log` — половина укрытия, остальное — декор вокруг
поля. Каждый предмет вписывается в свой холст (дерево 32×46, камень 24×18 и т.д.), так что их рост на листе не
важен.

## Лист 1 — герои и призывы (`--set heroes2`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheet: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline
(dark brown/navy, not black), light from top-left, 2-3 tone shading. Three-quarter view, full body, every
figure faces RIGHT, standing on an invisible ground line, no ground shadow, no text, no labels, no frames.
Dark fantasy tactics RPG, readable silhouettes, like classic SNES / GBA tactics games.
20 figures in 4 rows of 5, in EXACTLY this order (left to right, top row first). Leave wide empty magenta space
between figures: nothing may touch or overlap. Human heroes are all the same height; creatures as noted.

Row 1:
1. Storm shaman: wolf-pelt mantle with the wolf head as a hood, blue war paint, bone charms, a carved staff with
   crackling blue lightning on top.
2. Bard: feathered cap, colorful red-and-yellow doublet, a lute held ready to play, a short cape, cheerful.
3. Demolitionist: soot-stained leather apron, brass goggles on the forehead, bandolier of small bombs, holding a
   round black bomb with a lit sparking fuse.
4. Battering ram brute: huge broad man in heavy iron, a horned helmet, a massive iron-banded shoulder shield
   used for ramming, leaning forward in a charge.
5. Trapper: fur hat, leather and fur coat, hand crossbow, iron bear traps hanging from the belt, a coiled net on
   the shoulder.

Row 2:
6. Young necromancer (hero, not evil): pale, dark teal hooded robe, a lantern with teal ghost-fire, a thin staff
   topped with a small bird skull.
7. Chronomancer: midnight-blue robe with golden clock patterns, silver hair, a floating golden hourglass above
   the open hand, small gears orbiting.
8. Gravity mage: violet robe dotted with stars, three small rocks floating around her, a tiny black sphere with a
   purple ring in her palm.
9. Geomancer: stocky earth mage, brown and moss-green clothes, heavy stone gauntlets, amber crystals growing from
   the shoulders.
10. Potion brewer: round spectacles, green apron covered in vials, holding a big glass flask with a bubbling
    green potion, a ladle on the belt.

Row 3:
11. Blood berserker: bare-chested, wild red hair, glowing red tattoos, two short axes, a faint red aura.
12. Tactician: officer in a dark blue coat with a short cape, a commander's baton, a spyglass on the belt, a
    small banner pole on the back.
13. Binder: mystic in white-and-gold robes, a blindfold, glowing golden threads and chains flowing between the
    hands.
14. Spirit wolf (druid's wolf form): grey-green wolf with moss and small leaves in its fur, glowing green eyes,
    on four legs, as long as a human is tall.
15. Spirit tree: a small glowing sapling with a thick root base, soft green light in its leaves, about 2/3 of a
    human's height.

Row 4:
16. Ent: a walking tree guardian, bark body, leafy crown, thick root feet, branch arms, a bit taller than a human.
17. Storm totem: a carved wooden totem pole with a storm-bird head on top, blue lightning crackling around the
    beak, about 3/4 of a human's height.
18. Healing totem: a carved wooden totem wrapped in green vines, a glowing green gem in its chest, about 2/3 of a
    human's height.
19. Skeleton servant: a small risen skeleton with a rusty short sword, faint teal glow in the eye sockets,
    friendly-looking, about 3/4 of a human's height.
20. Hunter's decoy: a straw scarecrow dummy on a pole wearing a hooded green cloak and a hat, arms out.
```

## Лист 2 — остатки глав 1–2, Склеп, Перевалы (`--set crypt_pass`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy tactics RPG, enemies.
21 figures in 3 rows of 7, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
figures: nothing may touch. Elites (marked E) are about 1.4x a normal enemy, bosses (marked B) about 1.7x.

Row 1:
1. Toxic slime: purple-green poison slime blob, small skull-shaped bubbles inside, dripping, about half human
   height.
2. Bog horror: a hunched mound of mud, roots and reeds with long dripping arms and one glowing yellow eye.
3. Obsidian guard: warrior in black glassy obsidian armor with thin glowing lava cracks, a halberd.
4. Living lava: a small blob of molten orange lava with a dark crust and two bright eyes, about half human height.
5. Skeleton warrior: yellowed bones, rusty sword and a cracked round shield, tattered loincloth.
6. Skeleton archer: bones, a broken helmet, a shortbow aimed right, a quiver on the hip.
7. Ghoul: hunched grey-green ghoul, long claws, torn rags, hungry grin.

Row 2:
8. Necromancer (enemy): old hunched sorcerer in black and bone-white robes, red eyes, a skull staff, green
   ghost-fire in the raised hand.
9. Banshee: floating pale ghost woman, long white hair, translucent cyan gown, mouth open in a scream.
10. Bone golem: a large construct of stacked bones and skulls, big bone fists, about 1.2x human height.
11. Wraith: a floating hooded shadow with a long scythe, tattered black cloth, two cold blue eyes.
12. (E) Death knight: black plate armor, glowing blue eyes in the helmet slit, a greatsword, a tattered cape.
13. (B) Lich: crowned skeletal sorcerer in purple and gold robes, floating, a glowing green phylactery gem, a staff
    of bones.
14. Snow wolf: white wolf with an icy blue mane, frost on its paws, on four legs.

Row 3:
15. Yeti: white-furred hulking beast with blue-grey skin on face and hands, big fists.
16. Pass archer: mountain hunter in white furs and a fur hood, a longbow with an ice-blue arrow.
17. Frost shaman: old shaman in furs with an antler headdress, a staff with a floating ice crystal.
18. Ice golem: blocky golem of clear blue ice crystals, frost mist around the fists.
19. Ice wyrmling: a small pale blue dragon on four legs, frost breath in the jaws, small wings.
20. (E) Yeti alpha: a bigger scarred yeti with a bone necklace and a broken tree trunk as a club.
21. (B) Frost giant: giant with a beard of icicles, fur and iron armor, a huge club of ice.
```

## Лист 3 — Степь и Гробницы (`--set steppe_tomb`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy tactics RPG, enemies.
17 figures in 3 rows (6, 6, 5), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between figures: nothing may touch. Elites (E) about 1.4x a normal enemy, bosses (B) about 1.7x.

Row 1:
1. Steppe raider: nomad in a fur hat and leather lamellar, a curved sabre, a small round shield.
2. Storm hawk: a large hawk in flight, wings spread, feather tips crackling with small blue lightning.
3. Stormcaller: nomad shaman with a hand drum, long braids, blue lightning swirling around the raised hand.
4. Steppe ogre: big grey-skinned ogre, topknot, a spiked wooden club, about 1.3x human height.
5. Thunder elemental: a swirling dark storm cloud body with a bright lightning core and lightning arms, floating.
6. Wind rider: raider riding a small shaggy steppe horse, a lance pointed forward (wide figure).

Row 2:
7. (E) Raider warchief: heavy lamellar armor, a horse-tail standard on the back, a big axe.
8. (B) Storm khan: khan in golden armor and a storm-grey cloak, a lightning glaive, a crown-helmet with a plume.
9. Mummy: wrapped in dirty bandages, one glowing green eye, arms reaching forward.
10. Scarab: a big golden-blue scarab beetle, shiny shell, about half human height.
11. Tomb archer: skeletal archer with a striped Egyptian headdress, a recurve bow.
12. Sand priest: priest in white-and-gold robes, a blue-and-gold collar, an ankh staff.

Row 3:
13. Sarcophagus: an upright golden sarcophagus with a painted face, the lid slightly open, green glow inside.
14. Sand golem: golem of sandstone blocks carved with hieroglyphs, sand pouring from the joints.
15. Jackal guard: jackal-headed warrior with a khopesh sword and a gold-trimmed shield.
16. (E) Tomb guardian: huge animated stone statue guardian with a spear, cracked, glowing eyes.
17. (B) Pharaoh: undead pharaoh with a striped headdress, golden death mask, crook and flail, floating wraps.
```

## Лист 4 — Лес фей и Затонувший город (`--set fae_sunken`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy tactics RPG, enemies.
17 figures in 3 rows (6, 6, 5), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between figures: nothing may touch. Elites (E) about 1.4x a normal enemy, bosses (B) about 1.7x.

Row 1:
1. Pixie: a tiny winged trickster fairy with a pink glow, floating, about half human height.
2. Thorn beast: a wolf-like beast made of dark thorny vines with red berries for eyes.
3. Illusionist: masked fae trickster in a violet harlequin outfit, a mirror shard floating by the hand.
4. Man-eater: a giant carnivorous flytrap plant on a thick stem, open toothy jaws, roots on the ground.
5. Dryad: green-skinned woman with leaf hair and a bark dress, vines curling around her arms.
6. Treant: an old huge tree creature with a mossy face in the bark, about 1.3x human height.

Row 2:
7. Shadow fae: dark fae with grey moth wings, black-violet clothes, pale glowing eyes.
8. (E) Thorn knight: knight in thorny bark armor, a sword with a rose on the hilt, a vine cape.
9. (B) Fae queen: tall fae queen with large butterfly wings, a crown of antlers and flowers, a glowing scepter.
10. Drowned sailor: bloated pale drowned sailor with seaweed, a rusty anchor chain over the shoulder.
11. Electric eel: a big eel coiled up out of a small puddle, glowing yellow stripes, sparks.
12. Siren: siren with a long fish tail coiled on a small rock, wet hair, singing.

Row 3:
13. Crab knight: a crab-man with shell armor, one huge claw and a short spear.
14. Deep priest: fish-headed priest in green robes, a coral staff with a glowing pearl.
15. Kraken tentacle: one giant purple tentacle rising from a puddle, suckers visible, about 1.2x human height.
16. (E) Drowned captain: ghostly sea captain with a tricorn hat, a cutlass, barnacles on the coat.
17. (B) Lord of the deep: fish-headed lord with a crown of coral, a trident, a beard of small tentacles.
```

## Лист 5 — Небесная цитадель (`--set citadel`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
character, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view, full body, every figure faces RIGHT, standing on an
invisible ground line, no ground shadow, no text, no labels. Dark fantasy tactics RPG, enemies.
9 figures in 2 rows (5, 4), in EXACTLY this order (left to right, top row first). Wide empty magenta space
between figures: nothing may touch. Elite (E) about 1.4x a normal enemy, boss (B) about 1.7x.

Row 1:
1. Sky knight: white and gold armor, small wings on the helmet, a kite shield, a spear.
2. Harpy: woman-bird with grey feathered wings for arms and talons, wild hair, mid-leap.
3. Sentinel golem: a floating marble-and-brass construct with one glowing blue eye, ready to shoot a beam.
4. Seraph: angelic healer with two pairs of white wings, a golden halo, gentle light from the hands.
5. Star mage: robe patterned with constellations, a staff topped with a small star.

Row 2:
6. Griffin: eagle head and wings, lion body, on four legs, golden-brown.
7. Void watcher: a floating purple eye of the void with small tentacles below, dark aura.
8. (E) Spire paladin: heavy white-gold armor, a tower shield, a hammer crackling with lightning.
9. (B) Celestial archon: radiant being in golden armor, a large halo, wings of light, a spear of light.
```

## Лист 6 — объекты поля (`--set objects`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
object, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Three-quarter view from slightly above, standing on an invisible ground
line, no ground shadow, no text, no labels. Battlefield objects for a dark fantasy tactics RPG.
21 objects in 3 rows of 7, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
objects: nothing may touch. A human would be about as tall as the cart; sizes are noted.

Row 1:
1. Powder barrel: wooden barrel with a black powder mark and a short fuse on top, about half human height.
2. Oil barrel: wooden barrel stained with dark oil dripping into a small puddle, about half human height.
3. Big keg: large iron-banded keg with a red skull mark, about 2/3 human height.
4. Boulder: big grey boulder with moss on top, about 2/3 human height.
5. Beetle nest: a mound of dried mud with holes, eggs and small orange glowing cracks.
6. Forge hearth: a stone forge furnace with an open fire mouth and a chimney, embers flying.
7. Ice idol: a crystal statue of a hooded figure carved from blue ice, glowing faintly.

Row 2:
8. Raider tent: a nomad felt yurt with a red door flap and a small horse-tail banner on top.
9. Scarab hive: a sandstone mound shaped like a beehive with carved holes, golden glints.
10. Witch ring: a ring of tall mushrooms with small glowing fairy stones, low and wide.
11. Summoning conch: a giant spiral conch shell on a wet rock, a faint teal glow from its opening.
12. Portal anchor: a floating purple crystal above a carved stone pedestal, sparks around it.
13. Supply cart: a wooden two-wheeled cart loaded with sacks and crates.
14. Captive smith: a kneeling chained blacksmith in a torn apron, hands bound, looking up hopefully.

Row 3:
15. Ward torch: a tall iron torch pole with a bright flame and carved protective runes on the pole.
16. Caravan wagon: a covered wagon with a canvas roof and a lantern, wide.
17. Lightning rod: an iron rod on a stone base wrapped in a copper coil, small sparks on the tip.
18. Firefly tree: a small tree with glowing yellow firefly lights among its leaves.
19. Bronze bell: a bronze bell hanging in a wooden frame with a small roof.
20. Bridge pillar: a marble bridge support pillar with gold trim and a cracked top.
21. Bone wall: a low wall segment built from bones and skulls, about human height, one cell wide.
```

## Лист 7 — окружение 1: болото, кузни, склеп, перевалы (`--set env1`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art environment props in the exact same style as the previous sheets: crisp square pixels, no
anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline, light from top-left, 2-3 tone
shading. Three-quarter view from slightly above, standing on an invisible ground line, no ground shadow, no text.
Props for a dark fantasy tactics RPG battlefield; "cover block" = a solid obstacle a soldier hides behind, about
one battlefield tile wide and chest-high; "low cover" = a low obstacle, knee-high and one tile wide.
18 props in 3 rows of 6, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
props: nothing may touch.

Row 1 (swamp, then volcanic forge):
1. Swamp cover block: a big mossy boulder with reeds growing at its base.
2. Swamp low cover: a fallen rotting log with mushrooms and moss.
3. Swamp tree: a gnarled willow-like tree with drooping leaves, tall.
4. Swamp bush: a low round bush with reeds.
5. Swamp rock: a small mossy stone.
6. Forge cover block: a pile of black slag rock with glowing orange cracks.

Row 2 (forge, then crypt):
7. Forge low cover: a row of iron ingots and a broken anvil.
8. Forge rock: a small dark basalt stone with an ember glow.
9. Forge dead tree: a charred black dead tree, smoke wisps.
10. Crypt cover block: a broken crypt wall section of grey stone bricks with a gothic arch.
11. Crypt low cover: a stone coffin lying on the ground.
12. Crypt tombstone: a small leaning gravestone with a cross.

Row 3 (crypt, then snowy mountain pass):
13. Crypt dead tree: a twisted leafless grey tree.
14. Crypt rock: a small cracked grey stone with a skull beside it.
15. Pass cover block: a big boulder covered in ice and snow.
16. Pass low cover: a snowdrift with a frozen log.
17. Pass pine: a tall snow-covered fir tree.
18. Pass rock: a small snow-capped stone.
```

## Лист 8 — окружение 2: степь, гробницы, лес фей, затонувший город, цитадель (`--set env2`)

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art environment props in the exact same style as the previous sheets: crisp square pixels, no
anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline, light from top-left, 2-3 tone
shading. Three-quarter view from slightly above, standing on an invisible ground line, no ground shadow, no text.
Props for a dark fantasy tactics RPG battlefield; "cover block" = a solid obstacle a soldier hides behind, about
one battlefield tile wide and chest-high; "low cover" = a low obstacle, knee-high and one tile wide.
20 props in 4 rows of 5, in EXACTLY this order (left to right, top row first). Wide empty magenta space between
props: nothing may touch.

Row 1 (stormy steppe, then desert tombs):
1. Steppe cover block: a tall weathered standing stone with carved runes.
2. Steppe low cover: two hay bales and a broken wheel.
3. Steppe bush: a dry yellow-green tumbleweed bush.
4. Steppe rock: a small flat brown stone.
5. Tomb cover block: a big sandstone block carved with hieroglyphs.

Row 2 (desert tombs, then dark fae forest):
6. Tomb low cover: a fallen sandstone column segment.
7. Tomb column: a tall sandstone column with a lotus capital, slightly broken.
8. Tomb rock: a small sand-colored stone half buried in sand.
9. Fae cover block: a giant glowing blue mushroom with a thick stem.
10. Fae low cover: a big twisted mossy root arching out of the ground.

Row 3 (fae forest, then sunken city):
11. Fae mushroom: a cluster of three glowing violet mushrooms.
12. Fae tree: a dark twisted tree with violet leaves and small glowing lights.
13. Sunken cover block: a ruined stone wall covered in coral and barnacles.
14. Sunken low cover: broken ship planks and a rotten barrel.
15. Sunken column: a broken stone column wrapped in seaweed.

Row 4 (sunken city, then sky citadel):
16. Sunken rock: a small wet stone with a starfish.
17. Citadel cover block: a white marble block with gold trim.
18. Citadel low cover: a fallen white marble column.
19. Citadel column: a tall white marble column with a gold capital.
20. Citadel rock: a small white marble shard.
```
