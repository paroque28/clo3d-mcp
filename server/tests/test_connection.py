"""Tests for the file-based connection against the unified Command/Result protocol."""

import pytest
from clo3d_mcp.connection import CLO3DConnection, CLO3DConnectionError


def _wire(mock):
    """Point a fresh-ish connection at the mock's temp dir."""
    conn = CLO3DConnection()
    conn.comm_dir = mock.comm_dir
    conn.request_file = mock.request_file
    conn.response_file = mock.response_file
    return conn


class TestConnection:
    def test_send_returns_full_result(self, mock_server):
        conn = _wire(mock_server)
        res = conn.send_command("introspect")
        # The connection returns the whole Result, not just .result
        assert res["ok"] is True
        assert res["type"] == "introspect"
        assert res["result"]["project"]["pattern_count"] == 5
        assert len(res["result"]["patterns"]) == 5

    def test_run_code_roundtrip(self, mock_server):
        conn = _wire(mock_server)
        res = conn.send_command("run_code", {"code": "RESULT = 1"})
        assert res["ok"] is True
        assert res["result"] == {"ran": True}

    def test_snapshot(self, mock_server):
        conn = _wire(mock_server)
        res = conn.send_command("snapshot", {"path": "/tmp/x.png"})
        assert res["ok"] is True
        assert res["result"]["requested"] == "/tmp/x.png"

    def test_task_error_raises(self, mock_server):
        conn = _wire(mock_server)
        with pytest.raises(CLO3DConnectionError):
            conn.send_command("run_code", {"code": "BOOM"})

    def test_unknown_command_raises(self, mock_server):
        conn = _wire(mock_server)
        with pytest.raises(CLO3DConnectionError):
            conn.send_command("nonexistent_command")

    def test_ping_helper(self, mock_server):
        conn = _wire(mock_server)
        assert conn.ping() is True

    def test_missing_comm_dir_raises(self, tmp_path):
        conn = CLO3DConnection()
        conn.comm_dir = str(tmp_path / "nope")
        conn.request_file = str(tmp_path / "nope" / "request.json")
        conn.response_file = str(tmp_path / "nope" / "response.json")
        with pytest.raises(CLO3DConnectionError):
            conn.send_command("ping", retries=1)
