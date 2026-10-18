# FashionRise

FashionRise is a **tablet-first fashion creation PWA** with a **React / TypeScript** frontend and a **FastAPI / PostgreSQL** backend.

| | |
|--|--|
| **Handoff / what to do next** | [`docs/00-PROJECT-STATUS.md`](docs/00-PROJECT-STATUS.md) |
| **Doc index** | [`docs/README.md`](docs/README.md) |
| **Active frontend** | [`web-ui/`](web-ui/) — Vite + React + PWA Creator Studio |
| **Backend** | [`backend/`](backend/) — FastAPI + PostgreSQL |
| **Legacy client** | [`FashionRise/`](FashionRise/) — Unity project retained as historical reference only |
| **Remote** | [github.com/perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise) (`main`) |

## Quick start

### Backend

```bash
cd backend
cp .env.example .env   # edit secrets / DB URL
# create venv, install requirements, alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

See [`backend/README.md`](backend/README.md).

### Frontend (active)

```bash
cd web-ui
cp .env.example .env   # VITE_API_BASE_URL=http://127.0.0.1:8001/api/v1
npm install
npm run dev
```

Open the Vite URL → **Login** → **Creator Studio** (`/studio`).

### Product flow (WEB-1)

```text
APP START → LOGIN → CREATOR STUDIO
```

No Atelier / Home / Gallery dashboard gate after auth.

## Repository map

```text
FashionRise/
├── backend/                 # FastAPI + PostgreSQL (active)
├── web-ui/                  # React/TS PWA (active client)
├── FashionRise/             # LEGACY Unity client (do not extend for product UI)
├── deploy/                  # Production ops scripts
├── docs/                    # Living documentation
└── README.md
```

Do not commit `backend/.env`, `web-ui/.env`, or Unity `Library/`.

**Active development note (2026-10-18):** Frontend work moved from Unity to `web-ui/`. Unity draft PR #8 is superseded for active client work and must not be merged as the product path. Unity sources remain in-tree until the operator approves the web Studio.
