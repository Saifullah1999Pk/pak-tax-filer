import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
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
  const known = !failed && documents !== null;
  const steps = filingSteps(profile, known ? documents : null);
  // The band names the next step (task T059). No count: Tax and Wealth are never "done" (see
  // home/steps.ts), so a count could never reach the end.
  const next = steps.find((step) => step.state === "next");

  return (
    <main>
      <div className="home-band">
        <h1>Your tax return for {profile.tax_year}</h1>
        {user && <p className="band-lede">Logged in as {user.email}</p>}
        {known && next && (
          <p className="band-next">
            <span className="band-next-label">Next step:</span>{" "}
            {next.action.text}
          </p>
        )}
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
          <Step
            key={step.key}
            step={step}
            number={index + 1}
            loading={!failed && documents === null}
          />
        ))}
      </ol>
      <p className="guided-offer">
        Prefer to be walked through it?{" "}
        <Link to="/workflow">Let PakTaxFiler guide you</Link>
      </p>
    </main>
  );
}

const TAGS = { done: "Done", next: "Next", todo: null };

type StepProps = { step: FilingStep; number: number; loading: boolean };

function Step({ step, number, loading }: StepProps) {
  const tag = TAGS[step.state];
  return (
    <li
      className="step"
      // Each step appears a moment after the one before (CSS; off under "reduce motion").
      style={{ "--i": number } as CSSProperties}
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
        {step.detail === null && loading && step.key !== "profile" && (
          <span className="skeleton skeleton-line" aria-hidden="true" />
        )}
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
