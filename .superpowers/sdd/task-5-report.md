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
  (retaining only `.env.example`), ignores the generated `debug.log`, and
  changed Make's test/lint/format/typecheck/package/migration/evidence commands
  to `python -m ...`, so local gates use the interpreter selected by the
  canonical install path.
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
- The frontend Docker base is now the immutable Docker Hub multi-platform index
  `node:20.20.1-alpine3.22@sha256:c0a3cda003a229d51f0f118c12a706842f43450ae505ed6825d66b5acdef127f`.
  CI uses the matching `20.20.1` Node patch release. Updating the image is an
  intentional source-and-contract change, not a floating-tag refresh.
- PostgreSQL, Redis, Celery, and provider credentials were intentionally not
  started or required. SQLite/in-memory evidence is not a claim of live-service
  integration.
- `npm ci` reports 16 transitive dependency advisories (8 moderate, 7 high, 1
  critical). No `npm audit fix` was applied because it could alter unrelated
  locked dependencies; the requested change is limited to making the existing
  lint gate reproducible.
- Existing Vitest output retains non-failing React `act(...)` and Recharts
  zero-dimension warnings; all assertions pass and the smoke suite verifies the
  rendered routes in Chromium.

## Review follow-up — packaging hardening

### Delivered

- `frontend/.gitignore` now ignores every `.env*` file while explicitly keeping
  `.env.example` eligible for version control; the Docker context already has
  the same exclusion and exception.
- `scripts/check_forbidden.py` now examines tracked root and frontend `.env*`
  files through `git ls-files`, in addition to the frontend configuration files
  that determine builds and browser tooling. Ignored developer env files are not
  read, while a force-added `frontend/.env.production` containing a secret-shaped
  value deterministically fails.
- The Dockerfile shares one immutable Node base image, splits development,
  builder, production-dependency, and runtime stages, and copies runtime
  `node_modules` only from `npm ci --omit=dev`. The runtime cannot inherit
  Vitest, Playwright, or ESLint from the builder. The `dev` target remains the
  local `npm run dev` image.
- CI’s frontend job now pins Node `20.20.1`, which is the patch release named in
  the Docker image. Tooling contracts assert the image digest, CI pin, env
  exception, production install command, and absence of a builder-node-modules
  copy in the runtime stage.
- The Make package, migration, and evidence targets now invoke their scripts as
  Python modules, matching the interpreter-qualified test, lint, format, and
  typecheck targets; the module commands were executed successfully.

### TDD and verification

- RED: the new contracts failed before implementation: no immutable Node image,
  CI used floating Node `20`, the Docker context did not cover every `.env*`
  filename, and a git-tracked `frontend/.env.production` secret was outside the
  scanner scope; Make’s package, migration, and evidence targets also used
  file-path script invocations instead of `python -m`.
- GREEN: `python -m pytest -q -o addopts= tests/test_tooling_contracts.py`
  passed (12 tests); focused tooling/vendor suite passed (13 tests).
- Full Python suite: `python -m pytest -q -o addopts=` passed, **193 passed in
  30.25s**. Ruff check, Ruff format check, Pyright (**0 errors, 0 warnings**),
  forbidden scan, wheel isolation, SQLite migration, evidence generation and
  verification, and `git diff --check` all passed.
- Clean frontend install and browser gates passed: `npm.cmd ci`, Vitest
  **25/25**, lint, production build, and Chromium Playwright **6/6**. Routes
  remain `/`, `/runs`, `/runs/[id]`, `/dead-letters`, `/schedules`, and
  `/trigger`.
- Docker Compose YAML parsed successfully. Docker CLI/Desktop is still absent,
  so a real `docker compose config`, image build, and runtime layer inspection
  could not execute locally; CI owns those gates. The Dockerfile’s static
  production-dependency boundary is covered by the tooling contracts.

### Current limitations

- Local frontend verification used Node `v24.16.0`; CI is explicitly pinned to
  Node `20.20.1` and the Docker base is immutable. This Windows host has no
  Docker CLI, so it could not reproduce that image locally.
- GNU Make is not installed on this Windows host, so its updated package,
  migration, and evidence targets were not executable; their exact
  `python -m scripts...` commands were run directly and passed.
- `npm ci` emits package deprecation notices and 16 transitive advisories (8
  moderate, 7 high, 1 critical). They are recorded rather than silently
  remediated because an audit upgrade would expand this packaging-only change.
