// The tax assistant (feature 006), per specs/006-rag-mcp/contracts/ask-and-tokens-api.md.
// Every outcome, refusals included, is a 200 with a status; the backend writes every message.

import { apiFetch } from "./client";

export type Citation = {
  title: string;
  kind: "law" | "guidance";
  location: string;
  page: number;
};

export type AskStatus =
  | "answered"
  | "not_covered"
  | "limited"
  | "daily_limit"
  | "unavailable"
  | "not_ready";

export type AskResult = {
  status: AskStatus;
  answer: string;
  citations: Citation[];
  uncovered_part: string | null;
  tax_page_line: string | null;
  label: string;
};

export const askQuestion = (question: string) =>
  apiFetch<AskResult>("/api/ask", { method: "POST", body: { question } });
