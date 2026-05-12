# FashionRise

Fashion sketch & design app: **Unity** client (Windows + Android) + **FastAPI** backend + **PostgreSQL**.

| | |
|--|--|
| **Handoff / what to do next** | [`docs/00-PROJECT-STATUS.md`](docs/00-PROJECT-STATUS.md) — start with *When you open Cursor next* |
| **Doc index** | [`docs/README.md`](docs/README.md) |
| **Unity** | Open the project in [`FashionRise/`](FashionRise/) — details in [`FashionRise/Assets/FashionRise/README_Unity.md`](FashionRise/Assets/FashionRise/README_Unity.md) |
| **Backend** | [`backend/README.md`](backend/README.md) |
| **Remote** | [github.com/perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise) (`main`) |

```bash
git clone https://github.com/perielad2-netizen/FashionRise.git
cd FashionRise/backend && cp .env.example .env   # then edit .env
```

Do not commit `backend/.env` or Unity `Library/`.

**Changelog (root):** 2026-05-12 — **iOS** sketch import: Photos → `Imports` (see `FashionRise/Assets/Plugins/iOS/FashionRiseGalleryPickBridge.mm`, `IOSGalleryPick.cs`, `docs/00-PROJECT-STATUS.md`). 2026-05-11 — documentation session pause: see **`docs/00-PROJECT-STATUS.md`** (*Session pause — where we stopped*) for the next-session checklist; migration recovery notes in **`backend/README.md`**.
