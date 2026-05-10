# FashionRise Unity — screen flow (V1)

```mermaid
flowchart LR
  Splash --> Welcome
  Welcome --> LoginChoice
  LoginChoice --> HomeDashboard
  HomeDashboard --> CreateDesign
  HomeDashboard --> Gallery
  HomeDashboard --> Profile
  HomeDashboard --> Settings
  CreateDesign --> MaterialSelection
  CreateDesign --> ModelPreview
  MaterialSelection -->|Back| CreateDesign
  ModelPreview -->|Back| CreateDesign
  Gallery --> DesignDetail
```

## Payloads

- **DesignDetail**: `DesignDetailNavContext` with `GalleryItemId`.

## History

- `NavigationService` keeps a **stack** for `GoBackAsync`. Splash is never pushed.
- `[V2_READY]` modal overlays and tabbed home without losing stack discipline.
