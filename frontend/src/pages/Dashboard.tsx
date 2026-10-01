import { useEffect, useState } from "react";
import { api } from "../api";
import type { Dashboard } from "../types";

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/dashboard")
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load the dashboard."));
  }, []);

  if (error) return <p className="banner error">{error}</p>;
  if (!data) return <p className="loading">Loading dashboard</p>;

  const cards = [
    ["Active employees", data.active_employees],
    ["On leave status", data.employees_on_leave],
    ["Present today", data.present_today],
    ["Pending leave", data.pending_leave_requests],
  ] as const;

  return (
    <section>
      <h1>Dashboard</h1>
      <p className="lede">Counts follow your scope. Admins and HR see the organization. Managers see their direct reports. Employees see themselves.</p>
      <div className="stats">
        {cards.map(([label, value]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}
