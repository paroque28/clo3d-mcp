"""Test fixtures: a mock CLO agent that speaks the unified Command/Result protocol.

Mirrors runtimes/clo.py's serve transport: poll request.json, dispatch, write a
Result (protocol/result.schema.json) to response.json. No CLO needed.
"""

import json
import os
import tempfile
import threading
import time
import pytest

_FAKE_SCENE = {
    "project": {
        "project_name": "TestProject",
        "project_path": "/tmp/test.zprj",
        "clo_version": "2026.0.0",
        "pattern_count": 5,
        "fabric_count": 3,
        "colorway_count": 2,
    },
    "patterns": [
        {"index": i, "name": n}
        for i, n in enumerate(["Front", "Back", "SleeveL", "SleeveR", "Collar"])
    ],
    "fabrics": [{"index": 0}, {"index": 1}, {"index": 2}],
    "colorways": {
        "current_index": 0,
        "colorways": [
            {"index": 0, "name": "Default", "current": True},
            {"index": 1, "name": "Navy", "current": False},
        ],
    },
    "avatars": {"count": 1, "avatars": []},
    "garment": None,
}


def _dispatch(command):
    """Mock of clo.py dispatch(): returns the unified Result shape."""
    cid = command.get("id")
    ctype = command.get("type") or "introspect"
    params = command.get("params") or {}
    result, err = None, None

    if ctype == "ping":
        result = {"pong": True, "in_clo3d": False}
    elif ctype == "introspect":
        result = _FAKE_SCENE
    elif ctype == "snapshot":
        result = {"requested": params.get("path") or "/tmp/snap.png",
                  "returned": None, "exists": False}
    elif ctype == "run_code":
        code = command.get("code") or params.get("code") or ""
        if "BOOM" in code:
            err = "RuntimeError: boom"
        else:
            result = {"ran": True}
    else:
        err = "Unknown command type: " + str(ctype)

    snap = result if ctype == "snapshot" else {"requested": "/tmp/snap.png", "exists": False}
    return {
        "ok": err is None,
        "id": cid,
        "type": ctype,
        "result": result,
        "snapshot": snap,
        "stdout": "",
        "errors": {},
        "task_error": err,
        "started": "t0",
        "finished": "t1",
        "in_clo3d": False,
        "agent_dir": "/tmp",
    }


class MockCLOAgent:
    """Polls request.json in a temp dir and writes a unified Result to response.json."""

    def __init__(self):
        self.comm_dir = tempfile.mkdtemp(prefix="clo_agent_test_")
        self.request_file = os.path.join(self.comm_dir, "request.json")
        self.response_file = os.path.join(self.comm_dir, "response.json")
        self._thread = None
        self._running = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        for f in (self.request_file, self.response_file):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
        try:
            os.rmdir(self.comm_dir)
        except OSError:
            pass

    def _loop(self):
        while self._running:
            try:
                if os.path.exists(self.request_file):
                    with open(self.request_file) as f:
                        data = f.read()
                    try:
                        os.remove(self.request_file)
                    except OSError:
                        pass
                    if data.strip():
                        resp = _dispatch(json.loads(data))
                        tmp = self.response_file + ".tmp"
                        with open(tmp, "w") as f:
                            json.dump(resp, f)
                        os.replace(tmp, self.response_file)
            except Exception as e:  # pragma: no cover
                print("[MockCLOAgent] error:", e)
            time.sleep(0.02)


@pytest.fixture
def mock_server():
    server = MockCLOAgent()
    server.start()
    yield server
    server.stop()
