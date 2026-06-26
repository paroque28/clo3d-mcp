# python-plugin backend (experimental)

`clo_mcp_plugin.py` is the original live design: a background thread polls
`~/clo3d_mcp` for `request.json` and writes `response.json`, letting an MCP server drive
CLO without a manual "Run" each time.

## Status: experimental — do not depend on it

CLO's embedded Python has no main-thread pump and **starves background threads when CLO
is idle** — exactly when MCP calls arrive. It also calls the CLO API off the main
thread, which is unsafe. It works *while CLO is actively being used* and is kept for
that niche and for reference. See `docs/PLAN.md` §2.

This build is hardened relative to upstream:

- **Correct CLO 2026 / pybind11 signatures** (see `docs/api-signatures.md`).
- **Singleton guard** — re-running supersedes the previous instance (generation counter
  on `sys`) instead of stacking pollers.
- **Atomic `os.replace`** with per-instance temp files — no response-file race.
- **Flushed, leveled logging** — CLO buffers stdout, so logs are force-flushed.
- Honors `CLO3D_MCP_DIR` to match the server's comm-dir resolution.

For reliable use, prefer `runtimes/python-script`. For reliable *live* use, see
`runtimes/cpp-plugin`.
