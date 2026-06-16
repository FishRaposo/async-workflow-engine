// Bundled mock data so every view is fully explorable with NO backend running.
// Shapes mirror the FastAPI responses exactly (see src/workflow_engine/*).
// The api client falls back to these on any fetch error and flips on a visible
// "Demo mode" indicator.

import type {
  DagResponse,
  DeadLetter,
  RunDetail,
  RunListItem,
  Schedule,
  TaskInfo,
} from "@/types";

export const SAMPLE_YAML = `# Lead-intake workflow: parse an inbound message, classify it, and route a
# notification conditionally based on the classification result.
name: lead_intake
schedule: "*/15 * * * *"   # optional cron: every 15 minutes
steps:
  - id: parse_input
    task: parse_text
    params:
      text: "ACME Corp requests a business quote for 500 widgets. Priority lead."
      chunk_size: 128

  - id: classify
    task: classify_with_llm
    depends_on: [parse_input]
    params:
      labels: [business, support, spam]
      text: "ACME Corp requests a business quote for 500 widgets. Priority lead."

  # Conditional branch: only notify sales when the lead is classified business.
  - id: notify_sales
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: business
    params:
      channel: slack
      message: "New business lead — route to sales."

  # Alternate branch: only fires when classified as spam.
  - id: quarantine
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: spam
    params:
      channel: log
      message: "Spam lead quarantined."
`;

const ETL_YAML = `name: nightly_etl
steps:
  - id: extract
    task: parse_text
    params:
      text: "Nightly export from the orders database."
  - id: transform
    task: classify_with_llm
    depends_on: [extract]
    params:
      labels: [orders, refunds, fraud]
  - id: load_warehouse
    task: send_notification
    depends_on: [transform]
    params:
      channel: email
      message: "Warehouse load complete."
`;

const FLAKY_YAML = `name: payment_reconcile
steps:
  - id: fetch_ledger
    task: parse_text
    params:
      text: "Reconcile yesterday's settlement batch."
  - id: charge_gateway
    task: always_fail
    depends_on: [fetch_ledger]
    retries: 2
    params:
      message: "gateway timeout: upstream did not respond"
  - id: notify_finance
    task: send_notification
    depends_on: [charge_gateway]
    params:
      channel: slack
      message: "Reconciliation finished."
`;

// --------------------------------------------------------------------------- //
// Runs
// --------------------------------------------------------------------------- //
export const mockRuns: RunListItem[] = [
  {
    run_id: "11111111-1111-1111-1111-111111111111",
    workflow_name: "lead_intake",
    status: "completed",
    created_at: "2026-06-15T09:42:11.000Z",
  },
  {
    run_id: "22222222-2222-2222-2222-222222222222",
    workflow_name: "payment_reconcile",
    status: "failed",
    created_at: "2026-06-15T08:17:03.000Z",
  },
  {
    run_id: "33333333-3333-3333-3333-333333333333",
    workflow_name: "nightly_etl",
    status: "completed",
    created_at: "2026-06-15T02:00:00.000Z",
  },
  {
    run_id: "44444444-4444-4444-4444-444444444444",
    workflow_name: "lead_intake",
    status: "partial",
    created_at: "2026-06-14T21:11:47.000Z",
  },
  {
    run_id: "55555555-5555-5555-5555-555555555555",
    workflow_name: "nightly_etl",
    status: "completed",
    created_at: "2026-06-14T02:00:00.000Z",
  },
  {
    run_id: "66666666-6666-6666-6666-666666666666",
    workflow_name: "payment_reconcile",
    status: "failed",
    created_at: "2026-06-13T08:17:00.000Z",
  },
];

const leadDeadLetters: DeadLetter[] = [];

const paymentDeadLetters: DeadLetter[] = [
  {
    step_id: "charge_gateway",
    task: "always_fail",
    error: "gateway timeout: upstream did not respond",
    attempts: 3,
    params: { message: "gateway timeout: upstream did not respond" },
  },
];

export const mockRunDetails: Record<string, RunDetail> = {
  "11111111-1111-1111-1111-111111111111": {
    run_id: "11111111-1111-1111-1111-111111111111",
    workflow_name: "lead_intake",
    yaml_definition: SAMPLE_YAML,
    status: "completed",
    step_statuses: {
      parse_input: "COMPLETED",
      classify: "COMPLETED",
      notify_sales: "COMPLETED",
      quarantine: "SKIPPED",
    },
    results: {
      parse_input:
        "{'status': 'parsed', 'word_count': 11, 'chunk_count': 1, 'preview': 'ACME Corp requests a business quote for 500 widgets. Priority lead.'}",
      classify: "{'category': 'business', 'source': 'sim'}",
      notify_sales:
        "{'status': 'sent', 'channel': 'slack', 'message': 'New business lead — route to sales.'}",
    },
    errors: {},
    dead_letters: leadDeadLetters,
    task_names: {
      parse_input: "parse_text",
      classify: "classify_with_llm",
      notify_sales: "send_notification",
      quarantine: "send_notification",
    },
    created_at: "2026-06-15T09:42:11.000Z",
    completed_at: "2026-06-15T09:42:12.000Z",
  },
  "22222222-2222-2222-2222-222222222222": {
    run_id: "22222222-2222-2222-2222-222222222222",
    workflow_name: "payment_reconcile",
    yaml_definition: FLAKY_YAML,
    status: "failed",
    step_statuses: {
      fetch_ledger: "COMPLETED",
      charge_gateway: "FAILED",
      notify_finance: "PENDING",
    },
    results: {
      fetch_ledger:
        "{'status': 'parsed', 'word_count': 5, 'chunk_count': 1, 'preview': \"Reconcile yesterday's settlement batch.\"}",
    },
    errors: {
      charge_gateway: "gateway timeout: upstream did not respond",
    },
    dead_letters: paymentDeadLetters,
    task_names: {
      fetch_ledger: "parse_text",
      charge_gateway: "always_fail",
      notify_finance: "send_notification",
    },
    created_at: "2026-06-15T08:17:03.000Z",
    completed_at: "2026-06-15T08:17:09.000Z",
  },
  "33333333-3333-3333-3333-333333333333": {
    run_id: "33333333-3333-3333-3333-333333333333",
    workflow_name: "nightly_etl",
    yaml_definition: ETL_YAML,
    status: "completed",
    step_statuses: {
      extract: "COMPLETED",
      transform: "COMPLETED",
      load_warehouse: "COMPLETED",
    },
    results: {
      extract:
        "{'status': 'parsed', 'word_count': 5, 'chunk_count': 1, 'preview': 'Nightly export from the orders database.'}",
      transform: "{'category': 'orders', 'source': 'sim'}",
      load_warehouse:
        "{'status': 'sent', 'channel': 'email', 'message': 'Warehouse load complete.'}",
    },
    errors: {},
    dead_letters: [],
    task_names: {
      extract: "parse_text",
      transform: "classify_with_llm",
      load_warehouse: "send_notification",
    },
    created_at: "2026-06-15T02:00:00.000Z",
    completed_at: "2026-06-15T02:00:01.000Z",
  },
  "44444444-4444-4444-4444-444444444444": {
    run_id: "44444444-4444-4444-4444-444444444444",
    workflow_name: "lead_intake",
    yaml_definition: SAMPLE_YAML,
    status: "partial",
    step_statuses: {
      parse_input: "COMPLETED",
      classify: "COMPLETED",
      notify_sales: "SKIPPED",
      quarantine: "RUNNING",
    },
    results: {
      parse_input:
        "{'status': 'parsed', 'word_count': 11, 'chunk_count': 1}",
      classify: "{'category': 'spam', 'source': 'sim'}",
    },
    errors: {},
    dead_letters: [],
    task_names: {
      parse_input: "parse_text",
      classify: "classify_with_llm",
      notify_sales: "send_notification",
      quarantine: "send_notification",
    },
    created_at: "2026-06-14T21:11:47.000Z",
    completed_at: null,
  },
  "55555555-5555-5555-5555-555555555555": {
    run_id: "55555555-5555-5555-5555-555555555555",
    workflow_name: "nightly_etl",
    yaml_definition: ETL_YAML,
    status: "completed",
    step_statuses: {
      extract: "COMPLETED",
      transform: "COMPLETED",
      load_warehouse: "COMPLETED",
    },
    results: {},
    errors: {},
    dead_letters: [],
    task_names: {
      extract: "parse_text",
      transform: "classify_with_llm",
      load_warehouse: "send_notification",
    },
    created_at: "2026-06-14T02:00:00.000Z",
    completed_at: "2026-06-14T02:00:01.000Z",
  },
  "66666666-6666-6666-6666-666666666666": {
    run_id: "66666666-6666-6666-6666-666666666666",
    workflow_name: "payment_reconcile",
    yaml_definition: FLAKY_YAML,
    status: "failed",
    step_statuses: {
      fetch_ledger: "COMPLETED",
      charge_gateway: "FAILED",
      notify_finance: "PENDING",
    },
    results: {},
    errors: {
      charge_gateway: "gateway timeout: upstream did not respond",
    },
    dead_letters: [
      {
        step_id: "charge_gateway",
        task: "always_fail",
        error: "gateway timeout: upstream did not respond",
        attempts: 3,
        params: { message: "gateway timeout: upstream did not respond" },
      },
    ],
    task_names: {
      fetch_ledger: "parse_text",
      charge_gateway: "always_fail",
      notify_finance: "send_notification",
    },
    created_at: "2026-06-13T08:17:00.000Z",
    completed_at: "2026-06-13T08:17:06.000Z",
  },
};

// --------------------------------------------------------------------------- //
// DAGs (mirrors build_dag output)
// --------------------------------------------------------------------------- //
export function mockDagFor(runId: string): DagResponse {
  const detail = mockRunDetails[runId] ?? mockRunDetails[mockRuns[0].run_id];
  const statuses = detail.step_statuses;

  if (detail.workflow_name === "lead_intake") {
    return {
      nodes: [
        { id: "parse_input", task: "parse_text", status: statuses.parse_input ?? "PENDING", conditional: false, retries: 3 },
        { id: "classify", task: "classify_with_llm", status: statuses.classify ?? "PENDING", conditional: false, retries: 3 },
        { id: "notify_sales", task: "send_notification", status: statuses.notify_sales ?? "PENDING", conditional: true, retries: 3 },
        { id: "quarantine", task: "send_notification", status: statuses.quarantine ?? "PENDING", conditional: true, retries: 3 },
      ],
      edges: [
        { from: "parse_input", to: "classify", type: "dependency" },
        { from: "classify", to: "notify_sales", type: "dependency" },
        { from: "classify", to: "notify_sales", type: "conditional" },
        { from: "classify", to: "quarantine", type: "dependency" },
        { from: "classify", to: "quarantine", type: "conditional" },
      ],
    };
  }

  if (detail.workflow_name === "payment_reconcile") {
    return {
      nodes: [
        { id: "fetch_ledger", task: "parse_text", status: statuses.fetch_ledger ?? "PENDING", conditional: false, retries: 3 },
        { id: "charge_gateway", task: "always_fail", status: statuses.charge_gateway ?? "PENDING", conditional: false, retries: 2 },
        { id: "notify_finance", task: "send_notification", status: statuses.notify_finance ?? "PENDING", conditional: false, retries: 3 },
      ],
      edges: [
        { from: "fetch_ledger", to: "charge_gateway", type: "dependency" },
        { from: "charge_gateway", to: "notify_finance", type: "dependency" },
      ],
    };
  }

  // nightly_etl
  return {
    nodes: [
      { id: "extract", task: "parse_text", status: statuses.extract ?? "PENDING", conditional: false, retries: 3 },
      { id: "transform", task: "classify_with_llm", status: statuses.transform ?? "PENDING", conditional: false, retries: 3 },
      { id: "load_warehouse", task: "send_notification", status: statuses.load_warehouse ?? "PENDING", conditional: false, retries: 3 },
    ],
    edges: [
      { from: "extract", to: "transform", type: "dependency" },
      { from: "transform", to: "load_warehouse", type: "dependency" },
    ],
  };
}

// --------------------------------------------------------------------------- //
// Dead-letter queue, schedules, tasks
// --------------------------------------------------------------------------- //
export const mockDeadLetters: DeadLetter[] = [
  {
    step_id: "charge_gateway",
    task: "always_fail",
    error: "gateway timeout: upstream did not respond",
    attempts: 3,
    params: { message: "gateway timeout: upstream did not respond" },
    run_id: "22222222-2222-2222-2222-222222222222",
  },
  {
    step_id: "charge_gateway",
    task: "always_fail",
    error: "gateway timeout: upstream did not respond",
    attempts: 3,
    params: { message: "gateway timeout: upstream did not respond" },
    run_id: "66666666-6666-6666-6666-666666666666",
  },
];

export const mockSchedules: Schedule[] = [
  {
    name: "lead_intake_every_15m",
    cron: "*/15 * * * *",
    enabled: true,
    last_run: "2026-06-15T09:45:00.000Z",
    next_run: "2026-06-15T10:00:00.000Z",
  },
  {
    name: "nightly_etl",
    cron: "0 2 * * *",
    enabled: true,
    last_run: "2026-06-15T02:00:00.000Z",
    next_run: "2026-06-16T02:00:00.000Z",
  },
  {
    name: "weekly_report",
    cron: "0 9 * * 1",
    enabled: false,
    last_run: null,
    next_run: "2026-06-22T09:00:00.000Z",
  },
];

export const mockTasks: TaskInfo[] = [
  { name: "always_fail", description: "A task that always raises — used to exercise retries and the DLQ." },
  { name: "classify_with_llm", description: "Classify text into one of params['labels']." },
  { name: "parse_text", description: "Parse and chunk an input text, returning real statistics." },
  { name: "send_notification", description: "Simulate sending a notification (no external I/O)." },
];
