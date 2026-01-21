import time

from _support_api import BaseAPITestCase, db, hash_password


class TestBuiltinPayloads(BaseAPITestCase):
    def test_hr_admin_payload_validation_and_title_autofill(self):
        user_cookie = self.login("user", "user")

        cases = [
            ("overtime", {"date": "2026-01-02", "hours": 2.5, "reason": "项目上线支持"}, "加班："),
            ("attendance_correction", {"date": "2026-01-03", "kind": "in", "time": "09:01", "reason": "忘记打卡"}, "补卡："),
            ("business_trip", {"start_date": "2026-01-04", "end_date": "2026-01-06", "destination": "上海", "purpose": "客户拜访"}, "出差："),
            ("outing", {"date": "2026-01-07", "start_time": "14:00", "end_time": "16:30", "destination": "银行", "reason": "业务办理"}, "外出："),
            ("travel_expense", {"start_date": "2026-01-04", "end_date": "2026-01-06", "amount": 123.45, "reason": "差旅报销"}, "差旅报销："),
            ("onboarding", {"name": "张三", "start_date": "2026-01-08", "dept": "研发", "position": "工程师"}, "入职："),
            ("probation", {"name": "李四", "start_date": "2025-10-01", "end_date": "2026-01-01", "result": "pass", "comment": "表现良好"}, "转正："),
            ("resignation", {"name": "王五", "last_day": "2026-02-01", "reason": "个人原因", "handover": "交接给赵六"}, "离职："),
            ("job_transfer", {"name": "赵六", "from_dept": "研发", "to_dept": "产品", "effective_date": "2026-03-01", "reason": "业务调整"}, "调岗："),
            ("salary_adjustment", {"name": "钱七", "effective_date": "2026-04-01", "from_salary": 10000, "to_salary": 12000, "reason": "绩效优秀"}, "调薪："),
        ]

        for t, payload, title_prefix in cases:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertEqual(created["type"], t)
            self.assertTrue(created["title"].startswith(title_prefix))
            self.assertIsInstance(created["payload"], dict)
            for k in payload.keys():
                self.assertIn(k, created["payload"])

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "overtime", "title": "", "body": "", "payload": {"date": "2026-01-02", "reason": "x"}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_finance_workflows_exist_and_payloads_work(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        finance_types = [
            ("loan", {"amount": 1000, "reason": "差旅备用金"}, "借款："),
            ("payment", {"payee": "某某供应商", "amount": 8888.88, "purpose": "服务费"}, "付款："),
            ("budget", {"dept": "研发", "amount": 20000, "period": "2026Q1", "purpose": "项目预算"}, "预算："),
            ("invoice", {"title": "某某科技有限公司", "amount": 1234.56, "purpose": "开票"}, "开票："),
            ("fixed_asset_accounting", {"asset_name": "笔记本电脑", "amount": 6999, "acquired_date": "2026-01-10"}, "固定资产入账："),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _, _ in finance_types:
            self.assertIn(t, keys)

        for t, payload, title_prefix in finance_types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["title"].startswith(title_prefix))

            req_id = created["id"]
            status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
            tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id]
            self.assertTrue(tasks)

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "loan", "title": "", "body": "", "payload": {"amount": 0, "reason": "x"}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_procurement_asset_workflows_exist_and_payloads_work(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        types = [
            (
                "purchase_plus",
                {
                    "items": [{"name": "显示器", "qty": 2, "unit_price": 999}],
                    "reason": "办公设备",
                    "vendor": "某某供应商",
                    "delivery_date": "2026-02-01",
                },
                "采购（增强）：",
            ),
            ("quote_compare", {"subject": "服务器采购比价", "vendors": ["A", "B", "C"], "recommendation": "推荐B"}, "比价："),
            ("acceptance", {"purchase_ref": "PO-2026-001", "acceptance_date": "2026-02-10", "summary": "到货完好"}, "验收："),
            ("inventory_in", {"warehouse": "主仓", "date": "2026-02-11", "items": [{"name": "键盘", "qty": 10}]}, "入库："),
            ("inventory_out", {"warehouse": "主仓", "date": "2026-02-12", "items": [{"name": "鼠标", "qty": 5}], "reason": "发放"}, "出库："),
            ("device_claim", {"item": "显示器", "qty": 1, "reason": "新员工入职"}, "申领："),
            ("asset_transfer", {"asset": "资产#A1001", "from_user": "张三", "to_user": "李四", "date": "2026-02-15"}, "调拨："),
            ("asset_maintenance", {"asset": "资产#A1001", "issue": "无法开机", "amount": 200}, "维修："),
            ("asset_scrap", {"asset": "资产#A1002", "scrap_date": "2026-02-20", "reason": "报废", "amount": 0}, "报废："),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _, _ in types:
            self.assertIn(t, keys)

        for t, payload, title_prefix in types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["title"].startswith(title_prefix))
            req_id = created["id"]
            status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
            tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id]
            self.assertTrue(tasks)

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={
                "type": "purchase_plus",
                "title": "",
                "body": "",
                "payload": {"items": [], "reason": "x", "vendor": "v", "delivery_date": "2026-02-01"},
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_contract_legal_workflows_exist_and_payloads_work(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        types = [
            (
                "contract",
                {
                    "name": "框架合同A",
                    "party": "某某公司",
                    "amount": 100000,
                    "start_date": "2026-03-01",
                    "end_date": "2027-03-01",
                    "summary": "年度框架合同",
                },
                "合同：",
            ),
            ("legal_review", {"subject": "合同A法务审查", "risk_level": "medium", "notes": "关注违约条款"}, "法务审查："),
            ("seal", {"document": "合同A", "seal_type": "公章", "purpose": "签约", "needed_date": "2026-02-25"}, "用章："),
            ("archive", {"document": "合同A", "archive_type": "合同", "retention_years": 5}, "归档："),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _, _ in types:
            self.assertIn(t, keys)

        for t, payload, title_prefix in types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["title"].startswith(title_prefix))
            req_id = created["id"]
            status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
            tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id]
            self.assertTrue(tasks)

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "seal", "title": "", "body": "", "payload": {"document": "", "seal_type": "公章", "purpose": "x", "needed_date": "2026-02-25"}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_it_access_workflows_exist_and_payloads_work(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        types = [
            ("account_open", {"system": "Jira", "account": "user1", "dept": "研发", "reason": "入职"}, "账号开通："),
            ("permission", {"system": "GitLab", "permission": "reporter", "duration_days": 30, "reason": "项目需要"}, "权限申请："),
            ("vpn_email", {"kind": "vpn", "account": "user1", "reason": "远程办公"}, "开通："),
            ("it_device", {"item": "笔记本电脑", "qty": 1, "reason": "新员工入职"}, "设备申请："),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _, _ in types:
            self.assertIn(t, keys)

        for t, payload, title_prefix in types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["title"].startswith(title_prefix))
            req_id = created["id"]
            status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
            tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id]
            self.assertTrue(tasks)

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={"type": "permission", "title": "", "body": "", "payload": {"system": "x", "permission": "", "duration_days": 0, "reason": "x"}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_logistics_workflows_exist_and_payloads_work(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        types = [
            ("meeting_room", {"room": "A101", "date": "2026-03-01", "start_time": "10:00", "end_time": "11:00", "subject": "项目例会"}, "会议室预定："),
            ("car", {"date": "2026-03-02", "start_time": "09:00", "end_time": "12:00", "from": "公司", "to": "客户现场", "reason": "拜访"}, "用车："),
            ("supplies", {"items": [{"name": "A4纸", "qty": 2}], "reason": "日常消耗"}, "物品领用："),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _, _ in types:
            self.assertIn(t, keys)

        for t, payload, title_prefix in types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=user_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["title"].startswith(title_prefix))
            req_id = created["id"]
            status, _, inbox = self.http("GET", "/api/inbox", cookie=admin_cookie)
            tasks = [it for it in inbox["items"] if it["request"]["id"] == req_id]
            self.assertTrue(tasks)

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=user_cookie,
            json_body={
                "type": "meeting_room",
                "title": "",
                "body": "",
                "payload": {"room": "A101", "date": "bad", "start_time": "10:00", "end_time": "11:00", "subject": "x"},
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_policy_compliance_workflows_exist_and_payloads_work(self):
        user_cookie = self.login("user", "user")
        admin_cookie = self.login("admin", "admin")

        types = [
            ("policy_announcement", {"subject": "制度更新", "content": "请大家遵守新制度", "effective_date": "2026-04-01"}, "公告："),
            ("read_ack", {"subject": "信息安全培训", "content": "请阅读并确认", "due_date": "2026-04-10"}, "阅读确认："),
        ]

        status, _, data = self.http("GET", "/api/workflows", cookie=user_cookie)
        self.assertEqual(status, 200)
        keys = {it["key"] for it in (data["items"] or [])}
        for t, _, _ in types:
            self.assertIn(t, keys)

        for t, payload, title_prefix in types:
            status, _, created = self.http(
                "POST",
                "/api/requests",
                cookie=admin_cookie,
                json_body={"type": t, "title": "", "body": "", "payload": payload},
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["title"].startswith(title_prefix))

        status, _, out = self.http(
            "POST",
            "/api/requests",
            cookie=admin_cookie,
            json_body={"type": "policy_announcement", "title": "", "body": "", "payload": {"subject": "", "content": "x"}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "invalid_payload")

    def test_read_ack_requires_all_users_to_ack(self):
        # Add an extra user to ensure read-ack creates tasks for all users (excluding the creator).
        with db.connect(self.db_path) as conn:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("u2", hash_password("u2"), "user", now),
            )

        admin_cookie = self.login("admin", "admin")

        status, _, created = self.http(
            "POST",
            "/api/requests",
            cookie=admin_cookie,
            json_body={
                "type": "read_ack",
                "title": "",
                "body": "",
                "payload": {"subject": "安全制度", "content": "请阅读并确认", "due_date": "2026-04-10"},
            },
        )
        self.assertEqual(status, 201)
        req_id = created["id"]

        # Delegate all non-admin users to admin so we can approve acknowledgements without knowing all passwords.
        with db.connect(self.db_path) as conn:
            users = db.list_users(conn)
            admin_id = [u for u in users if str(u["username"]) == "admin"][0]["id"]
            for u in users:
                if int(u["id"]) == int(admin_id):
                    continue
                db.set_delegation(conn, int(u["id"]), delegate_user_id=int(admin_id), active=True)

        status, _, detail = self.http("GET", f"/api/requests/{req_id}", cookie=admin_cookie)
        self.assertEqual(status, 200)
        ack_tasks = [t for t in (detail["tasks"] or []) if t["step_key"] == "ack" and t["status"] == "pending"]
        self.assertTrue(len(ack_tasks) >= 2)
        assignees = {t.get("assignee_username") for t in ack_tasks}
        self.assertIn("user", assignees)
        self.assertIn("u2", assignees)

        # Approve all but one; request should remain pending.
        for t in ack_tasks[:-1]:
            status, _, updated = self.http("POST", f"/api/tasks/{t['id']}/approve", cookie=admin_cookie, json_body={})
            self.assertEqual(status, 200)
            self.assertEqual(updated["status"], "pending")

        status, _, updated = self.http("POST", f"/api/tasks/{ack_tasks[-1]['id']}/approve", cookie=admin_cookie, json_body={})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "approved")

