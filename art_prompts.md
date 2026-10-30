# Промпты для генерации спрайтов (ChatGPT / DALL·E, пиксель-арт)

Спрайты героев и врагов для сюжетного режима. Требования игры — `assets/sprites/README.md`: холст 32×32 (босс до
48×48), прозрачный фон, персонаж смотрит **вправо**, ноги — на нижнем ряду по центру, контур 1 пиксель, без тени.

Генератор картинок не умеет рисовать ровно 32×32, поэтому просим «пиксель-арт 32×32, увеличенный в 16 раз»
(картинка 512×512 из крупных квадратов) на однотонном фоне, а потом переводим её в спрайт скриптом:

```
python tools/import_sprite.py картинка.png assets/sprites/warrior.png          # 32×32
python tools/import_sprite.py картинка.png assets/sprites/forge_lord.png 48    # босс 48×48
```

Скрипт сам находит сетку крупных пикселей, убирает фон, урезает палитру и кладёт ноги на нижний ряд.

Если генератор выдал **все спрайты одним листом** (как вышло с главами 1–2 — исходник `assets/art_src/sheet_ch12.png`),
нарезать его целиком:

```
python tools/import_sheet.py assets/art_src/sheet_ch12.png assets/sprites --preview preview.png
```

Порядок персонажей на листе — как в списке ниже (ряды сверху вниз, в ряду слева направо). Каждый вырезается по
своему контуру, уменьшается в общем масштабе (рост относительно друг друга сохраняется), палитра урезается,
добавляется контур; элита — холст 40×40 (в игре 80 px), боссы — 48×48 (96 px).

---

## Общий блок стиля (вставлять в начало каждого промпта)

```
Pixel art game sprite, true pixel art on a 32x32 grid, every pixel a crisp solid square, upscaled 16x with
nearest neighbor to 512x512. No anti-aliasing, no blur, no gradients, no dithering noise. Limited palette of
12-16 colors, 1-pixel dark outline around the whole character (dark brown/navy, not pure black). Light from
top-left, simple 2-3 tone shading. Three-quarter view, full body, facing RIGHT, standing pose, feet touching the
bottom edge of the 32x32 grid, character centered horizontally, fills about 26-30 pixels of height. Plain flat
solid magenta background (#FF00FF), no shadow on the ground, no text, no frame, single character only.
Style: dark fantasy tactics RPG, readable silhouette at small size, like classic SNES / GBA tactics games.
```

Советы:
- Если вышло размыто или «нарисовано под пиксели» — добавить: `Hard pixel edges. Each square is exactly 16x16 screen
  pixels. Count the grid: 32 columns, 32 rows.`
- Одинаковый стиль у всех: генерируйте героев **в одном чате** подряд и пишите «same style, same palette rules as
  the previous sprite».
- Цвет команды не рисуем — игра добавляет кольцо под ногами сама.

---

## Герои

### Торвальд — Воин (`warrior.png`)
```
[стиль] A veteran mercenary warrior in his 40s: steel half-helm with a red plume, red tabard over chainmail,
round wooden shield with an iron rim on his left arm, broad straight sword raised in the right hand, short brown
beard, heavy boots. Sturdy, confident stance.
```

### Ирма — Пиромант (`mage.png`)
```
[стиль] A young female pyromancer apprentice: deep purple pointed hat and robe with ember-orange trim, a short
wooden staff topped with a small glowing amber stone, a tiny flame floating above her open left palm, red hair in
a braid. Determined face.
```

### Брат Осмунд — Жрец (`priest.png`)
```
[стиль] A kind middle-aged monk priest: white and gold hooded robe, bald head with a short grey beard, a bronze
holy symbol on a chain, holding a small silver flask of holy water and a prayer book. Calm, warm expression.
```

### Лина — Лучник (`archer.png`)
```
[стиль] A young female ranger archer: hooded green cloak, leather jerkin, quiver of arrows on her back, a tall
longbow drawn and aimed to the right, brown hair, light leather boots. Alert, agile pose.
```

### Гарм — Страж (`guardian.png`)
```
[стиль] An old grey-bearded guardian knight: heavy steel plate armor with blue-grey cloth, a huge rectangular tower
shield with an amber emblem held in front, a short spear with a hook in the other hand, scarred face. Immovable,
wide stance.
```

### Сив — Криомант (`cryo.png`)
```
[стиль] A pale female cryomancer: icy blue and white layered robes, silver-white hair, a staff topped with a sharp
floating ice crystal, frost on the hem of her robe, small ice shards orbiting her hand. Cool, stern expression.
```

### Ниа — Ассасин (`assassin.png`)
```
[стиль] A slim female assassin: dark violet leather armor, hood and face mask leaving only the eyes visible, twin
curved daggers held in reverse grip, a belt with small poison vials, crouched ready-to-strike pose.
```

### Олвин — Друид (`druid.png`) и облик медведя (`druid_bear.png`)
```
[стиль] An elderly druid: hooded mantle of moss and leaves with small antlers on the hood, long white beard braided
with twigs, gnarled wooden staff with green leaves and a glowing seed, bare feet wrapped in roots.
```
```
[стиль] A large brown bear with patches of moss and small leaves in its fur, glowing green eyes, standing on four
legs facing right, heavy and powerful. Fills about 26 pixels of width.
```

---

## Враги главы 1 — Болото

### Болотный слизень (`slime.png`)
```
[стиль] A green swamp slime blob, translucent with darker green core, two simple white eyes, a few bubbles and bits
of swamp weed inside, small puddle under it. About 18 pixels tall.
```

### Болотный стрелок (`bog_archer.png`)
```
[стиль] A hunched swamp goblin archer: mossy green skin, rags and reed armor, small crude bow aimed to the right,
a quiver of bone-tipped arrows, big yellow eyes.
```

### Огненный жук (`beetle.png`)
```
[стиль] A large swamp fire beetle: dark red shiny carapace with glowing orange cracks, six legs, small mandibles,
faint embers on its back. About 16 pixels tall.
```

### Жаба-шаман (`frog_shaman.png`)
```
[стиль] A fat toad shaman standing upright: warty olive skin, a feathered bone necklace, a gnarled staff with a
dangling skull charm, a small green poison wisp floating near the staff.
```

### Король слизней — элита (`slime_king.png`, 48×48)
```
[стиль, но 48x48 grid upscaled 10x to 480x480] A giant green slime king with a rusty iron crown sinking into its
top, smaller slimes and bones visible inside its body, angry eyes, dripping edges.
```

### Ледяная ведьма — босс (`ice_witch.png`, 48×48)
```
[стиль, но 48x48 grid] A tall sinister ice witch: ragged pale blue robes, long white hair, a crown of icicles,
holding a staff with a stolen glowing amber stone frozen inside a crystal, frost mist at her feet.
```

## Враги главы 2 — Огненные кузни

### Огненный бес (`fire_imp.png`)
```
[стиль] A small red fire imp: tiny horns, bat wings, a burning tail tip, mischievous grin, fireball forming in its
claw. About 18 pixels tall.
```

### Саламандра (`salamander.png`)
```
[стиль] A fire salamander lizard: orange and black scales, glowing lava spots, flames running along its spine,
low four-legged stance facing right.
```

### Метатель молотов (`hammer_thrower.png`)
```
[стиль] A stocky forge dwarf: soot-stained leather apron, heavy gloves, goggles on the forehead, a war hammer raised
to throw, a belt of spare hammers.
```

### Жрец пламени (`flame_priest.png`)
```
[стиль] A cultist flame priest: black and crimson robes with a hood, a mask of hammered bronze, a censer on a chain
pouring fire, glowing runes on the sleeves.
```

### Магмовый голем (`magma_golem.png`)
```
[стиль] A hulking magma golem: body of dark cooled basalt plates with glowing orange lava seams, huge fists,
small burning eyes, heavy and slow.
```

### Надсмотрщик кузни — элита (`forge_overseer.png`, 48×48)
```
[стиль, но 48x48 grid] A brutal forge overseer: horned iron helmet, massive bare arms with burn scars, a huge
glowing-hot whip of chain, leather and iron armor.
```

### Повелитель горна — босс (`forge_lord.png`, 48×48)
```
[стиль, но 48x48 grid] The forge lord: towering figure in black iron armor with molten lava pouring through the
joints, a crown of anvil horns, wielding a giant hammer with amber stones melted into its head.
```
