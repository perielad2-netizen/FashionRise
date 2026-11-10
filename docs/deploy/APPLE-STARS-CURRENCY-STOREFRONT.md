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

## Likely explanation (pending storefront metadata confirmation)

The **most likely** cause is an Apple **Sandbox storefront split**:

1. StoreKit localizes `displayPrice` to the **active storefront for the product query** (often the device / prior App Store region) → USD in the shop list.
2. The system payment sheet localizes to the **Sandbox Apple ID’s App Store country** → ILS when that tester account is Israel.

Treat this as a **likely explanation until confirmed** with actual storefront / `currencyCode` metadata from the device (Capgo exposes `currencyCode` on `StarsIapProduct` for QA) and the Sandbox Apple ID country setting. It is not FashionRise inventing USD.

## Verification (no new purchase required)

1. On the TF device: Settings → App Store → Sandbox Account country/region.
2. In ASC: each of `stars_50` / `stars_150` / `stars_500` has an **Israel** price point (ILS).
3. Optional QA: log Capgo `currencyCode` alongside `priceString` after `getProducts`.
4. Production expectation: a customer’s single App Store country drives **both** list and sheet → they match (ILS in Israel, USD in US, etc.).

## Resolution

- **No application price rewrite.** Keep StoreKit `displayPrice`.
- Reduce Sandbox confusion by aligning Sandbox Apple ID country with the region under test, and confirming ASC Israel availability.
- Ship a TF build with the real AppIcon so the sheet is trustworthy during currency QA.
