export type Role = "admin" | "hr" | "manager" | "employee";

export type Me = {
  id: string;
  email: string;
  role: Role;
  is_active: boolean;
  employee_id: string | null;
};

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type Employee = {
  id: string;
  user_id: string | null;
  employee_code: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  department_id: string;
  manager_id: string | null;
  job_title: string;
  employment_status: "active" | "on_leave" | "terminated";
  hire_date: string;
  termination_date: string | null;
  salary_cents?: number | null;
  currency?: string | null;
};

export type Department = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  manager_id: string | null;
};

export type Attendance = {
  id: string;
  employee_id: string;
  work_date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  status: "present" | "late" | "half_day" | "absent" | "on_leave";
  source: "self_service" | "correction";
  note: string | null;
};

export type LeaveType = {
  id: string;
  name: string;
  code: string;
  default_annual_days: string;
  is_paid: boolean;
  is_active: boolean;
};

export type LeaveBalance = {
  id: string;
  employee_id: string;
  leave_type_id: string;
  year: number;
  allocated_days: string;
  used_days: string;
};

export type LeaveRequest = {
  id: string;
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  days: string;
  reason: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  approver_id: string | null;
  decided_at: string | null;
  decision_note: string | null;
};

export type Dashboard = {
  active_employees: number;
  employees_on_leave: number;
  present_today: number;
  pending_leave_requests: number;
};

export type AuditLog = {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  ip_address: string | null;
};

export type HeadcountReport = {
  total: number;
  by_status: Record<string, number>;
  by_department: { department_id: string; department_name: string; count: number }[];
};

export type StatusReport = {
  date_from: string;
  date_to: string;
  by_status: Record<string, number>;
};

export type ReportExport = {
  id: string;
  report_type: string;
  status: "pending" | "ready" | "failed";
  result: Record<string, unknown> | null;
  error: string | null;
};
