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
from oa_server.auth import hash_password  # noqa: E402
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

    def test_static_notifications_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'data-tab="notifications"', body)
        self.assertIn(b'id="tab-notifications"', body)

        status, _, js = self.http("GET", "/app.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"/api/notifications", js)

    def test_static_attachments_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'id="attachFile"', body)

        status, _, js = self.http("GET", "/app.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"/api/requests/", js)
        self.assertIn(b"/attachments", js)

    def test_static_roles_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'data-tab="roles"', body)
        self.assertIn(b'id="tab-roles"', body)

        status, _, js = self.http("GET", "/app.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"/api/admin/roles", js)

    def test_me(self):
        cookie = self.login("admin", "admin")
        status, _, me = self.http("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(me["role"], "admin")

    def test_me_includes_permissions(self):
        cookie = self.login("user", "user")
        status, _, me = self.http("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("permissions", me)
        self.assertIsInstance(me["permissions"], list)

    def test_rbac_role_can_read_all_requests(self):
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("auditor", hash_password("auditor"), "auditor", now),
            )

        admin_cookie = self.login("admin", "admin")
        user_cookie = self.login("user", "user")
        auditor_cookie = self.login("auditor", "auditor")

        status, _, _ = self.http(
            "POST",
            "/api/admin/roles",
            cookie=admin_cookie,
            json_body={"role": "auditor", "permissions": ["requests:read_all"]},
        )
        self.assertEqual(status, 201)

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "r1", "body": "b"},
        )
        self.assertEqual(status, 201)
        r1 = created["id"]

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=auditor_cookie,
            json_body={"type": "generic", "title": "r2", "body": "b"},
        )
        self.assertEqual(status, 201)

        status, _, out = self.http("GET", "/api/requests?scope=all", cookie=auditor_cookie)
        self.assertEqual(status, 200)
        self.assertTrue([it for it in out["items"] if it["id"] == r1])

    def test_admin_can_update_user_role(self):
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            cur = conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("rbac_user", hash_password("rbac_user"), "user", now),
            )
            rbac_user_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("other_user", hash_password("other_user"), "user", now),
            )

        admin_cookie = self.login("admin", "admin")
        rbac_cookie = self.login("rbac_user", "rbac_user")
        other_cookie = self.login("other_user", "other_user")

        status, _, _ = self.http(
            "POST",
            "/api/admin/roles",
            cookie=admin_cookie,
            json_body={"role": "auditor", "permissions": ["requests:read_all"]},
        )
        self.assertEqual(status, 201)

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=other_cookie,
            json_body={"type": "generic", "title": "other", "body": "b"},
        )
        self.assertEqual(status, 201)
        other_req = created["id"]

        status, _, _ = self.http("GET", "/api/requests?scope=all", cookie=rbac_cookie)
        self.assertEqual(status, 403)

        status, _, _ = self.http(
            "POST",
            f"/api/users/{rbac_user_id}",
            cookie=admin_cookie,
            json_body={"role": "auditor"},
        )
        self.assertEqual(status, 204)

        status, _, out = self.http("GET", "/api/requests?scope=all", cookie=rbac_cookie)
        self.assertEqual(status, 200)
        self.assertTrue([it for it in out["items"] if it["id"] == other_req])

    def test_departments_tree_and_user_position(self):
        admin_cookie = self.login("admin", "admin")

        status, _, created = self.http(
            "POST",
            "/api/admin/departments",
            cookie=admin_cookie,
            json_body={"name": "HQ"},
        )
        self.assertEqual(status, 201)
        hq_id = created["id"]

        status, _, created = self.http(
            "POST",
            "/api/admin/departments",
            cookie=admin_cookie,
            json_body={"name": "IT", "parent_id": hq_id},
        )
        self.assertEqual(status, 201)
        it_id = created["id"]

        status, _, _ = self.http(
            "POST",
            "/api/users/2",
            cookie=admin_cookie,
            json_body={"dept_id": it_id, "position": "Engineer"},
        )
        self.assertEqual(status, 204)

        status, _, data = self.http("GET", "/api/admin/departments", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertTrue([d for d in data["items"] if d["id"] == it_id and d["parent_id"] == hq_id])

        status, _, tree = self.http("GET", "/api/org/tree", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertTrue([n for n in tree["items"] if n["name"] == "HQ" and n["children"]])

        status, _, users = self.http("GET", "/api/users", cookie=admin_cookie)
        self.assertEqual(status, 200)
        u = [x for x in users["items"] if x["id"] == 2][0]
        self.assertEqual(u["dept_id"], it_id)
        self.assertEqual(u["position"], "Engineer")

    def test_requests_search_and_csv_export(self):
        admin_cookie = self.login("admin", "admin")
        user_cookie = self.login("user", "user")

        tag = uuid.uuid4().hex[:8]
        t1 = f"alpha-{tag}"
        t2 = f"beta-{tag}"
        self.http("POST", "/api/requests", cookie=user_cookie, json_body={"type": "generic", "title": t1, "body": "b"})
        self.http("POST", "/api/requests", cookie=user_cookie, json_body={"type": "generic", "title": t2, "body": "b"})

        status, _, data = self.http("GET", f"/api/requests?scope=all&q={t1}", cookie=admin_cookie)
        self.assertEqual(status, 200)
        titles = [it["title"] for it in (data["items"] or [])]
        self.assertIn(t1, titles)
        self.assertNotIn(t2, titles)

        status, headers, raw = self.http(
            "GET",
            f"/api/requests?scope=all&format=csv&q={tag}",
            cookie=admin_cookie,
            expect_json=False,
        )
        self.assertEqual(status, 200)
        self.assertTrue((headers.get("Content-Type", "") or "").startswith("text/csv"))
        self.assertIn(t1.encode("utf-8"), raw)
        self.assertIn(t2.encode("utf-8"), raw)

    def test_workflow_catalog_list(self):
        cookie = self.login("admin", "admin")
        status, _, data = self.http("GET", "/api/workflows", cookie=cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        self.assertTrue({"leave", "expense", "purchase", "generic"}.issubset(keys))

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
        status, _, _ = self.http("POST", "/api/admin/workflows/delete", cookie=admin_cookie, json_body={"workflow_key": "purchase_it"})
        self.assertEqual(status, 204)

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

    def test_step_conditions_max_amount_min_amount(self):
        # Configure expense as:
        # manager -> audit(if amount<=1000) -> gm(if amount>=5000) -> finance
        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "expense",
                name="Expense (conditions)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "manager", "assignee_kind": "manager"},
                    {
                        "step_order": 2,
                        "step_key": "audit",
                        "assignee_kind": "role",
                        "assignee_value": "admin",
                        "condition_kind": "max_amount",
                        "condition_value": "1000",
                    },
                    {
                        "step_order": 3,
                        "step_key": "gm",
                        "assignee_kind": "role",
                        "assignee_value": "admin",
                        "condition_kind": "min_amount",
                        "condition_value": "5000",
                    },
                    {"step_order": 4, "step_key": "finance", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        def create_exp(amount):
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": "expense", "title": "", "body": "", "payload": {"amount": amount, "category": "t"}},
            )
            self.assertEqual(status, 201)
            return created["id"]

        low_id = create_exp(600)
        high_id = create_exp(6000)

        # low: manager -> audit -> finance (skip gm)
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "manager"][0]
        self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "audit"])
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "gm"])

        audit = [it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "audit"][0]
        self.http("POST", f"/api/tasks/{audit['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        fin = [it for it in inbox["items"] if it["request"]["id"] == low_id and it["task"]["step_key"] == "finance"][0]
        status, _, updated = self.http("POST", f"/api/tasks/{fin['task']['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

        # high: manager -> gm -> finance (skip audit)
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "manager"][0]
        self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "audit"])
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "gm"])

        gm = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "gm"][0]
        self.http("POST", f"/api/tasks/{gm['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        fin = [it for it in inbox["items"] if it["request"]["id"] == high_id and it["task"]["step_key"] == "finance"][0]
        status, _, updated = self.http("POST", f"/api/tasks/{fin['task']['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_step_condition_dept_in(self):
        admin_cookie = self.login("admin", "admin")
        # user dept=IT
        status, _, _ = self.http("POST", "/api/users/2", cookie=admin_cookie, json_body={"dept": "IT"})
        self.assertEqual(status, 204)

        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "purchase",
                name="Purchase (dept_in)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "manager", "assignee_kind": "manager"},
                    {
                        "step_order": 2,
                        "step_key": "it_lead",
                        "assignee_kind": "role",
                        "assignee_value": "admin",
                        "condition_kind": "dept_in",
                        "condition_value": "IT,Dev",
                    },
                    {"step_order": 3, "step_key": "finance", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "purchase", "title": "", "body": "", "payload": {"items": [{"name": "Mouse", "qty": 1, "unit_price": 100}], "reason": "work"}},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "manager"][0]
        self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "it_lead"])

        # switch user dept=HR -> should skip it_lead
        status, _, _ = self.http("POST", "/api/users/2", cookie=admin_cookie, json_body={"dept": "HR"})
        self.assertEqual(status, 204)
        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "purchase", "title": "", "body": "", "payload": {"items": [{"name": "Mouse", "qty": 1, "unit_price": 100}], "reason": "work"}},
        )
        self.assertEqual(status, 201)
        req2 = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == req2 and it["task"]["step_key"] == "manager"][0]
        self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == req2 and it["task"]["step_key"] == "it_lead"])

    def test_step_condition_min_days(self):
        # leave: manager -> hr(if days>=3) -> admin
        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "leave",
                name="Leave (min_days)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "manager", "assignee_kind": "manager"},
                    {
                        "step_order": 2,
                        "step_key": "hr",
                        "assignee_kind": "role",
                        "assignee_value": "admin",
                        "condition_kind": "min_days",
                        "condition_value": "3",
                    },
                    {"step_order": 3, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        def create_leave(days):
            payload = {"start_date": "2026-01-01", "end_date": "2026-01-02", "days": days, "reason": "r"}
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": "leave", "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            return created["id"]

        short_id = create_leave(2)
        long_id = create_leave(3)

        # short: manager -> admin (skip hr)
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == short_id and it["task"]["step_key"] == "manager"][0]
        self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == short_id and it["task"]["step_key"] == "hr"])
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == short_id and it["task"]["step_key"] == "admin"])

        # long: manager -> hr -> admin
        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        mgr = [it for it in inbox["items"] if it["request"]["id"] == long_id and it["task"]["step_key"] == "manager"][0]
        self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == long_id and it["task"]["step_key"] == "hr"])

    def test_parallel_approvals_users_all_and_any(self):
        # Create an extra approver user.
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("approver", hash_password("approver"), "user", now),
            )
            approver_id = int(conn.execute("SELECT id FROM users WHERE username='approver'").fetchone()["id"])

            # Generic: users_all( admin + approver ) -> admin
            db.replace_workflow_steps(
                conn,
                "generic",
                name="Generic (users_all)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "countersign", "assignee_kind": "users_all", "assignee_value": f"1,{approver_id}"},
                    {"step_order": 2, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")
        approver_cookie = self.login("approver", "approver")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "g1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        # both should have a countersign task
        status, _, inbox_a = self.http("GET", "/api/inbox", cookie=admin_cookie)
        status, _, inbox_b = self.http("GET", "/api/inbox", cookie=approver_cookie)
        t_admin = [it for it in inbox_a["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "countersign"][0]
        t_appr = [it for it in inbox_b["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "countersign"][0]

        # approver approves: should NOT advance yet (admin still pending)
        self.http("POST", f"/api/tasks/{t_appr['task']['id']}/approve", cookie=approver_cookie, json_body={})
        status, _, inbox_a = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox_a["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "admin"])

        # admin approves: now admin step should exist
        self.http("POST", f"/api/tasks/{t_admin['task']['id']}/approve", cookie=admin_cookie, json_body={})
        status, _, inbox_a = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox_a["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "admin"])

        # users_any: first approval advances and cancels remaining pending tasks
        with db.connect(self.db_path) as conn:
            db.replace_workflow_steps(
                conn,
                "generic",
                name="Generic (users_any)",
                enabled=True,
                steps=[
                    {"step_order": 1, "step_key": "anysign", "assignee_kind": "users_any", "assignee_value": f"1,{approver_id}"},
                    {"step_order": 2, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"},
                ],
            )

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "g2", "body": "b"},
        )
        self.assertEqual(status, 201)
        req2 = created["id"]

        status, _, inbox_b = self.http("GET", "/api/inbox", cookie=approver_cookie)
        t_appr = [it for it in inbox_b["items"] if it["request"]["id"] == req2 and it["task"]["step_key"] == "anysign"][0]
        self.http("POST", f"/api/tasks/{t_appr['task']['id']}/approve", cookie=approver_cookie, json_body={})

        status, _, inbox_a = self.http("GET", "/api/inbox", cookie=admin_cookie)
        # should advance to admin step
        self.assertTrue([it for it in inbox_a["items"] if it["request"]["id"] == req2 and it["task"]["step_key"] == "admin"])
        # should not still show pending anysign task for admin
        self.assertFalse([it for it in inbox_a["items"] if it["request"]["id"] == req2 and it["task"]["step_key"] == "anysign"])

    def test_return_for_changes_and_resubmit(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "needs changes", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]

        status, _, updated = self.http(
            "POST",
            f"/api/tasks/{task_id}/return",
            cookie=admin_cookie,
            json_body={"comment": "please update"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "changes_requested")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=user_cookie)
        resubmit_tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id and it["task"]["step_key"] == "resubmit"]
        self.assertTrue(resubmit_tasks)

        status, _, updated = self.http(
            "POST",
            f"/api/requests/{req_id}/resubmit",
            cookie=user_cookie,
            json_body={"title": "updated", "body": "updated body"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == req_id])

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

    def test_withdraw_and_void(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "w1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == req_id])

        status, _, updated = self.http("POST", f"/api/requests/{req_id}/withdraw", cookie=user_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "withdrawn")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == req_id])

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "v1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req2 = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertTrue([it for it in inbox["items"] if it["request"]["id"] == req2])

        status, _, updated = self.http("POST", f"/api/requests/{req2}/void", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "voided")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == req2])

    def test_task_transfer(self):
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("transfer_to", hash_password("transfer_to"), "user", now),
            )
            transfer_to_id = int(conn.execute("SELECT id FROM users WHERE username='transfer_to'").fetchone()["id"])
            db.replace_workflow_steps(
                conn,
                "generic",
                name="Generic (admin only)",
                enabled=True,
                steps=[{"step_order": 1, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"}],
            )

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")
        transfer_cookie = self.login("transfer_to", "transfer_to")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "transfer", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]

        status, _, updated = self.http(
            "POST",
            f"/api/tasks/{task_id}/transfer",
            cookie=admin_cookie,
            json_body={"assignee_user_id": transfer_to_id},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        self.assertFalse([it for it in inbox["items"] if it["request"]["id"] == req_id])

        status, _, inbox = self.http("GET", "/api/inbox", cookie=transfer_cookie)
        task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]
        status, _, updated = self.http("POST", f"/api/tasks/{task_id}/approve", cookie=transfer_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_add_sign_requires_both_approvals(self):
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("signer", hash_password("signer"), "user", now),
            )
            signer_id = int(conn.execute("SELECT id FROM users WHERE username='signer'").fetchone()["id"])
            db.replace_workflow_steps(
                conn,
                "generic",
                name="Generic (admin only)",
                enabled=True,
                steps=[{"step_order": 1, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"}],
            )

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")
        signer_cookie = self.login("signer", "signer")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "addsign", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        admin_task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]

        status, _, updated = self.http(
            "POST",
            f"/api/tasks/{admin_task_id}/addsign",
            cookie=admin_cookie,
            json_body={"assignee_user_id": signer_id},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "pending")

        self.http("POST", f"/api/tasks/{admin_task_id}/approve", cookie=admin_cookie, json_body={})
        status, _, updated = self.http("GET", f"/api/requests/{req_id}", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(updated["request"]["status"], "pending")

        status, _, inbox = self.http("GET", "/api/inbox", cookie=signer_cookie)
        signer_task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]
        status, _, updated = self.http("POST", f"/api/tasks/{signer_task_id}/approve", cookie=signer_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_delegation_proxy_can_approve_for_assignee(self):
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("proxy", hash_password("proxy"), "user", now),
            )
            proxy_id = int(conn.execute("SELECT id FROM users WHERE username='proxy'").fetchone()["id"])
            db.replace_workflow_steps(
                conn,
                "generic",
                name="Generic (explicit admin user)",
                enabled=True,
                steps=[{"step_order": 1, "step_key": "admin", "assignee_kind": "user", "assignee_value": "1"}],
            )

        admin_cookie = self.login("admin", "admin")
        user_cookie = self.login("user", "user")
        proxy_cookie = self.login("proxy", "proxy")

        status, _, _ = self.http(
            "POST",
            "/api/me/delegation",
            cookie=admin_cookie,
            json_body={"delegate_user_id": proxy_id},
        )
        self.assertEqual(status, 201)

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "proxy approve", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, inbox = self.http("GET", "/api/inbox", cookie=proxy_cookie)
        task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]
        status, _, updated = self.http("POST", f"/api/tasks/{task_id}/approve", cookie=proxy_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

    def test_cc_watchers_and_notifications(self):
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("cc_user", hash_password("cc_user"), "user", now),
            )
            cc_user_id = int(conn.execute("SELECT id FROM users WHERE username='cc_user'").fetchone()["id"])
            db.replace_workflow_steps(
                conn,
                "generic",
                name="Generic (admin only)",
                enabled=True,
                steps=[{"step_order": 1, "step_key": "admin", "assignee_kind": "role", "assignee_value": "admin"}],
            )

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")
        cc_cookie = self.login("cc_user", "cc_user")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "cc1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        status, _, _ = self.http(
            "POST",
            f"/api/requests/{req_id}/watchers",
            cookie=user_cookie,
            json_body={"kind": "cc", "user_ids": [cc_user_id]},
        )
        self.assertEqual(status, 201)

        status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
        task_id = [it for it in inbox["items"] if it["request"]["id"] == req_id][0]["task"]["id"]
        status, _, updated = self.http("POST", f"/api/tasks/{task_id}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

        status, _, notif = self.http("GET", "/api/notifications", cookie=cc_cookie)
        self.assertEqual(status, 200)
        items = notif["items"] or []
        related = [n for n in items if n["request_id"] == req_id and n["event_type"] == "request_approved"]
        self.assertTrue(related)

        status, _, _ = self.http("POST", f"/api/notifications/{related[0]['id']}/read", cookie=cc_cookie, json_body={})
        self.assertEqual(status, 204)

        status, _, notif = self.http("GET", "/api/notifications", cookie=cc_cookie)
        items = notif["items"] or []
        target = [n for n in items if n["id"] == related[0]["id"]][0]
        self.assertIsNotNone(target["read_at"])

    def test_attachments_upload_and_download(self):
        import base64

        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "generic", "title": "att1", "body": "b"},
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        content = b"hello attachment"
        status, _, uploaded = self.http(
            "POST",
            f"/api/requests/{req_id}/attachments",
            cookie=user_cookie,
            json_body={
                "filename": "a.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
        )
        self.assertEqual(status, 201)
        att_id = uploaded["id"]

        status, headers, raw = self.http(
            "GET",
            f"/api/attachments/{att_id}/download",
            cookie=admin_cookie,
            expect_json=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(raw, content)
        self.assertEqual(headers.get("Content-Type"), "text/plain")
        self.assertIn("attachment", (headers.get("Content-Disposition", "") or "").lower())

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
