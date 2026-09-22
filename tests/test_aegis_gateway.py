import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import aegis_gateway

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.old_token = aegis_gateway.TOKEN
        self.old_upstream = aegis_gateway.UPSTREAM
        aegis_gateway.TOKEN = "test-secret"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), aegis_gateway.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        aegis_gateway.TOKEN = self.old_token
        aegis_gateway.UPSTREAM = self.old_upstream

    def request(self, method, path, token=None, body=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = json.loads(response.read().decode())
        conn.close()
        return response.status, payload

    def test_requires_bearer_token(self):
        status, payload = self.request("GET", "/health")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")

    def test_rejects_unapproved_route(self):
        status, payload = self.request("GET", "/shell", "test-secret")
        self.assertEqual(status, 404)

    @patch("aegis_gateway.urlopen")
    def test_forwards_health(self, urlopen):
        class Response:
            status = 200
            def read(self, _limit): return b'{"ok": true, "agents": 2}'
            def __enter__(self): return self
            def __exit__(self, *_): return False
        urlopen.return_value = Response()
        status, payload = self.request("GET", "/health", "test-secret")
        self.assertEqual(status, 200)
        self.assertEqual(payload["agents"], 2)
        urlopen.assert_called_once()

    @patch("aegis_gateway.urlopen")
    def test_forwards_queue(self, urlopen):
        class Response:
            status = 200
            def read(self, _limit): return b'{"id": 7, "status": "queued"}'
            def __enter__(self): return self
            def __exit__(self, *_): return False
        urlopen.return_value = Response()
        status, payload = self.request("POST", "/queue", "test-secret", '{"hostname":"aegis-local","cmd":"echo ok"}')
        self.assertEqual(status, 200)
        self.assertEqual(payload["id"], 7)

    def test_limits_body_size(self):
        body = "x" * (aegis_gateway.MAX_BODY + 1)
        status, payload = self.request("POST", "/queue", "test-secret", body)
        self.assertEqual(status, 413)

if __name__ == "__main__":
    unittest.main()
