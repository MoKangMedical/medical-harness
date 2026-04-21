# OpenClaw-Medical-Harness

Medical AI agent orchestration framework built around reusable harness design.

This local working copy restores the package surface used by the published
repository and adds a stronger tool registry layer:

- `MedicalToolRegistry.list_all()`
- `MedicalToolRegistry.get_tools_for_harness()`
- alias compatibility such as `pubmed_search`, `chembl_query`,
  `opentargets_association`, `omim_lookup`, `openfda_safety`
- Demo Server health check no longer calls a missing registry method
- Xiaomi MiMo media integration for:
  - speech synthesis via `mimo-v2-tts`
  - audio understanding via `mimo-v2-omni`
  - video understanding via `mimo-v2-omni`
  - video production package generation via `mimo-v2-pro`

## MiMo Runtime

Configure the MiMo key in `.env`:

```bash
MIMO_API_KEY=your-key
MIMO_API_BASE_URL=https://api.xiaomimimo.com/v1
```

The demo server exposes:

- `GET /media/runtime`
- `GET /api/tools`
- `GET /api/toolchains`
- `POST /api/tools/{tool_name}/execute`
- `POST /api/toolchains/{harness_type}/execute`
- `POST /api/openclaw/execute`
- `POST /media/audio/synthesize`
- `POST /media/audio/analyze`
- `POST /media/video/analyze`
- `POST /media/video/create`

`/media/video/create` generates a storyboard/narration/caption package with MiMo.
It does not render an MP4 because Xiaomi's public MiMo docs currently expose video
understanding, not rendered video generation.

The demo API is also configured with permissive CORS (`*` origins, methods, and
headers) so browser clients can call the registered OpenClaw tools directly.

`POST /api/openclaw/execute` is the unified entry point. Send `{"target": "...",
"kind": "auto"}` to let the server resolve whether the target is a tool alias
or a named toolchain.

## Frontend SDK

An ESM client is available at `sdk/openclaw-client.js` with TypeScript hints in
`sdk/openclaw-client.d.ts`.

```js
import { OpenClawClient } from "./sdk/openclaw-client.js";

const client = new OpenClawClient({ baseUrl: "http://127.0.0.1:8001" });

const result = await client.execute({
  target: "pubmed_search",
  kind: "auto",
  context: { patient: { disease: "myasthenia gravis" } },
  params: { query: "myasthenia gravis", max_results: 1 },
});
```

Use `client.executeTool(...)` for a single registered tool and
`client.executeToolchain(...)` for `diagnosis`, `drug_discovery`, or
`health_management`.

## Background Server

Use the daemon CLI to run the API in the background:

```bash
cd /Users/apple/Desktop/medical-harness
uv sync --extra server --extra dev
./.venv/bin/python scripts/openclawd.py start --host 127.0.0.1 --port 8001
./.venv/bin/python scripts/openclawd.py status --host 127.0.0.1 --port 8001
./.venv/bin/python scripts/openclawd.py restart --host 127.0.0.1 --port 8001
./.venv/bin/python scripts/openclawd.py stop --host 127.0.0.1 --port 8001
```

The daemon writes runtime state to `.openclaw/openclawd.pid` and logs to
`.openclaw/openclawd.log`. If FastAPI/Uvicorn are missing, it will run
`uv sync --extra server` automatically before starting the service.
