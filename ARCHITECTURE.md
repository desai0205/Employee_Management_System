# Employee Management System — Architecture Plan

Status: **implemented**. The modules under `app/` follow this plan. Schema changes still go through Alembic only.

This is a modular monolith. One deployable API, one worker process, one PostgreSQL database, and one Redis instance. Features are separated by module, while dependency direction stays the same across the codebase.

## Decisions to confirm

1. **Layout is layer-first.** `app/api`, `app/schemas`, `app/services`, `app/repositories`, and `app/models` each contain one module per feature. Shared code stays in `app/core` and `app/db`. This keeps SQLAlchemy metadata in one registry for Alembic, and it matches the requested packages. A feature can later move into `app/modules/<feature>/` without changing the dependency rule.
2. **Background jobs use [arq](https://github.com/python-arq/arq).** It is async and uses Redis. Celery is a better fit only if jobs must run sync code.
3. **Primary keys are UUID.** Timestamps are `timestamptz` in UTC. `work_date` and leave dates are calendar `date` values in one organization timezone from settings.
4. **Employees are not hard-deleted.** Status becomes `terminated`. Audit rows are append-only.
5. **Passwords use Argon2id.** Access tokens are JWTs. Refresh tokens are opaque random values stored only as a hash.

If any of these should change, say so before implementation.

## Dependency rule

```
HTTP (app/api, middleware)
    -> services          business rules, transactions, audit emission
        -> repositories  queries and persistence only
            -> models    tables, relationships, constraints
                -> db    engine, session, Redis

services -> schemas      input/output DTOs
services -> core         settings, security, RBAC, errors
workers  -> services     jobs do not talk to repositories directly
```

Forbidden imports:

- Routes do not import repositories or models to make decisions.
- Repositories do not import services.
- Models do not import FastAPI, Pydantic schemas, or services.
- `app/core` does not import feature services.

Dependency injection:

- `app/api/deps.py` builds the request-scoped `AsyncSession`, Redis client, current user, and service instances.
- Route functions declare those dependencies and call one service method.
- Repositories receive the session in their constructor. They do not open sessions themselves.

Transaction boundary:

- The session dependency yields one `AsyncSession` per request.
- Repositories `flush` when they need generated ids. They do not `commit`.
- The session dependency commits on success and rolls back on any exception.
- A service that enqueues a job does so after the unit of work is successful, or the worker checks state so a rolled-back request cannot cause a false job. The implementation will enqueue in the service only after flush, and the worker re-reads the database before acting.

## Request path

1. Middleware assigns `request_id` and binds it on the structured logger.
2. The router validates the body and query with a Pydantic schema.
3. Auth dependencies verify the access token and load the user.
4. A role guard rejects the call when the permission is missing.
5. The service enforces finer rules (own record vs team vs organization), changes state through repositories, and records an audit event for writes.
6. Exception handlers turn application errors into one JSON shape. Unexpected errors are logged and returned as a generic 500 without stack traces.

Error body:

```json
{
  "error": {
    "code": "leave_balance_exceeded",
    "message": "Requested days exceed the remaining balance.",
    "details": [],
    "request_id": "..."
  }
}
```

Validation errors use the same envelope with code `validation_error` and field details.

## RBAC

Roles are stored on `users.role`: `admin`, `hr`, `manager`, `employee`. A user has one role in this version.

Permissions are an explicit map in `app/core/rbac.py`, not scattered `if role ==` checks in routes. Services also enforce scope:

| Scope | Meaning |
| --- | --- |
| `self` | The signed-in user's employee record |
| `team` | Direct reports of that employee, plus self |
| `org` | Every record |

| Capability | Admin | HR | Manager | Employee |
| --- | --- | --- | --- | --- |
| Sign in, refresh, logout, change own password | yes | yes | yes | yes |
| Read dashboard | org | org | team | self |
| List and read employees | org | org | team | self |
| Create and update employees | yes | yes | no | no |
| Terminate an employee | yes | yes | no | no |
| Read compensation fields | yes | yes | no | no |
| Manage departments | yes | yes | read only | read only |
| Check in and check out | self | self | self | self |
| Correct attendance | org | org | no | no |
| Read attendance | org | org | team | self |
| Request and cancel own leave | yes | yes | yes | yes |
| Approve or reject leave | org | org | team | no |
| Manage leave types and allocations | yes | yes | no | no |
| Run reports | org | org | team | self |
| Read audit logs | yes | no | no | no |

Manager scope requires an `employees` row linked to the user. A manager token with no employee profile can read only itself.

## Domain model

All mutable tables include `id` (UUID), `created_at`, and `updated_at` from `app/models/mixins.py`. `audit_logs` and `refresh_tokens` are append-only aside from revocation columns, and they do not use a general update flow.

### users

Account identity. Separate from the HR profile so a person can exist before they can log in.

| Column | Notes |
| --- | --- |
| email | unique, indexed, stored lowercase |
| password_hash | Argon2id string, never returned by the API |
| role | enum |
| is_active | false blocks login and refresh |
| last_login_at | nullable timestamptz |

### refresh_tokens

| Column | Notes |
| --- | --- |
| user_id | FK users, `ON DELETE CASCADE`, indexed |
| token_hash | unique. Raw token is returned once |
| family_id | UUID identifying a rotation chain |
| expires_at | indexed |
| revoked_at | nullable |
| replaced_by_id | nullable self-FK |
| user_agent, ip_address | optional audit context |

Reuse of a revoked token in the same family revokes the whole family.

### departments

| Column | Notes |
| --- | --- |
| name | unique |
| code | unique, short stable identifier |
| description | nullable |
| manager_id | nullable FK employees. The first insert order is: department without manager, employees, then set manager |

Delete is refused while employees still reference the department (`ON DELETE RESTRICT`).

### employees

| Column | Notes |
| --- | --- |
| user_id | unique, nullable FK users. Set when an account is linked |
| employee_code | unique |
| first_name, last_name | required |
| email | unique work email |
| phone | nullable |
| department_id | FK departments, indexed, `ON DELETE RESTRICT` |
| manager_id | nullable self-FK, indexed. Check constraint: `manager_id <> id` |
| job_title | required |
| employment_status | `active`, `on_leave`, `terminated` |
| hire_date | date |
| termination_date | nullable, required when status is `terminated` |
| salary_cents | nullable integer, omitted from schemas unless the role may read it |
| currency | char(3), default from settings |

Indexes: `(department_id)`, `(manager_id)`, `(employment_status)`, `(last_name, first_name)`.

### attendance_records

One row per employee per calendar day.

| Column | Notes |
| --- | --- |
| employee_id | FK employees, indexed, `ON DELETE RESTRICT` |
| work_date | date |
| check_in_at, check_out_at | timestamptz, check-out nullable |
| status | `present`, `late`, `half_day`, `absent`, `on_leave` |
| source | `self_service` or `correction` |
| note | nullable |

Unique constraint: `(employee_id, work_date)`. Check: `check_out_at` is null or later than `check_in_at`.

### leave_types

`name` unique, `code` unique, `default_annual_days` numeric(4,1), `is_paid` boolean, `is_active` boolean.

### leave_balances

`employee_id`, `leave_type_id`, `year`, `allocated_days`, `used_days`. Unique `(employee_id, leave_type_id, year)`. Check: both day columns are `>= 0` and `used_days <= allocated_days`.

### leave_requests

| Column | Notes |
| --- | --- |
| employee_id, leave_type_id | FKs, indexed |
| start_date, end_date | check `end_date >= start_date` |
| days | numeric(4,1), computed by the service from working days |
| reason | text |
| status | `pending`, `approved`, `rejected`, `cancelled` |
| approver_id | nullable FK employees |
| decided_at, decision_note | set when status leaves `pending` |

Indexes: `(employee_id, status)`, `(status, start_date)`.

Overlapping approved or pending requests for the same employee are rejected in the service, with a database exclusion if we add the `btree_gist` extension during the first migration. That constraint is part of implementation, not a manual SQL change.

### audit_logs

| Column | Notes |
| --- | --- |
| actor_user_id | nullable FK users, set null if the user is removed |
| action | string, for example `employee.updated` |
| entity_type, entity_id | indexed together |
| before, after | JSONB, secrets stripped |
| ip_address, request_id | nullable |
| created_at | indexed |

No update or delete API. Salary values are omitted from `before` and `after` unless the actor was allowed to see them; the stored diff still records that the field changed.

## API surface

Prefix from settings, default `/api/v1`. OpenAPI is FastAPI's generated `/docs` and `/openapi.json`. Routes only translate HTTP to a service call.

| Method | Path | Permission |
| --- | --- | --- |
| GET | `/health/live` | public |
| GET | `/health/ready` | public. Checks PostgreSQL and Redis |
| POST | `/auth/login` | public. Rate-limited in Redis |
| POST | `/auth/refresh` | public, with refresh token |
| POST | `/auth/logout` | authenticated |
| GET | `/auth/me` | authenticated |
| POST | `/auth/change-password` | authenticated |
| GET | `/dashboard` | any role, scoped |
| GET, POST | `/employees` | see matrix |
| GET, PATCH | `/employees/{id}` | see matrix |
| POST | `/employees/{id}/terminate` | admin, hr |
| GET, POST | `/departments` | read: any role. Create: admin, hr |
| GET, PATCH | `/departments/{id}` | patch: admin, hr |
| POST | `/attendance/check-in` | authenticated employee profile |
| POST | `/attendance/check-out` | authenticated employee profile |
| GET | `/attendance` | scoped |
| PATCH | `/attendance/{id}` | admin, hr correction |
| GET, POST | `/leave-types` | write: admin, hr |
| GET | `/leave-balances` | scoped |
| POST | `/leave-balances` | admin, hr allocation |
| GET, POST | `/leaves` | create own. List is scoped |
| GET | `/leaves/{id}` | scoped |
| POST | `/leaves/{id}/approve` | admin, hr, or manager of requester |
| POST | `/leaves/{id}/reject` | admin, hr, or manager of requester |
| POST | `/leaves/{id}/cancel` | owner while pending, or admin/hr |
| GET | `/reports/headcount` | scoped |
| GET | `/reports/attendance` | scoped |
| GET | `/reports/leave` | scoped |
| POST | `/reports/exports` | scoped. Returns a job id |
| GET | `/reports/exports/{id}` | owner of the job, or admin |
| GET | `/audit-logs` | admin |

List endpoints accept `page` (from 1), `page_size` (1–100, default 20), `sort` (allowlisted field per resource), and `order` (`asc` or `desc`). Unknown sort fields are a 422.

Filters, applied only when present:

- Employees: `department_id`, `status`, `manager_id`, `q` (name, email, or employee code)
- Attendance: `employee_id`, `department_id`, `date_from`, `date_to`, `status`
- Leaves: `employee_id`, `status`, `leave_type_id`, `date_from`, `date_to`
- Audit: `actor_user_id`, `entity_type`, `entity_id`, `action`, `created_from`, `created_to`

List response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "pages": 0
}
```

## Authentication

- Access token: JWT, HMAC via `SECRET_KEY`, lifetime 15 minutes. Claims: `sub` (user id), `role`, `exp`, `iat`, `jti`.
- Refresh token: 32-byte random URL-safe string, stored hashed (SHA-256). Lifetime 7 days. Sent in the JSON body in this version so a non-browser client can use it. Rotation issues a new token and revokes the previous one.
- Login failure, inactive user, and bad password all return the same 401 message.
- Logout revokes the presented refresh token.
- Password change revokes every refresh token for that user.
- Login attempts per email and IP are counted in Redis. The lockout threshold and window live in settings.

`SECRET_KEY` is required outside `local`. The process refuses to start when it is missing or shorter than 32 characters in non-local environments.

## Background jobs

Worker process: `arq app.workers.settings.WorkerSettings`.

| Job | Trigger |
| --- | --- |
| `notify_leave_decision` | Leave approved, rejected, or cancelled |
| `generate_report_export` | `POST /reports/exports` |
| `purge_expired_refresh_tokens` | nightly cron |
| `mark_missing_attendance` | nightly cron. Creates `absent` rows for active employees with no record and no approved leave |

Notification delivery in the first implementation writes a structured log and stores the intent. An SMTP provider can be added behind the same task without changing the leave service.

Redis also holds login rate-limit counters, the arq queue, and short-lived dashboard aggregates. Redis is not the source of truth for employees, leave, or tokens.

## Configuration

Settings class in `app/core/config.py` reads the environment. Names are already listed in `.env.example`. The application does not ship a real `.env`. Logging is JSON when `LOG_JSON=true`, with `request_id`, level, logger, and event. Passwords, tokens, and the secret key are never logged.

## Migrations

- Alembic is the only schema change path.
- `alembic/env.py` will use the async database URL from settings and import `app.models` so autogenerate sees the metadata.
- `script_location = alembic`. The database URL in `alembic.ini` stays empty so secrets are not written there.
- The first revision creates extensions only if we adopt the overlap exclusion constraint, then all tables, foreign keys, checks, and indexes above.
- Downgrades are required for every revision.

## Runtime

Docker Compose services, after approval:

| Service | Role | Health |
| --- | --- | --- |
| `postgres` | PostgreSQL 16 | `pg_isready` |
| `redis` | Redis 7 | `redis-cli ping` |
| `api` | Uvicorn, `app.main:app` | HTTP `GET /api/v1/health/ready` |
| `worker` | arq worker | process up; Redis connection on boot |

The API container starts only after Postgres and Redis are healthy, then runs `alembic upgrade head` before Uvicorn. Images use Python 3.12, a non-root user, and a multi-stage build. Tests are not copied into the runtime image.

## Quality gates

`pyproject.toml` will pin runtime and dev dependencies and configure:

- **Ruff** for lint and format, line length 88, target `py312`.
- **MyPy** strict on `app`, with SQLAlchemy's Pydantic plugins only if they are required.
- **Pytest** with `pytest-asyncio` in auto mode, `httpx.AsyncClient`, and `testcontainers` for PostgreSQL and Redis in integration tests.

Planned tests, matching the files already in `tests/`:

- Unit: password verification, access-token claims, permission map, refresh reuse detection, employee scope, leave balance and overlap rules.
- Integration: health checks, login and refresh rotation, employee list pagination and forbidden cross-scope reads, leave approval changing balances inside one transaction, unique `(employee_id, work_date)`.

CI (`.github/workflows/ci.yml`): on push and pull request, install the project, run Ruff, MyPy, and Pytest. Integration tests start their own database through testcontainers, so CI needs Docker.

Makefile targets to add with implementation: `install`, `lint`, `format`, `typecheck`, `test`, `migrate`, `up`, `down`.

## Logging and audit actions

Structured log on each request: method, path, status, duration, `request_id`, user id when authenticated. Do not log bodies.

Audit actions written by services on success: `auth.login`, `auth.logout`, `auth.password_changed`, `employee.created`, `employee.updated`, `employee.terminated`, `department.created`, `department.updated`, `attendance.checked_in`, `attendance.checked_out`, `attendance.corrected`, `leave.requested`, `leave.approved`, `leave.rejected`, `leave.cancelled`, `leave_balance.allocated`, `report.export_requested`.

## What implementation will produce next

After approval, code will be generated in this order:

1. Tooling: `pyproject.toml`, Ruff, MyPy, Pytest, Docker, and the empty Alembic environment.
2. Core: settings, logging, exceptions, security, RBAC, session, Redis.
3. Models and the initial Alembic revision.
4. Repositories, then services, then routers.
5. Worker tasks.
6. Unit tests, then integration tests.

No step writes schema SQL by hand outside Alembic revisions.
