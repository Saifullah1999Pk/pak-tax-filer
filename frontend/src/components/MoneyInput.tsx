import { useId } from "react";
import type { ChangeEvent, InputHTMLAttributes } from "react";
import { groupedAmount } from "../api/tax";
import { WHOLE_RUPEES, amountError, cleanAmount } from "./amountRule";
import type { AmountRule } from "./amountRule";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  /** What this box accepts (default: whole rupees, not negative, 14 digits). */
  rule?: AmountRule;
};

/**
 * An amount field with "Rs" shown inside it (feature 001, task T060, FR-032), and the value
 * repeated beneath with digit grouping so long figures are easy to check (task T066). Both are
 * visual only and hidden from screen readers, so the field's name and value are unchanged.
 *
 * Every amount box in the app applies the one amount rule here (the lead, 2026-11-16): letters,
 * "Rs", commas and spaces never reach the value, and an amount the rule refuses is marked
 * (`aria-invalid`) and explained beside the box. Forms also check `amountError` before sending;
 * the server still checks too.
 */
export function MoneyInput({ rule = WHOLE_RUPEES, ...props }: Props) {
  const errorId = useId();
  const value = typeof props.value === "string" ? props.value : "";
  const error = amountError(value, rule);
  const grouped = error === null ? groupedAmount(props.value) : null;
  const describedBy = [props["aria-describedby"], error !== null ? errorId : ""]
    .filter(Boolean)
    .join(" ");

  const change = (event: ChangeEvent<HTMLInputElement>) => {
    const cleaned = cleanAmount(event.target.value);
    if (cleaned !== event.target.value) {
      event.target.value = cleaned;
    }
    props.onChange?.(event);
  };

  return (
    <span className="money-input">
      <span className="money-field">
        <input
          // Phone keypads: digits only for whole rupees; with a point for paisa; plain text
          // where a minus may be typed (numeric keypads lack one). A page may override.
          inputMode={
            rule.allowNegative
              ? "text"
              : rule.decimals > 0
                ? "decimal"
                : "numeric"
          }
          {...props}
          aria-invalid={error !== null ? true : props["aria-invalid"]}
          aria-describedby={describedBy || undefined}
          onChange={change}
        />
      </span>
      {grouped !== null && (
        <span className="amount-preview" aria-hidden="true">
          {grouped}
        </span>
      )}
      {error !== null && (
        <span id={errorId} className="amount-error" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
