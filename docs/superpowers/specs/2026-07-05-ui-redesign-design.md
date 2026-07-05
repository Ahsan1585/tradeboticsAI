# TradeBotics UI Redesign — Design Spec

## Goal

The current UI (dark "hedge-fund terminal" aesthetic — glassmorphic translucent
cards, blue/purple gradients, heavy glows) feels dated and generic/template-y.
Redesign to a bold trading/crypto consumer aesthetic (Robinhood/Coinbase
style) to drive more signups and feel like a premium, distinctive product.

## Scope

Whole app, one shared design system, rolled out in stages:

1. Design tokens + reusable components + light/dark theme toggle
2. Landing page (`frontend/app/page.tsx`) — highest leverage for new signups
3. Hub + Beginner mode (`frontend/app/hub`, `frontend/app/beginner`) — pages
   new/prospective users live in
4. Terminal + Portfolio + Vault + Track-record — lower urgency (power users
   are less swayed by aesthetics), highest effort (Terminal is ~1000 lines)

Each stage ships and is reviewable independently before the next starts.

## Design tokens

**Signature color:** blue (continuity with existing brand/logo), pushed to a
punchier, more saturated electric blue (`#2563eb` → `#3b82f6`-family, used as
confident solid fills) rather than soft gradients/glows.

**Surfaces:** flat, solid-color cards with crisp 1px borders and subtle
elevation (box-shadow), replacing the current `bg-slate-900/40` translucent
+ backdrop-blur panels. This is the primary "less generic template" shift.

**Typography:** keep Geist (already modern). Bolder/larger headline weights,
tighter tracking on headlines, more generous line-height in body copy.

**Buttons:** keep the rounded-full pill shape (already Robinhood-esque).
Solid fill, no heavy glow/shadow effects.

**Themes:**
- Dark (default): near-black background (`#0a0a0f`), solid dark-gray card
  surfaces (`#151823`-family), light text.
- Light: white/near-white background (`#fafafa`), white card surfaces with
  a subtle border/shadow, dark text.
- User-toggleable, preference persisted (localStorage), respects system
  `prefers-color-scheme` as the initial default.

**Semantic colors unchanged:** emerald for gains/BUY, red for losses/AVOID,
amber for WAIT/HOLD — these are already correct and not part of the
"dated" complaint.

## Components (built once, reused everywhere)

- `Button` — primary (solid blue fill), secondary (outline/ghost), sizes
- `Card` — flat surface with border, optional interactive/hover state
- `StatTile` — label + big value, used for confidence meters, track-record
  stats, balances
- `Badge` — verdict/status pills (BUY/HOLD/WAIT/AVOID, trial/pro status)
- `ThemeToggle` — sun/moon switch, persists to localStorage

Implemented as plain React components + Tailwind utility classes reading
CSS custom properties for theme values (no new UI library dependency).

## Rollout order and testing

Each stage: implement → `npm run build` (typecheck/compile check) → visual
check in a browser if available → move to next stage. No stage blocks the
others from proceeding — if Terminal's redesign takes longer, Landing/Hub/
Beginner already shipped their improved look independently.

## Out of scope

- No new UI library/dependency (stay on Tailwind + plain React, matching
  existing stack).
- No changes to backend/API contracts — this is purely presentational.
- No changes to the Beginner/Pro mode split itself (already decided
  separately) — this redesign reskins both, doesn't restructure them.
