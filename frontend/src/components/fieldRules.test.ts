import { expect, test } from "vitest";
import { taxYearError, uploadError } from "./fieldRules";

// The frontend checks for the other kinds of field (lead, 2026-11-16: errors caught in the
// frontend too, one rule applied wherever). Each mirrors its backend; the server still checks.

const MB = 1024 * 1024;

test.each([
  [{ name: "certificate.pdf", size: 200_000 }, null],
  [{ name: "SCAN.JPG", size: 3 * MB }, null],
  [{ name: "photo.jpeg", size: 10 * MB }, null],
  [{ name: "photo.png", size: 1 }, null],
  [
    { name: "notes.docx", size: 1000 },
    "Only PDF, JPG or PNG files can be uploaded.",
  ],
  [
    { name: "no-extension", size: 1000 },
    "Only PDF, JPG or PNG files can be uploaded.",
  ],
  [{ name: "big.pdf", size: 10 * MB + 1 }, "The file is over 10 MB."],
  [{ name: "empty.pdf", size: 0 }, "The file is empty."],
])("uploadError(%j) is %j", (file, error) => {
  expect(uploadError(file)).toBe(error);
});

test.each([
  ["2025-26", null],
  [" 2025-2026 ", null],
  ["2025/26", null],
  ["TY2026", null],
  ["Tax year 2026", null],
  ["2026", null],
  // A period is read by the server (salary certificates print one); left to it.
  ["1 July 2025 to 30 June 2026", null],
  ["", "Enter the tax year, e.g. 2025-26."],
  ["2025-27", "The two years must follow each other, e.g. 2025-26."],
  ["2024-2026", "The two years must follow each other, e.g. 2025-26."],
  ["next year", "Enter the tax year like 2025-26."],
  ["20256", "Enter the tax year like 2025-26."],
])("taxYearError(%j) is %j", (text, error) => {
  expect(taxYearError(text)).toBe(error);
});
