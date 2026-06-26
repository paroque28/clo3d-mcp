# CLO 2026 API signatures — verified reference

Cross-language reference (used by every backend). Derived by auditing the plugin call
sites against `sdk/CLOAPIInterface/include/*.h`.

## The bug class: pybind11 drops C++ default arguments

CLO's Python API is a pybind11 binding. **pybind11 does not expose C++ default argument
values.** So a method declared in the header as `Foo(bool x = true)` must be called from
Python as `Foo(True)` — `Foo()` raises `TypeError`. Every "default arg" in the headers
is therefore mandatory from Python.

## Corrected calls (were broken in upstream)

| Call | Header signature | Correct Python |
|---|---|---|
| `GetFabricCount()` | `GetFabricCount(bool _bCurrentColorway = true)` | `GetFabricCount(True)` |
| `SetSimulationQuality(q)` | `SetSimulationQuality(int _quality, int _simulationMode)` | `SetSimulationQuality(q, 0)` |
| `CopyColorway(i)` | `CopyColorway(unsigned int index, int _colorwayCopyOption)` | `CopyColorway(i, 0)` |
| `NewImportExportOption()` | *(does not exist in SDK)* | `ImportExportOption()` |

## Confirmed-correct, commonly-used signatures

- `pattern_api.GetPatternCount()` — no args.
- `pattern_api.GetPatternPieceName(int index)`.
- `pattern_api.GetPatternInformation(int index)` → JSON string.
- `pattern_api.AddSeamlinePairGroup(patA, lineA, patB, lineB, dirA, dirB)` — programmatic sewing.
- `pattern_api.AddSeamlineTopstitch(seamGroupIdx, startRatio, endRatio, styleIdx)`.
- `fabric_api.AddFabric(str path)` → index.
- `fabric_api.AssignFabricToPattern(fabricIdx, patternIdx, assignOption)`.
- `fabric_api.SetFabricPBRMaterialBaseColor(fabricIdx, materialFace, r, g, b, a)` — floats 0..1.
- `fabric_api.GetFabricIndexForPattern(int patternIdx)`.
- `import_api.ImportFile(str path)`; `import_api.ImportAVAC(str file, str apf)`.
- `import_api.ImportMeasurement(str csvPath)` / `ImportAvatarMeasurement(csv, avt, opt)` — avatar sizing.
- `export_api.ExportSnapshot3D(str path)` → list[list[str]].
- `export_api.ExportRenderingImage(str path)`; `utility_api.SetQualityRender(True)` first.
- `export_api.ExportGarmentInformationToStream()` — no args → JSON string.
- `export_api.ExportTurntableImages(path, numImages, width, height)` — pass width/height explicitly.
- `utility_api.Simulate(int steps)`.
- `utility_api.SetStrainMapStatus(True)` / `SetStressMapStatus(True)` then `ExportMaskSnapshot3D` for fit maps.

## Capability gaps (no API exists — GUI-only)

- Adding/placing **buttons, zippers, pockets** (only recolor existing: `SetButtonHeadStyleColor`, `SetTrimStyleColor`).
- **Parametric avatar resize** (no `SetHeight`; only measurement-file import).
- Authoring quality garment **geometry from scratch** (possible in theory via
  `CreatePatternWithPoints` + `AddSeamlinePairGroup`, infeasible in practice — start from a block).

See `docs/PLAN.md` §6 for the full capability tiers.
