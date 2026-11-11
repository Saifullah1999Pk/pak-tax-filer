import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router";
import { askQuestion } from "../api/ask";
import type { AskResult, Citation } from "../api/ask";
import { ApiError } from "../api/client";

// The tax assistant (feature 006, tasks T014 and T018). Answers come only from FBR's texts and
// are checked by the backend before they arrive; this page shows them, their sources and the
// practitioner label, and writes no answer text of its own (constitution, Principle IV).

/** Shown whether or not a question has been asked (FR-008). */
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";
const MAX_LENGTH = 1000;
/** Searching takes about a second; after that the wait is for the written answer (FR-017). */
const SEARCH_STEP_MS = 1500;
const TAX_PAGE_WORDS = "open the Tax page";

type Progress = "searching" | "writing" | null;

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<Progress>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    // A new question replaces the last answer.
    setResult(null);
    setError(null);
    setProgress("searching");
    timer.current = window.setTimeout(
      () => setProgress((now) => (now === null ? null : "writing")),
      SEARCH_STEP_MS,
    );
    try {
      setResult(await askQuestion(question));
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Couldn't reach the tax assistant. Check your connection and try again.",
      );
    } finally {
      window.clearTimeout(timer.current);
      setProgress(null);
    }
  }

  return (
    <main>
      <h1>Ask about your tax</h1>
      <p>
        Answers come only from the Income Tax Ordinance and FBR&apos;s
        return-filing manual, with the section or chapter each one is from.
      </p>
      <form className="ask-form" onSubmit={submit}>
        <label htmlFor="question">Your question</label>
        <textarea
          id="question"
          value={question}
          maxLength={MAX_LENGTH}
          rows={3}
          required
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" disabled={progress !== null}>
          Ask
        </button>
      </form>
      <p role="status">
        {progress === "searching" && "Searching the FBR texts…"}
        {progress === "writing" && "Writing a cited answer…"}
      </p>
      {error !== null && <p role="alert">{error}</p>}
      {result !== null && <Answer result={result} />}
      <p className="notice">{result?.label ?? LABEL}</p>
    </main>
  );
}

function Answer({ result }: { result: AskResult }) {
  return (
    <section className="panel ask-answer" aria-label="Answer">
      <p>{result.answer}</p>
      {result.uncovered_part !== null && <p>{result.uncovered_part}</p>}
      {result.tax_page_line !== null && (
        <TaxPageLine line={result.tax_page_line} />
      )}
      {result.citations.length > 0 && (
        <>
          <h2 id="sources-heading">Sources</h2>
          <ul aria-labelledby="sources-heading" className="sources">
            {result.citations.map((citation) => (
              <Source
                key={`${citation.title} ${citation.location}`}
                citation={citation}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/** The backend's fixed line, with its "open the Tax page" words made a link. */
function TaxPageLine({ line }: { line: string }) {
  const at = line.indexOf(TAX_PAGE_WORDS);
  if (at === -1) {
    return (
      <p>
        {line} <Link to="/tax">{TAX_PAGE_WORDS}</Link>
      </p>
    );
  }
  return (
    <p>
      {line.slice(0, at)}
      <Link to="/tax">{TAX_PAGE_WORDS}</Link>
      {line.slice(at + TAX_PAGE_WORDS.length)}
    </p>
  );
}

function Source({ citation }: { citation: Citation }) {
  return (
    <li>
      <span className="badge" data-kind={citation.kind}>
        {citation.kind === "law" ? "Law" : "Guidance"}
      </span>{" "}
      {citation.title}, {citation.location}, page {citation.page}
    </li>
  );
}
