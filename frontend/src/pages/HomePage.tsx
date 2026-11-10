import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { apiFetch } from "../api/client";
import { listDocuments } from "../api/documents";
import type { DocumentSummary } from "../api/documents";
import type { User } from "../auth/AuthContext";
import { filingSteps } from "../home/steps";
import type { FilingStep } from "../home/steps";
import { useProfile } from "../profile/ProfileContext";

/**
 * The protected home page (task T028): it asks the API who is logged in, so a session that
 * ended elsewhere is noticed here and the user is sent back to log in (FR-013). It shows the
 * filing checklist: the four steps, what's done and what's next (feature 001, task T052).
 */
export function HomePage() {
  const { profile } = useProfile();
  const [user, setUser] = useState<User | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    apiFetch<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        // A 401 is handled by the API helper (back to login); nothing else to do here.
      });
  }, []);

  const loadDocuments = useCallback(() => {
    listDocuments()
      .then((loaded) => {
        setDocuments(loaded);
        setFailed(false);
      })
      .catch(() => setFailed(true));
  }, []);

  useEffect(loadDocuments, [loadDocuments]);

  function retry() {
    setFailed(false);
    loadDocuments();
  }

  // RequireProfile renders this page only once the profile has loaded.
  if (profile === null) {
    return null;
  }
  const steps = filingSteps(profile, failed ? null : documents);

  return (
    <main>
      <div className="page-intro">
        <h1>Your tax return for {profile.tax_year}</h1>
        {user && <p className="lede">Logged in as {user.email}</p>}
      </div>
      {failed && (
        <div role="alert">
          <p>
            Couldn't load your documents, so the steps below can't show where
            you are.
          </p>
          <button type="button" onClick={retry}>
            Try again
          </button>
        </div>
      )}
      {!failed && documents === null && (
        <p role="status">Loading your documents…</p>
      )}
      <h2 id="steps-heading" className="visually-hidden">
        Your steps
      </h2>
      {/* role="list": Safari drops the list role when list-style is none. */}
      <ol className="steps" aria-labelledby="steps-heading" role="list">
        {steps.map((step, index) => (
          <Step key={step.key} step={step} number={index + 1} />
        ))}
      </ol>
    </main>
  );
}

const TAGS = { done: "Done", next: "Next", todo: null };

function Step({ step, number }: { step: FilingStep; number: number }) {
  const tag = TAGS[step.state];
  return (
    <li
      className="step"
      data-state={step.state}
      aria-current={step.state === "next" ? "step" : undefined}
    >
      <span className="step-marker" aria-hidden="true">
        {step.state === "done" ? <Tick /> : number}
      </span>
      <div className="step-body">
        <h3>
          {step.title}
          {tag && (
            <>
              {" "}
              <span className="step-tag">{tag}</span>
            </>
          )}
        </h3>
        {step.detail !== null && <p className="step-detail">{step.detail}</p>}
        <Link
          to={step.action.to}
          className={
            step.state === "next" ? "button button-primary" : undefined
          }
        >
          {step.action.text}
        </Link>
      </div>
    </li>
  );
}

function Tick() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}
