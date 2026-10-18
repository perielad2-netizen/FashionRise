# FashionRise `web-ui` (active client)

Tablet-first React / TypeScript PWA for FashionRise Creator Studio.

## Stack

- Vite + React + TypeScript
- React Router
- Konva / react-konva + perfect-freehand
- CSS modules + design tokens
- vite-plugin-pwa
- Vitest + Testing Library

## Quick start

```bash
cd web-ui
cp .env.example .env
npm install
npm run dev
```

Open `http://127.0.0.1:5173` — signed-out users land on `/login`, then `/studio`.

Backend must be reachable at `VITE_API_BASE_URL` (default `http://127.0.0.1:8001/api/v1`).

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Local Vite server |
| `npm test` | Vitest |
| `npm run build` | Production build |
| `npm run lint` | oxlint |
| `npm run preview` | Preview production build |

## PWA install (operator)

1. Run `npm run build && npm run preview` (or deploy the `dist/` build).
2. In Chrome/Edge: open the app → install icon in the address bar / App available.
3. Installed FashionRise launches in **standalone** mode (no browser chrome).

Do **not** rely on browser hacks to hide the address bar in a normal tab.

## WEB-1 scope

Login → Creator Studio only. Magic is a visual CTA with a “coming next milestone” notice (no OpenAI calls).
