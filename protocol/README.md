# Protocol — the backend-agnostic contract

This is the boundary that future-proofs the project. The **client** (MCP server, or any
caller) speaks this contract; a **backend** (a thing running inside CLO that executes
commands on the main thread) implements it. Swap the backend, keep the contract.

```
client (server/)                       backend (runtimes/*)
  build Command (JSON)  ──────────────►  execute on CLO main thread
  read Result (JSON)    ◄──────────────  write Result + snapshot
```

## Backends

| Backend | Transport | Status |
|---|---|---|
| `runtimes/python-script` | files in `CLO_AGENT_DIR` (`task.py` → `result.json`) | **primary** |
| `runtimes/python-plugin` | files in `~/clo3d_mcp` (`request.json` → `response.json`) | experimental (idle-starves) |
| `runtimes/cpp-plugin` | TCP socket | future |

All three exchange the **same `Command` and `Result` JSON** (`command.schema.json`,
`result.schema.json`). Only the transport differs. That is the whole point: the C++
plugin can be added later as a faster transport for the *identical* messages — no client
changes, no reorg.

## Command types

- `run_code` — execute arbitrary Python against the CLO API (`code` field). The
  Blender-MCP model: one command reaches the entire API surface.
- `introspect` — full structured read-back (no params).
- `snapshot` — viewport image only.
- typed ops (`set_fabric_color`, `simulate`, …) — optional ergonomic shortcuts that a
  backend may special-case; everything they do is also reachable via `run_code`.

## Invariant

A backend MUST execute CLO API calls on CLO's **main thread** (Script Editor run, or a
C++ main-thread marshal). Calling the API from a background thread is unsafe and, in
embedded CPython, unreliable. See `docs/PLAN.md` §2.
