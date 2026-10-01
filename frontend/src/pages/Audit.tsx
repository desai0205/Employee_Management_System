import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { canReadAudit, useAuth } from "../auth";
import type { AuditLog, Page } from "../types";

export function AuditPage() {
  const { me } = useAuth();
  const [rows, setRows] = useState<Page<AuditLog> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!me || !canReadAudit(me.role)) return;
    api<Page<AuditLog>>("/audit-logs?page_size=25&sort=created_at&order=desc")
      .then(setRows)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load the audit log."));
  }, [me]);

  if (!me) return null;
  if (!canReadAudit(me.role)) return <Navigate to="/" replace />;

  return (
    <section>
      <h1>Audit log</h1>
      <p className="lede">Append-only record of sign-ins, profile changes, attendance, leave decisions, and report exports.</p>
      {error ? <p className="banner error">{error}</p> : null}
      {!rows ? <p className="loading">Loading audit log</p> : (
        <table>
          <thead>
            <tr><th>When</th><th>Action</th><th>Entity</th><th>Actor</th></tr>
          </thead>
          <tbody>
            {rows.items.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.action}</td>
                <td>{row.entity_type}</td>
                <td className="muted">{row.actor_user_id ?? "system"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
