import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// Sign-up page, per specs/002-auth-foundation/contracts/cli-and-ui.md (task T049, FR-024 to
// FR-027). The server checks the email and password rules; this page only checks that the two
// passwords match. A new user goes on to the profile setup step.

export function SignupPage() {
  const { user, loading, signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <p role="status">Loading…</p>;
  }
  if (user !== null && !submitting) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The passwords don't match.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, password);
      navigate("/profile", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Something went wrong. Try again.",
      );
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
          />
        </label>
        <label>
          Password (at least 8 characters)
          <input
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            autoComplete="new-password"
            aria-invalid={error !== null}
            aria-describedby={error ? "signup-error" : undefined}
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </label>
        {error && (
          <p id="signup-error" role="alert">
            {error}
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
