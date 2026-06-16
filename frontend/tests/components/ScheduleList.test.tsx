import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScheduleList from "@/components/ScheduleList";
import { mockSchedules } from "@/lib/mockData";

describe("ScheduleList", () => {
  it("renders each schedule with its cron expression", () => {
    render(<ScheduleList schedules={mockSchedules} />);
    expect(screen.getByText("lead_intake_every_15m")).toBeInTheDocument();
    expect(screen.getByText("*/15 * * * *")).toBeInTheDocument();
    expect(screen.getByText("0 2 * * *")).toBeInTheDocument();
  });

  it("shows enabled/disabled state", () => {
    render(<ScheduleList schedules={mockSchedules} />);
    expect(screen.getAllByText("enabled").length).toBeGreaterThan(0);
    expect(screen.getByText("disabled")).toBeInTheDocument();
  });

  it("calls onDelete with the schedule name", async () => {
    const onDelete = vi.fn();
    render(<ScheduleList schedules={mockSchedules} onDelete={onDelete} />);
    const btn = screen.getByRole("button", {
      name: /delete lead_intake_every_15m/i,
    });
    await userEvent.click(btn);
    expect(onDelete).toHaveBeenCalledWith("lead_intake_every_15m");
  });
});
