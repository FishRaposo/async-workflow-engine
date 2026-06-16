import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DagGraph from "@/components/DagGraph";
import { mockDagFor } from "@/lib/mockData";

describe("DagGraph", () => {
  it("renders a node group per DAG node", () => {
    const dag = mockDagFor("11111111-1111-1111-1111-111111111111");
    render(<DagGraph dag={dag} />);
    for (const node of dag.nodes) {
      expect(screen.getByTestId(`dag-node-${node.id}`)).toBeInTheDocument();
    }
  });

  it("labels nodes with their step id and task", () => {
    const dag = mockDagFor("11111111-1111-1111-1111-111111111111");
    render(<DagGraph dag={dag} />);
    expect(screen.getByText("parse_input")).toBeInTheDocument();
    expect(screen.getAllByText("send_notification").length).toBeGreaterThan(0);
  });

  it("marks conditional nodes", () => {
    const dag = mockDagFor("11111111-1111-1111-1111-111111111111");
    render(<DagGraph dag={dag} />);
    expect(screen.getAllByText(/conditional/).length).toBeGreaterThan(0);
  });

  it("shows a friendly message when there are no nodes", () => {
    render(<DagGraph dag={{ nodes: [], edges: [] }} />);
    expect(screen.getByText(/no steps to display/i)).toBeInTheDocument();
  });
});
