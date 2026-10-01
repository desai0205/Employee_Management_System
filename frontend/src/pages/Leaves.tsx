import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { canApproveLeave, canManageLeave, useAuth } from "../auth";
import type { Employee, LeaveBalance, LeaveRequest, LeaveType, Page } from "../types";

export function LeavesPage() {
  const { me } = useAuth();
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    Promise.all([
      api<LeaveType[]>("/leave-types"),
      api<Page<LeaveRequest>>("/leaves?page_size=20&sort=created_at&order=desc"),
      api<LeaveBalance[]>("/leave-balances"),
      api<Page<Employee>>("/employees?page_size=100"),
    ])
      .then(([leaveTypes, leavePage, leaveBalances, employeePage]) => {
        setTypes(leaveTypes);
        setRequests(leavePage.items);
        setBalances(leaveBalances);
        setEmployees(employeePage.items);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load leave."));
  }

  useEffect(() => {
    load();
  }, []);

  if (!me) return null;

  async function requestLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/leaves", {
        method: "POST",
        body: JSON.stringify({
          leave_type_id: String(form.get("leave_type_id")),
          start_date: String(form.get("start_date")),
          end_date: String(form.get("end_date")),
          reason: String(form.get("reason")),
        }),
      });
      event.currentTarget.reset();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request leave.");
    }
  }

  async function decide(id: string, action: "approve" | "reject" | "cancel") {
    try {
      await api(`/leaves/${id}/${action}`, {
        method: "POST",
        body: action === "cancel" ? undefined : JSON.stringify({ note: "" }),
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this request.");
    }
  }

  const typeName = new Map(types.map((item) => [item.id, item.name]));
  const person = new Map(employees.map((item) => [item.id, `${item.first_name} ${item.last_name}`]));

  return (
    <section>
      <h1>Leave</h1>
      <p className="lede">Requests count weekdays only and cannot overlap an open or approved request. Approval draws from the yearly balance.</p>
      {error ? <p className="banner error">{error}</p> : null}
      <div className="split">
        <form className="card" onSubmit={(event) => void requestLeave(event)}>
          <h2>Request leave</h2>
          <label>
            Type
            <select name="leave_type_id" required defaultValue="">
              <option value="" disabled>Select</option>
              {types.filter((item) => item.is_active).map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>Start<input name="start_date" type="date" required /></label>
          <label>End<input name="end_date" type="date" required /></label>
          <label>Reason<textarea name="reason" required minLength={1} rows={3} /></label>
          <button type="submit">Submit</button>
        </form>
        <div className="card">
          <h2>Balances</h2>
          {balances.length === 0 ? <p className="muted">No balances allocated yet.</p> : (
            <ul className="plain">
              {balances.map((balance) => (
                <li key={balance.id}>
                  {person.get(balance.employee_id) ?? "Employee"} · {typeName.get(balance.leave_type_id) ?? "Leave"} {balance.year}: {balance.used_days} used of {balance.allocated_days}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {canManageLeave(me.role) ? <LeaveAdmin types={types} employees={employees} onDone={load} onError={setError} /> : null}
      <table>
        <thead>
          <tr>
            <th>Person</th>
            <th>Type</th>
            <th>Dates</th>
            <th>Days</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => (
            <tr key={request.id}>
              <td>{person.get(request.employee_id) ?? "Employee"}</td>
              <td>{typeName.get(request.leave_type_id) ?? "Leave"}</td>
              <td>{request.start_date} to {request.end_date}</td>
              <td>{request.days}</td>
              <td><span className={`pill ${request.status}`}>{request.status}</span></td>
              <td className="actions">
                {request.status === "pending" && canApproveLeave(me.role) && request.employee_id !== me.employee_id ? (
                  <>
                    <button type="button" onClick={() => void decide(request.id, "approve")}>Approve</button>
                    <button type="button" className="secondary" onClick={() => void decide(request.id, "reject")}>Reject</button>
                  </>
                ) : null}
                {request.status === "pending" || (request.status === "approved" && canManageLeave(me.role)) ? (
                  <button type="button" className="ghost" onClick={() => void decide(request.id, "cancel")}>Cancel</button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function LeaveAdmin({
  types,
  employees,
  onDone,
  onError,
}: {
  types: LeaveType[];
  employees: Employee[];
  onDone: () => void;
  onError: (message: string) => void;
}) {
  async function createType(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/leave-types", {
        method: "POST",
        body: JSON.stringify({
          name: String(form.get("name")),
          code: String(form.get("code")),
          default_annual_days: String(form.get("days")),
          is_paid: true,
        }),
      });
      event.currentTarget.reset();
      onDone();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not create the leave type.");
    }
  }

  async function allocate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/leave-balances", {
        method: "POST",
        body: JSON.stringify({
          employee_id: String(form.get("employee_id")),
          leave_type_id: String(form.get("leave_type_id")),
          year: Number(form.get("year")),
          allocated_days: String(form.get("allocated_days")),
        }),
      });
      onDone();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not allocate leave.");
    }
  }

  return (
    <div className="split">
      <form className="card" onSubmit={(event) => void createType(event)}>
        <h2>Leave type</h2>
        <label>Name<input name="name" required /></label>
        <label>Code<input name="code" required minLength={2} /></label>
        <label>Default days<input name="days" type="number" min="0.5" step="0.5" required /></label>
        <button type="submit">Create type</button>
      </form>
      <form className="card" onSubmit={(event) => void allocate(event)}>
        <h2>Allocate balance</h2>
        <label>
          Employee
          <select name="employee_id" required defaultValue="">
            <option value="" disabled>Select</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>{employee.first_name} {employee.last_name}</option>
            ))}
          </select>
        </label>
        <label>
          Type
          <select name="leave_type_id" required defaultValue="">
            <option value="" disabled>Select</option>
            {types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label>Year<input name="year" type="number" defaultValue={new Date().getFullYear()} required /></label>
        <label>Days<input name="allocated_days" type="number" min="0" step="0.5" required /></label>
        <button type="submit">Allocate</button>
      </form>
    </div>
  );
}
