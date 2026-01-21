import os
import sys
import threading
import time
import unittest
import uuid
from http.client import HTTPConnection
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from oa_server import db  # noqa: E402
from oa_server.server import Handler as BaseHandler  # noqa: E402
from oa_server.server import OAHTTPServer  # noqa: E402


class QuietHandler(BaseHandler):
    def log_message(self, fmt, *args):
        return


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Path("data").mkdir(parents=True, exist_ok=True)
        cls.db_path = Path("data") / f"_test_{int(time.time())}_{os.getpid()}_{uuid.uuid4().hex}.sqlite3"
        db.init_db(cls.db_path)
        cls.httpd = OAHTTPServer(("127.0.0.1", 0), QuietHandler, db_path=cls.db_path, frontend_dir=Path("frontend"))
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)

    def http(self, method, path, *, json_body=None, cookie=None, expect_json=True):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        body = None
        if cookie:
            headers["Cookie"] = cookie
        if json_body is not None:
            import json

            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        conn.request(method, path, body=body, headers=headers)
        res = conn.getresponse()
        raw = res.read()
        resp_headers = dict(res.getheaders())
        conn.close()
        if not expect_json:
            return res.status, resp_headers, raw
        if not raw:
            return res.status, resp_headers, None
        import json

        return res.status, resp_headers, json.loads(raw)

    def login(self, username, password):
        status, headers, _ = self.http("POST", "/api/login", json_body={"username": username, "password": password})
        self.assertEqual(status, 200)
        cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
        self.assertTrue(cookie.startswith("oa_session="))
        return cookie

    def test_static_index(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"<!doctype html>"))

    def test_me(self):
        cookie = self.login("admin", "admin")
        status, _, me = self.http("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(me["role"], "admin")

    def test_workflow_catalog_list(self):
        cookie = self.login("admin", "admin")
        status, _, data = self.http("GET", "/api/workflows", cookie=cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        self.assertTrue({"leave", "expense", "purchase", "generic"}.issubset(keys))

    def test_leave_flow(self):
        user_cookie = self.login("user", "user")
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "leave", "title": "leave-1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        admin_cookie = self.login("admin", "admin")
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertEqual(status, 200)
        items = [it for it in inbox["items"] if it["request"]["id"] == req_id]
        self.assertTrue(items)
        task_id = items[0]["task"]["id"]

        status, _, updated = self.http("POST", f"/api/tasks/{task_id}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

        status, _, detail = self.http("GET", f"/api/requests/{req_id}", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertTrue(detail["tasks"])

    def test_expense_flow(self):
        user_cookie = self.login("user", "user")
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "expense", "title": "expense-1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        admin_cookie = self.login("admin", "admin")
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertEqual(status, 200)
        manager_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "manager"]
        self.assertTrue(manager_tasks)
        manager_task_id = manager_tasks[0]["task"]["id"]

        status, _, updated = self.http(
            "POST",
            f"/api/tasks/{manager_task_id}/approve",
            cookie=admin_cookie,
            json_body={"comment": "ok"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        finance_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "finance"]
        self.assertTrue(finance_tasks)
        finance_task_id = finance_tasks[0]["task"]["id"]

        status, _, updated = self.http("POST", f"/api/tasks/{finance_task_id}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_workflow_is_configurable(self):
        # Make leave flow require 2 steps (manager -> admin) to verify it is DB-driven.
        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "leave",
                name="Leave (2-step)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "manager", "assignee_kind": "manager", "assignee_value": None},
                    {"step_order": 2, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "leave", "title": "leave-2step", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        admin_cookie = self.login("admin", "admin")
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertEqual(status, 200)
        manager_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "manager"]
        self.assertTrue(manager_tasks)

        status, _, updated = self.http(
            "POST",
            f"/api/tasks/{manager_tasks[0]['task']['id']}/approve",
            cookie=admin_cookie,
            json_body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        admin_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "admin"]
        self.assertTrue(admin_tasks)

        status, _, updated = self.http(
            "POST",
            f"/api/tasks/{admin_tasks[0]['task']['id']}/approve",
            cookie=admin_cookie,
            json_body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_expense_threshold_branching(self):
        # Configure expense as: manager -> gm(if amount>=5000) -> finance
        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "expense",
                name="Expense (threshold)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "manager", "assignee_kind": "manager"},
                    {
                        "step_order": 2,
                        "step_key": "gm",
                        "assignee_kind": "role",
                        "assignee_value": "admin",
                        "condition_kind": "min_amount",
                        "condition_value": "5000",
                    },
                    {"step_order": 3, "step_key": "finance", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "expense", "title": "", "body": "", "payload": {"amount": 100, "category": "test"}},
        )
        self.assertEqual(status, 201)
        req_id_low = created["id"]

        admin_cookie = self.login("admin", "admin")
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        manager_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id_low and it["task"]["step_key"] == "manager"]
        self.assertTrue(manager_tasks)
        manager_task_id = manager_tasks[0]["task"]["id"]

        status, _, updated = self.http("POST", f"/api/tasks/{manager_task_id}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        # low amount should skip gm and go straight to finance
        gm_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id_low and it["task"]["step_key"] == "gm"]
        self.assertFalse(gm_tasks)
        fin_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id_low and it["task"]["step_key"] == "finance"]
        self.assertTrue(fin_tasks)

        status, _, updated = self.http(
            "POST", f"/api/tasks/{fin_tasks[0]['task']['id']}/approve", cookie=admin_cookie, json_body={}
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

        # high amount should require gm
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "expense", "title": "", "body": "", "payload": {"amount": 6000, "category": "test"}},
        )
        self.assertEqual(status, 201)
        req_id_high = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        manager_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id_high and it["task"]["step_key"] == "manager"]
        self.assertTrue(manager_tasks)
        status, _, updated = self.http(
            "POST", f"/api/tasks/{manager_tasks[0]['task']['id']}/approve", cookie=admin_cookie, json_body={}
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        gm_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id_high and it["task"]["step_key"] == "gm"]
        self.assertTrue(gm_tasks)
        status, _, updated = self.http("POST", f"/api/tasks/{gm_tasks[0]['task']['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        fin_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id_high and it["task"]["step_key"] == "finance"]
        self.assertTrue(fin_tasks)
        status, _, updated = self.http(
            "POST", f"/api/tasks/{fin_tasks[0]['task']['id']}/approve", cookie=admin_cookie, json_body={}
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_leave_payload_validation(self):
        user_cookie = self.login("user", "user")
        status, _, err = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "leave", "title": "x", "body": "x", "payload": {"start_date": "2026-01-01"}},
        )
        self.assertEqual(status, 400)
        self.assertIn(err["error"], {"invalid_payload", "missing_fields"})

    def test_leave_payload_roundtrip(self):
        user_cookie = self.login("user", "user")
        payload = {"start_date": "2026-01-01", "end_date": "2026-01-02", "days": 2, "reason": "rest"}
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "leave", "title": "", "body": "", "payload": payload},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]
        self.assertEqual(created["type"], "leave")

        admin_cookie = self.login("admin", "admin")
        status, _, detail = self.http("GET", f"/api/requests/{req_id}", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(detail["request"]["type"], "leave")
        self.assertEqual(detail["request"]["payload"]["days"], 2)

    def test_purchase_payload_validation(self):
        user_cookie = self.login("user", "user")
        status, _, err = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "purchase", "title": "", "body": "", "payload": {"items": [{"name": "x", "qty": 0, "unit_price": 1}]}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(err["error"], "invalid_payload")

    def test_purchase_threshold_branching(self):
        # Configure purchase as: manager -> gm(if amount>=20000) -> procurement -> finance
        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "purchase",
                name="Purchase (threshold)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "manager", "assignee_kind": "manager"},
                    {
                        "step_order": 2,
                        "step_key": "gm",
                        "assignee_kind": "role",
                        "assignee_value": "admin",
                        "condition_kind": "min_amount",
                        "condition_value": "20000",
                    },
                    {"step_order": 3, "step_key": "procurement", "assignee_kind": "role", "assignee_value": "admin"},
                    {"step_order": 4, "step_key": "finance", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")

        def create_purchase(amount):
            payload = {"items": [{"name": "Laptop", "qty": 1, "unit_price": amount}], "reason": "work"}
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": "purchase", "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertEqual(created["type"], "purchase")
            self.assertEqual(created["payload"]["amount"], amount)
            return created["id"]

        low_id = create_purchase(1000)
        high_id = create_purchase(30000)

        admin_cookie = self.login("admin", "admin")

        # low amount: manager -> procurement -> finance (skip gm)
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertEqual(status, 200)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "manager"][0]
        status, _, updated = self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "gm"])
        proc = [it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "procurement"][0]
        status, _, _ = self.http("POST", f"/api/tasks/{proc['task']['id']}/approve", cookie=admin_cookie, json_body={})
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        fin = [it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "finance"][0]
        status, _, updated = self.http("POST", f"/api/tasks/{fin['task']['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(updated["status"], "approved")

        # high amount: manager -> gm -> procurement -> finance
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "manager"][0]
        status, _, _ = self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        gm = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "gm"][0]
        status, _, _ = self.http("POST", f"/api/tasks/{gm['task']['id']}/approve", cookie=admin_cookie, json_body={})
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        proc = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "procurement"][0]
        status, _, _ = self.http("POST", f"/api/tasks/{proc['task']['id']}/approve", cookie=admin_cookie, json_body={})
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        fin = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "finance"][0]
        status, _, updated = self.http("POST", f"/api/tasks/{fin['task']['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(updated["status"], "approved")


if __name__ == "__main__":
    unittest.main()
