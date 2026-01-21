from _support_api import BaseAPITestCase, db


class TestPayloadRoundtrip(BaseAPITestCase):
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
            json_body={
                "type": "purchase",
                "title": "",
                "body": "",
                "payload": {"items": [{"name": "x", "qty": 0, "unit_price": 1}]},
            },
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
        status, _, _ = self.http("POST", f"/api/tasks/{mgr['task']['id']}/approve", cookie=admin_cookie, json_body={})
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

