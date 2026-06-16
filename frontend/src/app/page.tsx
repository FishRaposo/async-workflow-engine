import Link from "next/link";
import {
  GitBranch,
  ListChecks,
  PlayCircle,
  Inbox,
  CalendarClock,
} from "lucide-react";

const features = [
  {
    href: "/runs",
    icon: ListChecks,
    title: "Run history",
    body: "Browse every workflow run with status badges, and drill into a visual DAG of each step.",
  },
  {
    href: "/trigger",
    icon: PlayCircle,
    title: "Trigger a workflow",
    body: "Paste a YAML definition, validate it, and dispatch synchronously or async onto the queue.",
  },
  {
    href: "/dead-letters",
    icon: Inbox,
    title: "Dead-letter queue",
    body: "Inspect steps that exhausted their retries, with the captured error and a one-click rerun.",
  },
  {
    href: "/schedules",
    icon: CalendarClock,
    title: "Schedules",
    body: "Register cron-scheduled workflows and see when each one last ran and fires next.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <section className="mb-14 text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700">
          <GitBranch className="h-4 w-4" />
          Async Workflow Engine
        </div>
        <h1 className="mb-4 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Flowforge orchestration console
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-gray-600">
          A production-minded control plane for the workflow engine: dispatch
          YAML-defined DAGs, watch per-step status, retry failures from the
          dead-letter queue, and manage cron schedules.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link href="/runs" className="btn-primary px-6 py-3 text-base">
            View runs
          </Link>
          <Link href="/trigger" className="btn-secondary px-6 py-3 text-base">
            Trigger a workflow
          </Link>
        </div>
      </section>

      <section className="grid gap-5 sm:grid-cols-2">
        {features.map(({ href, icon: Icon, title, body }) => (
          <Link
            key={href}
            href={href}
            className="group rounded-xl border border-gray-200 bg-white p-6 transition-shadow hover:shadow-md"
          >
            <div className="mb-3 inline-flex rounded-lg bg-brand-50 p-2 text-brand-600">
              <Icon className="h-5 w-5" />
            </div>
            <h3 className="mb-1 font-semibold text-gray-900 group-hover:text-brand-700">
              {title}
            </h3>
            <p className="text-sm text-gray-600">{body}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
