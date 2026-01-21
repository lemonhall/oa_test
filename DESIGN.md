# OA Design Notes (iterative)

Goal: build a small but extensible OA baseline with **vanilla JS + Python (uv) + SQLite**.

## What we have now (v0)

- Cookie session login (`users` + `sessions`)
- Requests: create / list / detail
- Task-driven approvals (`tasks` table) + "Inbox"
- Basic request types + built-in flows:
  - `leave`: `manager` -> done
  - `expense`: `manager` -> `finance` (admin role) -> done
  - `generic`: `admin` -> done
- Admin user management: maintain `dept` and `manager_id`
- Audit trail: `request_events` (created / task created / task decided / final status)

## Core concepts

- Org: users / dept / manager relation
- RBAC: role -> permissions (demo keeps `admin` / `user`)
- Workflow: request type -> ordered steps
- Task: a single approval step assigned to a user or role
- Audit: all key actions are persisted for traceability

## Suggested next iterations

1) Workflow config in DB (not hardcoded in code)
2) RBAC + menu permissions
3) Form templates (structured payload per request type)
4) Notifications (in-app first, then email/IM)
5) Attachments (local first, then object storage)
6) Reports + exports (CSV)

