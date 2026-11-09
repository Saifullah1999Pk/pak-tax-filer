import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// Sign-up page, per specs/002-auth-foundation/contracts/cli-and-ui.md (task T049, FR-024 to
// FR-027). The server checks the email and password rules; this page only checks that the two
// passwords match. A new user goes on to the profile setup step.

type Field = "email" | "password" | "confirm";

/** Which field a server refusal is about: 409 the email, 422 the password (contract). */
function fieldFor(caught: unknown): Field | null {
  if (!(caught instanceof ApiError)) {
    return null;
  }
  return caught.status === 409
    ? "email"
    : caught.status === 422
      ? "password"
      : null;
}

export function SignupPage() {
  const { user, loading, signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<{
    message: string;
    field: Field | null;
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <p role="status">Loading…</p>;
  }
  if (user !== null && !submitting) {
    return <Navigate to="/" replace />;
  }

  /** Screen-reader marking for a field: invalid and described by the error only if it's the
   * field the error is about. */
  function errorProps(field: Field, hint?: string) {
    const isIt = error?.field === field;
    const describedBy = [hint, isIt ? "signup-error" : undefined]
      .filter(Boolean)
      .join(" ");
    return {
      "aria-invalid": isIt,
      "aria-describedby": describedBy || undefined,
    };
  }

  function changePassword(value: string, set: (value: string) => void) {
    set(value);
    if (error?.field === "confirm") {
      setError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirm) {
      setError({ message: "The passwords don't match.", field: "confirm" });
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, password);
      navigate("/profile", { replace: true });
    } catch (caught) {
      setError({
        message:
          caught instanceof ApiError
            ? caught.message
            : "Something went wrong. Try again.",
        field: fieldFor(caught),
      });
      setSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Create an account</h1>
      <p>
        <strong>Demo data only.</strong> Do not enter real personal information.
      </p>
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            {...errorProps("email")}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={password}
            onChange={(event) =>
              changePassword(event.target.value, setPassword)
            }
            {...errorProps("password", "signup-password-hint")}
          />
        </label>
        <p id="signup-password-hint">At least 8 characters.</p>
        <label>
          Confirm password
          <input
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => changePassword(event.target.value, setConfirm)}
            {...errorProps("confirm")}
          />
        </label>
        {error && (
          <p id="signup-error" role="alert">
            {error.message}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          Create account
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </main>
  );
}
