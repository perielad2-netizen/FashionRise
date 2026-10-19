# WEB-V1 visual QA — `/_design/studio`

**Date:** 2026-10-19  
**Branch:** `cursor/web-ui-reboot`  
**Route:** DEV-only `/_design/studio`  
**Primary target:** approved FashionRise Creator Studio mockup @ ~1536×1024

## Screenshot paths

| Viewport | Path |
|----------|------|
| 1536×1024 (primary) | `/opt/cursor/artifacts/screenshots/design-lab-1536x1024.png` |
| 1440×900 | `/opt/cursor/artifacts/screenshots/design-lab-1440x900.png` |
| 1024×768 tablet landscape | `/opt/cursor/artifacts/screenshots/design-lab-1024x768.png` |
| 768×1024 tablet portrait | `/opt/cursor/artifacts/screenshots/design-lab-768x1024.png` |
| 390×844 mobile | `/opt/cursor/artifacts/screenshots/design-lab-390x844.png` |
| Side-by-side vs mock | `/opt/cursor/artifacts/screenshots/webv1-vs-mock-1536x1024.png` |

## Discrepancy report (1536×1024 vs approved mock)

| Mockup area | Status | Notes |
|-------------|--------|-------|
| Global header (brand + tagline + My Studio + settings) | **Matched** | Playfair wordmark, pink FR mark, Dream + Sketch + Create, avatar / My Studio / gear. Prototype strip sits above the shell (not over brand). |
| Global left navigation | **Matched** | Home / Create (active pink) / Design Book / Discover / My Looks; bottom branding panel present. |
| Nav branding photo | **Partially matched** | Uses licensed-in-repo croquis fade, not the mock’s photographic fashion figure. |
| Workspace header | **Matched** | Back, New Design, Auto Save chrome, Undo/Redo, Magic, more menu. |
| Models panel chrome | **Matched** | Models / My Gallery tabs; All / Female / Male filters; pink selected card. |
| Model thumbnails | **Partially matched** | Only Female/Male production croquis are real selectable content. Extra cells are labeled **Placeholder**. No photographic editorial catalog in-repo. |
| Cream canvas + rim/shadow | **Matched** | Large cream paper plane with soft rim/shadow; croquis centered. |
| Finished fashion sketch (hat/dress) | **Not matched** | Licensed finished sketch artwork from the mock is unavailable. Dashed silhouette hint only. |
| Floating tool rail | **Matched** | Vertical dark rail; pencil active; Lucide line icons (not 3D glyphs). |
| Floating brush panel | **Matched** | Pencil size 2px / opacity 100% card. |
| Zoom controls | **Matched** | Bottom-right canvas controls. |
| Colors / hue / hex / swatches | **Matched** | Large picker, hue bar, swatches, `#D63384`, eyedropper chrome. |
| Fabrics & Textures | **Partially matched** | Visual gradient tiles only — not photographic fabric samples. Explicit prototype note in UI. |
| Gradients | **Matched** | Four preset tiles (visual only). |
| Layers | **Matched** | Hat / Sketch (active) / Design Notes / Background + eye/lock/delete chrome. Visual only. |
| Settings inspector | **Matched** | Settings/Help, canvas size, background, grid, brush, pressure, shortcuts, Generate with AI chrome. |
| Generate with AI / Magic | **Matched (chrome only)** | Buttons are non-functional; lab copy states no paid AI. |
| Overall proportions / depth | **Partially matched** | Strong wide-layout resemblance; denser prototype notes and placeholder badges reduce editorial polish vs mock. |

## Missing artwork / blockers

1. **Photographic model catalog** with confirmed usage rights (mock uses editorial photos).
2. **Finished pencil sketch** of hat + structural dress (mock canvas hero).
3. **Photographic fabric swatches** (optional; gradients currently stand in).
4. **Nav bottom fashion photograph** (optional; croquis fade used).

## Responsive behavior

- **1024×768:** Icon-narrow nav; materials/settings move behind dock chips; canvas prioritized.
- **768×1024 / 390×844:** Nav drawer; Models/Materials/Settings docks; horizontal tool rail; no multi-column squeeze; no horizontal overflow observed in captures.

## Production Studio

- `/studio` route and pointer/auth/drawing behavior **unchanged**.
- `/_design/studio` gated by `import.meta.env.DEV` + lazy import; absent from production bundle strings.

## Verdict

**Strong overall resemblance at wide layout for shell, chrome, and panel composition.** Not visual-acceptance complete until photographic models + finished sketch assets are available or explicitly waived. **STOP for PM visual review** — no WEB-V2 / shell integration / deploy.
