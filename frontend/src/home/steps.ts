import type { DocumentSummary } from "../api/documents";
import type { Profile } from "../profile/ProfileContext";

// Home's filing checklist (feature 001, User Story 6, task T051; FR-028): where the user is,
// worked out only from what the app already has (the profile and the documents list). Only
// documents for the profile's tax year count, the same ones the tax and wealth pages use. Tax
// and Wealth are never "done": knowing that would mean calling their endpoints, which also ask
// the AI for a summary, on every visit to Home. This only counts documents; no money here.

export type StepState = "done" | "next" | "todo";

export type FilingStep = {
  key: "profile" | "documents" | "tax" | "wealth";
  title: string;
  state: StepState;
  /** What's true now, e.g. "1 confirmed"; null while the documents are unknown. */
  detail: string | null;
  action: { to: string; text: string };
};

const NEEDS_SALARY = "Needs a confirmed salary certificate";

/** "1 confirmed, 1 to review": the counts that aren't zero, or "None yet". */
function documentCounts(docs: DocumentSummary[]): string {
  const count = (statuses: string[]) =>
    docs.filter((doc) => statuses.includes(doc.status)).length;
  const parts = [
    [count(["confirmed"]), "confirmed"],
    [count(["needs_review"]), "to review"],
    [count(["uploaded", "extracting"]), "being read"],
    [count(["failed"]), "failed"],
  ]
    .filter(([n]) => n !== 0)
    .map(([n, what]) => `${n} ${what}`);
  return parts.length ? parts.join(", ") : "None yet";
}

/**
 * The four steps, in order. `documents` is null while the list is loading or couldn't be
 * loaded: then nothing about documents, tax or wealth is guessed.
 */
export function filingSteps(
  profile: Profile,
  documents: DocumentSummary[] | null,
): FilingStep[] {
  const profileStep: FilingStep = {
    key: "profile",
    title: "Profile",
    state: "done",
    detail: `Tax year ${profile.tax_year}, ${profile.on_atl ? "on the ATL" : "not on the ATL"}`,
    action: { to: "/profile", text: "Edit profile" },
  };
  const taxAction = { to: "/tax", text: "See your tax" };
  const wealthAction = { to: "/wealth", text: "Open wealth statement" };

  if (documents === null) {
    return [
      profileStep,
      {
        key: "documents",
        title: "Documents",
        state: "todo",
        detail: null,
        action: { to: "/documents", text: "Upload documents" },
      },
      {
        key: "tax",
        title: "Tax",
        state: "todo",
        detail: null,
        action: taxAction,
      },
      {
        key: "wealth",
        title: "Wealth statement",
        state: "todo",
        detail: null,
        action: wealthAction,
      },
    ];
  }

  const thisYear = documents.filter((doc) => doc.tax_year === profile.tax_year);
  const salaryConfirmed = thisYear.some(
    (doc) =>
      doc.doc_type === "salary_certificate" && doc.status === "confirmed",
  );
  const toReview = thisYear.find((doc) => doc.status === "needs_review");
  const documentsDone = salaryConfirmed && toReview === undefined;
  const ready = salaryConfirmed ? "Ready" : NEEDS_SALARY;

  return [
    profileStep,
    {
      key: "documents",
      title: "Documents",
      state: documentsDone ? "done" : "next",
      detail: documentCounts(thisYear),
      action: toReview
        ? { to: `/documents/${toReview.id}`, text: "Review the next document" }
        : { to: "/documents", text: "Upload documents" },
    },
    {
      key: "tax",
      title: "Tax",
      state: documentsDone ? "next" : "todo",
      detail: ready,
      action: taxAction,
    },
    {
      key: "wealth",
      title: "Wealth statement",
      state: "todo",
      detail: ready,
      action: wealthAction,
    },
  ];
}
