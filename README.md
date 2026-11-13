# OMBAR FL-AI Studio

Natural-language web control for **FL Studio** via **MCP (Model Context Protocol)** + **FastAPI**.

Type a prompt in the dashboard, the AI engine translates it into FL Studio
MCP tool-calls (BPM, beat patterns, instruments, vocal chains, song structure),
and the bridge forwards them over TCP to the FL Studio MCP daemon on
`127.0.0.1:9787`.

---

## Architecture

```
 +-------------------+        HTTP / WebSocket        +-------------------+
 |  Web Dashboard    |  ----------------------------> |  FastAPI Backend  |
 |  (Vercel / local) |   POST /api/prompt   WS /ws    |  (Port 8080)      |
 |  index.html       |                                |  server.py        |
 |  app.js           |                                |  ai_engine.py     |
 |  style.css        |                                |  mcp_bridge.py    |
 +-------------------+                                +---------+---------+
                                                                |
                                                  JSON-RPC 2.0  |  TCP
                                                                v
                                                +-----------------------------+
                                                |  FL Studio MCP Daemon       |
                                                |  flstudio-mcp  :9787        |
                                                +--------------+--------------+
                                                               |
                                                               v
                                                        +-------------+
                                                        |  FL Studio  |
                                                        +-------------+
```

**Ports**

| Service        | Address            |
|----------------|--------------------|
| FastAPI server | `0.0.0.0:8080`     |
| MCP daemon     | `127.0.0.1:9787`   |
| Web dashboard  | served at `/` (8080) or open `index.html` directly |

---

## File structure

```
ombar-flai-studio/
+-- config.json                       # central config
+-- README.md                         # this file
+-- backend/
|   +-- server.py                     # FastAPI app (CORS + safe JSON + WS)
|   +-- mcp_bridge.py                 # async JSON-RPC client -> :9787
|   +-- ai_engine.py                  # NL prompt -> MCP tool-calls
|   +-- requirements.txt
+-- frontend/
|   +-- index.html                    # dashboard
|   +-- app.js                        # prompt + WS + history
|   +-- style.css                     # dark studio theme
+-- launchers/
    +-- OMBAR_FL-AI_Studio_Launcher.bat   # master: start everything
    +-- start_mcp_daemon.bat              # MCP daemon only (:9787)
    +-- start_server.bat                  # FastAPI only (:8080)
    +-- stop_all.bat                      # kill both
```

---

## Quick start (Windows)

1. **Install Python 3.10+** (with `pip`). Confirm with:
   ```
   python --version
   ```

2. **Extract / clone** this folder to:
   ```
   F:\BERTY\Projeck klaud FL\flstudio-mcp-main\flstudio-mcp-main
   ```
   ...or anywhere you like - just keep the structure intact.

3. **Make sure FL Studio is open** and the `flstudio-mcp` server
   (the sibling project) is available. The launcher auto-detects it.
   If auto-detection fails, set an env var:
   ```
   set FLSTUDIO_MCP_DIR=F:\path\to\flstudio-mcp-main
   ```

4. **Double-click** `launchers\OMBAR_FL-AI_Studio_Launcher.bat`.

   Two persistent console windows open:
   * `OMBAR - MCP Daemon :9787`
   * `OMBAR - FastAPI Backend :8080`

   Both use `cmd /k` so they **never auto-close**, even on error.

5. **Open the dashboard**:
   - <http://localhost:8080>  (served by FastAPI), **or**
   - open `frontend\index.html` directly in a browser.

6. **Type a prompt**, e.g.:
   ```
   buat beat hip-hop 90 bpm di A minor, kasih 808 dan hi-hat,
   lalu pasang vocal chain di insert 6 dengan auto-tune, eq,
   kompresor maximus, reverb
   ```
   Press **Ctrl+Enter** or click **Kirim ke FL Studio**.

---

## CORS / ERR_CONNECTION_REFUSED fixes (already built in)

`server.py` ships with a deliberately permissive CORS policy so that a
**Vercel-hosted** frontend can call a **localhost** backend without blocks:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],
    allow_origin_regex=".*",       # accept ANY origin incl *.vercel.app
    allow_credentials=False,        # required when origin is "*"
    allow_methods=["GET","POST","OPTIONS","PUT","DELETE"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

In `app.js` you can also change the **Backend URL** field at runtime - the
value is persisted in `localStorage`. Point a Vercel deployment at your
local machine (or a tunnel) by entering e.g. `http://192.168.1.10:8080`.

> For production, tighten `allow_origins` to your real domain list.

---

## Safe JSON handling (no SyntaxError ever leaks)

`POST /api/prompt` reads the raw body and parses it defensively:

- valid JSON `{"prompt":"..."}`  -> parsed normally
- plain text `buat beat ...`     -> treated as the prompt
- malformed JSON                 -> the raw string becomes the prompt
- empty body                     -> `400 {"error":"Empty request body"}`

No `SyntaxError` / `json.decoder.JSONDecodeError` can crash the server.

---

## Supported prompt families

### 1. Beat & instrument creation
```
buat beat hip-hop 90 bpm di A minor dengan 808, kick, snare, hi-hat
buat beat papua pop 95 bpm dengan FL Keys dan Sytrus
buat beat EDM 128 bpm
load plugin Sytrus
```
MCP tools: `set_bpm`, `set_key`, `set_genre`, `create_drum_pattern`,
`load_instrument`, `add_track`.

### 2. Mixing & vocal chain
```
pasang vocal chain di insert 6 dengan auto-tune, eq, kompresor maximus, reverb
load reverb di insert 3
```
MCP tools: `route_track_to_mixer`, `load_effect`, `set_effect_param`,
`enable_vocal_chain`.

Default vocal chain (Insert 6):
`Auto-Tune -> Fruity Parametric EQ 2 -> Maximus -> Fruity Reeverb 2`

### 3. Remix & arrangement
```
atur struktur lagu: intro, verse, chorus, drop, outro
remix track: duplicate verse jadi drop
automate filter cutoff selama 8 bar
```
MCP tools: `duplicate_pattern`, `set_song_structure`, `automate_param`,
`split_clip`, `move_clip`.

---

## API reference

| Method | Path            | Body                                   | Purpose                          |
|--------|-----------------|----------------------------------------|----------------------------------|
| GET    | `/`             | -                                      | Serves the dashboard HTML        |
| GET    | `/api/status`   | -                                      | Backend + MCP + FL Studio health |
| GET    | `/api/tools`    | -                                      | List MCP tools                   |
| POST   | `/api/prompt`   | `{"prompt":"..."}`                     | Run AI engine -> MCP             |
| POST   | `/api/command`  | `{"tool":"set_bpm","args":{"bpm":90}}` | Direct MCP call                  |
| WS     | `/ws`           | text / JSON                            | Live event stream                |

---

## Troubleshooting

| Symptom                                    | Fix                                                    |
|--------------------------------------------|--------------------------------------------------------|
| Backend status red                         | Run `launchers\start_server.bat`                       |
| MCP status red / `ERR_CONNECTION_REFUSED`  | Run `launchers\start_mcp_daemon.bat`; open FL Studio   |
| `pip install` fails                        | Run as admin, or use `py -m pip install ...`           |
| CORS error in browser console              | Already allowed - confirm backend is actually running |
| Tool returns `MCP error -32601`            | That tool isn't exposed by your flstudio-mcp version   |
| WebSocket reconnects endlessly             | Backend is down - start `server.py` first              |

---

## License

MIT - use it, remix it, ship it.  Built for OMBAR by Berty.
