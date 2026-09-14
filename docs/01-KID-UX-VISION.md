# FashionRise — product vision & next build slices

**Updated:** 2026-09-14

## What just shipped (Magic look in-app)

Magic already generates a sketch-faithful look on the server. The gap was **Unity aborting the poll** on a transient HTTP error (`An error occurred while sending the request`) so **Your look** never opened — even though the PNG was ready (browser URL worked).

Fixes in this branch:
- Resilient job polling (retry transient HTTP / timeouts during the ~1 min image edit)
- `image_url` plumbed into session + **Your look** `RawImage` preview
- Longer HTTP client timeout (180s)
- Backend `images.edit` path + storage URL fix (no double `uploads/`)

## Can we redesign the whole app to feel game-like for kids?

**Yes — that’s the product.** Do it in layers so Magic stays shippable while chrome gets fun.

### Layer 1 — Kid chrome (visual only, same flows)
- Soft pastel / paper-room backgrounds, big rounded CTAs, logo as hero
- Fewer words; emoji-free but playful motion (button squash, confetti on Magic done)
- Replace dense tool rows with **icon tiles** (Girl / Boy / Pose carousel)

### Layer 2 — Dress-up studio (interaction)
- Tap-to-paint colors on garment zones
- Fabric swatch tray (silk / denim / glitter) that recolors the look
- Accessory stickers (hats, bows, bags) as drag overlays on the sketch / Magic result
- Reuse existing materials / palettes APIs under a kid UI

### Layer 3 — Share & play loop
- One-tap Share with sticker frame
- Gallery “runway” for friends
- Later: short AI share video

### What we will *not* do in one pass
Full Unity UI rewrite + fabric physics + accessories + viral video in one PR. That would stall Magic.

## Suggested next session order
1. Confirm Your look shows Magic image after pull / Unity recompile
2. Kid chrome pass on Home → Sketch → Magic → Your look (visual + motion)
3. Color / fabric tray on sketch or result
4. Accessory stickers
5. Share polish

## Sync note
Local Windows work (kid sketch poses, etc.) may be ahead of GitHub. After this PR lands, **commit & push local changes** so Cloud Agents stay on the same tree.
