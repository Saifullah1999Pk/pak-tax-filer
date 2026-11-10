import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError } from "../api/client";
import {
  DOC_TYPE_LABELS,
  deleteDocument,
  listDocuments,
  retryDocument,
  uploadDocument,
} from "../api/documents";
import type { DocStatus, DocType, DocumentSummary } from "../api/documents";

// Upload a certificate and manage uploaded ones (feature 003, tasks T015 and T023; research
// R10). The backend checks every limit again; nothing here is trusted.

const STATUS_LABELS: Record<DocStatus, string> = {
  uploaded: "Uploaded",
  extracting: "Reading…",
  needs_review: "Ready to review",
  confirmed: "Confirmed",
  failed: "Failed",
};

function message(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/** "salary certificate uploaded 05/11/2026, 10:00:00": tells one row's buttons from another's. */
function describe(doc: DocumentSummary): string {
  const uploaded = new Date(doc.created_at).toLocaleString();
  return `${DOC_TYPE_LABELS[doc.doc_type].toLowerCase()} uploaded ${uploaded}`;
}

export function DocumentsPage() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Kept apart from loadError, so refreshing the list never hides why an action failed.
  const [actionError, setActionError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [docType, setDocType] = useState<DocType | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    listDocuments()
      .then((list) => {
        setDocs(list);
        setLoadError(null);
      })
      .catch((caught: unknown) =>
        setLoadError(message(caught, "Couldn't load your documents.")),
      );
  }, []);

  useEffect(refresh, [refresh]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadError(null);
    if (docType === "") {
      setUploadError("Choose the document type.");
      return;
    }
    if (file === null) {
      setUploadError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    try {
      const doc = await uploadDocument(file, docType);
      if (doc.status === "needs_review") {
        navigate(`/documents/${doc.id}`);
        return;
      }
      // Nothing to review: stay here with the reason; the list shows it with Retry (FR-005a).
      setUploadError(
        doc.failure_reason ?? "The figures couldn't be read. Try again.",
      );
      setUploading(false);
      refresh();
    } catch (caught) {
      setUploadError(message(caught, "The upload failed. Try again."));
      setUploading(false);
    }
  }

  async function handleRetry(id: string) {
    setActionError(null);
    setRetrying(id);
    try {
      await retryDocument(id);
    } catch (caught) {
      setActionError(message(caught, "The retry failed. Try again."));
    }
    setRetrying(null);
    refresh();
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Delete this document and its figures?")) {
      return;
    }
    setActionError(null);
    try {
      await deleteDocument(id);
    } catch (caught) {
      setActionError(message(caught, "Couldn't delete the document."));
    }
    refresh();
  }

  return (
    <main>
      <h1>Documents</h1>
      <p className="notice">
        <strong>Demo data only.</strong> Do not upload real documents: use the
        synthetic certificates from the project.
      </p>

      <form
        onSubmit={handleUpload}
        className="panel"
        aria-labelledby="upload-heading"
      >
        <h2 id="upload-heading">Upload a certificate</h2>
        <label>
          Document type
          <select
            value={docType}
            onChange={(event) => setDocType(event.target.value as DocType | "")}
          >
            <option value="">Choose…</option>
            <option value="salary_certificate">Salary certificate</option>
            <option value="bank_profit_certificate">
              Bank profit certificate
            </option>
          </select>
        </label>
        <label>
          File (PDF, JPG or PNG; up to 10&nbsp;MB and 5 pages)
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        {uploadError && <p role="alert">{uploadError}</p>}
        <button type="submit" disabled={uploading}>
          Upload
        </button>
        {uploading && (
          <p role="status">
            Reading the document… this can take up to a minute.
          </p>
        )}
      </form>

      <h2>Your documents</h2>
      {loadError && <p role="alert">{loadError}</p>}
      {actionError && <p role="alert">{actionError}</p>}
      {retrying && (
        <p role="status">
          Reading the document again… this can take up to a minute.
        </p>
      )}
      {docs === null ? (
        !loadError && <p>Loading…</p>
      ) : docs.length === 0 ? (
        <p>No documents yet.</p>
      ) : (
        // Explicit roles: below 720 px the rows are restyled as blocks, which makes some
        // browsers forget they are a table.
        <table className="stack" role="table">
          <thead role="rowgroup">
            <tr role="row">
              <th scope="col" role="columnheader">
                Type
              </th>
              <th scope="col" role="columnheader">
                Uploaded
              </th>
              <th scope="col" role="columnheader">
                Status
              </th>
              <th scope="col" role="columnheader">
                Actions
              </th>
            </tr>
          </thead>
          <tbody role="rowgroup">
            {docs.map((doc) => (
              <tr key={doc.id} role="row">
                <td role="cell" data-label="Type">
                  {DOC_TYPE_LABELS[doc.doc_type]}
                </td>
                <td role="cell" data-label="Uploaded">
                  {new Date(doc.created_at).toLocaleString()}
                </td>
                <td role="cell" data-label="Status">
                  {STATUS_LABELS[doc.status]}
                  {doc.failure_reason && `: ${doc.failure_reason}`}
                </td>
                <td role="cell" data-label="Actions">
                  <div className="row-actions">
                    {(doc.status === "needs_review" ||
                      doc.status === "confirmed") && (
                      <Link
                        className={
                          doc.status === "needs_review"
                            ? "button button-primary"
                            : "button"
                        }
                        to={`/documents/${doc.id}`}
                        aria-label={`${doc.status === "confirmed" ? "View" : "Review"} ${describe(doc)}`}
                      >
                        {doc.status === "confirmed" ? "View" : "Review"}
                      </Link>
                    )}{" "}
                    {doc.status === "failed" && (
                      <button
                        type="button"
                        onClick={() => handleRetry(doc.id)}
                        disabled={retrying !== null}
                        aria-label={`Retry ${describe(doc)}`}
                      >
                        Retry
                      </button>
                    )}{" "}
                    <button
                      type="button"
                      onClick={() => handleDelete(doc.id)}
                      disabled={retrying === doc.id}
                      aria-label={`Delete ${describe(doc)}`}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
