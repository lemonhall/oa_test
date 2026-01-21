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

1) Workflow config in DB (not hardcoded in code) ✅ (basic)
2) RBAC + menu permissions
3) Form templates (structured payload per request type)
4) Notifications (in-app first, then email/IM)
5) Attachments (local first, then object storage)
6) Reports + exports (CSV)

## Workflows (current)

Workflows are stored in SQLite:
- `workflow_definitions`: one row per request type
- `workflow_steps`: ordered steps (`step_order`) with assignee rules

Assignee rule (`assignee_kind`):
- `manager`: the request creator's `manager_id` (fallback to role `admin` if missing)
- `role`: assign to a role name in `assignee_value` (e.g. `admin`)
- `user`: assign to a specific user id in `assignee_value`

## Workflow catalog (tree-ready)

To support "company-wide vs department-specific" and future tree navigation, workflows now have a catalog layer:
- `workflow_variants`: a workflow "variant" identified by `workflow_key`
  - `category`: used for grouping in UI (tree root / folder)
  - `scope_kind/scope_value`: e.g. `global` or `dept` + dept name/value
  - multiple variants can exist for the same `request_type` (e.g. different purchase flows per dept)
- `workflow_variant_steps`: step definitions for a given `workflow_key`

Requests store the selected `workflow_key` (so the exact process is preserved even if defaults change later).

## Request payloads (current)

Some request types can store structured form data in `requests.payload_json` (JSON string), and the API also returns it as `request.payload`.

## Step conditions (current)

Workflow steps can optionally include conditions:
- `condition_kind`: currently supports `min_amount` (expense payload `amount` >= `condition_value`)
- `condition_value`: numeric threshold (stored as text)

## Added flows

- `expense`: manager -> gm(if amount>=5000) -> finance
- `purchase`: manager -> gm(if amount>=20000) -> procurement -> finance
