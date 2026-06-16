"use client";

import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { RunListItem } from "@/types";
import { runStatusStyle } from "@/lib/status";

interface Props {
  runs: RunListItem[];
}

/** Small run-status summary pie. Counts runs by aggregate status. */
export default function RunStatusChart({ runs }: Props) {
  const counts = runs.reduce<Record<string, number>>((acc, r) => {
    const key = (r.status || "unknown").toLowerCase();
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  const data = Object.entries(counts).map(([status, value]) => ({
    status,
    value,
    label: runStatusStyle(status).label,
    color: runStatusStyle(status).color,
  }));

  if (runs.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-gray-400">
        No runs to summarize yet.
      </div>
    );
  }

  return (
    <div data-testid="run-status-chart" className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={42}
            outerRadius={68}
            paddingAngle={2}
          >
            {data.map((entry) => (
              <Cell key={entry.status} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number, _name, item: any) => [
              value,
              item?.payload?.label ?? "",
            ]}
          />
          <Legend
            iconType="circle"
            formatter={(_value, _entry, index) => data[index]?.label ?? ""}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
