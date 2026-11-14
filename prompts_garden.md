# Промпты спрайтов сада

Сад использует 18 PNG: **6 растений × 3 стадии роста**. Игра ищет их здесь:

```
assets/sprites/garden/<вид>_<стадия>.png
```

Например: `assets/sprites/garden/sunleaf_0.png`, `sunleaf_1.png`, `sunleaf_2.png`.
Если файла нет, рисуется процедурный спрайт из `ui/garden_sprites.py`.

Стадии:
- `0` — росток;
- `1` — молодое растение;
- `2` — взрослое/цветущее.

Все спрайты рисуются **без горшка, без почвы, без клетки и без тени**: игра сама ставит их на изометрическую грядку. Низ растения — по нижнему краю картинки.

---

## Общий блок стиля

Вставлять в начало каждого отдельного промпта вместо `[стиль]`.

```
True pixel art game sprite of one garden plant, 64x64 logical grid, upscaled 8x with nearest neighbor
to 512x512. Crisp square pixels, hard pixel edges, no anti-aliasing, no blur, no gradients, no
photorealism, no 3D render. Limited palette of 12-16 colors, 1-pixel dark outline (dark brown/green,
not pure black), light from top-left, simple 2-3 tone shading. Isometric alchemy-garden view: the plant
is seen slightly from above and front, centered horizontally, roots/base touching the bottom edge of
the canvas, readable silhouette at 60 px tall. One single plant only: no pot, no planter, no soil tile,
no garden bed, no ground shadow, no text, no frame, no UI, no background objects. Plain flat solid
magenta background (#FF00FF). Dark fantasy tactics RPG / Potion Craft inspired alchemy garden.
```

Для отдельных стадий можно добавить:

```
Stage 0 is the smallest (about 32-38 px of the 64 px height), stage 1 is medium (about 44-50 px),
stage 2 is the tallest and most detailed (about 56-62 px).
```

---

## Вариант 1 — один лист со всеми 18 спрайтами

Плюс: все растения получаются в едином стиле. После генерации лист нужно разрезать на 18 PNG
по сетке **3 колонки × 6 строк**: колонки — стадии 0, 1, 2 слева направо; строки — растения
в указанном порядке.

```
Make ONE sprite sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art garden plants in the exact same style as the previous game sheets: true pixel art, crisp
square pixels, no anti-aliasing, no blur, no gradients, limited palette of 12-16 colors, 1-pixel
dark outline (dark brown/green, not black), light from top-left, 2-3 tone shading. Isometric
alchemy-garden view, every plant seen slightly from above and front, roots/base on an invisible
ground line, no ground shadow, no pot, no planter, no soil tile, no text, no labels, no frames.
Dark fantasy tactics RPG / Potion Craft inspired alchemy garden, readable silhouettes at small size.

18 separate plant sprites in 3 columns and 6 rows, in EXACTLY this order: columns are growth stages
0, 1, 2 from left to right; rows are plants from top to bottom. Each cell contains exactly one
complete plant, centered, with wide empty magenta space between cells: nothing may touch or overlap.
Stage 0 is a small sprout, stage 1 is a medium young plant, stage 2 is the largest flowering plant.

Row 1, Sunleaf:
1. Stage 0: a tiny golden-green sprout with two broad cotyledon leaves and a short pale stem.
2. Stage 1: a taller green stem with four broad oval leaves and a closed golden bud.
3. Stage 2: a lush sunleaf with six broad golden-green leaves, one open sunflower-like bloom with
   an amber center, faint golden motes around it.

Row 2, Moonroot:
4. Stage 0: a small blue-green sprout with two narrow leaves and a tiny pale root tip.
5. Stage 1: a young moonroot with a swelling blue-violet root, three leaves and a closed pale bud.
6. Stage 2: an adult moonroot with a fat exposed blue-violet root, silver-blue leaves and a pale
   crescent-shaped moonflower, soft cold glow.

Row 3, Thornbud:
7. Stage 0: a small dark-green thorny sprout with two pointed leaves and tiny thorns.
8. Stage 1: a branching thorny stem with sharp thorns, dark leaves and a closed magenta bud.
9. Stage 2: an adult thornbud with several open magenta buds, long sharp thorns, dark green leaves
   and a few loose pink petals.

Row 4, Starflower:
10. Stage 0: a thin teal sprout with two star-shaped cotyledons and a tiny pale tip.
11. Stage 1: a slender stem with four narrow leaves and a closed star-shaped bud.
12. Stage 2: an adult starflower with three five-pointed cyan-white flowers, glowing pale centers,
    thin teal leaves and tiny star-shaped motes.

Row 5, Emberfern:
13. Stage 0: a small curled fern sprout, orange-red at the tip, with two tiny fronds.
14. Stage 1: a young emberfern with several curled fronds, glowing orange edges and a few embers.
15. Stage 2: an adult emberfern with a full crown of orange-red fronds, glowing ember tips, a
    charred dark base and tiny floating sparks.

Row 6, Frostbell:
16. Stage 0: a small frosty sprout with two pale blue leaves and a tiny ice crystal.
17. Stage 1: a young frostbell with a slender stem, closed pale-blue bell buds and frost on the leaves.
18. Stage 2: an adult frostbell with three drooping bell-shaped pale-blue flowers, icy crystal leaves,
    frost sparkles and a soft cold glow.
```

Негативный промпт, если генератор поддерживает:

```
Negative prompt: pot, planter, soil, garden bed, tile, ground, shadow, text, labels, frame, border,
UI, multiple plants in one cell, anti-aliasing, blur, gradient, photorealistic, 3D render, noise.
```

---

## Вариант 2 — отдельные спрайты

Каждый блок — отдельная картинка. Вместо `[стиль]` подставить общий блок стиля выше.
Сохранять в `assets/sprites/garden/` под указанным именем.

### Солнечный лист

`sunleaf_0.png` — стадия 0:
```
[стиль] Sunleaf, growth stage 0 of 3 (sprout): a tiny golden-green seedling with two broad oval
cotyledon leaves, a short pale stem and a small root base. No flower yet. Warm yellow-green palette.
```

`sunleaf_1.png` — стадия 1:
```
[стиль] Sunleaf, growth stage 1 of 3 (young plant): a taller green stem with four broad oval leaves,
a closed golden bud at the top, small side shoots and a warm yellow-green palette.
```

`sunleaf_2.png` — стадия 2:
```
[стиль] Sunleaf, growth stage 2 of 3 (mature): a lush adult sunleaf with six broad golden-green
leaves, one large open sunflower-like bloom with an amber center, a few golden light motes and a
warm sunlit palette.
```

### Лунный корень

`moonroot_0.png` — стадия 0:
```
[стиль] Moonroot, growth stage 0 of 3 (sprout): a small blue-green seedling with two narrow leaves,
a short pale stem and a tiny pale root tip. No flower. Cool violet-blue palette.
```

`moonroot_1.png` — стадия 1:
```
[стиль] Moonroot, growth stage 1 of 3 (young plant): a young moonroot with a swelling blue-violet
root, three silver-blue leaves and a closed pale bud, faint cold glow.
```

`moonroot_2.png` — стадия 2:
```
[стиль] Moonroot, growth stage 2 of 3 (mature): an adult moonroot with a fat exposed blue-violet
tuber root, silver-blue leaves and a pale crescent-shaped moonflower, soft moonlight glow.
```

### Терновый бутон

`thornbud_0.png` — стадия 0:
```
[стиль] Thornbud, growth stage 0 of 3 (sprout): a small dark-green thorny seedling with two pointed
leaves, tiny thorns on the stem and a short root base. No open flower.
```

`thornbud_1.png` — стадия 1:
```
[стиль] Thornbud, growth stage 1 of 3 (young plant): a branching dark-green stem with sharp thorns,
several pointed leaves and one closed magenta bud.
```

`thornbud_2.png` — стадия 2:
```
[стиль] Thornbud, growth stage 2 of 3 (mature): an adult thornbud with several open magenta buds,
long sharp thorns, dark green leaves and a few loose pink petals.
```

### Звёздный цвет

`starflower_0.png` — стадия 0:
```
[стиль] Starflower, growth stage 0 of 3 (sprout): a thin teal seedling with two star-shaped
cotyledons, a pale tip and a small root base. No open flower.
```

`starflower_1.png` — стадия 1:
```
[стиль] Starflower, growth stage 1 of 3 (young plant): a slender teal stem with four narrow leaves
and one closed star-shaped bud, faint cyan glow.
```

`starflower_2.png` — стадия 2:
```
[стиль] Starflower, growth stage 2 of 3 (mature): an adult starflower with three five-pointed
cyan-white flowers, glowing pale centers, thin teal leaves and tiny star-shaped motes.
```

### Пепельный папоротник

`emberfern_0.png` — стадия 0:
```
[стиль] Emberfern, growth stage 0 of 3 (sprout): a small curled fern seedling with two tiny fronds,
orange-red tips and a dark charred root base.
```

`emberfern_1.png` — стадия 1:
```
[стиль] Emberfern, growth stage 1 of 3 (young plant): a young emberfern with several curled fronds,
glowing orange edges and a few tiny floating embers.
```

`emberfern_2.png` — стадия 2:
```
[стиль] Emberfern, growth stage 2 of 3 (mature): an adult emberfern with a full crown of orange-red
fronds, glowing ember tips, a charred dark base and tiny floating sparks.
```

### Морозный колокольчик

`frostbell_0.png` — стадия 0:
```
[стиль] Frostbell, growth stage 0 of 3 (sprout): a small frosty seedling with two pale-blue leaves,
a tiny ice crystal and a short root base.
```

`frostbell_1.png` — стадия 1:
```
[стиль] Frostbell, growth stage 1 of 3 (young plant): a young frostbell with a slender stem, closed
pale-blue bell buds and frost on the leaves.
```

`frostbell_2.png` — стадия 2:
```
[стиль] Frostbell, growth stage 2 of 3 (mature): an adult frostbell with three drooping bell-shaped
pale-blue flowers, icy crystal leaves, frost sparkles and a soft cold glow.
```

---

## Окружение сада

Отдельные ассеты для земли и клумбы. Они рисуются **без растений**: растения накладываются сверху игрой.

### Земляная ячейка (`garden_cell.png`)

```
True pixel art isometric garden ground tile, 512x256, upscaled 8x with nearest neighbor from a
64x32 logical diamond. A single empty 2:1 isometric diamond cell of dark rich garden soil, subtle
parallel furrows, a few tiny pebbles and a little moss on the edges, a thin dark outline around the
diamond, light from top-left, 2-3 tone shading, limited palette of 10-14 colors, crisp square
pixels, no anti-aliasing, no blur, no gradients, no photorealism. No plants, no seeds, no tools,
no fence, no shadow, no text, no frame, no UI. Plain flat solid magenta background (#FF00FF),
tile centered, the diamond fills the canvas with a small margin.
Dark fantasy alchemy garden / Potion Craft inspired, same style as the plant sprites.
```

Негатив:

```
Negative prompt: plant, flower, seed, pot, bed, fence, shadow, text, border, frame, UI,
anti-aliasing, blur, gradient, 3D render, perspective camera, multiple tiles.
```

### Клумба (`garden_bed.png`)

```
True pixel art isometric raised garden bed, 1536x1024, plain flat solid magenta background
(#FF00FF). A large empty isometric flowerbed / raised planter with a 6x4 cell footprint, viewed
from the same 2:1 isometric angle as the game garden. Thick weathered wooden beams or dark stone
edging around the perimeter, rich dark soil inside, faint 6x4 grid of furrows, small pebbles,
moss and a few roots on the border, light from top-left, 2-3 tone shading, limited palette of
14-18 colors, crisp square pixels, hard pixel edges, no anti-aliasing, no blur, no gradients,
no photorealism, no text, no labels, no plants, no flowers, no seeds, no tools, no shadow, no
UI. Dark fantasy alchemy garden / Potion Craft inspired, same style and outline language as the
plant sprites. The bed is centered, its whole diamond footprint visible, with empty magenta space
around it.
```

Негатив:

```
Negative prompt: plants, flowers, seeds, vegetables, gardener, tools, text, labels, frame, UI,
shadow, anti-aliasing, blur, gradient, 3D render, perspective, cropped edges.
```

Если нужен один лист:

```
Make ONE environment sheet image, 1536x1024, plain flat solid magenta background (#FF00FF).
Two separate assets only, in this order: left — one empty isometric 2:1 diamond garden soil cell
(about 512x256); right — one large empty isometric raised flowerbed with a 6x4 footprint and a
weathered wooden/stone border (about 900x700). Both in the same dark-fantasy alchemy pixel-art
style as the plant sprites: crisp square pixels, hard edges, no anti-aliasing, no blur, no
gradients, limited palette, 1-pixel dark outline, light from top-left, no plants, no flowers,
no tools, no text, no frame, no UI, no shadows. Wide empty magenta space between the two assets:
nothing may touch.
```

Куда сохранять (когда ассеты будут готовы):

```
assets/sprites/garden/env/garden_cell.png
assets/sprites/garden/env/garden_bed.png
```

Пока этих файлов нет, игра рисует землю процедурными ромбами.

## Сохранение и импорт

1. Сгенерировать отдельные картинки 512×512 или лист 1536×1024.
2. Отдельные картинки положить сразу в `assets/sprites/garden/` с именами из списка.
3. Если картинка с пурпурным фоном — игра вырежет фон при загрузке. Если хочется
   дополнительно уменьшить/почистить палитру, можно прогнать через `tools/import_sprite.py`:

```
python tools/import_sprite.py assets/art_src/sunleaf_2.png assets/sprites/garden/sunleaf_2.png 64
```

4. Если сгенерирован лист — положить его в `assets/art_src/sheet_garden.png` и нарезать:

```
python tools/import_garden_sheet.py assets/art_src/sheet_garden.png assets/sprites/garden
```

5. Перезапустить игру: `ui/garden_sprites.py` сначала ищет PNG, а при их отсутствии рисует
   процедурный спрайт.
