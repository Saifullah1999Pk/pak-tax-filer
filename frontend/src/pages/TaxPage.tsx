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
  const [shownYear, setShownYear] = useState(taxYear);

  // A different year: forget the previous result (React's reset-on-change pattern).
  if (taxYear !== shownYear) {
    setShownYear(taxYear);
    setResult(null);
    setError(null);
  }

  useEffect(() => {
    let current = true;
    if (taxYear === "") {
      return;
    }
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
    </main>
  );
}

function Result({ result }: { result: TaxResult }) {
  const fix = FIX_LINKS[result.blocked_reason ?? ""];
  return (
    <>
      <p className="notice">{result.label}</p>
      {result.blocked_reason !== null ? (
        <p className="panel">
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

/** One figure as the API gave it; left out when the API sent none (never shown as Rs 0). */
function Row({ term, amount }: { term: string; amount: string | null }) {
  if (amount === null) {
    return null;
  }
  return (
    <>
      <dt>{term}</dt>
      <dd>{rupees(amount)}</dd>
    </>
  );
}

/** A side's answer in large type, with what it is beneath; nothing if the API sent none. */
function Headline({ text, caption }: { text: string | null; caption: string }) {
  if (text === null) {
    return null;
  }
  return (
    <>
      <p className="headline">{text}</p>
      <p className="hint">{caption}</p>
    </>
  );
}

const words = (balance: string | null, overpaid: string) =>
  balance === null ? null : balanceWords(balance, overpaid);

function Figures({ result }: { result: TaxResult }) {
  return (
    <>
      {/* Shown separately: whether one side can be set off against the other is still
          a question for the lead, so there is no combined total (spec clarification). Each
          side's balance is its headline, above the parts it is made of (001, task T054). */}
      <div className="headline-pair">
        <section aria-labelledby="salary-heading" className="panel">
          <h2 id="salary-heading">Salary</h2>
          <Headline
            text={words(result.salary_balance, "over-deducted")}
            caption="After tax deducted by employers"
          />
          <dl className="figures">
            <Row term="Salary tax" amount={result.salary_tax} />
            <Row term="Surcharge" amount={result.surcharge} />
          </dl>
        </section>
        <section aria-labelledby="profit-heading" className="panel">
          <h2 id="profit-heading">Bank profit</h2>
          <Headline
            text={words(result.profit_balance, "over-withheld")}
            caption="After tax withheld by banks"
          />
          <dl className="figures">
            <Row term="Tax on bank profit" amount={result.profit_tax} />
          </dl>
          {result.non_atl_extra_withheld !== null && (
            <p className="notice">
              <strong>Not on the ATL:</strong>{" "}
              <span>
                {`${rupees(result.non_atl_extra_withheld)} extra tax withheld; whether it can be reclaimed needs confirmation`}
              </span>
            </p>
          )}
        </section>
      </div>
      {result.summary !== null && (
        <section
          aria-labelledby="summary-heading"
          className="panel summary-panel"
        >
          <h2 id="summary-heading">Summary</h2>
          <p>{result.summary}</p>
        </section>
      )}
      <h2 id="breakdown-heading">How it was worked out</h2>
      <ol aria-labelledby="breakdown-heading" className="ledger" role="list">
        {result.steps.map((step, index) => (
          <li key={`${index}-${step.description}`}>
            {step.description}
            <small>Source: {step.rule_location}</small>
          </li>
        ))}
      </ol>
    </>
  );
}
