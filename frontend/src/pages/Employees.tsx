import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { canWriteEmployees, useAuth } from "../auth";
import type { Department, Employee, Page, Role } from "../types";

export function EmployeesPage() {
  const { me } = useAuth();
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Page<Employee> | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  function load(nextPage = page, search = query) {
    const params = new URLSearchParams({
      page: String(nextPage),
      page_size: "10",
      sort: "last_name",
      order: "asc",
    });
    if (search.trim()) params.set("q", search.trim());
    api<Page<Employee>>(`/employees?${params}`)
      .then(setRows)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load employees."));
  }

  useEffect(() => {
    load(1, "");
    api<Page<Department>>("/departments?page_size=100&sort=name")
      .then((result) => setDepartments(result.items))
      .catch(() => setDepartments([]));
    // Initial load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!me) return null;
  const writable = canWriteEmployees(me.role);
  const names = new Map(departments.map((department) => [department.id, department.name]));

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Employees</h1>
          <p className="lede">Profiles in your scope. Compensation appears only for Admin and HR.</p>
        </div>
        {writable ? (
          <button type="button" onClick={() => setOpen(true)}>
            Add employee
          </button>
        ) : null}
      </div>
      {error ? <p className="banner error">{error}</p> : null}
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          load(1, query);
        }}
      >
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, email, or code" />
        <button type="submit" className="secondary">
          Search
        </button>
      </form>
      {!rows ? <p className="loading">Loading employees</p> : null}
      {rows ? (
        <>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Title</th>
                <th>Department</th>
                <th>Status</th>
                {writable ? <th>Pay</th> : null}
                {writable ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {rows.items.length === 0 ? (
                <tr>
                  <td colSpan={writable ? 7 : 5}>No employees match this view.</td>
                </tr>
              ) : (
                rows.items.map((employee) => (
                  <tr key={employee.id}>
                    <td>
                      <strong>
                        {employee.first_name} {employee.last_name}
                      </strong>
                      <span className="muted">{employee.email}</span>
                    </td>
                    <td>{employee.employee_code}</td>
                    <td>{employee.job_title}</td>
                    <td>{names.get(employee.department_id) ?? "Department"}</td>
                    <td>
                      <span className={`pill ${employee.employment_status}`}>{employee.employment_status.replace("_", " ")}</span>
                    </td>
                    {writable ? (
                      <td>{employee.salary_cents == null ? "—" : formatMoney(employee.salary_cents, employee.currency)}</td>
                    ) : null}
                    {writable ? (
                      <td>
                        {employee.employment_status !== "terminated" ? (
                          <button
                            type="button"
                            className="ghost danger"
                            onClick={() => void terminate(employee.id, () => load(page, query), setError)}
                          >
                            Terminate
                          </button>
                        ) : null}
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <Pager page={rows.page} pages={rows.pages} total={rows.total} onPage={(next) => { setPage(next); load(next, query); }} />
        </>
      ) : null}
      {open && writable ? (
        <CreateEmployee
          role={me.role}
          departments={departments}
          onClose={() => setOpen(false)}
          onCreated={() => {
            setOpen(false);
            load(1, query);
          }}
        />
      ) : null}
    </section>
  );
}

function formatMoney(cents: number, currency?: string | null): string {
  return `${currency ?? "USD"} ${(cents / 100).toFixed(2)}`;
}

async function terminate(id: string, reload: () => void, setError: (message: string) => void) {
  const termination_date = window.prompt("Termination date (YYYY-MM-DD)", new Date().toISOString().slice(0, 10));
  if (!termination_date) return;
  try {
    await api(`/employees/${id}/terminate`, { method: "POST", body: JSON.stringify({ termination_date }) });
    reload();
  } catch (err) {
    setError(err instanceof Error ? err.message : "Could not terminate this employee.");
  }
}

function CreateEmployee({
  role,
  departments,
  onClose,
  onCreated,
}: {
  role: Role;
  departments: Department[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("account_password") ?? "");
    const body: Record<string, unknown> = {
      employee_code: String(form.get("employee_code")),
      first_name: String(form.get("first_name")),
      last_name: String(form.get("last_name")),
      email: String(form.get("email")),
      job_title: String(form.get("job_title")),
      department_id: String(form.get("department_id")),
      hire_date: String(form.get("hire_date")),
    };
    const phone = String(form.get("phone") ?? "");
    const salary = String(form.get("salary") ?? "");
    if (phone) body.phone = phone;
    if (salary) body.salary_cents = Math.round(Number(salary) * 100);
    if (password) {
      body.account_password = password;
      body.account_role = String(form.get("account_role"));
    }
    setBusy(true);
    setError(null);
    try {
      await api("/employees", { method: "POST", body: JSON.stringify(body) });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the employee.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form className="modal" onClick={(event) => event.stopPropagation()} onSubmit={(event) => void onSubmit(event)}>
        <h2>New employee</h2>
        {error ? <p className="banner error">{error}</p> : null}
        {departments.length === 0 ? <p className="banner">Create a department before adding people.</p> : null}
        <div className="grid-form">
          <label>Code<input name="employee_code" required minLength={2} /></label>
          <label>First name<input name="first_name" required /></label>
          <label>Last name<input name="last_name" required /></label>
          <label>Email<input name="email" type="email" required /></label>
          <label>Job title<input name="job_title" required /></label>
          <label>Phone<input name="phone" /></label>
          <label>
            Department
            <select name="department_id" required defaultValue="">
              <option value="" disabled>Select</option>
              {departments.map((department) => (
                <option key={department.id} value={department.id}>{department.name}</option>
              ))}
            </select>
          </label>
          <label>Hire date<input name="hire_date" type="date" required /></label>
          <label>Annual pay<input name="salary" type="number" min="0" step="0.01" /></label>
          <label>
            Account password
            <input name="account_password" type="password" minLength={8} placeholder="Optional login" />
          </label>
          <label>
            Account role
            <select name="account_role" defaultValue="employee">
              <option value="employee">Employee</option>
              <option value="manager">Manager</option>
              {role === "admin" ? <option value="hr">HR</option> : null}
              {role === "admin" ? <option value="admin">Admin</option> : null}
            </select>
          </label>
        </div>
        <div className="actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy || departments.length === 0}>Save</button>
        </div>
      </form>
    </div>
  );
}

function Pager({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return (
    <div className="pager">
      <span>{total} records</span>
      <button type="button" className="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <span>{page} / {Math.max(pages, 1)}</span>
      <button type="button" className="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
    </div>
  );
}
