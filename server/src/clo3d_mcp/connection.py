"""
CLO3D file-based connection client.

Communicates with the CLO3D plugin via a shared directory.
The MCP server writes request.json, the plugin reads it, processes,
and writes response.json. Both sides use atomic writes (temp + rename).

On WSL, auto-detects the Windows home directory for the shared path.
Override with CLO_AGENT_DIR environment variable if needed (must match clo.py).
"""

import json
import os
import time
import uuid

TIMEOUT = 180  # seconds: simulation/export can take minutes
POLL_INTERVAL = 0.05  # seconds between file checks
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class CLO3DConnectionError(Exception):
    pass


def _find_comm_dir():
    """Determine the shared runtime directory (must match clo.py's CLO_AGENT_DIR).

    Priority:
    1. CLO_AGENT_DIR env var (explicit override)
    2. Windows ~/clo_agent via WSL mount (auto-detect, server-on-WSL + CLO-on-Windows)
    3. ~/clo_agent
    """
    # 1. Explicit override
    env_dir = os.environ.get("CLO_AGENT_DIR")
    if env_dir:
        return env_dir

    # 2. Auto-detect WSL: CLO runs on Windows, writing to the Windows home dir.
    if os.path.isdir("/mnt/c/Users"):
        try:
            users = [
                d
                for d in os.listdir("/mnt/c/Users")
                if d not in ("Public", "Default", "Default User", "All Users")
                and os.path.isdir(os.path.join("/mnt/c/Users", d))
            ]
            for user in users:
                d = os.path.join("/mnt/c/Users", user, "clo_agent")
                if os.path.isdir(d):  # plugin already running here
                    return d
            if users:
                return os.path.join("/mnt/c/Users", users[0], "clo_agent")
        except OSError:
            pass

    # 3. Fallback: ~/clo_agent
    return os.path.join(os.path.expanduser("~"), "clo_agent")


class CLO3DConnection:
    """File-based IPC client for the CLO3D plugin."""

    _instance = None

    def __new__(cls, comm_dir=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, comm_dir=None):
        if self._initialized:
            return
        self.comm_dir = comm_dir or _find_comm_dir()
        self.request_file = os.path.join(self.comm_dir, "request.json")
        self.response_file = os.path.join(self.comm_dir, "response.json")
        self._initialized = True

    @property
    def connected(self):
        """Check if the communication directory exists (plugin is likely running)."""
        return os.path.isdir(self.comm_dir)

    def connect(self):
        """Ensure the communication directory exists."""
        if not os.path.isdir(self.comm_dir):
            raise CLO3DConnectionError(
                "Cannot find CLO3D communication directory at: " + self.comm_dir + ". "
                "Is CLO3D running with the MCP plugin loaded?"
            )

    def disconnect(self):
        """No-op for file-based connection (kept for API compatibility)."""
        pass

    def send_command(self, command_type, params=None, retries=MAX_RETRIES):
        """
        Send a command to CLO3D and return the result.

        Writes request.json, waits for response.json, returns the parsed result.
        """
        request = {
            "id": str(uuid.uuid4()),
            "type": command_type,
            "params": params or {},
        }

        for attempt in range(retries):
            try:
                return self._do_send(request)
            except CLO3DConnectionError:
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise

    def _do_send(self, request):
        """Write request, poll for response, return result."""
        # Ensure comm dir exists
        if not os.path.isdir(self.comm_dir):
            raise CLO3DConnectionError(
                "CLO3D communication directory not found: " + self.comm_dir + ". "
                "Is CLO3D running with the MCP plugin loaded?"
            )

        # Clean up any stale response file
        if os.path.exists(self.response_file):
            try:
                os.remove(self.response_file)
            except OSError:
                pass

        # Write request atomically
        payload = json.dumps(request)
        tmp_file = self.request_file + ".tmp"
        with open(tmp_file, "w") as f:
            f.write(payload)

        # Atomic rename
        if os.path.exists(self.request_file):
            os.remove(self.request_file)
        os.rename(tmp_file, self.request_file)

        # Poll for response
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > TIMEOUT:
                raise CLO3DConnectionError(
                    "Timed out waiting for CLO3D response (" + str(TIMEOUT) + "s). "
                    "The operation may still be running in CLO3D."
                )

            if os.path.exists(self.response_file):
                try:
                    with open(self.response_file, "r") as f:
                        data = f.read()

                    # Delete response file
                    try:
                        os.remove(self.response_file)
                    except OSError:
                        pass

                    if not data.strip():
                        time.sleep(POLL_INTERVAL)
                        continue

                    response = json.loads(data)

                    # Match our request. serve mode echoes the id; once mode may
                    # omit it, so a response without an id is accepted as ours.
                    rid = response.get("id")
                    if rid is not None and rid != request["id"]:
                        time.sleep(POLL_INTERVAL)
                        continue

                    if not response.get("ok", True):
                        msg = response.get("task_error") or "Unknown error from CLO3D"
                        raise CLO3DConnectionError("CLO3D error: " + str(msg))

                    # Return the full Result (result + stdout + snapshot + errors).
                    return response

                except (json.JSONDecodeError, ValueError):
                    # File might be partially written, wait and retry
                    time.sleep(POLL_INTERVAL)
                    continue

            time.sleep(POLL_INTERVAL)

    def ping(self):
        """Test the connection. Returns True if CLO3D responds."""
        try:
            res = self.send_command("ping", retries=1)
            return bool((res.get("result") or {}).get("pong"))
        except CLO3DConnectionError:
            return False


# Module-level singleton
_connection = None


def get_connection(comm_dir=None):
    """Get or create the global CLO3D connection."""
    global _connection
    if _connection is None:
        _connection = CLO3DConnection(comm_dir)
    return _connection
