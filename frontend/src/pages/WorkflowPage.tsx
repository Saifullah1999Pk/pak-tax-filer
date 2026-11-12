import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { rupees } from "../api/tax";
import { getRun, startRun } from "../api/workflow";
import type { Passage, Run, Step } from "../api/workflow";

// The guided run (feature 007, task T011): documents, figures and the law that applies, then
// the approval gate. Every message and figure comes from the backend, which checked them; the
// page computes nothing (Principle I) and shows which texts the app wrote without the AI.

/** Shown in turn while steps 1-3 run in one request (FR-019, research R10). */
const PROGRESS = [
  "Checking your documents…",
  "Checking the figures…",
  "Finding the law that applies…",
];
const PROGRESS_STEP_MS = 2000;
const PLAIN = "Written by the app (the AI wasn't used)";

/** The indicator's labels; validate and research both show as their own step. */
const STEPS: { label: string; steps: Step[] }[] = [
  { label: "Documents", steps: ["document"] },
  { label: "Figures", steps: ["validate"] },
  { label: "Law", steps: ["research"] },
  { label: "Approve", steps: ["gate"] },
  { label: "Result", steps: ["result", "done"] },
];

type Loaded =
  { kind: "loading" } | { kind: "none" } | { kind: "run"; run: Run };

export function WorkflowPage() {
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let current = true;
    getRun()
      .then((run) => current && setLoaded({ kind: "run", run }))
      .catch((caught: unknown) => {
        if (!current) return;
        if (caught instanceof ApiError && caught.status === 404) {
          setLoaded({ kind: "none" });
        } else {
          setError(message(caught));
        }
      });
    return () => {
      current = false;
      window.clearInterval(timer.current);
    };
  }, []);

  async function start() {
    if (progress !== null) return;
    setError(null);
    setProgress(0);
    timer.current = window.setInterval(
      () =>
        setProgress((now) =>
          now === null ? null : Math.min(now + 1, PROGRESS.length - 1),
        ),
      PROGRESS_STEP_MS,
    );
    try {
      setLoaded({ kind: "run", run: await startRun() });
    } catch (caught: unknown) {
      setError(message(caught));
    } finally {
      window.clearInterval(timer.current);
      setProgress(null);
    }
  }

  const run = loaded.kind === "run" ? loaded.run : null;
  return (
    <main>
      <h1>Guided filing</h1>
      <p>
        PakTaxFiler checks your documents and figures, finds the parts of the
        tax law that apply to you, and then stops for you to approve before
        anything is calculated.
      </p>
      {run && <StepIndicator step={run.step} />}
      <p role="status">{progress !== null && PROGRESS[progress]}</p>
      {error !== null && <p role="alert">{error}</p>}
      {loaded.kind === "none" && (
        <button
          type="button"
          className="button-primary"
          aria-disabled={progress !== null}
          onClick={start}
        >
          Start
        </button>
      )}
      {run && <RunView run={run} />}
    </main>
  );
}

function message(caught: unknown): string {
  return caught instanceof ApiError
    ? caught.message
    : "Couldn't reach PakTaxFiler. Check your connection and try again.";
}

function StepIndicator({ step }: { step: Step }) {
  return (
    <ol className="run-steps" aria-label="Steps" role="list">
      {STEPS.map(({ label, steps }) => (
        <li
          key={label}
          aria-current={steps.includes(step) ? "step" : undefined}
        >
          {label}
        </li>
      ))}
    </ol>
  );
}

function RunView({ run }: { run: Run }) {
  return (
    <>
      {run.document && (
        <section className="panel" aria-labelledby="documents-heading">
          <h2 id="documents-heading">Your documents</h2>
          <p>{run.document.message}</p>
          {run.document.fallback && <PlainNote />}
          {run.document.missing.length > 0 && (
            <Link to="/documents" className="button button-primary">
              Go to documents
            </Link>
          )}
        </section>
      )}
      {run.gate && <Gate run={run} />}
    </>
  );
}

function PlainNote() {
  return <p className="plain-note">{PLAIN}</p>;
}

function Gate({ run }: { run: Run }) {
  const gate = run.gate!;
  return (
    <section className="panel" aria-labelledby="gate-heading">
      <h2 id="gate-heading">Before you approve</h2>
      <dl className="gate-figures">
        <dt>Tax year</dt>
        <dd>{run.tax_year}</dd>
        <dt>On the Active Taxpayers' List</dt>
        <dd>{gate.on_atl ? "Yes" : "No"}</dd>
        <dt>Taxable salary</dt>
        <dd>{rupees(gate.figures.taxable_salary)}</dd>
        <dt>Tax deducted by employers</dt>
        <dd>{rupees(gate.figures.tax_deducted)}</dd>
        <dt>Bank profit</dt>
        <dd>{rupees(gate.figures.gross_profit)}</dd>
        <dt>Tax withheld by banks</dt>
        <dd>{rupees(gate.figures.tax_withheld)}</dd>
      </dl>
      {run.validation && (
        <>
          <h3>Your figures</h3>
          <p>{run.validation.message}</p>
          {run.validation.fallback && <PlainNote />}
          {run.validation.issues.length > 0 && (
            <ul className="issues">
              {run.validation.issues.map((issue) => (
                <li key={`${issue.document_id} ${issue.field}`}>
                  {issue.certificate}: {issue.reason}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {run.research && (
        <>
          <h3 id="law-heading">The law that applies</h3>
          <p>{run.research.note}</p>
          {run.research.fallback && <PlainNote />}
          {run.research.passages.length > 0 && (
            <ul
              className="sources"
              aria-label="Where this comes from"
              role="list"
            >
              {run.research.passages.map((passage) => (
                <Source key={passage.id} passage={passage} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function Source({ passage }: { passage: Passage }) {
  return (
    <li>
      <span className="badge" data-kind={passage.kind}>
        {passage.kind === "law" ? "Law" : "Guidance"}
      </span>{" "}
      {passage.source}, {passage.location}, page {passage.page}
    </li>
  );
}
