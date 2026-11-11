import { useEffect, useState } from "react";

// The short AI summary, loaded on its own after the figures (feature 001, User Story 6): the
// figures never wait for it. It is already checked by the backend; this only displays it.

type Props = {
  /** The API helper for this page's summary request (a stable module function). */
  fetchSummary: (taxYear: string) => Promise<{ summary: string | null }>;
  taxYear: string;
  headingId: string;
  /** The heading level that fits where the panel sits on the page. */
  level?: 2 | 3;
};

/**
 * "Writing a short summary…" while it loads, then the summary. Nothing at all if the backend
 * dropped it (late, refused, or a number it couldn't check) or the request failed: the
 * breakdown is always there, so no summary is not an error. Remount (a new `key`) to ask again.
 */
export function SummaryPanel({
  fetchSummary,
  taxYear,
  headingId,
  level = 2,
}: Props) {
  const [summary, setSummary] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    let current = true;
    fetchSummary(taxYear)
      .then((reply) => current && setSummary(reply.summary))
      .catch(() => current && setSummary(null));
    return () => {
      current = false;
    };
  }, [fetchSummary, taxYear]);

  if (summary === null) {
    return null;
  }
  const Heading = level === 2 ? "h2" : "h3";
  return (
    // Busy while it loads; not a live region, so it never competes with a page's own
    // announcements (the wealth page's "Saved.").
    <section
      aria-labelledby={headingId}
      aria-busy={summary === undefined}
      className="panel summary-panel"
    >
      <Heading id={headingId}>Summary</Heading>
      {summary === undefined ? (
        <p className="hint">Writing a short summary…</p>
      ) : (
        <p>{summary}</p>
      )}
    </section>
  );
}
