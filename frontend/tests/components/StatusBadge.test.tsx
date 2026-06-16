import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBadge from "@/components/StatusBadge";

describe("StatusBadge", () => {
  it("renders a labeled run status", () => {
    render(<StatusBadge status="failed" kind="run" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("maps uppercase step statuses", () => {
    render(<StatusBadge status="SKIPPED" kind="step" />);
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("applies the completed badge styling", () => {
    const { container } = render(<StatusBadge status="completed" kind="run" />);
    const badge = container.querySelector('[data-testid="status-badge"]');
    expect(badge?.className).toContain("emerald");
  });

  it("falls back to the raw label for unknown statuses", () => {
    render(<StatusBadge status="weird" kind="run" />);
    expect(screen.getByText("weird")).toBeInTheDocument();
  });
});
