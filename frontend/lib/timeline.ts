import type { Agent, StepEvent } from "./api";

export type TimelineItem = {
  agent: Agent;
  status: "running" | "done";
  message: string;
  detail?: StepEvent["output"];
  pages?: StepEvent["pages"];
};

/** Fold a stream of step events into one timeline row per agent turn. */
export function applyStep(items: TimelineItem[], step: StepEvent): TimelineItem[] {
  const last = items[items.length - 1];
  if (step.status === "started" || !last || last.agent !== step.agent || last.status === "done") {
    if (step.status === "started") {
      return [...items, { agent: step.agent, status: "running", message: step.message ?? "" }];
    }
  }
  if (!last || last.agent !== step.agent) return items;
  const updated: TimelineItem =
    step.status === "progress"
      ? { ...last, message: step.message ?? last.message, pages: step.pages ?? last.pages }
      : { ...last, status: "done", detail: step.output };
  return [...items.slice(0, -1), updated];
}
