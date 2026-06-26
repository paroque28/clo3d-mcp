# clo3d-mcp — Claude × CLO3D

Drive CLO3D from Claude (or any MCP client): vary fabrics and colorways, tune and run
simulation, place graphics, export snapshots / renders / tech packs — and read the
results back so the model can *see* the garment and iterate.

> Fork of [`Ubani-Studio/clo3d-mcp`](https://github.com/Ubani-Studio/clo3d-mcp),
> restructured around a backend-agnostic protocol. See [`docs/PLAN.md`](docs/PLAN.md)
> for the full architecture and rationale.

## The one constraint that shapes everything

CLO API calls are only safe on CLO's **main thread**, and CLO's embedded Python has no
main-thread pump (unlike Blender's `bpy.app.timers`). So a background polling loop
starves when CLO is idle. The reliable model is to **run code on the main thread** — via
the Script Editor today, or a C++ main-thread marshal later. Both speak the *same*
protocol.

## Architecture

```
Claude / MCP client
        │   Command (JSON)  ──►  backend runs on CLO main thread  ──►  Result + snapshot
        ▼
   server/  ──────────────────────────────────────────────────────►  read back, iterate
                                   (protocol/)
```

## Layout

```
protocol/          backend-agnostic Command/Result contract (the future-proofing)
server/            MCP / client side (Python, backend-agnostic)
runtimes/
  python-script/   PRIMARY — clo_agent.py, run once in the Script Editor (main thread)
  python-plugin/   experimental — live file-poller (starves when idle), hardened
  cpp-plugin/      future — socket server + main-thread marshaling (scaffold)
sdk/               vendored CLO SDK headers (shared; used by the C++ build)
docs/              PLAN.md (architecture), api-signatures.md (verified API reference)
```

## Quick start (primary path)

1. In CLO: **Edit → Python Script**, open
   [`runtimes/python-script/clo_agent.py`](runtimes/python-script/clo_agent.py), **Run**
   (or drag it onto the 3D view). With no task queued it does a full introspection and
   writes `~/clo_agent/result.json` + `snapshot.png`.
2. The client writes a `task.py` (a `run_code` body) into `~/clo_agent`, you Run once,
   the client reads `result.json` + `snapshot.png` back, and iterates.

See [`runtimes/python-script/README.md`](runtimes/python-script/README.md).

## What it's good at (and not)

CLO's API is for **varying / tuning / simulating / exporting** on top of pre-made
blocks — not for generating garment geometry, placing buttons/zippers, or resizing
avatars parametrically (GUI-only). Full capability tiers in [`docs/PLAN.md`](docs/PLAN.md) §6.

## License

MIT.
