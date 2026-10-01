import { useEffect, useState } from "react";
import { api } from "../api";
import type { HeadcountReport, ReportExport, StatusReport } from "../types";

export function ReportsPage() {
  const [headcount, setHeadcount] = useState<HeadcountReport | null>(null);
  const [attendance, setAttendance] = useState<StatusReport | null>(null);
  const [leave, setLeave] = useState<StatusReport | null>(null);
  const [exportRow, setExportRow] = useState<ReportExport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<HeadcountReport>("/reports/headcount"),
      api<StatusReport>("/reports/attendance"),
      api<StatusReport>("/reports/leave"),
    ])
      .then(([people, presence, timeOff]) => {
        setHeadcount(people);
        setAttendance(presence);
        setLeave(timeOff);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load reports."));
  }, []);

  async function queueExport() {
    setError(null);
    try {
      const created = await api<ReportExport>("/reports/exports", {
        method: "POST",
        body: JSON.stringify({ report_type: "headcount" }),
      });
      let latest = created;
      setExportRow(latest);
      for (let attempt = 0; attempt < 8 && latest.status === "pending"; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        latest = await api<ReportExport>(`/reports/exports/${created.id}`);
        setExportRow(latest);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not queue the export.");
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <p className="lede">Figures use the same scope as the rest of the app. Attendance and leave default to the last 30 days.</p>
        </div>
        <button type="button" onClick={() => void queueExport()}>Queue headcount export</button>
      </div>
      {error ? <p className="banner error">{error}</p> : null}
      {exportRow ? <p className="banner">Export {exportRow.id.slice(0, 8)} is {exportRow.status}{exportRow.error ? `: ${exportRow.error}` : ""}.</p> : null}
      <div className="split">
        <ReportCard title="Headcount" total={headcount?.total} counts={headcount?.by_status} />
        <ReportCard title="Attendance" total={sum(attendance?.by_status)} counts={attendance?.by_status} caption={attendance ? `${attendance.date_from} to ${attendance.date_to}` : undefined} />
        <ReportCard title="Leave" total={sum(leave?.by_status)} counts={leave?.by_status} caption={leave ? `${leave.date_from} to ${leave.date_to}` : undefined} />
      </div>
      {headcount ? (
        <table>
          <thead>
            <tr><th>Department</th><th>People</th></tr>
          </thead>
          <tbody>
            {headcount.by_department.map((row) => (
              <tr key={row.department_id}><td>{row.department_name}</td><td>{row.count}</td></tr>
            ))}
          </tbody>
        </table>
      ) : <p className="loading">Loading reports</p>}
    </section>
  );
}

function sum(counts: Record<string, number> | undefined): number | undefined {
  if (!counts) return undefined;
  return Object.values(counts).reduce((total, value) => total + value, 0);
}

function ReportCard({ title, total, counts, caption }: { title: string; total?: number; counts?: Record<string, number>; caption?: string }) {
  return (
    <article className="card">
      <h2>{title}</h2>
      {caption ? <p className="muted">{caption}</p> : null}
      <strong className="figure">{total ?? "—"}</strong>
      <ul className="plain">
        {Object.entries(counts ?? {}).map(([name, value]) => (
          <li key={name}>{name.replace("_", " ")}: {value}</li>
        ))}
      </ul>
    </article>
  );
}
