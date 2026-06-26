"""clo_agent — main-thread CLO3D runner.

WHY THIS EXISTS
---------------
CLO's embedded Python has no main-thread pump (no Qt timer / idle callback), so a
background polling thread gets starved when CLO is idle. The reliable way to run CLO
API calls is *synchronously on the main thread* — which is exactly what CLO's Script
Editor does. So this file is meant to be RUN ONCE in the Script Editor each iteration:

    In CLO:  Edit > Python Script  (or drag this file onto the 3D view), then Run.
    Or:      exec(open(r"/path/to/clo_agent.py").read())

WHAT IT DOES EACH RUN
---------------------
1. If  <CLO_AGENT_DIR>/task.py  exists, it runs that task with the API helpers below
   in scope; the task sets RESULT = <json-able data> to return structured output.
2. Otherwise it runs a full introspection (project / patterns / fabrics / avatars /
   colorways / garment info).
3. Either way it takes a 3D snapshot and writes everything to:
       <CLO_AGENT_DIR>/result.json   (structured result + stdout + per-call errors)
       <CLO_AGENT_DIR>/snapshot.png  (viewport image)
   Claude reads those back to "see" the scene and decide the next task.

CLO_AGENT_DIR defaults to ~/clo_agent (override with the CLO_AGENT_DIR env var).

All API helpers use the pybind11-correct signatures (CLO 2026): C++ default arguments
are NOT exposed to Python, so every parameter is passed explicitly.
"""

import os
import sys
import json
import time
import io
import traceback

try:
    import utility_api
    import pattern_api
    import fabric_api
    import import_api  # noqa: F401  (available to tasks)
    import export_api
    IN_CLO3D = True
except ImportError:
    IN_CLO3D = False

AGENT_DIR = os.environ.get("CLO_AGENT_DIR") or os.path.join(
    os.path.expanduser("~"), "clo_agent"
)
TASK_FILE = os.path.join(AGENT_DIR, "task.py")
RESULT_FILE = os.path.join(AGENT_DIR, "result.json")
SNAPSHOT_FILE = os.path.join(AGENT_DIR, "snapshot.png")


def _log(msg):
    """Flushed print — CLO buffers stdout, so always flush to the Log Console."""
    try:
        print("[clo_agent] " + str(msg))
        sys.stdout.flush()
    except Exception:
        pass


def _safe(label, fn, *args, **kwargs):
    """Call an API fn, returning its value; record any error in _ERRORS by label."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        _ERRORS[label] = type(e).__name__ + ": " + str(e)
        return None


_ERRORS = {}


# ---------------------------------------------------------------------------
# Verified API helpers (correct CLO 2026 / pybind11 signatures)
# ---------------------------------------------------------------------------

def project_info():
    major = _safe("GetMajorVersion", utility_api.GetMajorVersion)
    minor = _safe("GetMinorVersion", utility_api.GetMinorVersion)
    patch = _safe("GetPatchVersion", utility_api.GetPatchVersion)
    version = None
    if None not in (major, minor, patch):
        version = "%s.%s.%s" % (major, minor, patch)
    return {
        "project_name": _safe("GetProjectName", utility_api.GetProjectName),
        "project_path": _safe("GetProjectFilePath", utility_api.GetProjectFilePath),
        "clo_version": version,
        "pattern_count": _safe("GetPatternCount", pattern_api.GetPatternCount),
        # bool is required: GetFabricCount(bool _bCurrentColorway=true) -> pybind needs it
        "fabric_count": _safe("GetFabricCount", fabric_api.GetFabricCount, True),
        "colorway_count": _safe("GetColorwayCount", utility_api.GetColorwayCount),
    }


def pattern_list():
    count = _safe("GetPatternCount", pattern_api.GetPatternCount) or 0
    out = []
    for i in range(count):
        out.append({
            "index": i,
            "name": _safe("GetPatternPieceName[%d]" % i,
                          pattern_api.GetPatternPieceName, i),
        })
    return out


def fabric_list():
    count = _safe("GetFabricCount", fabric_api.GetFabricCount, True) or 0
    out = []
    for i in range(count):
        entry = {"index": i}
        # GetFabricName may be (index) or unavailable; record errors, keep going.
        name = _safe("GetFabricName[%d]" % i, fabric_api.GetFabricName, i)
        if name is not None:
            entry["name"] = name
        out.append(entry)
    return out


def avatar_list():
    count = _safe("GetAvatarCount", export_api.GetAvatarCount)
    names = _safe("GetAvatarNameList", export_api.GetAvatarNameList)
    genders = _safe("GetAvatarGenderList", export_api.GetAvatarGenderList)
    out = []
    if names:
        for i, nm in enumerate(names):
            g = genders[i] if (genders and i < len(genders)) else None
            out.append({"index": i, "name": nm, "gender": g})
    return {"count": count, "avatars": out}


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


def snapshot(path=None):
    """Take a 3D viewport snapshot. Returns the path(s) CLO reports writing."""
    path = path or SNAPSHOT_FILE
    result = _safe("ExportSnapshot3D", export_api.ExportSnapshot3D, path)
    return {"requested": path, "returned": result,
            "exists": os.path.exists(path)}


def introspect():
    """Full read-back of the current scene — the default task."""
    return {
        "project": project_info(),
        "patterns": pattern_list(),
        "fabrics": fabric_list(),
        "avatars": avatar_list(),
        "colorways": colorway_list(),
        "garment": garment_info(),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    _ERRORS.clear()
    try:
        os.makedirs(AGENT_DIR, exist_ok=True)
    except Exception as e:
        _log("could not create AGENT_DIR %s: %r" % (AGENT_DIR, e))

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    _log("run starting at %s  IN_CLO3D=%s  AGENT_DIR=%s" %
         (started, IN_CLO3D, AGENT_DIR))

    result = None
    mode = None
    task_error = None

    # Capture task stdout so Claude can read it back (also echoed to the console).
    cap = io.StringIO()
    real_stdout = sys.stdout

    if not IN_CLO3D:
        task_error = ("Not running inside CLO3D — the *_api modules are unavailable. "
                      "Run this file from CLO's Script Editor.")
        mode = "error"
    elif os.path.exists(TASK_FILE):
        mode = "task"
        _log("executing task: %s" % TASK_FILE)
        ns = {
            # helpers
            "project_info": project_info, "pattern_list": pattern_list,
            "fabric_list": fabric_list, "avatar_list": avatar_list,
            "colorway_list": colorway_list, "garment_info": garment_info,
            "snapshot": snapshot, "introspect": introspect, "safe": _safe,
            # raw API for arbitrary calls (Blender-MCP style code execution)
            "utility_api": utility_api, "pattern_api": pattern_api,
            "fabric_api": fabric_api, "import_api": import_api,
            "export_api": export_api,
            "AGENT_DIR": AGENT_DIR, "RESULT": None,
        }
        try:
            sys.stdout = cap
            with open(TASK_FILE, "r") as f:
                code = f.read()
            exec(compile(code, TASK_FILE, "exec"), ns)
            result = ns.get("RESULT")
        except Exception:
            task_error = traceback.format_exc()
        finally:
            sys.stdout = real_stdout
    else:
        mode = "introspect"
        _log("no task.py found — running full introspection")
        try:
            sys.stdout = cap
            result = introspect()
        except Exception:
            task_error = traceback.format_exc()
        finally:
            sys.stdout = real_stdout

    # Always take a snapshot so Claude can see the current state.
    snap = None
    if IN_CLO3D:
        snap = snapshot()

    payload = {
        "ok": task_error is None,
        "mode": mode,
        "started": started,
        "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
        "in_clo3d": IN_CLO3D,
        "agent_dir": AGENT_DIR,
        "result": result,
        "snapshot": snap,
        "stdout": cap.getvalue(),
        "errors": dict(_ERRORS),
        "task_error": task_error,
    }

    try:
        tmp = RESULT_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(tmp, RESULT_FILE)
        _log("wrote %s" % RESULT_FILE)
    except Exception as e:
        _log("FAILED writing result.json: %r" % e)

    # Echo a short summary to the Log Console for the user.
    echo = cap.getvalue()
    if echo:
        _log("task stdout:\n" + echo)
    if task_error:
        _log("TASK ERROR:\n" + task_error)
    if _ERRORS:
        _log("per-call errors: " + json.dumps(_ERRORS))
    _log("done. mode=%s ok=%s snapshot_exists=%s" %
         (mode, task_error is None, bool(snap and snap.get("exists"))))


main()
