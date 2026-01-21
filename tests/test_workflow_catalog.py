import os
import time
import uuid
from pathlib import Path

from _support_api import BaseAPITestCase, db


class TestWorkflowCatalog(BaseAPITestCase):
    def test_workflow_catalog_list(self):
        cookie = self.login("admin", "admin")
        status, _, data = self.http("GET", "/api/workflows", cookie=cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        self.assertTrue({"leave", "expense", "purchase", "generic"}.issubset(keys))

    def test_hr_admin_workflows_exist_and_can_create(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        hr_types = [
            ("overtime", "manager"),
            ("attendance_correction", "manager"),
            ("business_trip", "manager"),
            ("outing", "manager"),
            ("travel_expense", "manager"),
            ("onboarding", "hr"),
            ("probation", "manager"),
            ("resignation", "manager"),
            ("job_transfer", "manager"),
            ("salary_adjustment", "manager"),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _ in hr_types:
            self.assertIn(t, keys)

        for t, expected_step in hr_types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": f"{t} title", "body": "b"},
            )
            self.assertEqual(status, 201)
            req_id = created["id"]

            status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
            tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id]
            self.assertTrue(tasks)
            self.assertEqual(tasks[0]["task"]["step_key"], expected_step)

    def test_migrate_adds_hr_admin_workflows_to_existing_db(self):
        # Simulate an existing DB that is missing the newer HR/Admin workflow catalog entries.
        db_path = Path("data") / f"_mig_{int(time.time())}_{os.getpid()}_{uuid.uuid4().hex}.sqlite3"
        db.init_db(db_path)

        hr_keys = [
            "overtime",
            "attendance_correction",
            "business_trip",
            "outing",
            "travel_expense",
            "onboarding",
            "probation",
            "resignation",
            "job_transfer",
            "salary_adjustment",
        ]

        with db.connect(db_path) as conn:
            for k in hr_keys:
                conn.execute("DELETE FROM workflow_variant_steps WHERE workflow_key=?", (k,))
                conn.execute("DELETE FROM workflow_variants WHERE workflow_key=?", (k,))
                conn.execute("DELETE FROM workflow_steps WHERE request_type=?", (k,))
                conn.execute("DELETE FROM workflow_definitions WHERE request_type=?", (k,))

        db.init_db(db_path)
        with db.connect(db_path) as conn:
            rows = db.list_available_workflow_variants(conn, dept=None)
            keys = {str(r["workflow_key"]) for r in rows}
            for k in hr_keys:
                self.assertIn(k, keys)

    def test_workflow_admin_crud_and_dept_default(self):
        admin_cookie = self.login("admin", "admin")

        # Set user dept=IT so dept-scoped workflows become visible and defaultable.
        status, _, _ = self.http("POST", "/api/users/2", cookie=admin_cookie, json_body={"dept": "IT"})
        self.assertEqual(status, 204)

        # Create a dept-specific purchase workflow variant and set it as default for dept IT.
        variant = {
            "workflow_key": "purchase_it",
            "request_type": "purchase",
            "name": "IT 采购流程",
            "category": "Procurement",
            "scope_kind": "dept",
            "scope_value": "IT",
            "enabled": True,
            "is_default": True,
            "steps": [
                {"step_order": 1, "step_key": "manager", "assignee_kind": "manager"},
                {"step_order": 2, "step_key": "it_lead", "assignee_kind": "role", "assignee_value": "admin"},
                {"step_order": 3, "step_key": "finance", "assignee_kind": "role", "assignee_value": "admin"},
            ],
        }
        status, _, _ = self.http("POST", "/api/admin/workflows", cookie=admin_cookie, json_body=variant)
        self.assertEqual(status, 201)

        # User should see it in /api/workflows (dept-scoped visibility).
        user_cookie = self.login("user", "user")
        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        self.assertIn("purchase_it", keys)

        # Creating a purchase request without specifying workflow should pick the dept default.
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={
                "type": "purchase",
                "title": "",
                "body": "",
                "payload": {"items": [{"name": "Mouse", "qty": 1, "unit_price": 100}], "reason": "work"},
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["workflow"]["key"], "purchase_it")

        # Admin can delete it.
        status, _, _ = self.http(
            "POST",
            "/api/admin/workflows/delete",
            cookie=admin_cookie,
            json_body={"workflow_key": "purchase_it"},
        )
        self.assertEqual(status, 204)

