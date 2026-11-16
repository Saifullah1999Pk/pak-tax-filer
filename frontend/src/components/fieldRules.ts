// Frontend checks for the kinds of field other than amounts (amounts: amountRule.ts). The lead,
// 2026-11-16: errors caught in the frontend too, one rule applied wherever. Each mirrors what its
// backend accepts and uses the same words; the server still checks (it stays the authority).

/** What the upload backend accepts (backend/app/documents/uploads.py). */
const UPLOAD_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];
const UPLOAD_MAX_BYTES = 10 * 1024 * 1024;

/**
 * Why a chosen file can't be uploaded, or null. Checks the name's extension and the size, as
 * the server does first; the server also checks the file's real type and a PDF's page count.
 */
export function uploadError(file: {
  name: string;
  size: number;
}): string | null {
  const name = file.name.toLowerCase();
  if (!UPLOAD_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "Only PDF, JPG or PNG files can be uploaded.";
  }
  if (file.size === 0) {
    return "The file is empty.";
  }
  if (file.size > UPLOAD_MAX_BYTES) {
    return "The file is over 10 MB.";
  }
  return null;
}

// The forms the backend reads as one tax year (backend/app/documents/extraction/normalise.py).
const YEAR_RANGE = /^(\d{4})\s*[-/–—]\s*(\d{4}|\d{2})$/;
const YEAR_ENDING = /^(?:(?:tax\s*year|ty)\s*)?\d{4}$/i;
// A period ("1 July 2025 to 30 June 2026"): the server reads those; left to it.
const PERIOD = /jul/i;

/** Why a typed tax year isn't one, or null. Lenient like the server: "2025-26", "2025-2026",
 * "2025/26", "TY2026" and a July-to-June period are all accepted. */
export function taxYearError(text: string): string | null {
  const value = text.trim();
  if (value === "") {
    return "Enter the tax year, e.g. 2025-26.";
  }
  const range = YEAR_RANGE.exec(value);
  if (range !== null) {
    const start = Number(range[1]);
    const end = range[2];
    const follows =
      end.length === 4
        ? Number(end) === start + 1
        : Number(end) === (start + 1) % 100;
    return follows
      ? null
      : "The two years must follow each other, e.g. 2025-26.";
  }
  if (YEAR_ENDING.test(value) || PERIOD.test(value)) {
    return null;
  }
  return "Enter the tax year like 2025-26.";
}
