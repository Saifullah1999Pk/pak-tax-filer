import { useId } from "react";

// The PDF download (feature 008, task T008). The backend makes the PDF, with the practitioner
// label and validation status on every page; this offers it as a plain download link (the
// session cookie goes along), or says why the result can't be exported.

export function DownloadPdfButton({
  href,
  disabledReason,
}: {
  href: string;
  /** Why the result can't be exported (blocked, not ready, not approved), or null. */
  disabledReason: string | null;
}) {
  const reasonId = useId();
  if (disabledReason !== null) {
    return (
      <p className="pdf-download">
        <button type="button" aria-disabled="true" aria-describedby={reasonId}>
          Download PDF
        </button>{" "}
        <span id={reasonId} className="hint">
          {disabledReason}
        </span>
      </p>
    );
  }
  return (
    <p className="pdf-download">
      <a className="button" href={href} download>
        Download PDF
      </a>
    </p>
  );
}
