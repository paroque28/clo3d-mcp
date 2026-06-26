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

## Recommended implementation: delegate to the Python `dispatch`, don't reimplement it

Do **not** re-wrap the ~400 CLO API methods in C++. The whole logic — `dispatch()`,
`run_code`, `introspect`, snapshots, the verified signatures — already exists in
`runtimes/clo.py`. The C++ plugin should be *only* the two things Python can't provide:

1. a socket server on a worker thread (an OS thread, which CLO does not starve), and
2. a **main-thread pump** (`QMetaObject::invokeMethod(..., Qt::QueuedConnection)`).

On the main thread it then hands the received command string to CLO's Python and calls
`clo.dispatch(command)`, returning the JSON Result over the socket. One dispatch
implementation, two transports — exactly the protocol promise. This keeps the C++ to a
few hundred lines of plumbing instead of a second full API binding.

## Why this stage is NOT implemented in this repo (honest)

It cannot be finished or verified without:

- the CLO **plugin SDK build** (Qt + the `MV_CLO_SCENE_API` libs) and a signing/loadable
  plugin on this machine — none of which exist here, so any C++ committed now would be
  *plausible but untested*, the exact failure mode to avoid;
- confirming **one SDK capability**: how a C++ plugin invokes CLO's embedded Python on the
  main thread (the binary exposes `HeadlessApiController::ExecutePython`, but the
  public-SDK entry point for "run this Python string in the live session" is unconfirmed).
  If that path is unavailable, the fallback is to dispatch via the C++ CLO API directly —
  more code, no Python reuse.

So this directory stays a **scaffold + design** on purpose. Building it is a real task
gated on a local CLO-SDK toolchain; the design above is ready to execute against one.

## When to build this

Only if unattended / hands-off automation is required (a render or variation farm
driven with no human in CLO). For interactive design, `runtimes/clo.py` (MODE=once) is
sufficient and free. See `docs/PLAN.md` §5 (Mode C) and §11.

## Build (placeholder)

```bash
mkdir build && cd build
cmake .. && cmake --build .
# load the resulting plugin via CLO's Plugins mechanism
```
