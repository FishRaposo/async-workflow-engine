import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import RunStatusChart from "@/components/RunStatusChart";
import { mockRuns } from "@/lib/mockData";

// recharts' ResponsiveContainer needs a measurable box in jsdom.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    value: 300,
  });
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    value: 200,
  });
});

describe("RunStatusChart", () => {
  it("renders the chart container for a non-empty run set", () => {
    render(<RunStatusChart runs={mockRuns} />);
    expect(screen.getByTestId("run-status-chart")).toBeInTheDocument();
  });

  it("shows an empty message when there are no runs", () => {
    render(<RunStatusChart runs={[]} />);
    expect(screen.getByText(/no runs to summarize/i)).toBeInTheDocument();
  });
});
