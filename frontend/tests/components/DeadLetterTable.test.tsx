import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeadLetterTable from "@/components/DeadLetterTable";
import { mockDeadLetters } from "@/lib/mockData";

describe("DeadLetterTable", () => {
  it("renders a row per dead letter with step, task and error", () => {
    render(<DeadLetterTable deadLetters={mockDeadLetters} />);
    expect(screen.getByTestId("dead-letter-table")).toBeInTheDocument();
    expect(screen.getAllByText("charge_gateway").length).toBe(
      mockDeadLetters.length
    );
    expect(screen.getAllByText("always_fail").length).toBe(
      mockDeadLetters.length
    );
    expect(
      screen.getAllByText(/gateway timeout/).length
    ).toBeGreaterThan(0);
  });

  it("invokes onRerun with the run id when Rerun is clicked", async () => {
    const onRerun = vi.fn();
    render(<DeadLetterTable deadLetters={mockDeadLetters} onRerun={onRerun} />);
    const buttons = screen.getAllByRole("button", { name: /rerun/i });
    await userEvent.click(buttons[0]);
    expect(onRerun).toHaveBeenCalledWith(mockDeadLetters[0].run_id);
  });
});
