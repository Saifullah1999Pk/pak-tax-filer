// The one rule for every amount box in the app (the lead, 2026-11-16: "make 1 rule in React and
// apply where[ever]"). MoneyInput applies it as the user types; forms check `amountError` before
// sending. Each page passes the rule its own backend accepts, and the server still checks
// (it stays the authority). Text only: nothing here calculates with an amount (Principle I).

export type AmountRule = {
  /** Places after the point: 0 for whole rupees, 2 where paisa are allowed. */
  decimals: 0 | 2;
  /** A leading minus (only last year's net assets on the wealth statement). */
  allowNegative: boolean;
  /** Digits allowed before the point. */
  maxDigits: number;
};

export const WHOLE_RUPEES: AmountRule = {
  decimals: 0,
  allowNegative: false,
  maxDigits: 14,
};

/**
 * The typed text with everything the rule doesn't allow taken out: letters, "Rs", commas and
 * spaces; any "." after the first; any "-" after the start. A leading "-" and the first "."
 * always stay, even where the rule doesn't allow them: dropping them would quietly turn -500
 * into 500 or 100.50 into 10050, so `amountError` says why instead.
 */
export function cleanAmount(raw: string): string {
  const negative = raw.trimStart().startsWith("-");
  let digits = "";
  let point = false;
  for (const char of raw) {
    if (char >= "0" && char <= "9") {
      digits += char;
    } else if (char === "." && !point) {
      digits += char;
      point = true;
    }
  }
  return (negative ? "-" : "") + digits;
}

/** Why a (cleaned) amount can't be sent, or null when it can (or the box is empty). */
export function amountError(value: string, rule: AmountRule): string | null {
  if (value === "") {
    return null;
  }
  if (value.startsWith("-") && !rule.allowNegative) {
    return "Can't be negative.";
  }
  const [whole, fraction] = value.replace(/^-/, "").split(".");
  if (whole === "" && (fraction ?? "") === "") {
    return "Enter an amount, e.g. 250000.";
  }
  if (whole.length > rule.maxDigits) {
    return rule.decimals > 0
      ? `At most ${rule.maxDigits} digits before the decimal point.`
      : `At most ${rule.maxDigits} digits.`;
  }
  if (fraction !== undefined && fraction.length > rule.decimals) {
    return rule.decimals > 0
      ? `At most ${rule.decimals} decimal places.`
      : "Whole rupees only.";
  }
  return null;
}
