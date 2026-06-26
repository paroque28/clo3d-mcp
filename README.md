# clo3d-mcp — Claude × CLO3D

Drive CLO3D from Claude (or any MCP client): vary fabrics and colorways, tune and run
simulation, place graphics, export snapshots / renders / tech packs — and read the
results back so the model can *see* the garment and iterate.

> **Independent project.** Based on, and originally derived from,
> [`Ubani-Studio/clo3d-mcp`](https://github.com/Ubani-Studio/clo3d-mcp) (MIT), but
> developed and maintained separately — **not affiliated with it and not upstreamed to
> it**. It has since been substantially rewritten (single shared CLO-side core, a
> backend-agnostic protocol, and a run-once main-thread model). See
> [`docs/PLAN.md`](docs/PLAN.md) for the architecture and rationale.

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
  clo.py           the CLO-side agent — one shared core, two modes (once / serve)
  cpp-plugin/      future — socket server + main-thread marshaling (scaffold)
sdk/               vendored CLO SDK headers (shared; used by the C++ build)
docs/              PLAN.md (architecture), api-signatures.md (verified API reference)
```

## Quick start (primary path)

1. In CLO: **Edit → Python Script**, open [`runtimes/clo.py`](runtimes/clo.py), **Run**
   (or drag it onto the 3D view). With nothing queued it does a full introspection and
   writes `~/clo_agent/response.json` + `snapshot.png`.
2. The client writes a `request.json` (or `task.py`) into `~/clo_agent`, you Run once,
   the client reads `response.json` + `snapshot.png` back, and iterates. For live
   driving without a click, run with `CLO_AGENT_MODE=serve` (experimental — see below).

See [`runtimes/README.md`](runtimes/README.md).

## What it's good at (and not)

CLO's API is for **varying / tuning / simulating / exporting** on top of pre-made
blocks — not for generating garment geometry, placing buttons/zippers, or resizing
avatars parametrically (GUI-only). Full capability tiers in [`docs/PLAN.md`](docs/PLAN.md) §6.

## License

MIT.
