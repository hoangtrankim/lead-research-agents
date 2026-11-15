import { test } from "node:test";
import assert from "node:assert/strict";
import { applyStep, type TimelineItem } from "./timeline.ts";

test("builds one row per agent turn, including revision loops", () => {
  let items: TimelineItem[] = [];
  const feed = (s: Parameters<typeof applyStep>[1]) => (items = applyStep(items, s));
  feed({ agent: "researcher", status: "started", message: "Reading" });
  feed({ agent: "researcher", status: "progress", message: "Read 2 pages", pages: [{ url: "u", title: "t" }] });
  feed({ agent: "researcher", status: "finished", output: {} });
  feed({ agent: "writer", status: "started", message: "Drafting" });
  feed({ agent: "writer", status: "finished", output: {} });
  feed({ agent: "reviewer", status: "started", message: "Reviewing" });
  feed({ agent: "reviewer", status: "finished", output: { approved: false } });
  feed({ agent: "writer", status: "started", message: "Revising" });
  assert.deepEqual(
    items.map((i) => [i.agent, i.status]),
    [["researcher", "done"], ["writer", "done"], ["reviewer", "done"], ["writer", "running"]],
  );
  assert.equal(items[0].message, "Read 2 pages");
  assert.equal(items[0].pages?.length, 1);
});
