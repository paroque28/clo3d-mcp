import json
import os
import sys
import time
import threading

try:
    import export_api
    import fabric_api
    import import_api
    import pattern_api
    import utility_api
    IN_CLO3D = True
except ImportError:
    IN_CLO3D = False
    print("[CLO MCP] WARNING: Not running inside CLO3D. API calls will fail.")

# Communication directory
COMM_DIR = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "clo3d_mcp")
REQUEST_FILE = os.path.join(COMM_DIR, "request.json")
RESPONSE_FILE = os.path.join(COMM_DIR, "response.json")
POLL_INTERVAL = 0.1

# Verbose logging. Set CLO3D_MCP_DEBUG=0 in the environment to quiet it down.
DEBUG = os.environ.get("CLO3D_MCP_DEBUG", "1") != "0"
# Emit a heartbeat line every N idle poll iterations so we can SEE the
# background thread is actually being scheduled by CLO's interpreter.
HEARTBEAT_EVERY = 100  # ~10s at POLL_INTERVAL=0.1

_server_running = False
_server_thread = None


def _log(msg, level="INFO"):
    """Print a flushed, timestamped log line.

    CLO's embedded Python buffers stdout, so without an explicit flush the
    Log Console can show nothing (or print lines out of order). Always flush.
    """
    try:
        ts = time.strftime("%H:%M:%S")
    except Exception:
        ts = "?"
    line = "[CLO MCP] " + ts + " [" + level + "] " + str(msg)
    try:
        print(line)
        sys.stdout.flush()
    except Exception:
        # Last resort: never let logging crash the loop.
        try:
            sys.stderr.write(line + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def _debug(msg):
    if DEBUG:
        _log(msg, level="DEBUG")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def handle_ping(params):
    return {"pong": True, "in_clo3d": IN_CLO3D}


# -- Scene --

def handle_get_project_info(params):
    name = utility_api.GetProjectName()
    path = utility_api.GetProjectFilePath()
    major = utility_api.GetMajorVersion()
    minor = utility_api.GetMinorVersion()
    patch = utility_api.GetPatchVersion()
    pattern_count = pattern_api.GetPatternCount()
    fabric_count = fabric_api.GetFabricCount(True)
    colorway_count = utility_api.GetColorwayCount()
    return {
        "project_name": name,
        "project_path": path,
        "clo_version": str(major) + "." + str(minor) + "." + str(patch),
        "pattern_count": pattern_count,
        "fabric_count": fabric_count,
        "colorway_count": colorway_count,
    }


def handle_new_project(params):
    utility_api.NewProject()
    return {"created": True}


def handle_open_file(params):
    file_path = params["file_path"]
    result = import_api.ImportFile(file_path)
    return {"opened": result, "file_path": file_path}


def handle_save_file(params):
    file_path = params["file_path"]
    result = export_api.ExportZPrj(file_path)
    return {"saved": bool(result), "file_path": result or file_path}


def handle_get_garment_info(params):
    info_str = export_api.ExportGarmentInformationToStream()
    if info_str:
        try:
            data = json.loads(info_str)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": str(info_str)}
        return {"garment_info": data}
    return {"garment_info": None}


# -- Pattern --

def handle_get_pattern_count(params):
    count = pattern_api.GetPatternCount()
    return {"count": count}


def handle_get_pattern_list(params):
    count = pattern_api.GetPatternCount()
    patterns = []
    for i in range(count):
        name = pattern_api.GetPatternPieceName(i)
        patterns.append({"index": i, "name": name})
    return {"patterns": patterns, "count": count}


def handle_get_pattern_info(params):
    index = params["pattern_index"]
    info_str = pattern_api.GetPatternInformation(index)
    try:
        info = json.loads(info_str) if info_str else {}
    except (json.JSONDecodeError, TypeError):
        info = {"raw": str(info_str)}
    name = pattern_api.GetPatternPieceName(index)
    return {"index": index, "name": name, "info": info}


def handle_get_bounding_box(params):
    index = params["pattern_index"]
    bb = pattern_api.GetBoundingBoxOfPattern(index)
    return {"index": index, "bounding_box": bb}


def handle_set_pattern_name(params):
    index = params["pattern_index"]
    name = params["name"]
    pattern_api.SetPatternPieceName(index, name)
    return {"index": index, "name": name}


def handle_copy_pattern(params):
    index = params["pattern_index"]
    x = params.get("x", 0)
    y = params.get("y", 0)
    pattern_api.CopyPatternPiecePos(index, x, y)
    return {"copied": True, "source_index": index, "position": [x, y]}


def handle_delete_pattern(params):
    index = params["pattern_index"]
    pattern_api.DeletePatternPiece(index)
    return {"deleted": True, "index": index}


def handle_flip_pattern(params):
    index = params["pattern_index"]
    horizontal = params.get("horizontal", True)
    each = params.get("each", True)
    pattern_api.FlipPatternPiece(index, horizontal, each)
    return {"flipped": True, "index": index, "horizontal": horizontal, "each": each}


def handle_create_pattern(params):
    points = params["points"]
    point_tuples = []
    for p in points:
        x, y = p[0], p[1]
        vtype = p[2] if len(p) > 2 else 0
        point_tuples.append((x, y, vtype))
    result = pattern_api.CreatePatternWithPoints(point_tuples)
    return {"created": True, "point_count": len(point_tuples), "result": result}


def handle_get_arrangement_list(params):
    arr_list = pattern_api.GetArrangementList()
    return {"arrangements": arr_list}


# -- Fabric --

def handle_get_fabric_count(params):
    count = fabric_api.GetFabricCount(True)
    return {"count": count}


def handle_get_fabric_list(params):
    count = fabric_api.GetFabricCount(True)
    fabrics = []
    for i in range(count):
        fabrics.append({"index": i})
    return {"fabrics": fabrics, "count": count}


def handle_add_fabric(params):
    file_path = params["file_path"]
    index = fabric_api.AddFabric(file_path)
    return {"added": True, "fabric_index": index, "file_path": file_path}


def handle_assign_fabric(params):
    fabric_index = params["fabric_index"]
    pattern_index = params["pattern_index"]
    option = params.get("assign_option", 1)
    result = fabric_api.AssignFabricToPattern(fabric_index, pattern_index, option)
    return {"assigned": result, "fabric_index": fabric_index, "pattern_index": pattern_index}


def handle_set_fabric_color(params):
    fabric_index = params["fabric_index"]
    r = params.get("r", 255)
    g = params.get("g", 255)
    b = params.get("b", 255)
    a = params.get("a", 255)
    material_face = params.get("material_face", 0)
    # Convert 0-255 int range to 0.0-1.0 float range
    r_f = r / 255.0
    g_f = g / 255.0
    b_f = b / 255.0
    a_f = a / 255.0
    fabric_api.SetFabricPBRMaterialBaseColor(fabric_index, material_face, r_f, g_f, b_f, a_f)
    return {"set": True, "fabric_index": fabric_index, "color": [r, g, b, a]}


def handle_get_fabric_for_pattern(params):
    pattern_index = params["pattern_index"]
    fabric_index = fabric_api.GetFabricIndexForPattern(pattern_index)
    return {"pattern_index": pattern_index, "fabric_index": fabric_index}


def handle_delete_fabric(params):
    fabric_index = params["fabric_index"]
    result = fabric_api.DeleteFabric(fabric_index)
    return {"deleted": result, "fabric_index": fabric_index}


# -- Export --

def handle_export_obj(params):
    file_path = params["file_path"]
    options = params.get("options", {})
    if options:
        opt = export_api.ImportExportOption()
        for key, val in options.items():
            if hasattr(opt, key):
                setattr(opt, key, val)
        result = export_api.ExportOBJ(file_path, opt)
    else:
        result = export_api.ExportOBJ(file_path)
    # ExportOBJ returns list[str], not str
    if isinstance(result, list):
        exported = len(result) > 0
        file_paths = result
    else:
        exported = bool(result)
        file_paths = [result] if result else [file_path]
    return {"exported": exported, "file_paths": file_paths, "format": "obj"}


def handle_export_fbx(params):
    file_path = params["file_path"]
    try:
        options = export_api.ImportExportOption()
        result = export_api.ExportFBX(file_path, options)
    except (AttributeError, TypeError):
        result = export_api.ExportFBX(file_path)
    return {"exported": bool(result), "file_path": result or file_path, "format": "fbx"}


def handle_export_glb(params):
    file_path = params["file_path"]
    try:
        options = export_api.ImportExportOption()
        result = export_api.ExportGLB(file_path, options)
    except (AttributeError, TypeError):
        result = export_api.ExportGLB(file_path)
    return {"exported": bool(result), "file_path": result or file_path, "format": "glb"}


def handle_export_gltf(params):
    file_path = params["file_path"]
    try:
        options = export_api.ImportExportOption()
        result = export_api.ExportGLTF(file_path, options, False)
    except (AttributeError, TypeError):
        result = export_api.ExportGLTF(file_path)
    return {"exported": bool(result), "file_path": result or file_path, "format": "gltf"}


def handle_export_thumbnail(params):
    file_path = params["file_path"]
    result = export_api.ExportThumbnail3D(file_path)
    return {"exported": bool(result), "file_path": result or file_path}


def handle_export_snapshot(params):
    file_path = params["file_path"]
    result = export_api.ExportSnapshot3D(file_path)
    return {"exported": bool(result), "file_path": result or file_path}


def handle_export_turntable(params):
    file_path = params["file_path"]
    num_images = params.get("number_of_images", 36)
    width = params.get("width", 2500)
    height = params.get("height", 2500)
    result = export_api.ExportTurntableImages(file_path, num_images, width, height)
    return {"exported": bool(result), "file_path": result or file_path,
            "number_of_images": num_images, "width": width, "height": height}


def handle_export_tech_pack(params):
    file_path = params["file_path"]
    try:
        options = export_api.ExportTechpackOption()
        result = export_api.ExportTechPack(file_path, options)
    except (AttributeError, TypeError):
        result = export_api.ExportTechPack(file_path)
    return {"exported": bool(result), "file_path": result or file_path}


# -- Import --

def handle_import_file(params):
    file_path = params["file_path"]
    result = import_api.ImportFile(file_path)
    return {"imported": result, "file_path": file_path}


def handle_import_avatar(params):
    file_path = params["file_path"]
    apf_path = params.get("apf_path", "")
    result = import_api.ImportAVAC(file_path, apf_path)
    return {"imported": result, "file_path": file_path}


def handle_import_fabric(params):
    file_path = params["file_path"]
    index = fabric_api.AddFabric(file_path)
    return {"imported": True, "fabric_index": index, "file_path": file_path}


# -- Simulation --

def handle_simulate(params):
    steps = params.get("steps", 100)
    utility_api.Simulate(steps)
    return {"simulated": True, "steps": steps}


def handle_set_simulation_quality(params):
    quality = params["quality"]
    simulation_mode = params.get("simulation_mode", 0)
    utility_api.SetSimulationQuality(quality, simulation_mode)
    return {"quality": quality, "simulation_mode": simulation_mode}


# -- Colorway --

def handle_get_colorways(params):
    count = utility_api.GetColorwayCount()
    names = export_api.GetColorwayNameList()
    current = utility_api.GetCurrentColorwayIndex()
    colorways = []
    if names:
        for i, name in enumerate(names):
            colorways.append({"index": i, "name": name, "current": i == current})
    else:
        for i in range(count):
            colorways.append({"index": i, "current": i == current})
    return {"colorways": colorways, "count": count, "current_index": current}


def handle_set_current_colorway(params):
    index = params["colorway_index"]
    utility_api.SetCurrentColorwayIndex(index)
    return {"set": True, "colorway_index": index}


def handle_set_colorway_name(params):
    index = params["colorway_index"]
    name = params["name"]
    utility_api.SetColorwayName(index, name)
    return {"set": True, "colorway_index": index, "name": name}


def handle_copy_colorway(params):
    index = params["colorway_index"]
    copy_option = params.get("copy_option", 0)
    utility_api.CopyColorway(index, copy_option)
    return {"copied": True, "source_index": index, "copy_option": copy_option}


def handle_delete_colorway(params):
    index = params["colorway_index"]
    utility_api.DeleteColorwayItem(index)
    return {"deleted": True, "colorway_index": index}


# -- Avatar --

def handle_get_avatars(params):
    count = export_api.GetAvatarCount()
    names = export_api.GetAvatarNameList()
    genders = export_api.GetAvatarGenderList()
    avatars = []
    if names:
        for i, name in enumerate(names):
            avatar = {"index": i, "name": name}
            if genders and i < len(genders):
                avatar["gender"] = genders[i]
            avatars.append(avatar)
    return {"avatars": avatars, "count": count}


def handle_show_hide_avatar(params):
    show = params.get("show", True)
    utility_api.SetShowHideAvatar(show)
    return {"visible": show}


def handle_get_avatar_genders(params):
    genders = export_api.GetAvatarGenderList()
    return {"genders": genders or []}


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

HANDLERS = {
    "ping": handle_ping,
    "get_project_info": handle_get_project_info,
    "new_project": handle_new_project,
    "open_file": handle_open_file,
    "save_file": handle_save_file,
    "get_garment_info": handle_get_garment_info,
    "get_pattern_count": handle_get_pattern_count,
    "get_pattern_list": handle_get_pattern_list,
    "get_pattern_info": handle_get_pattern_info,
    "get_bounding_box": handle_get_bounding_box,
    "set_pattern_name": handle_set_pattern_name,
    "copy_pattern": handle_copy_pattern,
    "delete_pattern": handle_delete_pattern,
    "flip_pattern": handle_flip_pattern,
    "create_pattern": handle_create_pattern,
    "get_arrangement_list": handle_get_arrangement_list,
    "get_fabric_count": handle_get_fabric_count,
    "get_fabric_list": handle_get_fabric_list,
    "add_fabric": handle_add_fabric,
    "assign_fabric": handle_assign_fabric,
    "set_fabric_color": handle_set_fabric_color,
    "get_fabric_for_pattern": handle_get_fabric_for_pattern,
    "delete_fabric": handle_delete_fabric,
    "export_obj": handle_export_obj,
    "export_fbx": handle_export_fbx,
    "export_glb": handle_export_glb,
    "export_gltf": handle_export_gltf,
    "export_thumbnail": handle_export_thumbnail,
    "export_snapshot": handle_export_snapshot,
    "export_turntable": handle_export_turntable,
    "export_tech_pack": handle_export_tech_pack,
    "import_file": handle_import_file,
    "import_avatar": handle_import_avatar,
    "import_fabric": handle_import_fabric,
    "simulate": handle_simulate,
    "set_simulation_quality": handle_set_simulation_quality,
    "get_colorways": handle_get_colorways,
    "set_current_colorway": handle_set_current_colorway,
    "set_colorway_name": handle_set_colorway_name,
    "copy_colorway": handle_copy_colorway,
    "delete_colorway": handle_delete_colorway,
    "get_avatars": handle_get_avatars,
    "show_hide_avatar": handle_show_hide_avatar,
    "get_avatar_genders": handle_get_avatar_genders,
}


# ---------------------------------------------------------------------------
# File-based communication
# ---------------------------------------------------------------------------

def process_command(data):
    """Parse and execute a single JSON command."""
    try:
        request = json.loads(data)
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"id": None, "status": "error", "message": "Invalid JSON: " + str(e)})

    req_id = request.get("id")
    cmd_type = request.get("type")
    params = request.get("params", {})
    _log("command received: type=" + str(cmd_type) + " id=" + str(req_id)
         + " params=" + json.dumps(params))

    handler = HANDLERS.get(cmd_type)
    if not handler:
        _log("unknown command: " + str(cmd_type), level="ERROR")
        return json.dumps({
            "id": req_id,
            "status": "error",
            "message": "Unknown command: " + str(cmd_type),
        })

    try:
        result = handler(params)
        _debug("command ok: type=" + str(cmd_type) + " id=" + str(req_id))
        return json.dumps({"id": req_id, "status": "success", "result": result})
    except Exception as e:
        _log("handler raised for type=" + str(cmd_type) + " id=" + str(req_id)
             + ": " + repr(e), level="ERROR")
        return json.dumps({
            "id": req_id,
            "status": "error",
            "message": str(type(e).__name__) + ": " + str(e),
        })


def poll_loop(my_gen=0):
    """Poll for request files and process them.

    my_gen is this instance's generation number. If a newer run supersedes us
    (sys._CLO_MCP_GEN changes), we exit, so only one poller stays active even
    after the script is re-run several times in CLO's persistent interpreter.
    """
    global _server_running

    try:
        tid = threading.get_ident()
    except Exception:
        tid = "?"
    _log("poll_loop ENTERED on thread id=" + str(tid)
         + " (if you never see this line, CLO is not scheduling the background thread)")

    # Create comm directory
    try:
        if not os.path.exists(COMM_DIR):
            os.makedirs(COMM_DIR)
            _debug("created comm dir: " + COMM_DIR)
        else:
            _debug("comm dir already exists: " + COMM_DIR)
    except Exception as e:
        _log("FAILED to create comm dir " + COMM_DIR + ": " + repr(e), level="ERROR")

    # Clean up stale files
    for f in [REQUEST_FILE, RESPONSE_FILE]:
        if os.path.exists(f):
            try:
                os.remove(f)
                _debug("removed stale file: " + f)
            except OSError as e:
                _debug("could not remove stale file " + f + ": " + repr(e))

    _log("Listening for commands in: " + COMM_DIR)

    iterations = 0
    handled = 0
    while _server_running and getattr(sys, "_CLO_MCP_GEN", my_gen) == my_gen:
        iterations += 1
        if DEBUG and iterations % HEARTBEAT_EVERY == 0:
            _debug("heartbeat: alive, polled " + str(iterations)
                   + " times, handled " + str(handled) + " request(s)")
        try:
            if os.path.exists(REQUEST_FILE):
                # Read request
                with open(REQUEST_FILE, "r") as f:
                    data = f.read()
                _debug("request file detected (" + str(len(data)) + " bytes)")

                # Delete request file
                try:
                    os.remove(REQUEST_FILE)
                except OSError as e:
                    _debug("could not remove request file: " + repr(e))

                if data.strip():
                    # Process and write response
                    response = process_command(data)

                    # Per-instance temp name avoids collisions if a stale
                    # instance is still running; os.replace is atomic and
                    # overwrites, so there is no remove/rename race window.
                    tmp_file = (RESPONSE_FILE + "." + str(my_gen)
                                + "." + str(tid) + ".tmp")
                    with open(tmp_file, "w") as f:
                        f.write(response)
                    os.replace(tmp_file, RESPONSE_FILE)
                    handled += 1
                    _debug("response written (" + str(len(response)) + " bytes)")

        except Exception as e:
            _log("poll error: " + repr(e), level="ERROR")

        time.sleep(POLL_INTERVAL)

    _log("Server stopped (gen " + str(my_gen) + ", handled "
         + str(handled) + " request(s))")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start():
    """Start the MCP plugin."""
    global _server_running, _server_thread

    # Singleton across repeated runs in CLO's persistent interpreter.
    # Bump a generation counter on `sys` (it survives script re-execution, so a
    # fresh module namespace can still see it). Any previously-started poll loop
    # checks this counter and exits when it changes — clicking Run replaces the
    # instance instead of stacking another poller.
    prev_gen = getattr(sys, "_CLO_MCP_GEN", 0)
    my_gen = prev_gen + 1
    sys._CLO_MCP_GEN = my_gen
    if prev_gen:
        _log("superseding previous instance (gen " + str(prev_gen) + ")")

    _log("start() called. gen=" + str(my_gen) + " IN_CLO3D=" + str(IN_CLO3D)
         + " COMM_DIR=" + COMM_DIR + " DEBUG=" + str(DEBUG))
    _server_running = True
    _server_thread = threading.Thread(target=poll_loop, args=(my_gen,), daemon=True)
    _server_thread.start()
    _log("Plugin started (spawned poll thread)")
    # Give the thread a moment, then report whether it actually came alive.
    try:
        time.sleep(0.3)
        alive = _server_thread.is_alive()
        _log("poll thread is_alive=" + str(alive))
        if not alive:
            _log("poll thread did NOT start — CLO is not running Python background "
                 "threads. The plugin cannot poll this way.", level="ERROR")
    except Exception as e:
        _debug("post-start check failed: " + repr(e))


def stop():
    """Stop the MCP plugin."""
    global _server_running, _server_thread

    if not _server_running:
        _log("Not running")
        return

    _server_running = False
    if _server_thread:
        _server_thread.join(timeout=5)
        _server_thread = None
    _log("Plugin stopped")


# Auto-start
_log("module loaded. __name__=" + str(__name__) + " IN_CLO3D=" + str(IN_CLO3D))
if __name__ == "__main__" or IN_CLO3D:
    start()
else:
    _log("auto-start skipped (not __main__ and not IN_CLO3D); call start() manually",
         level="WARN")
