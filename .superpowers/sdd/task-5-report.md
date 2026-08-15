# Task 5 — Packaging, frontend, Docker, and CI report

## Delivered

- Expanded GitHub Actions into Python, frontend, and Docker jobs. It uses the
  canonical editable install, Ruff check/format-check, Pyright, forbidden
  dependency/secret scan, wheel isolation check, SQLite migration check,
  evidence generation/verification, `npm ci`, Vitest, lint, production build,
  Playwright Chromium setup/smoke tests, Compose config, and a repository-local
  frontend Docker build.
- Added dependency-free Python tooling for forbidden imports/secret-shaped
  values, wheel content plus clean-virtualenv imports, and disposable SQLite
  Alembic upgrades. Make targets expose the package, migration, evidence, and
  Docker checks without changing the existing offline defaults.
- Updated the frontend image to copy the lockfile and use `npm ci`; added
  Docker context exclusions, ESLint configuration, a tracked empty `public/`
  directory, root-level ignores for generated frontend/evidence outputs, and a
  frontend setup command updated to `npm ci`.
- A final read-only review added exclusions for all frontend `.env` files
  (retaining only `.env.example`) and changed Make's test/lint/format/typecheck
  commands to `python -m ...`, so local gates use the interpreter selected by
  the canonical install path.
- Added the `eslint` and `eslint-config-next` development dependencies required
  by the pre-existing `next lint` script. The expanded lockfile is the resolved
  transitive tree for those two lint dependencies; no production dependency or
  route changed.
- Corrected the ignored Pyright configuration shape and applied minimal
  behavior-preserving type fixes. The Anthropic adapter additionally skips
  non-text content blocks before selecting a text response, covered by a focused
  regression test. API routes, dashboard routes, and offline fallbacks remain
  unchanged.

## TDD evidence

- RED: `tests/test_tooling_contracts.py` initially failed for missing CI gates,
  lockfile Docker install behavior, and absent forbidden scan.
- RED: the repository scan initially matched its own legacy-pattern literal and
  the SQLite checker asserted stale table names; regression checks failed before
  the source fixes.
- RED: the Pyright configuration contract failed because `analysis` is not a
  supported pyrightconfig key.
- RED: the optional-provider text-block regression failed to import the helper
  before it was implemented.
- RED: the frontend linter dependency contract failed before adding ESLint.

## Verification

- Clean temporary virtualenv: `python -m pip install -e ".[dev]"`, import of
  `workflow_engine` (`1.0.0`), and `pip check` all passed.
- Python suite: 188 passed in two complete partitions (103 + 85).
- Focused type/runtime suite: 44 passed.
- Ruff check and format check passed; Pyright: 0 errors, 0 warnings.
- Forbidden scan, wheel content/isolated import, SQLite migration, and evidence
  generation/verification all passed. The evidence reproducibility hash was
  `7a2584c22d4d91fbf9368194d068e94ced6dd149f87aa72e46f88f4dc4581029`.
- Frontend: `npm ci` passed; Vitest 25/25 passed; `npm run lint` passed;
  `npm run build` passed; Chromium Playwright smoke tests 6/6 passed.
- `git diff --check` passed.

## Limits and handoff

- Docker Desktop/CLI is not installed in this Windows environment, so local
  `docker compose config` and `docker build` were not executable. Both are
  explicit Ubuntu CI gates.
- The Dockerfile retains the upstream floating `node:20-alpine` tag. Pinning an
  immutable digest needs a separately reviewed base-image update policy and was
  not inferred from the requested repository-local build validation.
- PostgreSQL, Redis, Celery, and provider credentials were intentionally not
  started or required. SQLite/in-memory evidence is not a claim of live-service
  integration.
- `npm ci` reports 10 transitive dependency advisories (2 moderate, 7 high, 1
  critical). No `npm audit fix` was applied because it could alter unrelated
  locked dependencies; the requested change is limited to making the existing
  lint gate reproducible.
- Existing Vitest output retains non-failing React `act(...)` and Recharts
  zero-dimension warnings; all assertions pass and the smoke suite verifies the
  rendered routes in Chromium.
