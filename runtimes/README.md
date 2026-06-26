# runtimes — the CLO-side agent

One file, one shared core, two transports.

## `clo.py`

Load it in CLO's Script Editor (**Edit → Python Script**, or drag onto the 3D view).
It exposes a shared `dispatch(command)` core (API helpers + `run_code` + `introspect` +
`snapshot`, all on verified CLO 2026 signatures) behind two transports selected by the
`CLO_AGENT_MODE` env var:

| Mode | Reliability | Trigger | Use |
|---|---|---|---|
| `once` (default) | ✅ main thread | one Run per command | scripted / iterative work |
| `serve` | ⚠️ starves when CLO idle | load once, then autonomous | live driving while CLO is active |

Both speak the same files in `CLO_AGENT_DIR` (default `~/clo_agent`):

```
request.json  (or task.py)  ──►  response.json   (+ snapshot.png)
```

and emit the same Result (`../protocol/result.schema.json`). The client (`../server`)
writes `request.json` and reads `response.json`; in `once` mode it then waits for you to
Run, in `serve` mode the poller picks it up.

### Commands

- `{"type": "run_code", "code": "..."}` — the whole CLO API in one call (`RESULT = ...`).
- `{"type": "introspect"}` — full structured read-back.
- `{"type": "snapshot", "params": {"path": "..."}}` — viewport image.
- `{"type": "ping"}` — health.

> Why one file: the script and plugin used to duplicate every helper and the corrected
> signatures, inviting drift. `dispatch()` is now the single source of truth; the
> transports are thin. See `../docs/PLAN.md`.

## `cpp-plugin/`

Future C++ backend (socket transport, main-thread marshaling) — same protocol, reliable
even when idle. Scaffold only. See its README.
