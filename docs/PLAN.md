# CLO3D × Claude — Architecture & Build Plan

*Status: proposal. Author: investigation session 2026-06-26. Owner: paroque28.*

This document records what we learned reverse-engineering the CLO3D API and three
reference projects, the architectural decision that follows from it, and a concrete
build plan.

---

## 1. Executive decision

**Fork `Ubani-Studio/clo3d-mcp` — do not start from zero, do not build live on its
current architecture.**

- **Reuse** the vendored CLO SDK headers, the MCP-server scaffolding, and the
  (now signature-corrected) API handler logic.
- **Adopt** the *official Blender MCP* tool design: a small set of high-leverage
  tools (`execute_code` + `snapshot`/`render` + `scene_info`), not 400 hand-wrapped
  functions.
- **Replace** the unreliable background-thread file-poller as the *primary* path
  with a **main-thread execution core** (run-once in CLO's Script Editor) plus
  disk-based read-back.
- **Keep** the live plugin as an explicitly-experimental "works while CLO is active"
  mode, not the thing we depend on.

Rationale below.

---

## 2. What we learned (the constraints that drive everything)

### 2.1 CLO API calls must run on the main thread
Confirmed by `gregor124/clo-mcp`, whose entire C++ proof-of-concept exists only to
marshal one call onto the main thread via Qt `QueuedConnection`. Standard for a Qt
scene application.

### 2.2 CLO's embedded Python has no main-thread pump
- No `PySide`/`PyQt`/`shiboken` in the app bundle or binary strings.
- The CLO Python API exposes **no timer / idle / callback** primitive (we enumerated
  the entire surface — ~400 methods across Utility/Pattern/Fabric/Import/Export/Rest).
- Therefore a Python background thread is the *only* option from pure Python, and CLO
  **starves it when idle** (observed directly: requests sat unconsumed while CLO idle,
  consumed only while the user was actively clicking).

> **This is the linchpin.** The official Blender MCP works because Blender exposes
> `bpy.app.timers.register(...)` — a main-thread pump callable from Python. The socket
> thread is just a mailbox; real work runs on a main-thread timer. **CLO has no
> equivalent.** That single missing primitive is why a live Python socket can't be made
> reliable in CLO, and why gregor had to drop to C++.

### 2.3 The CLO API is a *modification/automation* API, not a *generative* one
It is excellent at varying, tuning, simulating, exporting, and reading back. It cannot
author quality garment geometry from text, place trims (buttons/zippers/pockets) at
semantic locations, or parametrically resize avatars. See the capability tiers (§6).

### 2.4 Read-back is rich (Claude can "see")
- Structured: full garment JSON, per-piece info, fabric info, colorways, BOM, tech pack.
- Visual: `ExportSnapshot3D`, `ExportThumbnail3D`, turntable, photoreal
  `ExportRenderingImage`, multi-view, and **strain/stress fit maps**.

---

## 3. Reference projects — what we take from each

| Project | Architecture | What we take | What we reject |
|---|---|---|---|
| **Ubani-Studio/clo3d-mcp** (our base) | Python plugin, background-thread file polling | SDK headers, MCP scaffolding, fixed API handlers | The background-thread poller as primary path |
| **gregor124/clo-mcp** | C++ Qt plugin, socket server, main-thread marshaling (PoC, unfinished) | The *correct* live design (if we ever need it); proof main-thread is mandatory | Building C++ now — disproportionate effort |
| **Ubani-Studio/clo3d-garment-generator** | Pure Python, run-once in Script Editor | The reliable execution model (main thread, synchronous) | Its narrowness (single hard-coded batch) |
| **Official Blender MCP** (`ahujasid/blender-mcp`) | Socket + `bpy.app.timers` main-thread pump | The **tool design**: `execute_code` + `screenshot` + `scene_info` + asset libs | The live-socket transport (needs a pump CLO lacks) |

---

## 4. Fork vs. from-zero vs. reuse-in-place — the call

- **From zero:** rejected. Throws away the vendored CLO SDK (hard to obtain), the MCP
  server scaffolding, and weeks of API signature reverse-engineering, for no benefit.
- **Reuse-in-place (keep building the live poller):** rejected. Inherits the doomed
  background-thread architecture as the foundation.
- **Fork + restructure:** **chosen.** Preserves attribution, SDK, scaffolding, and the
  upstream-contribution path; lets us pivot the architecture cleanly.

**Action:** fork `Ubani-Studio/clo3d-mcp` → `paroque28/clo3d-mcp`. Restructure on a
new architecture branch. Optionally rename later to reflect the new design
(e.g. `clo-agent`).

---

## 5. Target architecture

```
            ┌──────────────────────────────────────────────┐
 Claude ──► │ tool layer (Blender-MCP style)               │
            │  • run_code(code)   • snapshot()/render()    │
            │  • garment_info()   • write_script()         │
            └───────────────┬──────────────────────────────┘
                            │  (script + spec on disk)
                            ▼
            ┌──────────────────────────────────────────────┐
            │ clo_agent.py — runs in CLO Script Editor      │
            │ (MAIN THREAD, synchronous) — the reliable core│
            │  • verified API helpers (correct signatures)  │
            │  • dumps result.json + snapshot.png per run   │
            └───────────────┬──────────────────────────────┘
                            │  (result.json, *.png)
                            ▼
                  Claude reads results back → iterates
```

Two execution modes, same tool surface:

- **Mode A — Script run (primary, reliable).** Claude writes a script/spec; it runs
  once on the main thread (drag-drop or `exec(open(...))`); results land on disk;
  Claude reads them. No threading, no starvation, full API access.
- **Mode B — Live plugin (experimental).** The hardened background-thread poller
  (singleton guard + atomic writes + flushed logging already built). Documented as
  "works while CLO is in the foreground / active." Not depended upon.

The **only** way to get Blender-grade *live* behavior is Mode C (future): a C++ plugin
that pumps the main thread. Out of scope unless unattended automation becomes a goal.

---

## 6. Capability tiers (sets honest expectations + scopes the helpers)

**Tier 1 — fully supported, build first:**
- Fabric / colour / colorway variation (`AddFabric`, `SetFabricPBRMaterialBaseColor`,
  substance, PBR maps).
- Topstitch styling (`AddSeamlineTopstitch`, `SetPatternAssignedTopstitchStyle`).
- Simulation tuning + run (`SetSimulation*`, `Simulate`).
- Graphics/prints placement (`SetGraphicStyle*`).
- Exports: snapshot, turntable, photoreal render, tech pack, BOM, strain/stress maps.
- Full read-back (garment/pattern/fabric JSON).

**Tier 2 — supported *with a supplied/generated asset*:**
- Avatar height/measurement → `ImportMeasurement(csv)` / `ImportAvatarMeasurement`
  (no `SetHeight()`; Claude can author the CSV once we pin the schema).
- Realistic fabric drape → physical `.zfab`.
- Known trims → `ImportTrim` (drops at origin; placement is crude).

**Tier 3 — the API cannot do (GUI-only / pre-made blocks):**
- Create garments from scratch (geometry).
- Add/place buttons, zippers, pockets at semantic locations.
- Parametric avatar resize.

> Design implication: aim Claude at **vary + tune + simulate + render + read-back +
> iterate on pre-made blocks** — not construction.

---

## 7. Repo structure (after restructure)

```
clo3d-mcp/                    (independent project, based on Ubani-Studio/clo3d-mcp)
├── README.md
├── protocol/                 Command/Result JSON contract
├── server/                   MCP client side
│   ├── pyproject.toml
│   └── src/clo3d_mcp/        server.py (run_code/introspect/snapshot + wrappers),
│                             connection.py (file IPC, unified Result)
│   └── tests/                mock CLO agent + protocol tests
├── runtimes/
│   ├── clo.py               ← the CLO-side agent: one shared dispatch() core,
│   │                          two modes (once reliable / serve experimental)
│   └── cpp-plugin/           future socket backend (scaffold)
├── sdk/                      vendored CLO SDK headers
└── docs/                     PLAN.md (this file), api-signatures.md
```

> Note: an earlier draft of this plan proposed separate `clo_agent/` + `plugin/` +
> `src/` trees. The implementation collapsed the two CLO-side artifacts into the single
> `runtimes/clo.py` (shared core, thin transports) — fewer moving parts, no duplicated
> signatures. The layout above is the real one.

---

## 8. Tool surface (mirror Blender MCP)

- `run_code(code: str)` — execute arbitrary Python against the CLO API; returns
  stdout + structured result. (Covers the whole API in one tool.)
- `snapshot(view?, colorway?)` / `render(quality?)` — return an Image Claude sees.
- `garment_info()` / `pattern_info(i)` / `fabric_info(i)` — structured read-back.
- `strain_map()` — fit assessment image.
- `write_script(name, code)` / `run_script(name)` — Mode A trigger.
- (later) asset helpers: import avatar/measurement, import fabric/trim.

---

## 9. Roadmap

This is an **independent project** — there is no upstream-contribution phase (no PRs to
Ubani-Studio). Status below is honest about what is verified vs not.

**Phase 1 — Main-thread core (`runtimes/clo.py`). DONE; live-verify pending.** Shared
`dispatch()` + verified helpers; writes `response.json` + `snapshot.png`. Loop proven
once with the earlier runner (introspect + recolor). The *unified* `clo.py` still needs a
single live run to confirm the refactor on a real CLO build.

**Phase 2 — Tool layer. DONE.** MCP tools pruned to `run_code` / `introspect` /
`snapshot` (+ thin `open_file` / `save_project` / `render`). Unit-tested against a mock
(7 pass). **Not yet exercised through a live MCP connection** to CLO.

**Phase 3 — Capability helpers (Tier 1 → 2). Open.** Most of this is now unnecessary —
`run_code` reaches it all (see `examples/`). Worth adding only as ergonomic wrappers
where a multi-step recipe recurs (e.g. measurement-CSV authoring for avatars once the
CSV schema is pinned; a topstitch helper). Resist re-growing the tool list.

**Phase 4 (optional) — Live C++ plugin. Designed, not built.** The only idle-proof
no-click path. Design in `runtimes/cpp-plugin/README.md` (socket + main-thread marshal,
delegating to the Python `dispatch`). Honestly gated on a local CLO-SDK build env; not
implementable/verifiable from here, so deliberately left as scaffold + design.

---

## 10. Open questions / risks

- **Measurement CSV schema** (Tier 2 avatars) — need to pin the exact columns CLO's
  `ImportMeasurement` expects.
- **Mode A trigger ergonomics** — "click Run once" per iteration; can we make a
  file-watcher that *the user* leaves running, accepting it only fires while CLO is
  active? (Same starvation caveat as Mode B.)
- **`run_code` safety** — arbitrary exec inside CLO. Fine for a personal tool; needs a
  guard/allowlist if ever shared.
- **MCP↔server reconnection** — the Claude-side stdio link dropped once this session;
  orthogonal to CLO, but worth a reconnect/health check in the server.

---

## 11. TL;DR

CLO lacks the one primitive (`bpy.app.timers`-style main-thread pump) that makes a live
MCP reliable. So: **fork the existing repo, keep its SDK + handlers, adopt Blender
MCP's `code + screenshot + info` tool design, and execute on the main thread via
script runs with disk read-back.** Build for *vary/tune/simulate/render/iterate on
pre-made blocks* — the thing the CLO API is actually good at.
