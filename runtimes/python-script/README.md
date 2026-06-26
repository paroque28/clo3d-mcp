# python-script backend (primary)

`clo_agent.py` is run **once** in CLO's Script Editor each iteration. It runs on CLO's
**main thread** (the only place CLO API calls are reliable), executes a task or full
introspection, takes a snapshot, and writes a `Result` to `CLO_AGENT_DIR` (default
`~/clo_agent`).

## Use

In CLO: **Edit → Python Script**, open this file, **Run**. Or drag it onto the 3D view.
Or in the editor:

```python
exec(open(r"/abs/path/to/clo_agent.py").read())
```

## Loop

1. Client writes `CLO_AGENT_DIR/task.py` (a `run_code` command body; sets `RESULT = ...`).
2. User runs `clo_agent.py` once.
3. It writes `CLO_AGENT_DIR/result.json` (see `protocol/result.schema.json`) and
   `snapshot.png`.
4. Client reads both back and decides the next task.

With no `task.py` present, it runs a full introspection — good for a first run.

## Why not a loop / daemon

A persistent loop would block CLO's main thread (freeze) or need a background thread
(starves — see `docs/PLAN.md` §2). Run-once is the reliable model. The cost is one
"Run" click per iteration.
