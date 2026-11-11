// Documents and their extracted figures (feature 003), per
// specs/003-document-extraction/contracts/documents-api.md. Money arrives as decimal strings
// and is only displayed, never calculated with (constitution, Principle I).

import { apiFetch, apiUpload } from "./client";

export type DocType = "salary_certificate" | "bank_profit_certificate";
export type DocStatus =
  "uploaded" | "extracting" | "needs_review" | "confirmed" | "failed";

export type ExtractedField = {
  name: string;
  /** A decimal string for amounts, "2025-26" for tax_year, null if not found. */
  value: string | null;
  confidence: "high" | "medium" | "low";
  source_page: number | null;
  source_label: string | null;
  rule_reason: string | null;
  user_edited: boolean;
  confirmed: boolean;
};

export type DocumentSummary = {
  id: string;
  doc_type: DocType;
  tax_year: string;
  status: DocStatus;
  failure_reason: string | null;
  media_type: string;
  page_count: number;
  created_at: string;
  confirmed_at: string | null;
};

export type DocumentDetail = DocumentSummary & { fields: ExtractedField[] };

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  salary_certificate: "Salary certificate",
  bank_profit_certificate: "Bank profit certificate",
};

export const FIELD_LABELS: Record<string, string> = {
  tax_year: "Tax year",
  gross_salary: "Gross salary",
  taxable_salary: "Taxable salary",
  tax_deducted: "Tax deducted",
  profit_amount: "Profit amount",
  tax_withheld: "Tax withheld (section 151)",
};

const base = (id: string) => `/api/documents/${encodeURIComponent(id)}`;

export const listDocuments = () =>
  apiFetch<DocumentSummary[]>("/api/documents");

export const getDocument = (id: string) => apiFetch<DocumentDetail>(base(id));

export function uploadDocument(file: File, docType: DocType) {
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", docType);
  return apiUpload<DocumentDetail>("/api/documents", form);
}

export const updateField = (
  id: string,
  name: string,
  body: { value?: string; confirmed?: boolean },
) =>
  apiFetch<ExtractedField>(`${base(id)}/fields/${encodeURIComponent(name)}`, {
    method: "PATCH",
    body,
  });

export const confirmDocument = (id: string) =>
  apiFetch<DocumentDetail>(`${base(id)}/confirm`, { method: "POST" });

export const retryDocument = (id: string) =>
  apiFetch<DocumentDetail>(`${base(id)}/retry`, { method: "POST" });

export const deleteDocument = (id: string) =>
  apiFetch<void>(base(id), { method: "DELETE" });

/** Where the review page loads the original file from (owner-checked by the backend). */
export const documentFileUrl = (id: string) => `${base(id)}/file`;
