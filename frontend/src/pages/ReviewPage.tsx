import { useCallback, useEffect, useRef, useState } from "react";
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

const CONFIDENCE_LABELS = { high: "High", medium: "Medium", low: "Low" };

function message(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

const labelOf = (name: string) => FIELD_LABELS[name] ?? name;

export function ReviewPage() {
  const { id = "" } = useParams();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [shownId, setShownId] = useState(id);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  // Fields with a typed change not yet saved; the document can't be confirmed past them.
  const [unsaved, setUnsaved] = useState<ReadonlySet<string>>(new Set());
  // Only the newest load may update the page (two saves close together, or a new id).
  const latestLoad = useRef(0);

  // A different document: forget the previous one (React's reset-on-change pattern).
  if (id !== shownId) {
    setShownId(id);
    setDoc(null);
    setLoadError(null);
    setError(null);
    setUnsaved(new Set());
  }

  const load = useCallback(() => {
    const request = ++latestLoad.current;
    getDocument(id)
      .then((loaded) => {
        if (request === latestLoad.current) {
          setDoc(loaded);
          setLoadError(null);
          setError(null);
        }
      })
      .catch((caught: unknown) => {
        if (request === latestLoad.current) {
          setLoadError(message(caught, "Couldn't load the document."));
        }
      });
  }, [id]);

  useEffect(load, [load]);

  const markUnsaved = useCallback((name: string, isUnsaved: boolean) => {
    setUnsaved((current) => {
      if (current.has(name) === isUnsaved) {
        return current;
      }
      const next = new Set(current);
      if (isUnsaved) {
        next.add(name);
      } else {
        next.delete(name);
      }
      return next;
    });
  }, []);

  async function handleConfirmDocument() {
    setError(null);
    if (unsaved.size > 0) {
      const names = [...unsaved].map(labelOf).join(", ");
      setError(`Confirm or undo your changes first: ${names}.`);
      return;
    }
    setConfirming(true);
    try {
      setDoc(await confirmDocument(id));
    } catch (caught) {
      setError(message(caught, "Couldn't confirm the document. Try again."));
    }
    setConfirming(false);
  }

  if (doc === null) {
    return (
      <main>
        <h1>Check the figures</h1>
        {loadError ? (
          <p role="alert">{loadError}</p>
        ) : (
          <p role="status">Loading…</p>
        )}
        <p>
          <Link to="/documents">Back to documents</Link>
        </p>
      </main>
    );
  }

  const confirmed = doc.status === "confirmed";
  return (
    <main>
      <h1>Check the figures: {DOC_TYPE_LABELS[doc.doc_type]}</h1>
      <p>
        <Link to="/documents">Back to documents</Link>
      </p>
      {loadError && (
        <p role="alert">Couldn't refresh the figures: {loadError}</p>
      )}
      {doc.status === "failed" && (
        <p role="alert">
          The figures couldn't be read: {doc.failure_reason} Retry it from the
          documents list.
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
          {doc.media_type === "application/pdf" ? (
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
          {doc.fields.map((field) => (
            <FieldRow
              // Re-created when the saved field changes, so a draft never outlives a save.
              key={`${field.name}:${field.value}:${field.confirmed}`}
              documentId={id}
              field={field}
              readOnly={confirmed}
              onSaved={load}
              onUnsavedChange={markUnsaved}
            />
          ))}
          {doc.status === "needs_review" && (
            <>
              {error && <p role="alert">{error}</p>}
              <button
                type="button"
                onClick={handleConfirmDocument}
                disabled={confirming}
              >
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
  onUnsavedChange: (name: string, unsaved: boolean) => void;
};

function FieldRow({
  documentId,
  field,
  readOnly,
  onSaved,
  onUnsavedChange,
}: FieldRowProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const label = labelOf(field.name);
  const changed = !readOnly && draft !== null && draft !== (field.value ?? "");
  const ids = {
    source: `${field.name}-source`,
    confidence: `${field.name}-confidence`,
    error: `${field.name}-error`,
  };

  useEffect(() => {
    onUnsavedChange(field.name, changed);
  }, [field.name, changed, onUnsavedChange]);

  async function handleConfirm() {
    setError(null);
    setSaving(true);
    try {
      await updateField(
        documentId,
        field.name,
        changed ? { value: draft ?? "", confirmed: true } : { confirmed: true },
      );
      // The server may store the same value it already had, which doesn't re-create this
      // row, so clear the draft here rather than relying on the reload.
      setDraft(null);
      setSaving(false);
      onSaved();
    } catch (caught) {
      setError(message(caught, "Couldn't save this field. Try again."));
      setSaving(false);
    }
  }

  return (
    <fieldset
      className={field.confidence === "low" ? "field low-confidence" : "field"}
    >
      <legend>{label}</legend>
      <input
        type="text"
        aria-label={label}
        aria-describedby={[ids.source, ids.confidence, error ? ids.error : ""]
          .filter(Boolean)
          .join(" ")}
        aria-invalid={error ? true : undefined}
        // Read-only shows exactly what is stored, never an unsaved draft.
        value={readOnly ? (field.value ?? "") : (draft ?? field.value ?? "")}
        placeholder={field.value === null ? "Not found" : undefined}
        disabled={readOnly}
        onChange={(event) => setDraft(event.target.value)}
      />
      <p id={ids.source}>
        {field.value === null
          ? "Not found on the document: enter the figure, or 0 if it doesn't apply."
          : field.user_edited
            ? "You entered this."
            : `Found on page ${field.source_page}${
                field.source_label ? `, labelled "${field.source_label}"` : ""
              }.`}
      </p>
      <p id={ids.confidence}>
        {field.confidence === "low" ? (
          <>
            <strong>Low confidence:</strong>{" "}
            {field.rule_reason ?? "check this figure carefully."}
          </>
        ) : (
          `Confidence: ${CONFIDENCE_LABELS[field.confidence]}`
        )}
      </p>
      {error && (
        <p id={ids.error} role="alert">
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
