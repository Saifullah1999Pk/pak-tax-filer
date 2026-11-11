import type { InputHTMLAttributes } from "react";

/**
 * An amount field with "Rs" shown inside it (feature 001, task T060, FR-032). The prefix is
 * drawn by CSS and hidden from screen readers, so the field's name and value are unchanged.
 */
export function MoneyInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <span className="money-field">
      <input {...props} />
    </span>
  );
}
