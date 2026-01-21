from _support_api import BaseAPITestCase


class TestStaticUI(BaseAPITestCase):
    def test_static_index(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"<!doctype html>"))

    def test_static_notifications_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'data-tab="notifications"', body)
        self.assertIn(b'id="tab-notifications"', body)

        status, _, js = self.http("GET", "/js/views/notifications.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"/api/notifications", js)

    def test_static_attachments_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'id="attachFile"', body)

        status, _, js = self.http("GET", "/js/create/submit.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"/api/requests/", js)
        self.assertIn(b"/attachments", js)

    def test_static_hr_admin_forms_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'id="overtimeFields"', body)
        self.assertIn(b'id="attendanceFields"', body)
        self.assertIn(b'id="businessTripFields"', body)
        self.assertIn(b'id="travelExpenseFields"', body)
        self.assertIn(b'id="salaryAdjustFields"', body)

        status, _, js = self.http("GET", "/js/workflows.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"attendance_correction", js)
        self.assertIn(b"travel_expense", js)
        self.assertIn(b"salary_adjustment", js)

    def test_static_finance_procurement_forms_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'id="loanFields"', body)
        self.assertIn(b'id="paymentFields"', body)
        self.assertIn(b'id="purchasePlusFields"', body)
        self.assertIn(b'id="inventoryOutFields"', body)
        self.assertIn(b'id="assetScrapFields"', body)

        status, _, js = self.http("GET", "/js/workflows.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"purchase_plus", js)
        self.assertIn(b"fixed_asset_accounting", js)
        self.assertIn(b"asset_scrap", js)

    def test_static_contract_it_logistics_forms_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'id="contractFields"', body)
        self.assertIn(b'id="vpnEmailFields"', body)
        self.assertIn(b'id="meetingRoomFields"', body)
        self.assertIn(b'id="policyAnnouncementFields"', body)
        self.assertIn(b'id="readAckFields"', body)

        status, _, js = self.http("GET", "/js/workflows.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"legal_review", js)
        self.assertIn(b"vpn_email", js)
        self.assertIn(b"meeting_room", js)
        self.assertIn(b"policy_announcement", js)
        self.assertIn(b"read_ack", js)

    def test_static_workflow_visual_editor_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'id="wfStepsEditor"', body)
        self.assertIn(b'id="wfStepsList"', body)
        self.assertIn(b'id="wfAddStepBtn"', body)
        self.assertIn(b'id="wfShowJsonBtn"', body)

        status, _, js = self.http("GET", "/js/admin/workflows_editor.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"renderWfStepsEditor", js)
        self.assertIn(b"readWfStepsEditor", js)

    def test_static_app_is_modularized(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'src="/js/dom.js"', body)
        self.assertIn(b'src="/app.js"', body)

        status, _, js = self.http("GET", "/app.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"bindAppEvents", js)
        self.assertIn(b"refreshAll", js)

    def test_static_roles_ui_wiring(self):
        status, _, body = self.http("GET", "/", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b'data-tab="roles"', body)
        self.assertIn(b'id="tab-roles"', body)

        status, _, js = self.http("GET", "/js/admin/roles.js", expect_json=False)
        self.assertEqual(status, 200)
        self.assertIn(b"/api/admin/roles", js)

