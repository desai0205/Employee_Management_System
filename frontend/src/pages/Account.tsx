import { FormEvent, useState } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";

export function AccountPage() {
  const { me } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!me) return null;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setMessage(null);
    setError(null);
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: String(form.get("current_password")),
          new_password: String(form.get("new_password")),
        }),
      });
      setMessage("Password updated. Other sessions were signed out.");
      event.currentTarget.reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the password.");
    }
  }

  return (
    <section className="narrow">
      <h1>Account</h1>
      <p className="lede">{me.email} · {me.role}</p>
      {message ? <p className="banner">{message}</p> : null}
      {error ? <p className="banner error">{error}</p> : null}
      <form className="card" onSubmit={(event) => void onSubmit(event)}>
        <h2>Change password</h2>
        <label>Current password<input name="current_password" type="password" required /></label>
        <label>New password<input name="new_password" type="password" required minLength={8} /></label>
        <p className="muted">At least 8 characters, with a letter and a number.</p>
        <button type="submit">Update password</button>
      </form>
    </section>
  );
}
