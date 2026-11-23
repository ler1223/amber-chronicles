---
name: descent-card-design
description: Design, audit, and implement new cards, tags, items, tiers, and decks for the game «Спуск» (I:\Mygame2), especially CZN-inspired mechanics, damage amplification, enemy debuffs, AoE/movement, starter decks, and card rarity. Use this skill whenever the user asks to add, rework, balance, tier, port from Chaos Zero Nightmare, or analyze cards/decks in this project.
---

# Card design for «Спуск»

Use this skill for any card/deck/content task in `I:\Mygame2`. The game is a **grid tactical card roguelike**, not a pure card battler: movement, range, AoE, push, collision, and terrain matter.

Read these first:

- `docs/descent_damage_model.md` — exact damage formula and the two amplification axes.
- `docs/descent_tactics.md` — grid tags and tactical decks.
- `docs/descent_builds.md` — current schools and archetypes.
- `docs/descent_tiers.md` — basic/neutral/rarity/start-deck rules.
- `docs/czn_cards.md` and `data/czn/cards.json` — full CZN catalog and source mapping.
- `docs/descent_deckbuilding.md` — CZN deck-building principles.

## First analyze, then add

1. Inspect the existing cards in `data/deck/cards.json`; do not duplicate an existing effect under a new name.
2. Identify the card's role in a pipeline:
   - **Generator** — creates a resource, status, or cards.
   - **Amplifier** — makes that resource stronger.
   - **Payoff** — spends the resource for a large effect.
   - **Support** — draw, energy, defense, healing, positioning.
   - **Utility** — movement, control, terrain, scouting.
3. Check what the card does on the grid:
   - single target / area / line / adjacent;
   - range and line of sight;
   - movement, push, pull, collision, wall;
   - whether it enables an ally or exposes the player.
4. Choose a tag only if it already exists or if it will have 3–5 engines and 2 payoffs. Avoid tag inflation.

## Damage: always use both axes

The game currently has two independent ways to increase damage. New content should use both.

### Attacker buffs

- `strength` — flat +N to every hit.
- `ranged_bonus` — flat +N to ranged hits.
- `focus` — next ranged hit ×2.
- `empower` — next card of a tag gets a bonus.
- `temper` — one card gets +N for the rest of battle.
- `momentum` — Mercenary only; converts into hit damage.
- `hunt` — follow-up shot after a single-target `[Травля]` attack.
- `tag_bonus` on items — passive tag damage.
- `double_next` — rare multiplier; use sparingly.

### Enemy debuffs

- `vulnerable` — incoming damage ×1.5.
- `mark` — +N to the next hit, then consumed.
- `bleed` / `poison` / `burn` — DoT; bleed and poison bypass shield.
- `weak` — reduces enemy outgoing damage; it is defense, not a damage-taken amplifier.
- `root` / `stun` — tempo/position control, not direct damage amplification.

Do not add a generic new “+X% damage taken” status unless the design explicitly needs one. Prefer vulnerable/mark first.

## Card design checklist

Before implementing a card, answer:

- What is the card's **role** and which existing pipeline does it join?
- Is it a **buff**, **debuff**, **payoff**, **support**, or **utility**?
- Does it require the player to make a **positional choice** or only click the best target?
- Does it create a new resource/status, or reuse one?
- What is its **cost / rarity / tier**?
- What are 5 epiphany variants? At least one should change the role or add a bridge, not only increase numbers.
- What cards/item support it, and what removes its weakness?

### Balance budgets

- Cost 0: only created cards, priest scrolls, rare reactions, or explicitly approved exceptions.
  Normal cards cost at least 1.
- Cost 1: one solid effect, or two small ones.
- Cost 2: payoff/area/power; should need setup for high value.
- Cost 3+: signature/legendary; needs a clear deck constraint.
- Basic cards: only standard attack/defense/movement; no rare engine.
- Neutral cards: simple, useful to all, no class-only resource.
- Tier 1: common, simple; Tier 2: conditional/utility; Tier 3: powers/area/payoff; Tier 4: build-defining.

### Alternative use is an exception

Do **not** add `alt` by default. Alternative use is a designed feature and must be
approved during the card audit. Current allowed alt cards are listed in
`docs/card_balance.md`; if a generator reruns, finish with
`python tools/card_balance_policy.py` to re-apply the policy.

Every new card needs an audit with the user first: role, unique effect, cost,
rarity, tags, interactions, alt decision, five epiphany options, and impact on
starter/reward pools. Do not batch-add cards without that audit.

## CZN porting rules

Use `data/czn/cards.json` as the source of truth. Every adapted card keeps:

```json
"source": {
  "game": "CZN",
  "character": "Tressa",
  "name": "Vital Attack",
  "effect": "80% Damage x 3; if Agony +50%"
}
```

Map CZN resources to existing game resources instead of duplicating them:

- Shadow Dagger → temporary arrows or a temporary token.
- Agony → bleeding or poison.
- Retain/Exhaust → existing `retain` / `exhaust`.
- Push/collision → existing `push`/`collide`.
- Draw/energy/AP → `draw` / `energy`.
- Bullet/Futility/Rhythm/Archetype/Decibel → **do not fake**; first add a real engine mechanic or leave the card catalogued.

Keep the source effect text in the catalog even when the playable version is approximate.

## Technical workflow

- Add cards through a tool under `tools/`, not by hand-editing thousands of JSON lines.
- Use the existing helper patterns (`op`, `shot`, `me`, `V`, `add_new`).
- Give each card a unique `ill` tuple and 5 growth options.
- Set `category`, `rarity`, and optional `owner`; then add the card to the correct reward pool. Neutral cards go in `data["cards"]["neutral"]`.
- If the card is a basic, set `basic_role` and add it to the hero's `basic` map.
- Run generators in this order:

```text
python tools/descent_builds.py
python tools/descent_czn_pack.py       # if CZN cards changed
python tools/descent_hunter_more.py
python tools/descent_hunter_damage.py
python tools/descent_hunter_ranger.py   # CZN Ranger/Hunter pack
python tools/descent_merc_more.py       # Mercenary: standstill + collision
python tools/descent_merc_hunter_more.py # extra Mercenary/Hunter cards
python tools/descent_items.py
python tools/descent_tiers.py          # preserves CZN source cards
python tools/card_balance_policy.py    # always last: cost/alt policy
```

- Update docs (`docs/descent_damage_model.md`, `docs/descent_builds.md`, `docs/czn_cards.md`).
- Run focused tests, then the full suite. Add tests for:
  - card playability and text;
  - buff/debuff interaction;
  - reward pool / tier / basic / neutral rules;
  - no duplicate art IDs.

## Avoid

- Adding cards that are only “damage + bigger damage” without a setup/role.
- Adding a new tag for one card.
- Giving permanent strength to every cheap attack without a cost or condition.
- Making area damage strictly better than single-target; area should pay with lower damage/range or position.
- Copying CZN AP/Ego/Bullet systems in name only. Either implement the mechanic or keep it in the catalog.
