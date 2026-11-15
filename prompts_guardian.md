# Промпты: Страж и сет «Спасение строя»

Страж переработан вокруг защитного конуса за спиной. Визуальный язык класса:
тяжёлая броня, копьё, круглый щит, тёмное золото и янтарный свет зоны.

---

## G1 — портрет класса

```
Pixel art character portrait for a dark fantasy tactics RPG, 64x64 logical grid, crisp square pixels,
no anti-aliasing, no blur, limited palette, 1-pixel dark outline, light from top-left.
A veteran guardian in dark-gold heavy plate, a tall spear in one hand, a round shield with an amber
inlay in the other. Calm, protective stance, scarred armor, short beard, amber light reflecting from
the shield. Seen from the chest up, readable at small size. Plain dark transparent background,
no text, no frame, no UI.
```

---

## G2 — иконки 13 способностей (лист 5x3)

Сохранить как `assets/art_src/sheet_icons_guardian.png` и нарезать в `assets/icons/`:

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32
grid per icon, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette,
1-pixel dark outline, light from top-left, 2-3 tone shading. Each icon is ONE ability of a dark
fantasy tactics RPG, seen from the front, filling most of its square, readable when tiny.
No text, no letters, no numbers, no frames, no background plates. Wide empty magenta space between
icons: nothing may touch.

13 icons in 3 rows of 5 (last row has 3), in EXACTLY this order, left to right, top row first.
```

1. **Стена щитов** — a row of three overlapping round shields, amber runes on the central boss.
2. **Прикрытие** — a large shield angled over a smaller silhouette, a protective amber arc.
3. **Стойка** — a planted spear behind a low shield, two amber arcs bracing the ground.
4. **Разворот строя** — a wide amber cone sweeping behind a small shield, three direction chevrons.
5. **Крюк** — a hooked spearhead on a chain, pulling a small enemy silhouette.
6. **Копейный заслон** — a fan of three spear tips inside an amber cone, dust at the base.
7. **Провокация** — a raised gauntlet and a shouting helm, three amber sound rings.
8. **Рывок к союзнику** — a guardian silhouette dashing along an amber arc toward a small ally.
9. **Вытащить** — a gauntleted hand pulling a small ally silhouette behind a shield.
10. **Обет защиты** — a drop of blood above an amber shield, a circle of small protective sparks.
11. **Клич защиты** — a horned helm shouting, a dome of amber light over three small allies.
12. **Спасение строя** — a guardian carrying a wounded ally inside an amber bubble, spear planted.
13. **Приказ на прорыв** — a spear pointing forward through a broken enemy shield, amber cracks.

---

## G3 — 6 классовых предметов

Сохранить как `assets/art_src/sheet_icons_guardian_items.png` и нарезать в `assets/icons/`.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32
grid per icon, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette,
1-pixel dark outline, light from top-left, 2-3 tone shading. Each icon is ONE wearable artifact of a
dark fantasy tactics RPG, seen from the front, filling most of its square, readable when tiny.
No text, no letters, no numbers, no frames, no background plates, no circles behind the objects.
Wide empty magenta space between icons: nothing may touch.

6 icons in 2 rows of 3, in EXACTLY this order:
```

1. **Эгида Стража** (`unique_guardian_aegis`, `plate`) — a heavy dark-gold breastplate with a round amber sunburst on the chest,
   layered plates, small shield-shaped rivets.
2. **Оплот** (`mail`) — a dense dark-steel mail hauberk with a broad belt and a square amber buckle,
   reinforced shoulder plates.
3. **Копьё заслона** (`blade`) — a long spear with a broad leaf-shaped head, amber inlay along the socket,
   a small guard shaped like a shield.
4. **Обет стража** (`charm`) — a round amber medallion on a short chain, a tiny shield and spear crossed
   inside the stone, dark-gold rim.
5. **Латы прикрытия** (`leather`) — reinforced leather-and-steel forearm guards, layered plates, amber
   stitching, small spikes on the outer edge.
6. **Плащ строя** (`cloak`) — a dark-gold cloak with a high collar, a round shield clasp, amber trim and
   a short torn edge.

---

## G4 — иконки сета «Спасение строя» (5 предметов)

Сет: `guardian_rescue`, редкость `epic`, материал `pearl`.
Сохранить как `assets/art_src/sheet_icons_guardian_set.png` и нарезать в `assets/icons/`.

```
Make ONE icon sheet image, 1536x1024, plain flat solid magenta background (#FF00FF) everywhere.
Pixel art game icons in the exact same style as the previous icon sheets: true pixel art on a 32x32
grid per icon, crisp square pixels, no anti-aliasing, no blur, no gradients, limited palette,
1-pixel dark outline, light from top-left, 2-3 tone shading. Each icon is ONE wearable artifact of a
dark fantasy tactics RPG, seen from the front, filling most of its square, readable when tiny.
No text, no letters, no numbers, no frames, no background plates, no circles behind the objects.
Wide empty magenta space between icons: nothing may touch.

5 icons in one row of 5, in EXACTLY this order:
```

1. **Bracers** — dark-gold bracers with a pearl-white inlay, a small amber rescue rune, layered plates.
2. **Belt** — a broad dark-gold belt with a pearl clasp, a small shield buckle and a short amber chain.
3. **Ring** — a dark-gold signet ring with a pearl cabochon, two tiny shield-shaped shoulders.
4. **Amulet** — a pearl pendant inside a dark-gold shield frame, a short chain and a drop of amber.
5. **Talisman** — a dark-gold rescue token, a pearl center, crossed spear and shield, a strip of amber cloth.

---

## G5 — иконки сетов кузни (если ещё не сгенерированы)

Для четырёх сетов кузни используй `prompts_sets.md`. Новый сет «Спасение строя» входит в
общий загрузчик `game/workshop_scenes.py`: он ищет `art_guardian_rescue_<вид>.png`, затем
старую иконку вида/редкости.
