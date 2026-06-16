"use client";

import { useMemo } from "react";
import type { DagNode, DagResponse } from "@/types";
import { stepStatusStyle } from "@/lib/status";

interface Props {
  dag: DagResponse;
}

interface Positioned extends DagNode {
  x: number;
  y: number;
}

const NODE_W = 168;
const NODE_H = 64;
const COL_GAP = 96;
const ROW_GAP = 32;
const PAD = 24;

/**
 * Assign each node a column index from the longest dependency path (longest-path
 * layering), so dependencies always sit to the left of their dependents.
 */
function computeLevels(dag: DagResponse): Map<string, number> {
  const level = new Map<string, number>();
  const incoming = new Map<string, string[]>();
  for (const n of dag.nodes) {
    level.set(n.id, 0);
    incoming.set(n.id, []);
  }
  for (const e of dag.edges) {
    if (incoming.has(e.to)) incoming.get(e.to)!.push(e.from);
  }

  // Iterate to a fixed point (DAG is acyclic, so this converges).
  let changed = true;
  let guard = dag.nodes.length + 1;
  while (changed && guard-- > 0) {
    changed = false;
    for (const e of dag.edges) {
      const from = level.get(e.from);
      const to = level.get(e.to);
      if (from === undefined || to === undefined) continue;
      if (to < from + 1) {
        level.set(e.to, from + 1);
        changed = true;
      }
    }
  }
  return level;
}

export default function DagGraph({ dag }: Props) {
  const { positioned, width, height } = useMemo(() => {
    const level = computeLevels(dag);
    const columns = new Map<number, DagNode[]>();
    for (const node of dag.nodes) {
      const col = level.get(node.id) ?? 0;
      if (!columns.has(col)) columns.set(col, []);
      columns.get(col)!.push(node);
    }

    const positioned: Positioned[] = [];
    let maxRows = 0;
    const sortedCols = Array.from(columns.keys()).sort((a, b) => a - b);
    for (const col of sortedCols) {
      const nodes = columns.get(col)!;
      maxRows = Math.max(maxRows, nodes.length);
      nodes.forEach((node, row) => {
        positioned.push({
          ...node,
          x: PAD + col * (NODE_W + COL_GAP),
          y: PAD + row * (NODE_H + ROW_GAP),
        });
      });
    }

    const cols = sortedCols.length || 1;
    const width = PAD * 2 + cols * NODE_W + (cols - 1) * COL_GAP;
    const height = PAD * 2 + maxRows * NODE_H + (maxRows - 1) * ROW_GAP;
    return { positioned, width: Math.max(width, 320), height: Math.max(height, 120) };
  }, [dag]);

  const byId = useMemo(() => {
    const m = new Map<string, Positioned>();
    positioned.forEach((p) => m.set(p.id, p));
    return m;
  }, [positioned]);

  // Deduplicate edges (a step can have both a dependency + conditional edge from
  // the same source); prefer the conditional flag for styling.
  const edges = useMemo(() => {
    const seen = new Map<string, boolean>();
    for (const e of dag.edges) {
      const key = `${e.from}->${e.to}`;
      seen.set(key, seen.get(key) || e.type === "conditional");
    }
    return Array.from(seen.entries()).map(([key, conditional]) => {
      const [from, to] = key.split("->");
      return { from, to, conditional };
    });
  }, [dag]);

  if (dag.nodes.length === 0) {
    return (
      <div className="card flex h-40 items-center justify-center text-sm text-gray-500">
        This workflow has no steps to display.
      </div>
    );
  }

  return (
    <div className="overflow-auto rounded-lg border border-gray-200 bg-white p-4">
      <svg
        role="img"
        aria-label="Workflow DAG"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="min-w-full"
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>

        {edges.map(({ from, to, conditional }) => {
          const a = byId.get(from);
          const b = byId.get(to);
          if (!a || !b) return null;
          const x1 = a.x + NODE_W;
          const y1 = a.y + NODE_H / 2;
          const x2 = b.x;
          const y2 = b.y + NODE_H / 2;
          const mx = (x1 + x2) / 2;
          const d = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
          return (
            <path
              key={`${from}->${to}`}
              d={d}
              fill="none"
              stroke="#94a3b8"
              strokeWidth={1.5}
              strokeDasharray={conditional ? "5 4" : undefined}
              markerEnd="url(#arrow)"
            />
          );
        })}

        {positioned.map((node) => {
          const style = stepStatusStyle(node.status);
          return (
            <g key={node.id} data-testid={`dag-node-${node.id}`}>
              <rect
                x={node.x}
                y={node.y}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill="#ffffff"
                stroke={style.color}
                strokeWidth={2}
              />
              <rect
                x={node.x}
                y={node.y}
                width={6}
                height={NODE_H}
                rx={3}
                fill={style.color}
              />
              <text
                x={node.x + 18}
                y={node.y + 24}
                className="fill-gray-900"
                fontSize="13"
                fontWeight="600"
              >
                {node.id.length > 18 ? node.id.slice(0, 17) + "…" : node.id}
              </text>
              <text x={node.x + 18} y={node.y + 42} fontSize="11" fill="#6b7280">
                {node.task}
              </text>
              <text
                x={node.x + 18}
                y={node.y + 56}
                fontSize="10"
                fontWeight="600"
                fill={style.color}
              >
                {style.label}
                {node.conditional ? " · conditional" : ""}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
