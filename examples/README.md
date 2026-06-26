# Examples

Each example is a single **Command** (`../protocol/command.schema.json`). To run one:

```bash
cp examples/<file>.json ~/clo_agent/request.json
# then in CLO: run runtimes/clo.py once (Edit > Python Script > Run, or drag it in)
cat ~/clo_agent/response.json     # the Result; snapshot.png sits next to it
```

(Over the live `serve` mode / MCP server you send the same objects as tool calls — no
files.)

## introspect.json — read the whole scene
```json
{"type": "introspect"}
```

## snapshot.json — just an image
```json
{"type": "snapshot"}
```

## recolor.json — set fabric 0 to navy (run_code; whole API in one call)
```json
{"type": "run_code", "code": "for f in (0,1): fabric_api.SetFabricPBRMaterialBaseColor(0, f, 0.05, 0.08, 0.28, 1.0)\nutility_api.Refresh3DWindow()\nRESULT = {'recolored': True}"}
```

## simulate_render.json — drape, then photoreal render
```json
{"type": "run_code", "code": "utility_api.Simulate(80)\nutility_api.SetQualityRender(True)\nRESULT = {'render': export_api.ExportRenderingImage(r'~/clo_agent/render.png')}"}
```

## strain_map.json — fit assessment (a thing Blender can't do)
```json
{"type": "run_code", "code": "utility_api.SetStrainMapStatus(True)\nutility_api.Refresh3DWindow()\nRESULT = {'strain_map': 'enabled'}"}
```

## colorways.json — make 3 colorways and snapshot each
```json
{"type": "run_code", "code": "shots=[]\ncolors=[(0.03,0.03,0.03),(0.18,0.02,0.04),(0.02,0.03,0.10)]\nfor i,(r,g,b) in enumerate(colors):\n    fabric_api.SetFabricPBRMaterialBaseColor(0,0,r,g,b,1.0)\n    utility_api.Refresh3DWindow()\n    shots.append(export_api.ExportSnapshot3D(r'~/clo_agent/cw_%d.png'%i))\nRESULT={'shots':shots}"}
```

> Signatures follow `../docs/api-signatures.md` — pybind11 drops C++ default args, so pass
> every parameter (e.g. `GetFabricCount(True)`). Anything not shown here: write `run_code`.
