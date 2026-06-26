# server — MCP / client side

The backend-agnostic client. Builds `Command`s and reads `Result`s per `../protocol`,
and selects a backend (`runtimes/python-script` today; `runtimes/cpp-plugin` later) via
its transport.

```bash
uv sync
uv run clo3d-mcp          # start the MCP server
uv run --group dev pytest # tests (mock backend, no CLO needed)
```

Package: `clo3d_mcp` (`src/clo3d_mcp`). Entry point: `clo3d-mcp = clo3d_mcp:main`.

> The tool surface is being migrated toward the Blender-MCP shape: `run_code`,
> `snapshot`/`render`, `garment_info`, `write_script`/`run_script`. See `../docs/PLAN.md` §8.
