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
                self.assertEqual(mutation.exception.code, 405)
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


if __name__ == "__main__":
    unittest.main()
