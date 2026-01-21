import time
import uuid

from _support_api import BaseAPITestCase, db, hash_password


class TestAuthRbacOrgSearch(BaseAPITestCase):
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

        status, _, _ = self.http(
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

