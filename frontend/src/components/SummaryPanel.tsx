// The result's short summary, written by code on the server from the result's own amounts
// (design 2026-11-16-plain-summary; the AI summary it replaces was removed the same day). It
// arrives with the result, so nothing loads; the page only displays it (Principle I).

type Props = {
  /** The result's `summary`; null (blocked or not ready) shows nothing. */
  summary: string | null;
  headingId: string;
  /** The heading level that fits where the panel sits on the page. */
  level?: 2 | 3;
};

export function SummaryPanel({ summary, headingId, level = 2 }: Props) {
  if (summary === null) {
    return null;
  }
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section aria-labelledby={headingId} className="panel summary-panel">
      <Heading id={headingId}>Summary</Heading>
      <p>{summary}</p>
    </section>
  );
}
