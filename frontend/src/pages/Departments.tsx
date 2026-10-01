import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { canManageDepartments, useAuth } from "../auth";
import type { Department, Employee, Page } from "../types";

export function DepartmentsPage() {
  const { me } = useAuth();
  const [rows, setRows] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<Page<Department>>("/departments?page_size=100&sort=name")
      .then((result) => setRows(result.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load departments."));
    api<Page<Employee>>("/employees?page_size=100")
      .then((result) => setEmployees(result.items))
      .catch(() => setEmployees([]));
  }

  useEffect(() => {
    load();
  }, []);

  if (!me) return null;
  const writable = canManageDepartments(me.role);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/departments", {
        method: "POST",
        body: JSON.stringify({
          name: String(form.get("name")),
          code: String(form.get("code")),
          description: String(form.get("description") || "") || null,
        }),
      });
      event.currentTarget.reset();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the department.");
    }
  }

  async function assignManager(department: Department, managerId: string) {
    try {
      await api(`/departments/${department.id}`, {
        method: "PATCH",
        body: JSON.stringify({ manager_id: managerId || null }),
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not assign a manager.");
    }
  }

  return (
    <section>
      <h1>Departments</h1>
      <p className="lede">Create a department first, then assign a manager who already belongs to it.</p>
      {error ? <p className="banner error">{error}</p> : null}
      {writable ? (
        <form className="inline-form" onSubmit={(event) => void create(event)}>
          <input name="name" required placeholder="Name" />
          <input name="code" required placeholder="Code" minLength={2} />
          <input name="description" placeholder="Description" />
          <button type="submit">Add</button>
        </form>
      ) : null}
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Code</th>
            <th>Manager</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((department) => {
            const members = employees.filter((employee) => employee.department_id === department.id && employee.employment_status !== "terminated");
            return (
              <tr key={department.id}>
                <td>
                  <strong>{department.name}</strong>
                  {department.description ? <span className="muted">{department.description}</span> : null}
                </td>
                <td>{department.code}</td>
                <td>
                  {writable ? (
                    <select value={department.manager_id ?? ""} onChange={(event) => void assignManager(department, event.target.value)}>
                      <option value="">No manager</option>
                      {members.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.first_name} {employee.last_name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    members.find((employee) => employee.id === department.manager_id)?.last_name ?? "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
