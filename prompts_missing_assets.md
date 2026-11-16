# Промпты для недостающих спрайтов и иконок

Проверка ассетов по всей игре (17.11.2026):

- 21 класс — у всех есть спрайты.
- 79 врагов — у всех есть спрайты.
- 40 призывов — у 21 есть свой PNG, у 19 своего спрайта нет (часть сейчас живёт на алиасах и заглушках).
- 26 объектов — у 23 есть свой спрайт, у 3 нет; ещё 16 значений `art` используют процедурную заглушку.
- 53 предмета, 62 дара, 7 иконок карты, 16 иконок эффектов — иконки на месте.
- 164 иллюстрации — реальных пропусков среди иллюстраций нет.
- 9 реликвий и 5 рун — иконок нет, но UI пока рисует их текстом; это необязательный polish-лист.

Ниже — готовые запросы. Сначала самое заметное в бою: призывы и объекты. Реликвии и руны — опционально.

---

## 1. Недостающие призывы и духи

Лист на 19 фигур: 4 ряда (5, 5, 5, 4). Порядок совпадает с набором `missing_summons` в `tools/import_sheet.py`.

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game sprites in the exact same style as the previous sheets: true pixel art on a 32x32 grid per
figure, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark
outline (dark brown/navy, not black), light from top-left, 2-3 tone shading. Three-quarter view, full
body, every character faces RIGHT, standing on an invisible ground line, no ground shadow, no text,
no labels, no frames. Dark fantasy tactics RPG, readable silhouettes like classic SNES / GBA tactics
games. Normal figures are about 26-30 pixels tall; spirits may float above the ground line; totems are
short static objects. Leave wide empty magenta space between figures: nothing may touch or overlap.
19 figures in 4 rows (5, 5, 5, 4), in EXACTLY this order (left to right, top row first).

Row 1:
1. Risen corpse: a simple recently raised dead human, ragged grave clothes, pale bony hands, no armor,
   slumped shambling pose, faint teal glow in empty eye sockets.
2. Risen knight: a skeleton knight in broken rusty plate armor, a notched sword and a cracked round
   shield, green soul-fire leaking from the helmet, heavy undead stance.
3. Mummy risen: a bandaged mummy with loose trailing wraps, tomb dust, one arm raised, green soul glow
   in the eye holes, ancient gold funerary bits.
4. Spirit wolf: a translucent blue-white spectral wolf, four legs, trailing mist instead of a lower
   body, glowing cyan eyes, lean hunting silhouette, seen from three-quarter side.
5. Spirit healer: a floating robed spirit healer with no legs, blue-green glow, gentle open hands,
   a small healing wisp above the palm, calm hooded face.

Row 2:
6. Illusion: a translucent purple duplicate of a small humanoid fairy, shimmering edges, blank mask-like
   face, no weapon, slightly transparent, magical afterimage.
7. Archer clone: a ghostly pale-blue mirror copy of a skeleton archer, translucent short bow, same
   archer stance, fading edges, cold blue eye glow.
8. Decoy thorns: a straw-and-bone scarecrow decoy on a wooden post, thorny vines wrapped around it,
   a taunting carved face, tattered cloth, no legs.
9. Banner: a small planted war banner, dark wood pole, tattered green-black cloth with a simple skull
   emblem, bone charms hanging from the crossbar, faint green command glow.
10. Totem thunder: a carved storm totem of dark wood and stone, jagged crystal shards, small lightning
    arcs around the top, purple-blue glow, heavy base.

Row 3:
11. Totem ward: a guardian totem of grey stone and dark wood, shield-shaped carved face, heavy square
    base, pale blue protective glow, sturdy and defensive.
12. Totem rage war: a tall red-orange war totem, iron spikes, burning runes, aggressive carved face,
    embers around the top, wide stance.
13. Totem rage close: a short compact red totem, cracked stone, fiery seams, small flames at the top,
    dense and aggressive.
14. Totem spirit might: a purple spirit totem with a carved skull, feathers and bone charms, strong
    violet aura, power radiating from the top.
15. Totem spirit wise: a blue-violet wise totem with an owl-like carved face, calm glow, hanging bone
    beads, quiet magical aura.

Row 4:
16. Totem stone rock: a rough granite totem, deep cracks, moss in the seams, heavy blunt shape, earthy
    grey-brown palette.
17. Totem stone shield: a grey stone totem with a round shield plate carved into the front, blue ward
    glow around the edges, solid defensive base.
18. Totem heal burst: a green life totem, blooming moss and small leaves, a glowing green heart-shaped
    core, warm restorative light.
19. Totem heal clean: a teal cleansing totem, spring-water motif, clean white-green glow, simple carved
    face, calm and pure.
```

---

## 2. Недостающие объекты поля

Лист на 19 объектов: 4 ряда (5, 5, 5, 4). Порядок совпадает с набором `missing_objects` в `tools/import_sheet.py`.

```
Make ONE object sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game object sprites in the exact same style as the previous sheets: true pixel art on a 32x32
logical grid, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel
dark outline, light from top-left, 2-3 tone shading. Three-quarter view, objects standing on an
invisible ground line, no ground shadow, no text, no labels, no frames. Dark fantasy tactics RPG.
Small props fit in 32x32; tall objects may use 32x40; center each object on its cell bottom. Leave wide
empty magenta space between objects: nothing may touch or overlap. 19 objects in 4 rows (5, 5, 5, 4),
in EXACTLY this order (left to right, top row first).

Row 1:
1. Barrel: a generic wooden barrel with dark iron bands and a closed lid.
2. Fire barrel: a charred wooden barrel with flames licking from the top, glowing orange seams,
   blackened iron bands.
3. Dynamite crate: a reinforced wooden crate with red dynamite sticks, a short lit fuse, iron corners,
   warning-scratched planks.
4. Ice wall: a jagged wall of blue-white ice, sharp crystal shards, translucent edges, frost mist,
   wide enough to block a tile.
5. Bones: a small pile of old bones and two skulls, scattered ribs, faint green soul mote.

Row 2:
6. Captive: a bound prisoner kneeling on the ground, dark ragged clothes, ropes around wrists,
   a wooden post behind, no gore, readable silhouette.
7. Coffin: a dark wooden coffin with iron handles, a cracked lid, old grave dust, subtle green glow
   from the seam.
8. Crystal: a cluster of sharp glowing crystals, teal and violet, dark rock base, magical inner light.
9. Furnace: a small stone furnace with an open orange fire mouth, iron grate, soot stains, warm glow.
10. Ice block: a single large block of blue ice, chipped corners, frosty white highlights, solid and
    heavy.

Row 3:
11. Idol: a carved stone idol with a squat body and glowing green eyes, ancient runes, moss in the
    cracks.
12. Mound: a grave mound of dark earth and stones, a small wooden marker, tufts of dead grass.
13. Pillar: a broken stone pillar, carved bands, cracked capital, moss and dust, tall vertical shape.
14. Ring: a ritual ring of small standing stones and mushrooms, a faint green circle on the ground,
    no characters inside.
15. Rod: a tall iron lightning rod on a stone base, copper coil and a small blue spark at the tip.

Row 4:
16. Sapling: a young tree sapling with a thin trunk, a few green leaves, dark soil clump at the base.
17. Shell: a giant spiral seashell, pale pink and bone-white, open lip, wet sheen, coastal prop.
18. Tent: a ragged raider tent of hide and dark cloth, wooden poles, rope ties, small entrance flap.
19. Torch: a standing wooden torch with an iron bracket, bright orange flame, charred top, warm light.
```

---

## 3. Опционально: иконки реликвий и рун

Сейчас UI рисует реликвии и руны текстом. Если делать им иконки — вот лист на 14 иконок: 4×4, две
последние ячейки пустые. Порядок совпадает с набором `icons_relics` в `tools/import_sheet.py`.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art upgrade icons in the exact same style as the previous icon sheets: each icon is true pixel art
on a 32x32 grid, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel
dark outline, light from top-left, 2-3 tone shading. Each icon is ONE bold centered emblem, readable at
small size, with a subtle magical glow where noted. No text, no letters, no numbers, no frames, no
background plates, no UI. Dark fantasy tactics RPG.
14 icons in 4 rows of 4, in EXACTLY this order (left to right, top row first). The last two cells of the
bottom row are empty magenta. Leave wide empty magenta space between icons: nothing may touch.

Row 1:
1. Amber charm: a glowing amber pendant on a dark cord.
2. Whetstone: a grey whetstone with a few orange sparks.
3. War drum: a round dark war drum with two crossed drumsticks.
4. Wanderer cloak: a green travel cloak with a small leaf clasp.

Row 2:
5. Bog moss: a clump of dark green swamp moss with a tiny mushroom.
6. Miser purse: a fat brown coin purse with gold coins spilling out.
7. Boiling pot: a black cauldron with green bubbling brew and steam.
8. Iron vow: a heavy iron ring wrapped in a short chain.

Row 3:
9. Soul catcher: a glass jar with a green soul-wisp trapped inside.
10. Rune of power: a red rune shaped like a fist and a sword.
11. Rune of thrift: a gold coin with a green leaf and a small plus sign.
12. Rune of haste: a winged boot with a small hourglass.

Row 4:
13. Rune of reach: a long arrow with a circular range arc.
14. Rune of breadth: a radial burst of small green runes.
15. EMPTY — plain magenta.
16. EMPTY — plain magenta.
```

---

## Как импортировать

Наборы уже добавлены в `tools/import_sheet.py`:

```
python tools/import_sheet.py assets/art_src/sheet_missing_summons.png --set missing_summons --preview assets/art_src/missing_summons_preview.png
python tools/import_sheet.py assets/art_src/sheet_missing_objects.png --set missing_objects --preview assets/art_src/missing_objects_preview.png
python tools/import_sheet.py assets/art_src/sheet_icons_relics.png --set icons_relics --preview assets/art_src/icons_relics_preview.png
```

Для высокого разрешения повторить с `--res 2` — спрайты уйдут в `assets/sprites/x2`.

Приоритет для картинки в бою: сначала **лист 1 (призывы)**, затем **лист 2 (объекты)**, затем
**лист 3 (реликвии/руны)**.
