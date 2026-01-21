import time

from _support_api import BaseAPITestCase, db, hash_password


class TestWorkflowActions(BaseAPITestCase):
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

