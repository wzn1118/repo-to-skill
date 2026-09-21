import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.model_adapter import ModelConfig, propose


def test_model_preview_is_offline_and_execute_requires_transfer_authorization():
    discovery = discover(Path(__file__).parent / "fixtures/python_cli")
    config = ModelConfig(endpoint="https://model.example.invalid/propose", model="fixed-model")
    preview = propose(discovery, "inspect commands", config)
    assert preview["status"] == "PREVIEW" and preview["actual_usage"] is None
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        propose(discovery, "inspect commands", config, execute=True)


def test_model_endpoint_rejects_embedded_credentials():
    discovery = discover(Path(__file__).parent / "fixtures/python_cli")
    with pytest.raises(ValueError, match="ENDPOINT_INVALID"):
        propose(discovery, "inspect commands", ModelConfig(endpoint="https://secret@example.invalid", model="fixed"))


def test_gateway_candidates_require_real_facts_and_record_reported_usage():
    response = {"model": "fixed", "workflow": {"title": "Use demo", "origin": "model_candidate", "steps": [{"command": "demo", "parameters": {}, "expected_observation": "check output"}]}, "input_tokens": 80, "output_tokens": 40}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        discovery = discover(Path(__file__).parent / "fixtures/python_cli")
        config = ModelConfig(endpoint=f"http://127.0.0.1:{server.server_port}", model="fixed")
        result = propose(discovery, "use demo", config, True, True)
        assert result["status"] == "CANDIDATE_VALIDATED"
        assert result["actual_usage"]["input_tokens"] == 80
        response["workflow"]["steps"][0]["parameters"] = {"--fabricated": []}
        with pytest.raises(ValueError, match="UNKNOWN_OR_WRONG_OWNER"):
            propose(discovery, "use demo", config, True, True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
