import { useEffect, useState } from "react";
import { api } from "../api";
import { canCorrectAttendance, useAuth } from "../auth";
import type { Attendance, Page } from "../types";

export function AttendancePage() {
  const { me } = useAuth();
  const [rows, setRows] = useState<Page<Attendance> | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<Page<Attendance>>("/attendance?page_size=20&sort=work_date&order=desc")
      .then(setRows)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load attendance."));
  }

  useEffect(() => {
    load();
  }, []);

  if (!me) return null;

  async function stamp(path: "check-in" | "check-out") {
    setError(null);
    setMessage(null);
    try {
      const record = await api<Attendance>(`/attendance/${path}`, { method: "POST" });
      setMessage(`${path === "check-in" ? "Checked in" : "Checked out"} as ${record.status.replace("_", " ")}.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Attendance update failed.");
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Attendance</h1>
          <p className="lede">Check in and out for today. A start after 09:15 is recorded as late.</p>
        </div>
        <div className="actions">
          <button type="button" onClick={() => void stamp("check-in")}>Check in</button>
          <button type="button" className="secondary" onClick={() => void stamp("check-out")}>Check out</button>
        </div>
      </div>
      {message ? <p className="banner">{message}</p> : null}
      {error ? <p className="banner error">{error}</p> : null}
      {!rows ? <p className="loading">Loading attendance</p> : null}
      {rows ? (
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Status</th>
              <th>In</th>
              <th>Out</th>
              <th>Source</th>
              {canCorrectAttendance(me.role) ? <th /> : null}
            </tr>
          </thead>
          <tbody>
            {rows.items.length === 0 ? (
              <tr><td colSpan={6}>No attendance records in your scope.</td></tr>
            ) : rows.items.map((row) => (
              <tr key={row.id}>
                <td>{row.work_date}</td>
                <td><span className={`pill ${row.status}`}>{row.status.replace("_", " ")}</span></td>
                <td>{formatTime(row.check_in_at)}</td>
                <td>{formatTime(row.check_out_at)}</td>
                <td>{row.source.replace("_", " ")}</td>
                {canCorrectAttendance(me.role) ? (
                  <td>
                    <button type="button" className="ghost" onClick={() => void correct(row, load, setError)}>
                      Correct
                    </button>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function correct(row: Attendance, reload: () => void, setError: (message: string) => void) {
  const status = window.prompt("Status: present, late, half_day, absent, on_leave", row.status);
  if (!status) return;
  const note = window.prompt("Note", row.note ?? "") ?? "";
  try {
    await api(`/attendance/${row.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        status,
        note,
        check_in_at: row.check_in_at,
        check_out_at: row.check_out_at,
      }),
    });
    reload();
  } catch (err) {
    setError(err instanceof Error ? err.message : "Could not correct this record.");
  }
}
