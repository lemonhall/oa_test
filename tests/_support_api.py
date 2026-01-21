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


class BaseAPITestCase(unittest.TestCase):
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


__all__ = ["BaseAPITestCase", "QuietHandler", "db", "hash_password"]

