# FashionRise — Living documentation

This folder is the **single source of truth** for FashionRise architecture and planning. Update these files as the product and codebase evolve.

## How to use

- **Starting a new chat or sprint:** open **[00 — Project status & handoff](./00-PROJECT-STATUS.md)** — use the section **“When you open Cursor next”** — then [Implementation phases](./06-implementation-phases.md) for checkboxes.
- **Before major changes**: skim [Architecture overview](./01-architecture-overview.md) and the relevant topic doc.
- **When adding features**: extend [API](./05-api.md), [Database](./04-database.md), and phases in [Implementation plan](./06-implementation-phases.md).
- **When restructuring code**: update [Unity client](./02-unity-client.md) or [Backend](./03-backend.md) to match reality.
- **After each finished step:** update **`00-PROJECT-STATUS.md`** (last updated, milestones, next steps if needed) and **`06-implementation-phases.md`** when a phase item moves; add a row to the revision log below when doc content changes materially.

## Document index

| Doc | Contents |
|-----|----------|
| [**00 — Project status & handoff**](./00-PROJECT-STATUS.md) | Current phase, repo map, config cheatsheet, suggested next steps |
| [01 — Architecture overview](./01-architecture-overview.md) | System context, principles, diagrams |
| [02 — Unity client](./02-unity-client.md) | Folders, systems, design rules |
| [03 — Backend](./03-backend.md) | FastAPI layout, modules, deployment notes |
| [04 — Database](./04-database.md) | PostgreSQL tables, fields, constraints |
| [05 — API](./05-api.md) | REST endpoints, versioning |
| [06 — Implementation phases](./06-implementation-phases.md) | Phase plan, status checklist |
| [Unity — architecture notes](./unity-architecture-notes.md) | Client layers, rules, extension points |
| [Unity — screen flow](./unity-screen-flow.md) | Navigation diagram + payloads |
| [Unity — services](./unity-services.md) | Interface ↔ mock ↔ API map |
| [Unity — backend integration](./unity-backend-integration.md) | How to swap in REST |
| [Deployment (production)](../deploy/README_DEPLOYMENT.md) | Ubuntu, systemd, Nginx, Postgres, scripts |

**Unity source tree:** `FashionRise/Assets/FashionRise/` — see `README_Unity.md` in that folder.

## Project identity

- **Name**: FashionRise  
- **Remote**: [github.com/perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise) (`main`).  
- **Product**: Premium fashion design app — sketch capture, garments, materials, gallery, export, ratings; AI and maker handoff later.  
- **Clients**: Unity (URP); **v1 ship targets:** Windows PC + **Android**; iOS/iPad later.  
- **Backend**: FastAPI, PostgreSQL, JWT, Nginx on Ubuntu; local storage first, S3-compatible later.

## Revision log

| Date | Author | Summary |
|------|--------|---------|
| 2026-05-10 | — | Initial docs from architecture plan |
| 2026-05-10 | — | Unity V1 foundation: mocks, navigation, screens, API stubs; Unity docs split out |
| 2026-05-10 | — | Unity V1 code landed under `FashionRise/Assets/FashionRise/`; docs paths + Phase 0 checklist aligned |
| 2026-05-10 | — | Handoff workflow: `00-PROJECT-STATUS.md`; README index + deploy link; API/backend/Unity docs aligned with implemented routes and client stack |
| 2026-05-10 | — | Prompt 6 / V2: `05-api`, `06` Phase 5b, `unity-services`, handoff status — sketch routes, gallery social, Unity sketch stack |
| 2026-05-10 | — | Handoff refresh: GitHub link, **“When you open Cursor next”** in `00-PROJECT-STATUS`; API-first Unity; repo map + identity updated |
| 2026-05-11 | — | Docs sweep: Pillar B progress (`00`, `06`), gallery + profiles API (`05`), Unity integration + services + screen payloads + client index (`unity-*`, `02`); rate limits marked done in phases |
| 2026-05-11 | — | `GalleryNavContext.CommunitySort`, home **Following feed** + publish/home gallery explicit newest; `03` rate_limit note; `unity-screen-flow` Back semantics |
| 2026-05-12 | — | **iOS Photos import** for sketch `Imports`; `06` Pillar A import line; `00` handoff + changelog; `README_Unity` platforms + platform folder |
| 2026-05-11 | — | **Session pause:** `00` handoff (pause block + next steps); `06` Guided/Pro, reputation v1, handoff slice, CI note; `05-api` profiles + designs handoff/revisions; `03-backend` + `backend/README` migration recovery; `04` profile API note; `02` + `unity-backend-integration` alignment |

_Add a row for each meaningful doc update._
