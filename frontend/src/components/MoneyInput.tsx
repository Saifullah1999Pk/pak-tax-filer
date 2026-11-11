import type { InputHTMLAttributes } from "react";
import { groupedAmount } from "../api/tax";

/**
 * An amount field with "Rs" shown inside it (feature 001, task T060, FR-032), and the value
 * repeated beneath with digit grouping so long figures are easy to check (task T066). Both are
 * visual only and hidden from screen readers, so the field's name and value are unchanged.
 */
export function MoneyInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const grouped = groupedAmount(props.value);
  return (
    <span className="money-input">
      <span className="money-field">
        <input {...props} />
      </span>
      {grouped !== null && (
        <span className="amount-preview" aria-hidden="true">
          {grouped}
        </span>
      )}
    </span>
  );
}
