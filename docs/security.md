# Security Boundaries & Rules — Async Workflow Engine

How the engine secures task execution, input ingestion, persistence, and its
trigger surface (webhooks, schedules). This reflects the implemented system.

---

## 1. Execution Boundary Assurances

- **No arbitrary code execution**: Workflows are *data*, not code. The engine
  never `eval`s or `exec`s anything from a definition and never runs shell
  commands. Steps map to functions in `TASK_REGISTRY`; an unknown task name is
  rejected by `WorkflowExecutor.validate_registry()` **before** any step runs.
- **No expression evaluation in conditions**: Conditional branching uses a typed
  `StepCondition` (`equals` / `contains` / `not_equals` against a prior step's
  string result). There is no condition DSL to inject into — by construction.
- **Safe deserialization**: All parsing uses `yaml.safe_load()` (never
  `yaml.load()`), preventing YAML object-construction attacks.

---

## 2. Secrets Handling & Parameter Injection

- **No credentials in definitions**: Workflow YAML must not carry tokens or keys.
  Tasks that need secrets (e.g. real LLM classification) read them from the
  environment via `AppConfig`/`BaseAppConfig` (`OPENAI_API_KEY`,
  `ANTHROPIC_API_KEY`), unwrapped from Pydantic `SecretStr` only at call time.
- **Validated inputs**: `StepConfig`/`StepCondition` are Pydantic models, so
  step params and conditions are type-checked before reaching a task.
- **Bounded retries**: `retries` is validated `>= 0`, preventing a definition
  from requesting unbounded retry loops.

---

## 3. Trigger Surface (Webhooks & Schedules)

- **Registration-gated webhooks**: `POST /webhooks/{name}` only fires a workflow
  that was previously registered via `POST /webhooks/{name}/register`; the YAML is
  validated at registration time. An unregistered name returns 404 — arbitrary
  callers cannot inject a definition through the trigger path.
- **Validated cron**: `POST /schedules` rejects invalid cron expressions
  (croniter validation) and validates the workflow YAML before registering.
- **No payload execution**: Webhook request bodies are read only to verify an
  optional HMAC signature. They are not interpreted as code, merged into the
  definition, or exposed to workflow steps.
- **Optional HMAC verification**: a registration can carry a secret; when it does,
  `POST /webhooks/{name}` requires a valid `X-Hub-Signature-256` value before
  dispatch. A webhook with no registered secret intentionally remains open in the
  offline default, so deployments must configure a secret and network restrictions.

---

## 4. Queue, State, and Persistence Boundaries

- **Broker protection**: Redis is optional and used for Celery dispatch and opt-in
  distributed locks. Local compose exposes 6379; production must restrict ingress
  to internal networks and enable Redis AUTH/TLS.
- **Run-state persistence**: Runs persist to PostgreSQL (`workflow_runs`,
  `step_executions`) with the original YAML stored to enable rerun. The
  `dead_letters` column and step `result`/`error` may contain task output — if
  workflows process PII, those columns must be encrypted at rest and access-controlled.
- **Schema migrations**: Alembic owns versioned schema changes and operators must
  run `alembic upgrade head`. After a successful database connectivity probe, the
  current startup path also calls `create_tables()` for compatibility with a fresh
  database; that creates mapped tables but is not a substitute for applying the
  Alembic revision chain.

---

## 5. Optional Controls and Production Boundaries

- **API-key roles** are implemented (`viewer`, `operator`, `admin`) but are open by
  default. Enabling them requires `WORKFLOW_AUTH_REQUIRED=true` and a securely
  managed `WORKFLOW_API_KEYS` mapping.
- **Rate limiting** is implemented only as a process-local limiter and is disabled
  at `WORKFLOW_RATE_LIMIT=0`; it is not a distributed production limiter.
  Recognized configured API keys receive key-scoped buckets. Missing or unknown
  keys are scoped to the request client identity, so an open-auth deployment cannot
  evade a bucket by supplying arbitrary key strings. Bucket updates are serialized
  within the process.
- **Runtime persistence** is durable only with reachable PostgreSQL. Offline
  schedules, webhooks, versions, idempotency claims, and execution events are
  process-local and are lost on restart.
- **No multi-tenancy / per-workflow RBAC, secret rotation, TLS termination,
  distributed rate limiting, or production observability claim** is made here.

These boundaries preserve an offline demo while making production hardening an
explicit deployment responsibility.

## 6. Frontend Dependency Audit Boundary

On 2026-08-15, `npm audit` reported 16 locked frontend findings (8 moderate,
7 high, 1 critical), including development-tooling chains. The production image
uses `npm ci --omit=dev`, so Vitest, Vite, Playwright, and ESLint tooling does not
ship in its runtime layer. This does not make the runtime audit clean:
`npm audit --omit=dev` still reported 3 high findings through the locked Next.js
14/PostCSS/nanoid production tree, with no clean in-range fix offered. A hosted
dashboard deployment and the major framework upgrade needed to clear those findings
remain deferred; no zero-vulnerability or production-hardened frontend claim is made.
