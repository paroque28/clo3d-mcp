# cpp-plugin backend (future)

The only way to get **reliable live** control of CLO (no manual "Run", no idle
starvation) is a C++ plugin built against the CLO SDK that runs a socket server on a
worker thread and **marshals each command onto CLO's main thread** before touching the
API.

This directory is a scaffold. It is intentionally empty of build artifacts; the design
is fixed so it can be implemented later without touching the rest of the repo.

## Design

```
client ──TCP──► socket thread (recv Command JSON)
                     │  QMetaObject::invokeMethod(..., Qt::QueuedConnection)
                     ▼
                CLO main thread: exec via CLO API → build Result JSON
                     │
client ◄──TCP──── socket thread (send Result JSON)
```

- **Same protocol** as the Python backends: `protocol/command.schema.json` /
  `protocol/result.schema.json`. Only the transport (socket vs files) differs, so the
  MCP server needs no changes to adopt it.
- **Main-thread marshaling** is the whole reason to go to C++. Reference proof of the
  technique: `gregor124/clo-mcp` (`ExportPlugin.cpp`) and `sdk/Samples/CloEventPlugin`.
- Entry points follow the CLO plugin ABI: `DoFunction`, `GetActionName`,
  `GetObjectNameTreeToAddAction`, `GetPositionIndexToAddAction` (see
  `sdk/Samples/CloEventPlugin`).

## When to build this

Only if unattended / hands-off automation is required (a render or variation farm
driven with no human in CLO). For interactive design, `runtimes/python-script` is
sufficient and free. See `docs/PLAN.md` §5 (Mode C) and §11.

## Build (placeholder)

```bash
mkdir build && cd build
cmake .. && cmake --build .
# load the resulting plugin via CLO's Plugins mechanism
```
