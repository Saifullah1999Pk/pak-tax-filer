import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { rupees } from "../api/tax";
import {
  ASSET_CATEGORIES,
  EXPENSE_CATEGORIES,
  getWealth,
  saveWealth,
} from "../api/wealth";
import type {
  AutoFilledLine,
  StatementIn,
  Wealth,
  WealthResult,
} from "../api/wealth";
import { useProfile } from "../profile/ProfileContext";

// The wealth statement for the profile's tax year (feature 005, tasks T011, T017, T023). The
// user enters what they own, owe and spent; the backend fills in the certificate lines and
// reconciles. This page only displays its figures (constitution, Principles I and IV).

type Asset = {
  key: number;
  category: string;
  description: string;
  amount: string;
};
type Liability = {
  key: number;
  description: string;
  creditor: string;
  amount: string;
};
type Form = Omit<
  StatementIn,
  "assets" | "liabilities" | "previous_net_assets"
> & {
  previous_net_assets: string;
  assets: Asset[];
  liabilities: Liability[];
};

const MONEY_FIELDS: [keyof Form, string][] = [
  ["other_exempt_income", "Other exempt income"],
  ["foreign_remittance", "Foreign remittance"],
  ["inheritance", "Inheritance"],
  ["gifts_received", "Gifts received"],
  ["family_contribution", "Family members' contribution to expenses"],
  ["gifts_given", "Gifts given"],
];

let nextKey = 0;
const key = () => ++nextKey;

function toForm(statement: Wealth["statement"]): Form {
  return {
    ...statement,
    previous_net_assets: statement.previous_net_assets ?? "",
    assets: statement.assets.map((a) => ({ key: key(), ...a })),
    liabilities: statement.liabilities.map((l) => ({
      key: key(),
      ...l,
      creditor: l.creditor ?? "",
    })),
  };
}

/** The statement as the API takes it: empty amounts are zero, an empty previous figure is
 * "not entered". The server checks every rule. */
function toStatement(form: Form): StatementIn {
  const zero = (value: string) => value.trim() || "0";
  return {
    previous_net_assets: form.previous_net_assets.trim() || null,
    assets: form.assets.map(({ category, description, amount }) => ({
      category,
      description,
      amount: zero(amount),
    })),
    liabilities: form.liabilities.map(({ description, creditor, amount }) => ({
      description,
      creditor: creditor.trim() || null,
      amount: zero(amount),
    })),
    other_exempt_income: zero(form.other_exempt_income),
    foreign_remittance: zero(form.foreign_remittance),
    inheritance: zero(form.inheritance),
    gifts_received: zero(form.gifts_received),
    family_contribution: zero(form.family_contribution),
    gifts_given: zero(form.gifts_given),
    expenses: Object.fromEntries(
      Object.entries(form.expenses).filter(([, value]) => value.trim() !== ""),
    ),
  };
}

export function WealthPage() {
  const { profile } = useProfile();
  // RequireProfile renders this page only once the profile has loaded.
  const taxYear = profile?.tax_year ?? "";
  const [wealth, setWealth] = useState<Wealth | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let current = true;
    if (taxYear === "") {
      return;
    }
    getWealth(taxYear)
      .then((loaded) => {
        if (current) {
          setWealth(loaded);
          setForm(toForm(loaded.statement));
        }
      })
      .catch((caught: unknown) => {
        if (current) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Couldn't load your wealth statement. Try again.",
          );
        }
      });
    return () => {
      current = false;
    };
  }, [taxYear]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form === null) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = await saveWealth(taxYear, toStatement(form));
      setWealth(saved);
      setForm(toForm(saved.statement));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Couldn't save. Try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  const update = (changes: Partial<Form>) =>
    setForm((current) => (current ? { ...current, ...changes } : current));

  return (
    <main>
      <h1>Wealth statement for {taxYear}</h1>
      {error !== null && <p role="alert">{error}</p>}
      {wealth === null || form === null ? (
        error === null && <p role="status">Loading…</p>
      ) : (
        <>
          <p className="notice">{wealth.label}</p>
          {wealth.certificates_changed && (
            <p role="status">
              Your confirmed certificates changed since you last saved. Check
              the result below and save again.
            </p>
          )}
          <form onSubmit={handleSave}>
            <Assets form={form} update={update} />
            <Liabilities form={form} update={update} />
            <MoneyInAndOut
              form={form}
              update={update}
              autoFilled={wealth.auto_filled}
            />
            <button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </form>
          <Result result={wealth.result} />
        </>
      )}
      <nav>
        <Link to="/">Home</Link>
      </nav>
    </main>
  );
}

type FormProps = { form: Form; update: (changes: Partial<Form>) => void };

function Assets({ form, update }: FormProps) {
  const change = (k: number, changes: Partial<Asset>) =>
    update({
      assets: form.assets.map((a) => (a.key === k ? { ...a, ...changes } : a)),
    });
  return (
    <section aria-labelledby="own-heading">
      <h2 id="own-heading">What I own</h2>
      <p>Each asset at its cost, as on 30 June 2026.</p>
      {form.assets.map((asset) => (
        <fieldset key={asset.key}>
          <label>
            Category
            <select
              value={asset.category}
              onChange={(e) => change(asset.key, { category: e.target.value })}
            >
              {ASSET_CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Description
            <input
              value={asset.description}
              maxLength={200}
              onChange={(e) =>
                change(asset.key, { description: e.target.value })
              }
            />
          </label>
          <label>
            Amount
            <input
              inputMode="numeric"
              value={asset.amount}
              onChange={(e) => change(asset.key, { amount: e.target.value })}
            />
          </label>
          <button
            type="button"
            onClick={() =>
              update({ assets: form.assets.filter((a) => a.key !== asset.key) })
            }
          >
            Remove {asset.description || "this asset"}
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        onClick={() =>
          update({
            assets: [
              ...form.assets,
              {
                key: key(),
                category: "bank_account",
                description: "",
                amount: "",
              },
            ],
          })
        }
      >
        Add an asset
      </button>
    </section>
  );
}

function Liabilities({ form, update }: FormProps) {
  const change = (k: number, changes: Partial<Liability>) =>
    update({
      liabilities: form.liabilities.map((l) =>
        l.key === k ? { ...l, ...changes } : l,
      ),
    });
  return (
    <section aria-labelledby="owe-heading">
      <h2 id="owe-heading">What I owe</h2>
      {form.liabilities.map((row) => (
        <fieldset key={row.key}>
          <label>
            Description
            <input
              value={row.description}
              maxLength={200}
              onChange={(e) => change(row.key, { description: e.target.value })}
            />
          </label>
          <label>
            Creditor
            <input
              value={row.creditor}
              maxLength={200}
              onChange={(e) => change(row.key, { creditor: e.target.value })}
            />
          </label>
          <label>
            Amount
            <input
              inputMode="numeric"
              value={row.amount}
              onChange={(e) => change(row.key, { amount: e.target.value })}
            />
          </label>
          <button
            type="button"
            onClick={() =>
              update({
                liabilities: form.liabilities.filter((l) => l.key !== row.key),
              })
            }
          >
            Remove {row.description || "this liability"}
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        onClick={() =>
          update({
            liabilities: [
              ...form.liabilities,
              { key: key(), description: "", creditor: "", amount: "" },
            ],
          })
        }
      >
        Add a liability
      </button>
    </section>
  );
}

function MoneyInAndOut({
  form,
  update,
  autoFilled,
}: FormProps & { autoFilled: AutoFilledLine[] }) {
  return (
    <section aria-labelledby="money-heading">
      <h2 id="money-heading">Money in and out</h2>
      <h3 id="certificates-heading">From your certificates</h3>
      <ul aria-labelledby="certificates-heading">
        {autoFilled.map((line) => (
          <li key={line.label}>
            <strong>
              {line.label}
              {line.line ? ` (${line.line})` : ""}
            </strong>{" "}
            <span>{rupees(line.amount)}</span>{" "}
            <small>
              {line.certificates.length
                ? `From: ${line.certificates.join(", ")}`
                : "No confirmed certificate"}
            </small>
            {line.provisional && <small> (provisional)</small>}
          </li>
        ))}
      </ul>
      <p>
        These come from your confirmed certificates and can't be changed here.
        To correct one, correct the certificate: delete it on{" "}
        <Link to="/documents">Documents</Link> and upload it again.
      </p>
      <label>
        Net assets on 30 June 2025 (from last year's statement)
        <input
          inputMode="numeric"
          value={form.previous_net_assets}
          onChange={(e) => update({ previous_net_assets: e.target.value })}
        />
      </label>
      {MONEY_FIELDS.map(([field, label]) => (
        <label key={field}>
          {label}
          <input
            inputMode="numeric"
            value={form[field] as string}
            onChange={(e) => update({ [field]: e.target.value })}
          />
        </label>
      ))}
      <h3>Personal expenses</h3>
      {EXPENSE_CATEGORIES.map(([category, label]) => (
        <label key={category}>
          {label}
          <input
            inputMode="numeric"
            value={form.expenses[category] ?? ""}
            onChange={(e) =>
              update({
                expenses: { ...form.expenses, [category]: e.target.value },
              })
            }
          />
        </label>
      ))}
    </section>
  );
}

function Result({ result }: { result: WealthResult }) {
  return (
    <section aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
      <p>{result.message}</p>
      {result.not_ready_reason === null && (
        <>
          {result.where_to_look.length > 0 && (
            <>
              <h3 id="look-heading">Where to look</h3>
              <ul aria-labelledby="look-heading">
                {result.where_to_look.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {result.summary !== null && (
            <section aria-labelledby="wealth-summary-heading">
              <h3 id="wealth-summary-heading">Summary</h3>
              <p>{result.summary}</p>
            </section>
          )}
          <h3 id="wealth-breakdown-heading">How it was worked out</h3>
          <ol aria-labelledby="wealth-breakdown-heading">
            {result.steps.map((step, index) => (
              <li key={`${index}-${step.form_line}`}>
                {step.description}
                <br />
                <small>Form line {step.form_line}</small>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
