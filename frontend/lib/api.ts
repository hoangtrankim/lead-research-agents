import { SseParser } from "./sse";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Agent = "researcher" | "writer" | "reviewer";

export type Profile = {
  name: string;
  summary: string;
  industry: string;
  products: string[];
  customers: string;
  signals: string[];
  likely_needs: string[];
};
export type Email = { subject: string; body: string; personalization: string[] };
export type Review = {
  score: number;
  strengths: string[];
  problems: string[];
  unsupported_claims: string[];
  feedback: string;
};
export type PageRef = { url: string; title: string };

export type StepEvent = {
  agent: Agent;
  status: "started" | "progress" | "finished";
  message?: string;
  pages?: PageRef[];
  output?: { profile?: Profile; draft?: Email; review?: Review; approved?: boolean };
};

export type RunResult = {
  profile: Profile;
  email: Email;
  review: Review;
  approved: boolean;
  revisions: number;
  pages: PageRef[];
  cost: { input_tokens: number; output_tokens: number; usd: number };
};

export type RunInput = { company_url: string; offer: string; sender_name: string; language: string };

export type RunHandlers = {
  onStep: (step: StepEvent) => void;
  onResult: (result: RunResult) => void;
  onError: (message: string) => void;
};

export async function startRun(input: RunInput, handlers: RunHandlers, signal?: AbortSignal): Promise<void> {
  const res = await fetch(`${API_URL}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    signal,
  });
  if (!res.ok || !res.body) {
    handlers.onError(res.status === 422 ? "Please check the form fields." : `Request failed (${res.status})`);
    return;
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SseParser();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const { event, data } of parser.push(value)) {
      if (event === "step") handlers.onStep(data as StepEvent);
      else if (event === "result") handlers.onResult(data as RunResult);
      else if (event === "error") handlers.onError(String((data as { message?: string }).message ?? "Something went wrong."));
    }
  }
}
