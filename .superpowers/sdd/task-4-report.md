# Task 4 Finalization Report

## Scope completed

- Added an offline-only portfolio evidence generator and strict verifier.
- Generated output is limited to `artifacts/portfolio/async-workflow-engine-evidence/`
  (ignored); `tests/fixtures/golden/portfolio-evidence.json` is the committed,
  normalized contract.
- The generator pins in-memory SQLite, disables async dispatch, blanks LLM
  credentials, and sets the source path before workflow-engine imports.
- Evidence comes from parser, executor, runner, trace, storage, runtime,
  scheduler, webhook, auth, rate-limit, idempotency, and task services. It covers
  validation/cycles/unknown tasks, branch skip, bounded parallelism, typed I/O,
  retries/DLQ/rerun, both storage implementations, due schedules, HMAC,
  deterministic simulated classification/text parsing, and a dashboard-shaped
  fixture.
- The closed artifact has canonical JSON and Markdown, a manifest, SHA-256
  checksums, a reproducibility hash, and rejects missing, malformed, extra,
  tampered, checksum-invalid, and self-consistent-but-non-golden content.

## TDD evidence

- RED: `python -m pytest tests/test_portfolio_evidence.py --basetemp
  '..\\.pytest-temp\\async-workflow-engine-task4-red' -q` collected 7 tests and
  failed because the requested scripts and golden fixture did not exist.
- RED: the self-consistent-tamper contract initially failed because the verifier
  accepted recomputed checksums and a recomputed manifest hash for altered
  evidence; it now anchors verification to the normalized golden fixture.
- RED: the unexpected-directory contract initially failed because the verifier
  ignored directories while checking for unexpected evidence entries; it now
  rejects every unexpected directory entry as well as unexpected files.
- GREEN: the focused suite collected 9 tests and passed.

## Verification

- `python -m pytest tests/test_portfolio_evidence.py --basetemp
  '..\\.pytest-temp\\async-workflow-engine-task4-review-final-focused' -q` — 11 passed.
- `python -m pytest --basetemp '..\\.pytest-temp\\async-workflow-engine-task4-review-final-full'
  -q` — 174 passed.
- `npm.cmd test -- --run` from `frontend/` — 10 files / 25 tests passed. Existing
  React `act(...)`, Recharts zero-size, and Vite CJS deprecation warnings remain
  unrelated; no frontend files changed.
- `python -m ruff check scripts tests/test_portfolio_evidence.py` — passed.
- `python -m ruff format --check scripts tests/test_portfolio_evidence.py` —
  3 files already formatted.
- `git diff --check` — passed.
- `python scripts/portfolio_demo.py` followed by `python
  scripts/verify_portfolio_evidence.py artifacts\\portfolio\\async-workflow-engine-evidence`
  — passed with reproducibility hash
  `7a2584c22d4d91fbf9368194d068e94ced6dd149f87aa72e46f88f4dc4581029`.

## Self-review

- Confirmed the scripts do not import application settings before pinning local
  offline values and contain no network or credential path.
- Confirmed generated output is ignored while the golden fixture is tracked.
- Confirmed verifier requires the exact four-file manifest, validates all
  checksums, recomputes the canonical evidence hash, checks Markdown coherence,
  and compares against the normalized fixture.
- Confirmed Task 4 makes no public-site, docs, CI, or frontend-package wiring
  changes.
- `node sync-repos.mjs` reports this worktree's current branch has no configured
  upstream (`[NOBRANCH]`); the requested scope was local commit only, so no push
  was attempted. All other registered present children were clean and pushed.

## Review fixes

- A self-consistent manifest or Markdown rewrite can no longer pass after
  recalculating public checksums: the verifier now builds the exact normalized
  manifest from the golden evidence and requires the canonical Markdown report.
  Regression tests cover altered manifest schema and altered report text.
- Typed-I/O evidence now executes a `TypedTask` that consumes `TaskInput` and
  returns `TaskResult`; the normalized fixture records its typed-only output.
- Due-schedule evidence resets the same fire time and dispatches it again through
  the scheduler with the runtime idempotency store. The second result must be
  empty, proving the integration boundary rather than only a raw store claim.
- The failure slice now records the completed/failed step map, ordered failure
  trace, observed exponential backoff (`[0.5]`), and retry event. Those fields
  are part of the golden fixture and focused assertion set.
- RED: self-consistent manifest tampering and self-consistent report tampering
  each initially passed verification. The typed-I/O evidence assertion was also
  red until the real typed task was added. The final focused evidence suite is
  11 passed.

## Canonical-byte review fix

- Root cause: the verifier compared parsed JSON semantics. A pretty-printed or
  reordered `evidence.json` or `manifest.json` with correct values and freshly
  recomputed checksums therefore passed.
- RED: new self-consistent formatting-only regressions for each JSON artifact,
  plus missing-final-newline regressions, failed as intended under the prior
  verifier: 4 failures / 11 passes (`pytest` collected 15 tests).
- Fix: after checksum validation and JSON parsing, the verifier requires exact
  UTF-8 bytes for `evidence.json` (`canonical golden JSON + LF`) and
  `manifest.json` (`canonical normalized manifest + LF`). `report.md` remains
  an exact expected-text comparison.
- The report-tamper regression now changes only the innocuous phrase
  `fixtures are recorded.` to `fixtures are archived.`, retains the valid
  reproducibility hash, and recomputes checksums before asserting rejection.
- GREEN: `python -m pytest tests/test_portfolio_evidence.py -q` — 15 passed.
- Full regression: `python -m pytest -q` — 178 passed.
- Style: `python -m ruff check scripts/verify_portfolio_evidence.py
  tests/test_portfolio_evidence.py` and `python -m ruff format --check
  scripts/verify_portfolio_evidence.py tests/test_portfolio_evidence.py` — passed.
- Reproducibility: two runs of `python scripts/portfolio_demo.py`, each followed
  by `python scripts/verify_portfolio_evidence.py
  artifacts/portfolio/async-workflow-engine-evidence`, passed with identical
  hash `7a2584c22d4d91fbf9368194d068e94ced6dd149f87aa72e46f88f4dc4581029`.
