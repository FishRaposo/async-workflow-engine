import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EmptyState from "@/components/EmptyState";

describe("EmptyState", () => {
  it("renders title, message and action", () => {
    render(
      <EmptyState
        title="Nothing here"
        message="Try again later"
        action={<button>Do it</button>}
      />
    );
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try again later")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Do it" })).toBeInTheDocument();
  });
});
