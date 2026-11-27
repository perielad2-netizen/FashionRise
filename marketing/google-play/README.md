# FashionRise — Google Play Store Listing Assets

Prepared for Google Play Console default store listing.  
**Scope:** branding assets + listing copy verification only. No app code, launcher icons, billing, or production config were changed. Nothing was submitted to Google Play.

---

## Package contents

| File | Dimensions | Size | Role |
|------|------------|------|------|
| `fashionrise-app-icon.png` | **512 × 512** | ~312 KB (≤ 1 MB) | Google Play high-res application icon |
| `fashionrise-feature-graphic.png` | **1024 × 500** | ~285 KB (≤ 15 MB) | Google Play feature graphic |
| `fashionrise-logo-transparent.png` | ~1031 × 1048 | ~1.2 MB | Transparent wordmark/logo export |
| `fashionrise-icon-1024.png` | **1024 × 1024** | ~724 KB | High-res square brand icon |
| `fashionrise-google-play-assets.zip` | — | (bundle) | Downloadable package of the above + this README |
| `README.md` | — | — | This document |

### Not included (intentional)

| Asset | Reason |
|-------|--------|
| `fashionrise-logo.svg` | **No genuine FashionRise vector logo** exists in the repository. `web-ui/public/favicon.svg` is unrelated. A vector was **not fabricated**. |
| Phone / tablet screenshots | Per brief: capture from the running Android app. Recommendations below. |

---

## Source assets used

| Source path | Use |
|-------------|-----|
| `web-ui/public/icons/icon-512.png` | Primary Play **512** icon (full-square dark canvas, official shipped mark) |
| `web-ui/public/branding/fashion_rise_mark.png` | Mark for **1024** icon composite + feature graphic |
| `web-ui/public/branding/fashion_rise_logo.png` | Transparent logo export |
| `web-ui/branding-src/fashion_rise_app_icon_1024.png` | Inspected; light letterbox corners — **not** used as Play canvas |
| `web-ui/public/assets/ui/home/hero-look-01.jpg` | Feature graphic fashion hero (owned home marketing art; “AI Look” chip cropped out) |
| `web-ui/public/assets/ui/home/hero-sketch-01.jpg` | Feature graphic sketch vignette (owned; UI chrome cropped out) |
| Android `ic_launcher_background` `#1C1030` | Adaptive icon background color |
| `web-ui/src/shell/shellTokens.css` | Brand pink `#d63384`, navy, Playfair Display / DM Sans |

Also inspected (not required for Play upload): Android adaptive icons under `web-ui/android/app/src/main/res/mipmap-*`, web PWA icons under `web-ui/public/icons/`, emblems/login art under `web-ui/public/branding/`.

---

## Branding decisions

1. **App icon** — Full opaque square on `#1C1030` (same as Android adaptive background). Official FashionRise “R” mark. **No** external rounded corners or drop shadows (Play applies its own mask). Corners validated as solid `#1C1030`.
2. **Feature graphic** — Opaque RGB navy panel + owned fashion hero + sketch vignette; copy: **FashionRise** / **AI Fashion Design Studio** / **Imagine. Design. Create.** Typography aligned with shell (Playfair + DM Sans / Noto Bold fallback). Safe margins from edges. No Play badges, pricing, or fake UI chrome.
3. **Logo transparency** — Direct export/trim of `fashion_rise_logo.png`; proportions preserved.
4. **No redesigned logo** — Existing mark reused; no new brand identity.

---

## Google Play upload instructions

1. Open **Play Console → Your app → Grow → Store presence → Main store listing** (wording may vary slightly by Console version).
2. **App icon:** upload `fashionrise-app-icon.png` (512 × 512 PNG, ≤ 1 MB).
3. **Feature graphic:** upload `fashionrise-feature-graphic.png` (1024 × 500 PNG, ≤ 15 MB).
4. Add **phone screenshots** (and tablet if you target tablets) captured from the live Android build — see recommended frames below.
5. Paste **short** and **full** descriptions from this README (verified against current native flags).
6. Set **Website** `https://fashionrise.app`, **Email** `Fashionriseapp@gmail.com`, **Privacy policy** `https://fashionrise.app/privacy`.
7. Do **not** replace in-app adaptive launcher resources with these files unless you intentionally ship a new icon build later — this package is for **store listing** only.

---

## Contact & policy (from project config — not invented)

| Field | Value | Source |
|-------|--------|--------|
| Support email | `Fashionriseapp@gmail.com` | `web-ui/src/lib/contact.ts` (`CONTACT_EMAIL`) |
| Website | `https://fashionrise.app` | `VITE_PUBLIC_APP_URL` in `.env.native` / `.env.production` |
| Privacy policy | `https://fashionrise.app/privacy` | Public route `/privacy` (`PrivacyPolicyPage`); Android App Links for `fashionrise.app/privacy` |

---

## Verified application functionality (Android / native shell)

Gates from `web-ui/.env.native` and shipped UI modules:

| Feature | Status | Notes |
|---------|--------|-------|
| Fashion Studio (Create / drawing canvas) | **Available** | Core studio; front/back when `VITE_STUDIO_FRONT_BACK_ENABLED=true` |
| Digital drawing tools / brushes | **Available** | Brush sizes, fill, eraser, color & materials tools |
| Photoshop-style multi-layer stack | **Partial / not as claimed** | Front/back sides + fill/fabric layers exist; do **not** market as full multi-layer PSD editor |
| My Croquis / Create Model | **Available** | `VITE_MY_CROQUIS_UI_ENABLED=true` |
| AI fashion design generation (Magic) | **Available** | `VITE_MAGIC_UI_ENABLED=true`; dual Magic on |
| AI fashion model creation | **Available** | Create Model / My Croquis AI generate flow |
| Virtual Try-On (Fitting Room) | **Available** | `VITE_FITTING_ROOM_UI_ENABLED=true` |
| Fabric / textile design | **Available** | Color & materials / fabric tools; AI fabric incurs Stars |
| Technical PDF (Tech Pack) | **Available** | Studio techpack path + PDF generation (Stars-costed) |
| Runway | **Available** | Nav destination `runway` |
| FashionRise social / discover feed | **Available** | Nav “FashionRise” destination |
| Stars credit system (balance + spend) | **Available** | Wallet used for Magic / Model / Fabric / PDF |
| Stars **purchase on Google Play** | **Not production-ready** | Shop copy: “Google Play Stars purchasing is not available yet.” IAP adapter notes Android purchasing gated; iOS StoreKit path exists separately |
| New email registration UI | **Off on native** | `VITE_REGISTRATION_UI_ENABLED=false` — listing should not promise open self-serve signup inside the Android app unless that gate changes |

---

## Recommended store listing descriptions

### Short description (≤ 80 characters)

```text
AI fashion studio: sketch, Magic looks, models, try-on, fabrics & tech packs.
```

Character count: **78**.

### Full description (≤ 4,000 characters)

```text
FashionRise is an AI fashion design studio for creating looks from sketch to polished presentation.

Design in Studio
Sketch garments with digital brushes, color, and fabric tools. Work front and back views as you refine a design.

AI Magic looks
Turn sketches into fashion looks with AI generation. Use Stars from your balance when AI features are enabled for your account.

Create Model (My Croquis)
Upload an eligible adult fashion pose reference to generate a private model underlay for Studio (subject to consent and policy notices in-app).

Fitting Room
Virtually try designs on your models with the Fitting Room experience.

Fabrics & materials
Explore textile and color tools to style garments — including AI-assisted fabric options when available.

Tech packs
Build technical documentation and export PDFs for production-ready communication.

Runway & FashionRise
Browse Runway and the FashionRise feed to explore published looks and social discovery features available in the app.

Stars
Stars power AI features (Magic, model creation, fabric, and PDF). Your balance is shown in-app. Purchasing Stars on Google Play is not available yet; existing balances still apply where features are enabled.

FashionRise is built for designers who want to imagine, design, and create — from first sketch to shareable look.

Support: Fashionriseapp@gmail.com
Web: https://fashionrise.app
Privacy: https://fashionrise.app/privacy
```

---

## Recommended screenshots (capture yourself — 6 strongest)

Do **not** use mockups. Capture from the signed-in Android app:

1. **Studio canvas** — croquis + garment sketch with brush/toolbar visible (core product).
2. **Magic results** — AI-generated look after Magic (shows AI value).
3. **Create Model / My Croquis** — model library or create flow (differentiator).
4. **Fitting Room** — try-on result with design + model.
5. **Runway or FashionRise feed** — social/discovery surface with real looks.
6. **Tech pack editor or Color & materials / fabric panel** — production or textile depth (pick whichever looks strongest on device).

Avoid screens that imply Google Play Stars checkout, open public registration, or unfinished surfaces.

---

## Validation (programmatic)

Run from repo root:

```bash
python3 marketing/google-play/validate_assets.py
```

Expected: exit code `0`, all mandatory dims/sizes pass.

---

## Outstanding issues / limitations

1. **No official SVG logo** in repo — PNG mark/logo only.
2. **Android Stars IAP** not ready — do not claim in-app Google Play purchases.
3. **Registration UI** disabled in native env — wording above avoids promising Create Account inside Android.
4. **Screenshots** still needed from device/emulator.
5. `branding-src/fashion_rise_app_icon_1024.png` has light corners — unsuitable as Play full-bleed icon; shipped `icon-512.png` / mark-on-`#1C1030` used instead.
6. Feature graphic uses owned home hero art with marketing chips cropped; if legal prefers zero photo models, regenerate with mark-only composition.

---

## Safety checklist

- [x] No application functionality changes  
- [x] No Android launcher resource edits  
- [x] No auth / billing / Stars / production config changes  
- [x] No deploy / Play submission  
- [x] No credentials exposed  
- [x] Assets only under `marketing/google-play/`  
