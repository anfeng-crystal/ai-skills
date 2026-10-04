"""Loopback-only transport and offline URL-boundary regression checks."""

import sys
import json
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import network_probe
import poc_runner


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.paths.append(self.path)
        if self.path.startswith("/redirect/"):
            code = int(self.path.rsplit("/", 1)[-1])
            self.send_response(code)
            self.send_header("Location", self.server.destination)
        else:
            self.send_response(200)
        self.end_headers()

    do_HEAD = do_GET

    def log_message(self, *args):
        pass


class TransportScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servers = [ThreadingHTTPServer(("127.0.0.1", 0), Handler) for _ in range(2)]
        cls.threads = []
        for server in cls.servers:
            server.paths = []
            server.destination = ""
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)
        cls.base, cls.other = [f"http://127.0.0.1:{s.server_port}" for s in cls.servers]

    @classmethod
    def tearDownClass(cls):
        for server, thread in zip(cls.servers, cls.threads):
            server.shutdown()
            server.server_close()
            thread.join()

    def test_redirect_does_not_send_second_request(self):
        for destination in (self.base + "/same-origin", self.other + "/other-origin",
                            "file:///denied?custom=synthetic-location-secret#synthetic-fragment-secret"):
            for code in (301, 302, 303, 307, 308):
                for caller in ("poc", "probe"):
                    with self.subTest(destination=destination, status=code, caller=caller):
                        for server in self.servers:
                            server.paths.clear()
                        self.servers[0].destination = destination
                        url = self.base + f"/redirect/{code}"
                        if caller == "poc":
                            request = urllib.request.Request(url, headers={"access_token": "synthetic-test-only"})
                            result = poc_runner.run_request(request, 2)
                        else:
                            result = network_probe.probe(url, 2)
                        self.assertEqual([f"/redirect/{code}"], self.servers[0].paths)
                        self.assertEqual([], self.servers[1].paths)
                        self.assertFalse(result["ok"])
                        self.assertEqual(code, result["status"])
                        self.assertTrue(result["redirect_blocked"])
                        self.assertNotIn("synthetic-location-secret", json.dumps(result))
                        self.assertNotIn("synthetic-fragment-secret", json.dumps(result))

    def test_direct_request_still_succeeds(self):
        self.assertTrue(poc_runner.run_request(urllib.request.Request(self.base + "/ok"), 2)["ok"])
        self.assertTrue(network_probe.probe(self.base + "/ok", 2)["ok"])


class InitialRouteScopeTest(unittest.TestCase):
    def test_route_cannot_leave_approved_base(self):
        for path in ("../admin", "/../admin", "api/../../admin", "../ierp-other/admin",
                     "https://other.invalid/api", "//other.invalid/api", "..%2fadmin",
                     "%252e%252e%252fadmin", "..\\admin"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                poc_runner.build_request("https://approved.invalid/ierp", {"path": path})

    def test_in_scope_route_and_payload_are_preserved(self):
        req = poc_runner.build_request("https://approved.invalid/ierp", {
            "path": "/api/check", "method": "POST", "params": {"q": "../test.txt"},
            "body": "../test.txt", "headers": {"access_token": "synthetic-test-only"},
        })
        self.assertEqual("https://approved.invalid/ierp/api/check?q=..%2Ftest.txt", req.full_url)
        self.assertEqual(b"../test.txt", req.data)
        self.assertEqual("POST", req.get_method())
        self.assertIn(("Access_token", "synthetic-test-only"), req.header_items())


if __name__ == "__main__":
    unittest.main()
