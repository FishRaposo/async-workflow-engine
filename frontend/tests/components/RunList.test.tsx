import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RunList from "@/components/RunList";
import { mockRuns } from "@/lib/mockData";

describe("RunList", () => {
  it("renders a row per run with workflow name and status", () => {
    render(<RunList runs={mockRuns} />);
    expect(screen.getByTestId("run-list")).toBeInTheDocument();
    // Two lead_intake and two payment_reconcile runs in the mock set.
    expect(screen.getAllByText("lead_intake").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("payment_reconcile").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(mockRuns[0].run_id)).toBeInTheDocument();
  });

  it("links each run to its detail page", () => {
    render(<RunList runs={mockRuns.slice(0, 1)} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", `/runs/${mockRuns[0].run_id}`);
  });

  it("shows a Completed badge for completed runs", () => {
    render(<RunList runs={mockRuns.filter((r) => r.status === "completed")} />);
    expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
  });
});
