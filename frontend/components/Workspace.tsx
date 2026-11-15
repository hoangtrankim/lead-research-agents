"use client";

import { useRef, useState } from "react";
import GraphView from "./GraphView";
import { startRun, type Agent, type RunResult } from "@/lib/api";
import { applyStep, type TimelineItem } from "@/lib/timeline";

const AGENT_NAME: Record<Agent, string> = { researcher: "Researcher", writer: "Writer", reviewer: "Reviewer" };

export default function Workspace() {
  const [form, setForm] = useState({ company_url: "", offer: "", sender_name: "", language: "English" });
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (running) return;
    setItems([]);
    setResult(null);
    setError(null);
    setRunning(true);
    abort.current = new AbortController();
    try {
      await startRun(
        form,
        {
          onStep: (step) => setItems((prev) => applyStep(prev, step)),
          onResult: setResult,
          onError: setError,
        },
        abort.current.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError("Could not reach the API. Is the backend running?");
    } finally {
      setRunning(false);
    }
  }

  async function copyEmail() {
    if (!result) return;
    await navigator.clipboard.writeText(`Subject: ${result.email.subject}\n\n${result.email.body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const last = items[items.length - 1];
  const active = running && last?.status === "running" ? last.agent : null;
  const done = new Set(items.filter((i) => i.status === "done").map((i) => i.agent));
  const looping = items.filter((i) => i.agent === "writer").length > 1 && active === "writer";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">◆</span> LeadScout
        </div>
        <p className="tagline">A team of three AI agents researches a company and writes a personalized outreach email.</p>
        <form onSubmit={submit}>
          <label>
            Company website
            <input value={form.company_url} onChange={set("company_url")} placeholder="https://example.com" required minLength={3} />
          </label>
          <label>
            What you offer
            <textarea
              value={form.offer}
              onChange={set("offer")}
              placeholder="e.g. We build AI support chatbots that answer customer questions 24/7 from your own documents."
              rows={4}
              required
              minLength={10}
            />
          </label>
          <label>
            Your name
            <input value={form.sender_name} onChange={set("sender_name")} placeholder="Optional" />
          </label>
          <label>
            Email language
            <select value={form.language} onChange={set("language")}>
              <option>English</option>
              <option>Vietnamese</option>
              <option>Japanese</option>
              <option>Spanish</option>
              <option>German</option>
              <option>French</option>
            </select>
          </label>
          {running ? (
            <button type="button" className="primary" onClick={() => abort.current?.abort()}>
              Stop
            </button>
          ) : (
            <button type="submit" className="primary">
              Run agents
            </button>
          )}
        </form>
      </aside>

      <main className="main">
        <section className="card">
          <h2>Workflow</h2>
          <GraphView active={active} done={done} looping={looping} finished={!!result} />
        </section>

        {items.length === 0 && !error && (
          <p className="muted empty">Enter a company website and your offer, then run the agents to watch them work.</p>
        )}

        {items.length > 0 && (
          <section className="card">
            <h2>Activity</h2>
            <ol className="timeline">
              {items.map((item, i) => (
                <li key={i} className={item.status}>
                  <span className={`dot ${item.agent}`} />
                  <div>
                    <b>{AGENT_NAME[item.agent]}</b> <span className="muted">{item.message}</span>
                    {item.pages && (
                      <div className="chips">
                        {item.pages.map((p) => (
                          <a key={p.url} href={p.url} target="_blank" rel="noreferrer noopener" className="chip">
                            {p.title || p.url}
                          </a>
                        ))}
                      </div>
                    )}
                    {item.detail?.profile && (
                      <p className="detail">
                        {item.detail.profile.name}: {item.detail.profile.summary}
                      </p>
                    )}
                    {item.detail?.draft && <p className="detail">Subject: {item.detail.draft.subject}</p>}
                    {item.detail?.review && (
                      <p className="detail">
                        <span className={`score ${item.detail.approved ? "ok" : "warn"}`}>{item.detail.review.score}/10</span>{" "}
                        {item.detail.approved ? "Approved." : item.detail.review.feedback}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {error && <p className="error card">{error}</p>}

        {result && (
          <>
            <section className="card">
              <div className="row">
                <h2>Email</h2>
                <button onClick={copyEmail}>{copied ? "Copied" : "Copy"}</button>
              </div>
              <p className="subject">{result.email.subject}</p>
              <pre className="email">{result.email.body}</pre>
              <p className="muted small">
                Reviewer score <b>{result.review.score}/10</b>
                {result.approved ? ", approved" : ", not approved (revision limit reached)"} · {result.revisions} revision(s) ·{" "}
                {(result.cost.input_tokens + result.cost.output_tokens).toLocaleString()} tokens · about ${result.cost.usd.toFixed(2)} for this run
              </p>
            </section>

            <section className="card">
              <h2>Company profile</h2>
              <p>
                <b>{result.profile.name}</b> · {result.profile.industry}
              </p>
              <p>{result.profile.summary}</p>
              <div className="cols">
                <List title="Products" items={result.profile.products} />
                <List title="Signals" items={result.profile.signals} />
                <List title="Likely needs" items={result.profile.likely_needs} />
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <ul>
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
