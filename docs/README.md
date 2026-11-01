# FashionRise — Living documentation

This folder is the **single source of truth** for FashionRise architecture and planning.

## How to use

- **Starting a new chat or sprint:** open **[00 — Project status & handoff](./00-PROJECT-STATUS.md)** first.
- **Active client:** React/TypeScript PWA in `web-ui/` — **not** Unity.
- **Backend:** FastAPI + PostgreSQL — [03 — Backend](./03-backend.md), [05 — API](./05-api.md).
- Unity docs below are **LEGACY** reference only.

## Document index

| Doc | Contents | Status |
|-----|----------|--------|
| [**00 — Project status & handoff**](./00-PROJECT-STATUS.md) | Current phase, repo map, next steps | **ACTIVE** |
| [01 — Architecture overview](./01-architecture-overview.md) | System context | **ACTIVE** (web-first) |
| [02 — Unity client](./02-unity-client.md) | Unity folders/systems | **LEGACY** |
| [03 — Backend](./03-backend.md) | FastAPI layout | **ACTIVE** |
| [04 — Database](./04-database.md) | PostgreSQL | **ACTIVE** |
| [05 — API](./05-api.md) | REST endpoints | **ACTIVE** |
| [06 — Implementation phases](./06-implementation-phases.md) | Phase plan | **ACTIVE** |
| [OpenAI model migration](./OPENAI_MODEL_MIGRATION.md) | gpt-6-luna notes | ACTIVE (backend) |
| [Unity — architecture notes](./unity-architecture-notes.md) | Client layers | **LEGACY** |
| [Unity — screen flow](./unity-screen-flow.md) | Navigation | **LEGACY** |
| [Unity — services](./unity-services.md) | Interface map | **LEGACY** |
| [Unity — backend integration](./unity-backend-integration.md) | REST swap notes | **LEGACY** |
| [Deployment](../deploy/README_DEPLOYMENT.md) | Ubuntu/Nginx/Postgres | ACTIVE |

**Active frontend source:** `web-ui/`
**Legacy Unity tree:** `FashionRise/Assets/FashionRise/` (do not extend for product UI)

## Project identity

- **Name**: FashionRise
- **Remote**: [github.com/perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise) (`main`).
- **Product**: Premium fashion design app — sketch, gallery, AI pipeline, maker handoff.
- **Active clients**: Tablet-first **web PWA** (`web-ui/`); future optional Tauri packaging.
- **Legacy client**: Unity (Windows/Android) — archived reference.
- **Backend**: FastAPI, PostgreSQL, JWT, Nginx on Ubuntu.

## Revision log

| Date | Summary |
|------|---------|
| 2026-10-18 | Web/PWA pivot: `web-ui/` active; Unity docs marked LEGACY; handoff reset |
| 2026-05-10 … | Earlier Unity-era documentation history |

_Add a row for each meaningful doc update._
