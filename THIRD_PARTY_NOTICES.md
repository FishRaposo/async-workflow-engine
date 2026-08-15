# Third-party notices

## Vendored infrastructure runtime

This distribution contains a package-private, unmodified-functionality import
closure from the archived `operator-shared-core` v1.3.0 source commit
`dbf276a7708da65b55e1f10b35af634b300d1f07`.

The copied modules are:

- `__init__.py`
- `config.py`
- `database.py`
- `errors.py`
- `health.py`
- `logging.py`
- `redis.py`
- `tasks.py`
- `llm.py`
- `pricing.py`
- `docparse.py`
- `testing.py`

They are shipped under `workflow_engine.internal.vendor_core`. References within
that closure were retargeted from its former top-level package name to this
private namespace; no behavior, public workflow route, response key, YAML
semantic, retry/DLQ/rerun handling, or synchronous offline default was changed.

The source is licensed under the MIT License. Its complete license text is
included in this repository's [LICENSE](LICENSE).
