import time

from _support_api import BaseAPITestCase, db, hash_password


class TestWorkflowEngine(BaseAPITestCase):
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
            json_body={
                "type": "purchase",
                "title": "",
                "body": "",
                "payload": {"items": [{"name": "Mouse", "qty": 1, "unit_price": 100}], "reason": "work"},
            },
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
            json_body={
                "type": "purchase",
                "title": "",
                "body": "",
                "payload": {"items": [{"name": "Mouse", "qty": 1, "unit_price": 100}], "reason": "work"},
            },
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
                    {
                        "step_order": 1,
                        "step_key": "countersign",
                        "assignee_kind": "users_all",
                        "assignee_value": f"1,{approver_id}",
                    },
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

