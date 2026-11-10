# Stars shop currency: USD list vs ILS purchase sheet (Sandbox)

## Observation (C1 TestFlight)

- FashionRise Stars shop showed **USD** (`priceString` from Capgo/StoreKit).
- Apple’s system purchase confirmation sheet showed **ILS**.

## Code path (not a hardcode bug)

Capgo `@capgo/native-purchases` maps StoreKit 2:

| Capgo field | StoreKit source |
|---|---|
| `priceString` | `Product.displayPrice` |
| `currencyCode` | `Product.priceFormatStyle.currencyCode` |

FashionRise native shop renders **only** `priceString` (friendly pack title is FashionRise-owned; price is Apple-owned). There is **no** USD hardcode and **no** FX conversion in the iOS buy path.

## Root cause (environment-specific)

StoreKit localizes `displayPrice` to the **active storefront for product query**.  
The payment sheet localizes to the **Sandbox Apple ID’s App Store country**.

In Sandbox these often diverge:

1. Device / App Store storefront (or prior Production Apple ID region) → USD product query.
2. Sandbox tester Apple ID registered for **Israel** → ILS on the confirm sheet.

This is an Apple Sandbox storefront split, not FashionRise inventing USD.

## Verification (no new purchase required)

1. On the TF device: Settings → App Store → Sandbox Account country/region.
2. In ASC: each of `stars_50` / `stars_150` / `stars_500` has an **Israel** price point (ILS).
3. Optional QA log: Capgo `currencyCode` alongside `priceString` after `getProducts` (exposed on `StarsIapProduct.currencyCode` for diagnostics).
4. Production expectation: customer’s single App Store country drives **both** list and sheet → they match (ILS in Israel, USD in US, etc.).

## Resolution

- **No application price rewrite.** Keep StoreKit `displayPrice`.
- Fix Sandbox confusion by aligning Sandbox Apple ID country with the device region under test, and confirming ASC Israel availability.
- Ship real AppIcon (separate issue) so the sheet is trustworthy during currency QA.
