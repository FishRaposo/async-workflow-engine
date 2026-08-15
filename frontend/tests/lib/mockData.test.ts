import { describe, expect, it } from "vitest";
import { mockRunDetails } from "@/lib/mockData";

describe("dashboard runtime fixtures", () => {
  it("includes additive version and trace metadata on a representative run", () => {
    const run = mockRunDetails["11111111-1111-1111-1111-111111111111"];

    expect(run.version_hash).toMatch(/^[a-f0-9]{64}$/);
    expect(run.events?.map((event) => event.kind)).toEqual([
      "trigger.received",
      "run.started",
      "step.started",
      "step.completed",
      "run.finished",
    ]);
  });
});
