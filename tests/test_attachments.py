import base64

from _support_api import BaseAPITestCase


class TestAttachments(BaseAPITestCase):
    def test_attachments_upload_and_download(self):
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

