# Промпты: новые сеты кузни

Четыре новых сета доступны во всех мастерских:

| Сет | Редкость | Тема |
|---|---|---|
| «Кровавая наковальня» | rare | кровотечение, sustained-урон |
| «Молот и наковальня» | epic | крит, уязвимость одной цели |
| «Шлаковый панцирь» | epic | шипы, контрудар |
| «Кузнечный оберег» | legendary | поддержка отряда, AP |

Иконки предметов лежат в `assets/icons/`:

- `art_blood_anvil_<вид>.png`
- `art_hammer_anvil_<вид>.png`
- `art_slag_armor_<вид>.png`
- `art_forge_ward_<вид>.png`

`<вид>`: `bracers`, `belt`, `ring`, `amulet`, `talisman`.

Пока картинок нет, игра рисует прежние силуэты по виду и редкости. После импорта
`game/workshop_scenes.py` сначала ищет иконку сета, затем старую иконку вида/редкости.

---

## Лист S1 — иконки четырёх сетов (20 штук)

Сохранить как `assets/art_src/sheet_icons_sets.png` и нарезать:

```
python tools/import_sheet.py assets/art_src/sheet_icons_sets.png --set icons_sets --preview p.png
```

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32 grid per
icon, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette, 1-pixel dark outline,
light from top-left, 2-3 tone shading. Each icon is ONE wearable artifact of a dark fantasy tactics RPG,
seen from the front, filling most of its square, readable when tiny. No text, no letters, no numbers, no
frames, no background plates, no circles behind the objects. Wide empty magenta space between icons:
nothing may touch.

20 icons in 4 rows of 5, in EXACTLY this order (left to right, top row first).
The five columns are always: bracers, belt, ring, amulet, talisman.

ROW 1 — set "Blood Anvil" (rare, blood and blackened iron):
1. Bracers: a pair of heavy blackened-iron forearm guards with deep crimson grooves, small blood-red rivets,
   forge-scale texture, a faint red glow in the seams.
2. Belt: a thick smith's belt of dark leather and iron plates, a heavy square buckle with a drop of red enamel,
   small hanging chain and a blood-red leather tongue.
3. Ring: a thick iron signet ring with a rough blood-red stone, the band shaped like a tiny anvil, dark
   hammer marks on the metal.
4. Amulet: a heavy iron pendant shaped like a small anvil, a red teardrop gem hanging below it, short black
   chain, soot and dried blood in the crevices.
5. Talisman: a dark leather-and-iron charm, a small blood-red crystal bound with wire, a hammer-shaped
   clasp, a strip of crimson cloth, rough and worn.

ROW 2 — set "Hammer and Anvil" (epic, polished steel and brass):
6. Bracers: articulated steel forearm guards with brass edges, a raised hammer-and-anvil emblem on each,
   precise geometric plates, a few orange sparks caught in the seams.
7. Belt: a broad steel-buckled belt with brass anvil plaques, a short chain and a small smith's hammer charm,
   clean and master-crafted.
8. Ring: a polished steel ring with a square brass anvil face, a tiny orange ember set in the center, fine
   engraved hammer marks around the band.
9. Amulet: a brass anvil pendant on a steel chain, a small glowing orange ember in the anvil's throat,
   polished metal with dark engraved lines.
10. Talisman: a compact steel-and-brass master's token, an anvil and crossed hammer, a hanging ember bead,
    precise edges and a warm orange highlight.

ROW 3 — set "Slag Armor" (epic, black slag and molten cracks):
11. Bracers: rough black slag-plate bracers with jagged edges, glowing orange cracks between the plates,
    tiny sharp spikes, soot and cooled lava texture.
12. Belt: a heavy belt of black slag plates and chain, a crude iron buckle, molten orange seams, small
    hanging slag shards.
13. Ring: a chunky black slag ring with a rough volcanic stone, orange cracks across the stone, jagged
    iron prongs, a few tiny spikes.
14. Amulet: a jagged black-slag pendant with a glowing molten core, rough iron chain, sharp shards around
    the edge, smoke-like dark highlights.
15. Talisman: a crude slag-and-iron ward, a cluster of sharp black shards bound with wire, a glowing orange
    crack in the center, a short charred leather cord.

ROW 4 — set "Forge Ward" (legendary, bronze, gold and warm runes):
16. Bracers: ornate bronze forearm guards with gold trim, warm amber runes, a small anvil-and-flame emblem,
    polished but battle-worn, soft golden glow in the engravings.
17. Belt: a masterwork bronze belt with a gold anvil buckle, hanging rune plates, a deep red leather tongue,
    warm amber highlights and fine engraved knotwork.
18. Ring: a gold-and-bronze ring with a tiny anvil-shaped crown, a warm amber gem, runes around the band,
    a subtle golden glow.
19. Amulet: a large bronze anvil pendant with gold inlay, a glowing amber heart-stone, a heavy chain with
    small rune links, warm protective light.
20. Talisman: an ornate bronze-and-gold smith's ward, an anvil with a flame above it, hanging amber beads,
    engraved runes, a short chain and a small red cloth ribbon.

```

---

## Если генератор не тянет 20 иконок

Можно генерировать по одному сету: 5 иконок в одном ряду, тот же стиль и тот же порядок
`bracers, belt, ring, amulet, talisman`. Сохранять как `sheet_icons_set_<set>.png` и резать вручную
или добавить отдельный набор в `tools/import_sheet.py`.

Главное — не смешивать палитры сетов:

- «Кровавая наковальня»: чёрное железо + тёмно-красный, почти без золота.
- «Молот и наковальня»: светлая сталь + латунь + оранжевые искры.
- «Шлаковый панцирь»: чёрный шлак + оранжевые трещины, грубые края.
- «Кузнечный оберег»: бронза + золото + тёплый янтарный свет, самые богатые и аккуратные иконки.
