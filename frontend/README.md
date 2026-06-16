# Flowforge — Async Workflow Engine console

A polished Next.js 14 dashboard for the [async workflow engine](../) FastAPI
backend. It is the orchestration console: list and inspect runs, visualize each
run's DAG, trigger workflows from YAML, retry dead letters, and manage cron
schedules.

## Stack

- **Next.js 14** (App Router) + **React 18** + **TypeScript**
- **Tailwind CSS** for styling, **lucide-react** for icons
- **recharts** for the run-status summary chart
- **Vitest** + **@testing-library/react** + **jsdom** for component tests
- **Playwright** for the E2E smoke spec

## Getting started

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

By default the UI talks to the backend at `http://localhost:8000`. Start the
backend separately (from the repo root):

```bash
uvicorn workflow_engine.main:app --reload   # or: make run
```

## Demo mode (no backend required)

The dashboard is **showcase-ready offline**. Every data view first tries the live
API and, on a network failure (backend unreachable), transparently falls back to
a bundled mock-data module (`src/lib/mockData.ts`). When that happens a visible
**"Demo mode"** banner appears at the top of the app.

This means you can explore the entire UI — run list, DAG visualizer,
dead-letter queue, schedules — with **no backend running**. Mutating actions
(validate / trigger / rerun / create schedule) detect demo mode and show an
explanatory message instead of failing, since they require a real backend.

Real HTTP errors (4xx/5xx from a reachable backend) are surfaced to the user as
error states rather than triggering the demo fallback.

## Environment variables

| Variable              | Default                 | Purpose                          |
| --------------------- | ----------------------- | -------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |

Copy `.env.example` to `.env.local` to override.

## Pages

| Route             | Description                                                                 | Backend endpoints                                                                 |
| ----------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `/`               | Landing / feature overview.                                                 | —                                                                                 |
| `/runs`           | Run list with status badges + a recharts status-summary pie.                | `GET /workflows`                                                                  |
| `/runs/[id]`      | Run detail: visual DAG, per-step status, results/errors, dead letters, rerun. | `GET /workflows/{id}`, `GET /workflows/{id}/dag`, `POST /workflows/{id}/rerun`    |
| `/trigger`        | Paste YAML → validate → dispatch sync or async.                             | `POST /workflows/validate`, `POST /workflows/run`                                 |
| `/dead-letters`   | Dead-letter queue table with per-row rerun.                                 | `GET /workflows/dead-letters`, `POST /workflows/{id}/rerun`                       |
| `/schedules`      | Cron schedules list + create/delete form.                                   | `GET /schedules`, `POST /schedules`, `DELETE /schedules/{name}`                   |

## Scripts

```bash
npm run dev          # dev server
npm run build        # production build
npm start            # serve the production build
npm test             # vitest run (component + api tests, no backend needed)
npm run test:e2e     # playwright smoke spec (drives the demo-mode UI)
```

## Tests

- **Component / unit tests** (`tests/`) render components against the bundled
  mock data and assert content; they pass with **no backend**.
- **E2E smoke spec** (`e2e/smoke.spec.ts`) navigates the demo-mode UI end to end.

## Docker

A `web` service is wired into the repo-root `docker-compose.yml`:

```bash
docker compose up web
```
