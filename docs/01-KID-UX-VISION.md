# FashionRise — product vision & next build slices

**Updated:** 2026-09-14

## What just shipped (Magic look in-app)

Magic already generates a sketch-faithful look on the server. The gap was **Unity aborting the poll** on a transient HTTP error (`An error occurred while sending the request`) so **Your look** never opened — even though the PNG was ready (browser URL worked).

Fixes in this branch:
- Resilient job polling (retry transient HTTP / timeouts during the ~1 min image edit)
- `image_url` plumbed into session + **Your look** `RawImage` preview
- Longer HTTP client timeout (180s) + GET retries for flaky Unity `HttpClient`
- Store polish **job id as soon as the job starts** so recovery still works after a poll failure
- Always-visible **See last result** on Magic (opens Your look / refreshes `image_url`)
- Backend `images.edit` path + storage URL fix (no double `uploads/`)

## Kid / game-like UI — not in this PR

**No full visual redesign has shipped yet.** Magic / Home / Sketch still use the same flat utility chrome on purpose: image display had to work first. If the app “looks the same,” that’s expected until Layer 1 below.

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

## How to verify Your look shows the image
1. Pull / merge branch `cursor/magic-look-image-display-77c6` into the Unity tree you Play-mode from
2. Let scripts recompile; confirm Magic shows **See last result** (always visible, not only under More)
3. Restart API on 8001 from `backend/`
4. Run Magic once; after ~1 min you should land on **Your look** with the PNG
5. If Magic still shows a red HTTP error but the server log has `stored look image`, tap **See last result**

## Suggested next session order
1. Confirm Your look shows Magic image after pull / Unity recompile
2. Kid chrome pass on Home → Sketch → Magic → Your look (visual + motion)
3. Color / fabric tray on sketch or result
4. Accessory stickers
5. Share polish

## Sync note
Local Windows work (kid sketch poses, “More options…”, etc.) may be ahead of or divergent from GitHub. After this PR lands, **commit & push local changes** so Cloud Agents stay on the same tree. If your Magic button still says **More options…** instead of **More AI tools…** / **See last result**, you are not running this branch’s scripts.
