// The guided run (feature 007), per specs/007-agentic-workflow/contracts/workflow-api.md.
// Figures arrive as decimal strings and are only displayed (constitution, Principle I).

import { apiFetch } from "./client";

export type Step =
  "document" | "validate" | "research" | "gate" | "result" | "done";

export type Passage = {
  id: string;
  source: string;
  kind: "law" | "guidance";
  location: string;
  page: number;
  text: string;
};

export type Issue = {
  document_id: string;
  certificate: string;
  field: string;
  reason: string;
};

export type Run = {
  step: Step;
  tax_year: string;
  fingerprint: string | null;
  document: { message: string; missing: string[]; fallback: boolean } | null;
  validation: { message: string; issues: Issue[]; fallback: boolean } | null;
  research: { note: string; passages: Passage[]; fallback: boolean } | null;
  gate: {
    figures: {
      taxable_salary: string;
      tax_deducted: string;
      gross_profit: string;
      tax_withheld: string;
    };
    on_atl: boolean;
  } | null;
  approved_at: string | null;
  done_at: string | null;
};

export const getRun = () => apiFetch<Run>("/api/workflow");
export const startRun = () =>
  apiFetch<Run>("/api/workflow/start", { method: "POST" });
