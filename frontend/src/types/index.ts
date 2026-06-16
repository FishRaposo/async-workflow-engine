// Type definitions mirroring the workflow_engine FastAPI response shapes.
// See src/workflow_engine/{main,storage,dag,runner,scheduler}.py for the source.

/** Per-step status emitted by the executor. */
export type StepStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED";

/** Aggregate run status (executor.overall_status). */
export type RunStatus = "completed" | "failed" | "partial" | "pending";

/** A row in GET /workflows -> { runs: [...] }. */
export interface RunListItem {
  run_id: string;
  workflow_name: string;
  status: RunStatus | string;
  created_at: string;
}

export interface RunListResponse {
  runs: RunListItem[];
}

/** A single dead-letter entry (executor.dead_letters + run_id). */
export interface DeadLetter {
  step_id: string;
  task: string;
  error: string;
  attempts: number;
  params: Record<string, unknown>;
  run_id?: string;
}

/** Full run record from GET /workflows/{run_id}. */
export interface RunDetail {
  run_id: string;
  workflow_name: string;
  yaml_definition?: string | null;
  status: RunStatus | string;
  step_statuses: Record<string, StepStatus | string>;
  results: Record<string, string>;
  errors: Record<string, string>;
  dead_letters: DeadLetter[];
  task_names?: Record<string, string>;
  created_at: string | null;
  completed_at?: string | null;
}

/** A node in GET /workflows/{run_id}/dag. */
export interface DagNode {
  id: string;
  task: string;
  status: StepStatus | string;
  conditional: boolean;
  retries: number;
}

/** An edge in GET /workflows/{run_id}/dag. */
export interface DagEdge {
  from: string;
  to: string;
  type: "dependency" | "conditional";
}

export interface DagResponse {
  nodes: DagNode[];
  edges: DagEdge[];
}

export interface DeadLetterResponse {
  dead_letters: DeadLetter[];
}

/** A schedule from GET /schedules -> { schedules: [...] }. */
export interface Schedule {
  name: string;
  cron: string;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
}

export interface ScheduleListResponse {
  schedules: Schedule[];
}

/** Result of creating a schedule (POST /schedules). */
export interface ScheduleCreated {
  name: string;
  cron: string;
  next_run: string | null;
}

/** Synchronous dispatch result (run_workflow). */
export interface SyncRunResult {
  dispatched: "sync";
  run_id: string;
  workflow: string;
  status: RunStatus | string;
  step_statuses: Record<string, StepStatus | string>;
  results: Record<string, string>;
  errors: Record<string, string>;
  dead_letters: DeadLetter[];
}

/** Async dispatch result (Celery enqueue). */
export interface AsyncRunResult {
  dispatched: "async";
  task_id: string;
  run_id: string | null;
}

export type DispatchResult = SyncRunResult | AsyncRunResult;

/** POST /workflows/validate result. */
export interface ValidateResult {
  valid: boolean;
  workflow: string;
  steps: { id: string; task: string; depends_on: string[] }[];
}

/** A registered task from GET /tasks. */
export interface TaskInfo {
  name: string;
  description: string;
}

export interface TaskListResponse {
  tasks: TaskInfo[];
}

/** GET /health result. */
export interface HealthCheck {
  status: string;
  service?: string;
  storage?: "database" | "in-memory" | string;
  [key: string]: unknown;
}
