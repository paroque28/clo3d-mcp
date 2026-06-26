"""clo.py — the CLO3D-side agent. One file, one shared core, two transports.

Load this in CLO's Script Editor (Edit > Python Script, or drag onto the 3D view).

Modes — set the CLO_AGENT_MODE env var (default "once"):
  once   Reliable. Reads one command, runs it on CLO's MAIN thread, snapshots,
         writes the result, and exits. Use this for scripted/iterative work.
  serve  Experimental. Background-polls for commands so a client can drive CLO
         with no per-task click. Starves when CLO is idle (CLO gives Python no
         main-thread pump — see docs/PLAN.md); works while CLO is the active app.

Runtime dir: CLO_AGENT_DIR (default ~/clo_agent). Both modes speak the same files:
  request.json (or task.py)  ->  response.json   (+ snapshot.png)
and emit the SAME Result shape (protocol/result.schema.json). The dispatch() core is
shared; only how a command arrives differs.
"""

import os
import sys
import json
import time
import io
import traceback

try:
    import export_api
    import fabric_api
    import import_api
    import pattern_api
    import utility_api
    IN_CLO3D = True
except ImportError:
    IN_CLO3D = False

AGENT_DIR = os.environ.get("CLO_AGENT_DIR") or os.path.join(
    os.path.expanduser("~"), "clo_agent"
)
REQUEST_FILE = os.path.join(AGENT_DIR, "request.json")
RESPONSE_FILE = os.path.join(AGENT_DIR, "response.json")
TASK_FILE = os.path.join(AGENT_DIR, "task.py")
SNAPSHOT_FILE = os.path.join(AGENT_DIR, "snapshot.png")
MODE = os.environ.get("CLO_AGENT_MODE", "once").strip().lower()
DEBUG = os.environ.get("CLO_AGENT_DEBUG", "1") != "0"
POLL_INTERVAL = 0.1

# Bump this on every change. Printed on each load and echoed in every Result, so it
# is always obvious which version of this file CLO actually has loaded (CLO keeps one
# long-lived interpreter, so stale copies can linger across reloads).
VERSION = "0.3.0"


def _log(msg, level="INFO"):
    """Flushed print — CLO buffers stdout, so always flush to the Log Console."""
    try:
        line = "[clo] " + time.strftime("%H:%M:%S") + " [" + level + "] " + str(msg)
        print(line)
        sys.stdout.flush()
    except Exception:
        pass


def _debug(msg):
    if DEBUG:
        _log(msg, level="DEBUG")


# ---------------------------------------------------------------------------
# Shared core: API helpers (verified CLO 2026 / pybind11 signatures)
# ---------------------------------------------------------------------------

_ERRORS = {}


def _safe(label, fn, *args, **kwargs):
    """Call an API fn; record any error under `label` instead of aborting."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        _ERRORS[label] = type(e).__name__ + ": " + str(e)
        return None


def project_info():
    major = _safe("GetMajorVersion", utility_api.GetMajorVersion)
    minor = _safe("GetMinorVersion", utility_api.GetMinorVersion)
    patch = _safe("GetPatchVersion", utility_api.GetPatchVersion)
    version = "%s.%s.%s" % (major, minor, patch) if None not in (major, minor, patch) else None
    return {
        "project_name": _safe("GetProjectName", utility_api.GetProjectName),
        "project_path": _safe("GetProjectFilePath", utility_api.GetProjectFilePath),
        "clo_version": version,
        "pattern_count": _safe("GetPatternCount", pattern_api.GetPatternCount),
        # pybind11 does not expose the C++ default; the bool is required.
        "fabric_count": _safe("GetFabricCount", fabric_api.GetFabricCount, True),
        "colorway_count": _safe("GetColorwayCount", utility_api.GetColorwayCount),
    }


def pattern_list():
    count = _safe("GetPatternCount", pattern_api.GetPatternCount) or 0
    return [{"index": i, "name": _safe("GetPatternPieceName[%d]" % i,
                                       pattern_api.GetPatternPieceName, i)}
            for i in range(count)]


def fabric_list():
    count = _safe("GetFabricCount", fabric_api.GetFabricCount, True) or 0
    out = []
    for i in range(count):
        entry = {"index": i}
        name = _safe("GetFabricName[%d]" % i, fabric_api.GetFabricName, i)
        if name is not None:
            entry["name"] = name
        out.append(entry)
    return out


def avatar_list():
    names = _safe("GetAvatarNameList", export_api.GetAvatarNameList)
    genders = _safe("GetAvatarGenderList", export_api.GetAvatarGenderList)
    out = []
    if names:
        for i, nm in enumerate(names):
            g = genders[i] if (genders and i < len(genders)) else None
            out.append({"index": i, "name": nm, "gender": g})
    return {"count": _safe("GetAvatarCount", export_api.GetAvatarCount), "avatars": out}


def colorway_list():
    names = _safe("GetColorwayNameList", export_api.GetColorwayNameList)
    current = _safe("GetCurrentColorwayIndex", utility_api.GetCurrentColorwayIndex)
    out = []
    if names:
        for i, nm in enumerate(names):
            out.append({"index": i, "name": nm, "current": i == current})
    return {"current_index": current, "colorways": out}


def garment_info():
    raw = _safe("ExportGarmentInformationToStream",
                export_api.ExportGarmentInformationToStream)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": str(raw)[:5000]}


def take_snapshot(path=None):
    """3D viewport snapshot. Returns the path(s) CLO reports writing."""
    path = path or SNAPSHOT_FILE
    returned = _safe("ExportSnapshot3D", export_api.ExportSnapshot3D, path)
    return {"requested": path, "returned": returned, "exists": os.path.exists(path)}


def introspect():
    """Full structured read-back of the current scene."""
    return {
        "project": project_info(),
        "patterns": pattern_list(),
        "fabrics": fabric_list(),
        "avatars": avatar_list(),
        "colorways": colorway_list(),
        "garment": garment_info(),
    }


def run_code(code):
    """Exec arbitrary Python against the CLO API. Sets RESULT to return data."""
    ns = {
        "utility_api": utility_api, "pattern_api": pattern_api,
        "fabric_api": fabric_api, "import_api": import_api, "export_api": export_api,
        "introspect": introspect, "snapshot": take_snapshot, "safe": _safe,
        "RESULT": None,
    }
    cap, real, err = io.StringIO(), sys.stdout, None
    try:
        sys.stdout = cap
        exec(compile(code, "<run_code>", "exec"), ns)
    except Exception:
        err = traceback.format_exc()
    finally:
        sys.stdout = real
    return {"result": ns.get("RESULT"), "stdout": cap.getvalue(), "error": err}


# ---------------------------------------------------------------------------
# Shared core: dispatch one command -> one Result shape
# ---------------------------------------------------------------------------

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def dispatch(command):
    """Run a single command and return the unified Result (protocol/result.schema.json)."""
    _ERRORS.clear()
    cid = command.get("id")
    ctype = command.get("type") or "introspect"
    params = command.get("params") or {}
    started = _now()
    result, stdout, err = None, "", None

    if not IN_CLO3D:
        err = "Not running inside CLO3D — the *_api modules are unavailable."
    elif ctype == "ping":
        result = {"pong": True, "in_clo3d": True}
    elif ctype == "introspect":
        result = introspect()
    elif ctype == "snapshot":
        result = take_snapshot(params.get("path"))
    elif ctype == "run_code":
        # Accept code top-level (schema form) or in params (the server wraps args
        # in params via send_command). Tolerating both avoids a silent empty exec.
        code = command.get("code") or params.get("code") or ""
        rc = run_code(code)
        result, stdout, err = rc["result"], rc["stdout"], rc["error"]
    else:
        err = "Unknown command type: " + str(ctype)

    # Always include a fresh snapshot so the client can see the result.
    snap = result if ctype == "snapshot" else (take_snapshot() if IN_CLO3D else None)

    return {
        "ok": err is None,
        "version": VERSION,
        "id": cid,
        "type": ctype,
        "result": result,
        "snapshot": snap,
        "stdout": stdout,
        "errors": dict(_ERRORS),
        "task_error": err,
        "started": started,
        "finished": _now(),
        "in_clo3d": IN_CLO3D,
        "agent_dir": AGENT_DIR,
    }


def _write_response(payload):
    """Atomic write of the Result to response.json."""
    tmp = RESPONSE_FILE + "." + str(payload.get("id") or "x") + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    os.replace(tmp, RESPONSE_FILE)


# ---------------------------------------------------------------------------
# Transport: once (reliable, main thread)
# ---------------------------------------------------------------------------

def run_once():
    try:
        os.makedirs(AGENT_DIR, exist_ok=True)
    except Exception as e:
        _log("could not create %s: %r" % (AGENT_DIR, e), level="ERROR")

    # Resolve the command: request.json > task.py > full introspection.
    command, consume = None, None
    if os.path.exists(REQUEST_FILE):
        try:
            with open(REQUEST_FILE) as f:
                command = json.load(f)
            consume = REQUEST_FILE
        except Exception as e:
            _log("bad request.json: %r" % e, level="ERROR")
    if command is None and os.path.exists(TASK_FILE):
        with open(TASK_FILE) as f:
            command = {"type": "run_code", "code": f.read()}
        consume = TASK_FILE
    if command is None:
        command = {"type": "introspect"}

    _log("once: dispatching type=%s" % command.get("type"))
    payload = dispatch(command)
    _write_response(payload)
    # Consume the input so it cannot re-fire on the next run.
    if consume:
        try:
            os.remove(consume)
        except OSError:
            pass
    if payload["stdout"]:
        _log("stdout:\n" + payload["stdout"])
    if payload["task_error"]:
        _log("TASK ERROR:\n" + payload["task_error"], level="ERROR")
    if payload["errors"]:
        _log("per-call errors: " + json.dumps(payload["errors"]))
    _log("once: done ok=%s snapshot=%s -> %s" %
         (payload["ok"], bool(payload["snapshot"] and payload["snapshot"].get("exists")),
          RESPONSE_FILE))


# ---------------------------------------------------------------------------
# Transport: serve (experimental, background poll — see module docstring)
# ---------------------------------------------------------------------------

import threading  # noqa: E402  (only needed in serve mode)


def _poll_loop(my_gen):
    try:
        os.makedirs(AGENT_DIR, exist_ok=True)
    except Exception as e:
        _log("could not create %s: %r" % (AGENT_DIR, e), level="ERROR")
    for f in (REQUEST_FILE, RESPONSE_FILE):
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    _log("serve: listening (gen %d) in %s" % (my_gen, AGENT_DIR))
    n = 0
    while getattr(sys, "_CLO_AGENT_GEN", my_gen) == my_gen:
        n += 1
        if DEBUG and n % 100 == 0:
            _debug("serve: heartbeat gen=%d polled=%d" % (my_gen, n))
        try:
            if os.path.exists(REQUEST_FILE):
                with open(REQUEST_FILE) as f:
                    data = f.read()
                try:
                    os.remove(REQUEST_FILE)
                except OSError:
                    pass
                if data.strip():
                    _write_response(dispatch(json.loads(data)))
        except Exception as e:
            _log("serve poll error: %r" % e, level="ERROR")
        time.sleep(POLL_INTERVAL)
    _log("serve: stopped (gen %d)" % my_gen)


def serve(my_gen):
    """Start a single background poller for the given (already-bumped) generation."""
    t = threading.Thread(target=_poll_loop, args=(my_gen,), daemon=True)
    t.start()
    time.sleep(0.3)
    _log("serve: started gen=%d thread_alive=%s "
         "(if it never processes commands while CLO is idle, that is the documented "
         "starvation; prefer MODE=once)" % (my_gen, t.is_alive()))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Every load bumps the shared generation, so any poll loop still running in CLO's
# persistent interpreter from an earlier load sees the change and exits. This
# self-heals the stale-instance pile-up that produces confusing duplicate log lines.
_GEN = getattr(sys, "_CLO_AGENT_GEN", 0) + 1
sys._CLO_AGENT_GEN = _GEN
_log("clo.py v%s loaded. gen=%d mode=%s in_clo3d=%s agent_dir=%s"
     % (VERSION, _GEN, MODE, IN_CLO3D, AGENT_DIR))
if MODE == "serve":
    serve(_GEN)
else:
    run_once()
