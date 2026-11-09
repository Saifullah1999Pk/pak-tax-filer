import { useEffect, useState } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { balanceWords, getTax, rupees } from "../api/tax";
import type { TaxResult } from "../api/tax";
import { useProfile } from "../profile/ProfileContext";

// The user's tax for the profile's tax year (feature 004, tasks T013, T019, T023). Every figure
// and every refusal comes from the backend, which recalculates from confirmed certificates and
// the profile's ATL status; this page only displays them (constitution, Principles I and IV).

/** Where to go to fix a refusal the user can fix themselves. */
const FIX_LINKS: Record<string, { to: string; text: string }> = {
  needs_atl_answer: { to: "/profile", text: "Go to your profile" },
  no_confirmed_salary_certificate: {
    to: "/documents",
    text: "Go to documents",
  },
};

export function TaxPage() {
  const { profile } = useProfile();
  // RequireProfile renders this page only once the profile has loaded.
  const taxYear = profile?.tax_year ?? "";
  const [result, setResult] = useState<TaxResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    getTax(taxYear)
      .then((loaded) => current && setResult(loaded))
      .catch((caught: unknown) => {
        if (current) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Couldn't load your tax. Check your connection and try again.",
          );
        }
      });
    return () => {
      current = false;
    };
  }, [taxYear]);

  return (
    <main>
      <h1>Your tax for {taxYear}</h1>
      {error !== null && <p role="alert">{error}</p>}
      {result === null && error === null && <p role="status">Calculating…</p>}
      {result !== null && <Result result={result} />}
      <nav>
        <Link to="/">Home</Link>
      </nav>
    </main>
  );
}

function Result({ result }: { result: TaxResult }) {
  const fix = FIX_LINKS[result.blocked_reason ?? ""];
  return (
    <>
      <p className="notice">{result.label}</p>
      {result.blocked_reason !== null ? (
        <p>
          {result.message}
          {fix && (
            <>
              {" "}
              <Link to={fix.to}>{fix.text}</Link>
            </>
          )}
        </p>
      ) : (
        <Figures result={result} />
      )}
    </>
  );
}

function Figures({ result }: { result: TaxResult }) {
  return (
    <>
      {result.summary !== null && (
        <section aria-labelledby="summary-heading">
          <h2 id="summary-heading">Summary</h2>
          <p>{result.summary}</p>
        </section>
      )}
      {/* Shown separately: whether one side can be set off against the other is still
          a question for the lead, so there is no combined total (spec clarification). */}
      <section aria-labelledby="salary-heading">
        <h2 id="salary-heading">Salary</h2>
        <dl>
          <dt>Salary tax</dt>
          <dd>{rupees(result.salary_tax ?? "0")}</dd>
          <dt>Surcharge</dt>
          <dd>{rupees(result.surcharge ?? "0")}</dd>
          <dt>After tax deducted by employers</dt>
          <dd>{balanceWords(result.salary_balance ?? "0", "over-deducted")}</dd>
        </dl>
      </section>
      <section aria-labelledby="profit-heading">
        <h2 id="profit-heading">Bank profit</h2>
        <dl>
          <dt>Tax on bank profit</dt>
          <dd>{rupees(result.profit_tax ?? "0")}</dd>
          <dt>After tax withheld by banks</dt>
          <dd>{balanceWords(result.profit_balance ?? "0", "over-withheld")}</dd>
          {result.non_atl_extra_withheld !== null && (
            <>
              <dt>Not on the ATL</dt>
              <dd>
                {rupees(result.non_atl_extra_withheld)} extra withheld: to be
                confirmed whether it can be reclaimed
              </dd>
            </>
          )}
        </dl>
      </section>
      <h2 id="breakdown-heading">How it was worked out</h2>
      <ol aria-label="Breakdown">
        {result.steps.map((step) => (
          <li key={step.description}>
            {step.description}
            <br />
            <small>Source: {step.rule_location}</small>
          </li>
        ))}
      </ol>
    </>
  );
}
