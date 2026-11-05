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

export function DocumentsPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [docType, setDocType] = useState<DocType | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    listDocuments()
      .then((list) => {
        setDocuments(list);
        setListError(null);
      })
      .catch((caught: unknown) =>
        setListError(message(caught, "Couldn't load your documents.")),
      );
  }, []);

  useEffect(refresh, [refresh]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (docType === "") {
      setError("Choose the document type.");
      return;
    }
    if (file === null) {
      setError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    try {
      const document = await uploadDocument(file, docType);
      navigate(`/documents/${document.id}`);
    } catch (caught) {
      setError(message(caught, "The upload failed. Try again."));
      setUploading(false);
    }
  }

  async function handleRetry(id: string) {
    try {
      await retryDocument(id);
    } catch (caught) {
      setListError(message(caught, "The retry failed. Try again."));
    }
    refresh();
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Delete this document and its figures?")) {
      return;
    }
    try {
      await deleteDocument(id);
    } catch (caught) {
      setListError(message(caught, "Couldn't delete the document."));
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

      <h2>Upload a certificate</h2>
      <form onSubmit={handleUpload}>
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
          File (PDF, JPG or PNG; up to 10 MB and 5 pages)
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        {error && <p role="alert">{error}</p>}
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
      {listError && <p role="alert">{listError}</p>}
      {documents === null ? (
        !listError && <p>Loading…</p>
      ) : documents.length === 0 ? (
        <p>No documents yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">Type</th>
              <th scope="col">Uploaded</th>
              <th scope="col">Status</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id}>
                <td>{DOC_TYPE_LABELS[document.doc_type]}</td>
                <td>{new Date(document.created_at).toLocaleString()}</td>
                <td>
                  {STATUS_LABELS[document.status]}
                  {document.failure_reason && `: ${document.failure_reason}`}
                </td>
                <td>
                  {(document.status === "needs_review" ||
                    document.status === "confirmed") && (
                    <Link to={`/documents/${document.id}`}>
                      {document.status === "confirmed" ? "View" : "Review"}
                    </Link>
                  )}{" "}
                  {document.status === "failed" && (
                    <button
                      type="button"
                      onClick={() => handleRetry(document.id)}
                    >
                      Retry
                    </button>
                  )}{" "}
                  <button
                    type="button"
                    onClick={() => handleDelete(document.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p>
        <Link to="/">Home</Link>
      </p>
    </main>
  );
}
