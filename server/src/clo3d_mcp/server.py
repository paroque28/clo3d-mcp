"""CLO3D MCP server — a few powerful tools over the shared CLO agent.

Design (the Blender-MCP lesson, applied honestly):
the ENTIRE CLO API is reachable through `run_code`; `introspect` and `snapshot` cover
read-back. `open_file` / `save_project` / `render` are thin, common-case wrappers over
`run_code`. Anything else — write `run_code`. We deliberately do NOT wrap 40 typed
operations: every wrapper is a place a CLO-2026 signature bug can hide (we found five),
and a long tool list is worse for the model than one powerful primitive.

The CLO side is runtimes/clo.py; both speak the protocol/ Command/Result contract.
"""

from mcp.server.fastmcp import FastMCP
from clo3d_mcp.connection import get_connection

mcp = FastMCP(
    "clo3d",
    instructions=(
        "Control CLO3D (3D garment design). Use run_code to execute Python against the "
        "full CLO API (utility_api / pattern_api / fabric_api / import_api / export_api; "
        "set RESULT = <json-able> to return data). Use introspect to read the scene and "
        "snapshot to see it. CLO's API is for varying / tuning / simulating / exporting "
        "on pre-made garment blocks — it cannot author geometry from scratch or place "
        "buttons/zippers (GUI-only). See docs/api-signatures.md for verified signatures."
    ),
)


def _send(command: str, params: dict | None = None) -> dict:
    """Send a command to the CLO agent and return the full Result."""
    return get_connection().send_command(command, params)


def _run(code: str) -> dict:
    return _send("run_code", {"code": code})


# ─── Primitives ─────────────────────────────────────────────────────────────


@mcp.tool()
def run_code(code: str) -> dict:
    """Execute arbitrary Python inside CLO3D against its API; returns the full Result.

    In scope: utility_api, pattern_api, fabric_api, import_api, export_api, plus
    introspect() and snapshot(). Set RESULT = <json-able> to return data; stdout is
    captured. This reaches the ENTIRE CLO API in one call — prefer it for anything
    without a dedicated tool. Signatures: docs/api-signatures.md (pybind11 drops C++
    default args, so pass every parameter, e.g. GetFabricCount(True)).
    """
    return _run(code)


@mcp.tool()
def introspect() -> dict:
    """Full structured read-back: project, patterns, fabrics, colorways, avatars, garment."""
    return _send("introspect")


@mcp.tool()
def snapshot(path: str | None = None) -> dict:
    """Take a 3D viewport snapshot. The Result's snapshot.requested is the saved PNG path — read that file to view the garment."""
    return _send("snapshot", {"path": path} if path else None)


# ─── Ergonomic wrappers over run_code (common cases) ────────────────────────


@mcp.tool()
def open_file(file_path: str) -> dict:
    """Open a CLO file (.zprj/.zpac/.obj/.fbx/.avt)."""
    return _run("RESULT = import_api.ImportFile(%r)" % file_path)


@mcp.tool()
def save_project(file_path: str) -> dict:
    """Save the current project as a .zprj."""
    return _run("RESULT = export_api.ExportZPrj(%r)" % file_path)


@mcp.tool()
def render(file_path: str) -> dict:
    """Photoreal-render the current scene to a PNG path."""
    return _run(
        "utility_api.SetQualityRender(True)\n"
        "RESULT = export_api.ExportRenderingImage(%r)" % file_path
    )
