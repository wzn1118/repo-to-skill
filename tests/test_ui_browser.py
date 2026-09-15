import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from r2s.ui import make_server

CHROME = os.environ.get("R2S_TEST_CHROME")
pytestmark = pytest.mark.skipif(not CHROME, reason="Set R2S_TEST_CHROME; browser integration also needs Node 22+")


def test_browser_static_workbench(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[1]
    source = project / "tests/fixtures/python_cli"
    server = make_server(tmp_path / "output", "127.0.0.1", 0, (source,))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    profile = tmp_path / "browser"
    with subprocess.Popen([
        CHROME or "", "--headless", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=0",
        f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as browser:
        try:
            port_file = profile / "DevToolsActivePort"
            for _ in range(100):
                if port_file.is_file():
                    break
                if browser.poll() is not None:
                    pytest.fail("Browser exited before opening debug port")
                time.sleep(0.1)
            port = int(port_file.read_text().splitlines()[0])
            completed = subprocess.run([
                "node", str(project / "scripts/check_ui_browser.mjs"),
                f"http://127.0.0.1:{port}", f"http://127.0.0.1:{server.server_port}", str(source),
                os.environ.get("R2S_TEST_SCREENSHOT", str(tmp_path / "workbench.png")),
            ], capture_output=True, text=True, timeout=60, check=False)
            assert completed.returncode == 0, completed.stderr
            result = json.loads(completed.stdout)
            assert result["javascriptExceptions"] == 0
            assert len(result["checks"]) == 6
            print(completed.stdout)
        finally:
            browser.terminate()
            try:
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=5)
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
