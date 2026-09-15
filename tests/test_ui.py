import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from r2s.core import discover
from r2s.storage import write_discovery
from r2s.ui import make_server, validate_ui_host

ROOT = Path(__file__).parent


class UIDashboardTests(unittest.TestCase):
    def _server(self, output_root: Path):
        server = make_server(output_root, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address[:2]
        return server, thread, f"http://{host}:{port}"

    def test_dashboard_serves_verified_run_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            output_root = Path(output)
            run_root = write_discovery(discover(ROOT / "fixtures/python_cli"), output_root)
            server, thread, base_url = self._server(output_root)
            try:
                with urlopen(base_url + "/") as response:
                    page = response.read().decode()
                    self.assertIn("Repo → Skill", page)
                    self.assertIn("Content-Security-Policy", response.headers)
                with urlopen(base_url + "/api/runs") as response:
                    runs = json.loads(response.read())
                self.assertEqual([item["run_id"] for item in runs["runs"]], [run_root.name])
                with urlopen(base_url + "/api/runs/" + run_root.name) as response:
                    detail = json.loads(response.read())
                self.assertEqual(detail["integrity"], "VERIFIED")
                self.assertEqual(detail["discovery"]["capabilities"], 1)
                self.assertEqual(detail["capabilities"][0]["command"], "demo")
                with urlopen(
                    base_url + "/api/runs/" + run_root.name + "/evidence?offset=0&limit=1"
                ) as response:
                    evidence = json.loads(response.read())
                self.assertEqual(evidence["limit"], 1)
                self.assertEqual(len(evidence["items"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_dashboard_is_read_only_and_rejects_invalid_routes(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            server, thread, base_url = self._server(Path(output))
            try:
                with self.assertRaises(HTTPError) as missing:
                    urlopen(base_url + "/api/runs/not-a-run")
                self.assertEqual(missing.exception.code, 404)
                with self.assertRaises(HTTPError) as mutation:
                    urlopen(Request(base_url + "/api/runs", method="POST"))
                self.assertEqual(mutation.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_dashboard_write_requires_token_and_runs_static_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            output_root = Path(output)
            server, thread, base_url = self._server(output_root)
            try:
                with urlopen(base_url + "/api/session") as response:
                    token = json.loads(response.read())["csrf_token"]
                body = json.dumps({"source": str(ROOT / "fixtures/python_cli")}).encode()
                request = Request(
                    base_url + "/api/runs", data=body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": base_url,
                        "X-R2S-UI-Token": token,
                    },
                )
                with urlopen(request) as response:
                    created = json.loads(response.read())
                self.assertTrue(created["run_id"].startswith("run_"))
                goal_body = json.dumps({"goal": "inspect options", "target": "portable"}).encode()
                build_request = Request(
                    base_url + "/api/runs/" + created["run_id"] + "/compilations",
                    data=goal_body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": base_url,
                        "X-R2S-UI-Token": token,
                    },
                )
                with urlopen(build_request) as response:
                    built = json.loads(response.read())
                self.assertEqual(built["result"]["readiness"], "STATIC_READY")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_dashboard_requires_loopback_binding(self) -> None:
        for host in ("0.0.0.0", "192.168.1.2", "example.com"):
            with self.subTest(host=host), self.assertRaisesRegex(
                ValueError,
                "UI_HOST_MUST_BE_LOOPBACK",
            ):
                validate_ui_host(host)

    def test_rebinding_and_bad_payloads_fail_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            server, thread, base_url = self._server(Path(output))
            try:
                for route in ("/", "/api/session", "/api/runs"):
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(Request(base_url + route, headers={"Host": "attacker.invalid"}))
                    self.assertEqual(failure.exception.code, 403)
                with urlopen(base_url + "/api/session") as response:
                    token = json.loads(response.read())["csrf_token"]
                for body in ([], {"source": "/"}, {"source": False}):
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(Request(base_url + "/api/runs", data=json.dumps(body).encode(), headers={
                            "Content-Type": "application/json", "Origin": base_url,
                            "X-R2S-UI-Token": token,
                        }))
                    self.assertEqual(failure.exception.code, 409)
                with self.assertRaises(HTTPError) as cross_origin:
                    urlopen(Request(base_url + "/api/runs", data=b"{}", headers={
                        "Content-Type": "application/json", "Origin": "https://attacker.invalid",
                        "X-R2S-UI-Token": token,
                    }))
                self.assertEqual(cross_origin.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
