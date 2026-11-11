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

/** One figure as the API gave it; left out when the API sent none (never shown as Rs 0). */
function Row({
  term,
  amount,
  show = rupees,
}: {
  term: string;
  amount: string | null;
  show?: (amount: string) => string;
}) {
  if (amount === null) {
    return null;
  }
  return (
    <>
      <dt>{term}</dt>
      <dd>{show(amount)}</dd>
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
          <Row term="Salary tax" amount={result.salary_tax} />
          <Row term="Surcharge" amount={result.surcharge} />
          <Row
            term="After tax deducted by employers"
            amount={result.salary_balance}
            show={(balance) => balanceWords(balance, "over-deducted")}
          />
        </dl>
      </section>
      <section aria-labelledby="profit-heading">
        <h2 id="profit-heading">Bank profit</h2>
        <dl>
          <Row term="Tax on bank profit" amount={result.profit_tax} />
          <Row
            term="After tax withheld by banks"
            amount={result.profit_balance}
            show={(balance) => balanceWords(balance, "over-withheld")}
          />
          <Row
            term="Not on the ATL"
            amount={result.non_atl_extra_withheld}
            show={(extra) =>
              `${rupees(extra)} extra tax withheld; whether it can be reclaimed needs confirmation`
            }
          />
        </dl>
      </section>
      <h2 id="breakdown-heading">How it was worked out</h2>
      <ol aria-labelledby="breakdown-heading">
        {result.steps.map((step, index) => (
          <li key={`${index}-${step.description}`}>
            {step.description}
            <br />
            <small>Source: {step.rule_location}</small>
          </li>
        ))}
      </ol>
    </>
  );
}
