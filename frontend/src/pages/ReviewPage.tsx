import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "../api/client";
import {
  DOC_TYPE_LABELS,
  FIELD_LABELS,
  confirmDocument,
  documentFileUrl,
  getDocument,
  updateField,
} from "../api/documents";
import type { DocumentDetail, ExtractedField } from "../api/documents";

// Check each figure against the original, correct it, confirm it (feature 003, task T019;
// research R10). Only confirmed documents reach other features; the backend enforces that
// (constitution, Principle III). Values are shown as given, never calculated with.

function message(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

export function ReviewPage() {
  const { id = "" } = useParams();
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getDocument(id)
      .then(setDocument)
      .catch((caught: unknown) =>
        setLoadError(message(caught, "Couldn't load the document.")),
      );
  }, [id]);

  useEffect(load, [load]);

  async function handleConfirmDocument() {
    setError(null);
    try {
      setDocument(await confirmDocument(id));
    } catch (caught) {
      setError(message(caught, "Couldn't confirm the document. Try again."));
    }
  }

  if (loadError !== null) {
    return (
      <main>
        <p role="alert">{loadError}</p>
        <Link to="/documents">Back to documents</Link>
      </main>
    );
  }
  if (document === null) {
    return <p role="status">Loading…</p>;
  }

  const confirmed = document.status === "confirmed";
  return (
    <main>
      <h1>Check the figures: {DOC_TYPE_LABELS[document.doc_type]}</h1>
      <p>
        <Link to="/documents">Back to documents</Link>
      </p>
      {document.status === "failed" && (
        <p role="alert">
          The figures couldn't be read: {document.failure_reason} Retry it from
          the documents list.
        </p>
      )}
      {confirmed && (
        <p>
          This document is confirmed, so its figures can now be used. It can't
          be changed; delete it and upload it again if something is wrong.
        </p>
      )}
      <div className="review">
        <section aria-label="Original document">
          {document.media_type === "application/pdf" ? (
            <object
              data={documentFileUrl(id)}
              type="application/pdf"
              title="Original document"
              className="original"
            >
              <a href={documentFileUrl(id)}>Open the original document</a>
            </object>
          ) : (
            <img
              src={documentFileUrl(id)}
              alt="Original document"
              className="original"
            />
          )}
        </section>
        <section aria-label="Figures">
          {document.fields.map((field) => (
            <FieldRow
              // Re-created when the saved field changes, so a draft never outlives a save.
              key={`${field.name}:${field.value}:${field.confirmed}`}
              documentId={id}
              field={field}
              readOnly={confirmed}
              onSaved={load}
            />
          ))}
          {document.status === "needs_review" && (
            <>
              {error && <p role="alert">{error}</p>}
              <button type="button" onClick={handleConfirmDocument}>
                Confirm document
              </button>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

type FieldRowProps = {
  documentId: string;
  field: ExtractedField;
  readOnly: boolean;
  onSaved: () => void;
};

function FieldRow({ documentId, field, readOnly, onSaved }: FieldRowProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const label = FIELD_LABELS[field.name] ?? field.name;
  const changed = draft !== null && draft !== (field.value ?? "");
  const errorId = `${field.name}-error`;

  async function handleConfirm() {
    setError(null);
    setSaving(true);
    try {
      await updateField(
        documentId,
        field.name,
        changed ? { value: draft, confirmed: true } : { confirmed: true },
      );
      onSaved();
    } catch (caught) {
      setError(message(caught, "Couldn't save this field. Try again."));
      setSaving(false);
    }
  }

  return (
    <fieldset
      className={field.confidence === "low" ? "field low-confidence" : "field"}
      aria-describedby={error ? errorId : undefined}
    >
      <legend>{label}</legend>
      <input
        type="text"
        aria-label={label}
        value={draft ?? field.value ?? ""}
        placeholder={field.value === null ? "Not found" : undefined}
        disabled={readOnly}
        onChange={(event) => setDraft(event.target.value)}
      />
      {field.value === null ? (
        <p>
          Not found on the document: enter the figure, or 0 if it doesn't apply.
        </p>
      ) : field.user_edited ? (
        <p>You entered this.</p>
      ) : (
        <p>
          Found on page {field.source_page}
          {field.source_label && `, labelled "${field.source_label}"`}.
        </p>
      )}
      {field.confidence === "low" && (
        <p>
          <strong>Low confidence:</strong>{" "}
          {field.rule_reason ?? "check this figure carefully."}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert">
          {error}
        </p>
      )}
      {!readOnly &&
        (field.confirmed && !changed ? (
          <p>Confirmed.</p>
        ) : (
          <button type="button" onClick={handleConfirm} disabled={saving}>
            Confirm {label.toLowerCase()}
          </button>
        ))}
    </fieldset>
  );
}
