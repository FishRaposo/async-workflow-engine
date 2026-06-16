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
- **No payload execution**: Webhook request bodies are not interpreted as code or
  merged into the definition; they are available to the workflow as inert data.
- **Hardening gap (known)**: Webhook endpoints have **no signature verification or
  authentication** in this MVP. Production deployments must add HMAC signature
  checks (e.g. an `X-Signature` header) and network restrictions.

---

## 4. Queue, State, and Persistence Boundaries

- **Broker protection**: Redis is the Celery broker. Local compose exposes 6379;
  production must restrict ingress to internal networks and enable Redis AUTH/TLS.
- **Run-state persistence**: Runs persist to PostgreSQL (`workflow_runs`,
  `step_executions`) with the original YAML stored to enable rerun. The
  `dead_letters` column and step `result`/`error` may contain task output — if
  workflows process PII, those columns must be encrypted at rest and access-controlled.
- **Schema migrations**: Alembic owns the schema; `create_tables()` is used only
  for the offline/test fast path.

---

## 5. Known Gaps (MVP posture)

- **No API authentication / authorization** on any endpoint.
- **In-memory webhook/schedule registries** — not access-controlled, lost on restart.
- **No rate limiting** on trigger endpoints (`shared_core.ratelimit` is available
  to add).
- **No multi-tenancy / per-workflow RBAC.**

These are appropriate for a showcase but must be closed before any production use.
