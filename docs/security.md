# Security Boundaries & Rules - Async Workflow Engine

This document defines the security parameters and boundaries of the Async Workflow Engine. It outlines how the system secures task execution, input ingestion, and execution environments.

---

## 1. Execution Boundary Assurances

- **No Arbitrary Code Execution**: The engine does NOT execute arbitrary Python script blocks or shell commands defined in workflows.
- **Task Registry Constraint**: The parser matches steps to task strings (e.g., `classify_with_llm`) and runs the mapped functions from `TASK_REGISTRY` only. If a task name is not found in the registry, it is rejected before execution.
- **Safe Serialization**: All file parsing utilizes `yaml.safe_load()` (via PyYAML) rather than `yaml.load()` to prevent YAML object deserialization attacks.

---

## 2. Secrets Handling & Parameter Injection

- **Decoupled API Keys**: Workflow definitions must not contain credentials, tokens, or API keys. Tasks requiring secrets (such as the LLM monitoring or classification tasks) must pull credentials from Pydantic config schemas backed by environment variables.
- **Input Sanitization**: Variables passed to tasks are validated via Pydantic model attributes (`StepConfig`). This mitigates parameter injection vulnerabilities.

---

## 3. Queue and State Access Boundaries

- **Message Broker Protection**: Redis acts as the message broker. Since the host ports are exposed in local development setups, production deployments must restrict Redis ingress to local networks and configure authentication.
- **Run State Access**: The workflow state is held in memory during execution. If run state persistence is added in the future, database schemas must separate general run logs from potential PII or encrypted payload variables.
