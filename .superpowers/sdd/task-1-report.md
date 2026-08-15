# Task 1 — self-containment and package alignment

## Status

Implemented on top of baseline `253c2a244131a2823617eb2ea1cbd17685f53758`.
The engine installs, tests, and builds its wheel without an external package or
Git URL for the former shared infrastructure runtime.

## Provenance

- Archived source: `operator-shared-core` v1.3.0.
- Verified source commit: `dbf276a7708da65b55e1f10b35af634b300d1f07`.
- Verification: temporary source checkout resolved to that exact `HEAD`; its MIT
  `LICENSE` matched this repository's existing `LICENSE` byte-for-byte.
- License/provenance record: `THIRD_PARTY_NOTICES.md`.

The copied closure is under `src/workflow_engine/internal/vendor_core/`:

`__init__.py`, `config.py`, `database.py`, `errors.py`, `health.py`,
`logging.py`, `redis.py`, `tasks.py`, `llm.py`, `pricing.py`, `docparse.py`, and
`testing.py`. Its prior top-level imports were redirected to the private
`workflow_engine.internal.vendor_core` namespace.

## Delivered

- Rewrote source, migration, and test imports to the private vendor namespace.
- Kept document chunking in the packaged runtime; added optional `llm` and
  `document-parsers` extras for provider and heavy parser integrations.
- Made `python -m pip install -e ".[dev]"` the single canonical Makefile, CI,
  README, and AGENTS installation path.
- Removed the CI Git install and all sibling-package operational references.
- Updated technical and operational docs to describe the vendored runtime and
  kept sync/offline execution as the default.
- Added wheel-isolation and operational-reference contract tests.

No workflow endpoint, response key, YAML semantic, retry behavior, dead-letter
handling, rerun behavior, dispatch default, or hosted infrastructure was added
or changed.

## TDD evidence

1. `test_wheel_contains_and_imports_internal_vendor_core` was written first and
   failed because the baseline wheel did not contain
   `workflow_engine/internal/vendor_core/__init__.py`.
2. After vendoring and retargeting imports, the same wheel test passed. It builds
   a no-dependency wheel, installs it into an isolated target, confirms
   `shared_core` cannot be resolved, and imports the internal namespace.
3. `test_installation_and_operational_references_are_self_contained` then failed
   because the baseline lacked the required optional extras and still had external
   operational references. It passed after the package/CI/Makefile/doc changes.
4. Review found that the project still supports Python 3.10 while the contract
   test used Python 3.11's `tomllib`. A focused test failed until the dev extra
   supplied conditional `tomli`; the test import now falls back on Python 3.10.

## Validation

| Command | Result |
| --- | --- |
| `python -m pip install -e ".[dev]"` | Pass |
| `python -m pytest --noconftest tests/test_self_containment.py -q` | Pass, 3 tests |
| `python -m pytest` | Pass, 125 tests |
| `python -m ruff check src/workflow_engine tests examples alembic` | Pass |
| `python -m ruff format --check src/workflow_engine tests examples alembic` | Pass, 48 files already formatted |
| `git diff --check` | Pass (line-ending warnings only) |
| External-import scan excluding provenance/test fixtures | Pass, no former package import, sibling install, or Git install path |

## Known limitation

`python -m pyright src` is not clean (18 errors). The output includes unrelated
existing engine typing issues in `executor.py`, `scheduler.py`, and
`storage_db.py`, the existing FastAPI exception-handler signature, and optional
Anthropic response-union annotations that become visible when the archived LLM
module is type-checked in-tree. It also reports the pre-existing obsolete
`analysis` configuration key and missing `.venv`. This slice deliberately does
not change workflow behavior or expand into a type-system cleanup; runtime tests,
wheel isolation, and lint pass.

## Review

Independent review of the amended change found and verified fixes for Python 3.10
TOML compatibility, optional-extra activation documentation, and the test-count
documentation. Final re-review verdict: approved with no merge blockers.
