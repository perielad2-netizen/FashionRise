# FashionRise social accounts (share promo)

The in-app **Share FashionRise** sheet promotes `https://fashionrise.app` and mentions `@fashionrise` on Instagram. Create the brand accounts below so those links and captions land on real profiles.

## Recommended handles (claim early)

| Channel | Suggested handle | Why |
|---------|------------------|-----|
| Instagram | `@fashionrise` (fallback `@fashionrise.app`) | Feed + Stories; designers paste the copied caption + saved look image |
| TikTok | `@fashionrise` | Short process videos (sketch → Magic look) |
| WhatsApp | Business profile / Channel named **FashionRise** | In-app share already opens WhatsApp with promo text; a Business profile builds trust |
| Pinterest | `fashionrise` | Look mood boards |
| X (Twitter) | `@fashionrise` | Optional launch updates |

If a handle is taken, pick the closest available and set the Vite env vars below so captions stay correct.

## Env (frontend build)

```bash
VITE_PUBLIC_APP_URL=https://fashionrise.app
VITE_SOCIAL_INSTAGRAM=fashionrise
VITE_SOCIAL_TIKTOK=fashionrise
```

Rebuild/publish the FE after changing these.

## What the product can / cannot do

| Channel | In-app behavior |
|---------|-----------------|
| **WhatsApp** | Opens `wa.me` with FashionRise promo caption prefilled |
| **Device share** | OS sheet (phone/tablet) — user can pick Instagram, Messages, Mail, etc., and attach the look image when supported |
| **Instagram** | No public “post for me” web API. We **copy the promo caption**, **save the look image** when available, and open the Instagram profile. User pastes into Stories / New post |
| **Copy caption / link** | Clipboard fallback for any network |

## Account setup checklist

1. Create an **Instagram Professional / Business** account with brand avatar (FashionRise mark) and bio linking to `https://fashionrise.app`.
2. Create **WhatsApp Business** (same brand phone or Meta Business Suite) — optional Channel for announcements.
3. Create **TikTok Business** with the same handle if available.
4. Update `VITE_SOCIAL_*` if the live handle differs from `fashionrise`.
5. Pin a launch Story/highlight: “Design in FashionRise — Dream · Sketch · Create”.

## Privacy note

Looks stay private in FashionRise. Sharing is **user-initiated** (image + promo text + app URL). There is no public gallery permalink yet.
