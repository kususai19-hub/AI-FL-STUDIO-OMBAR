"""
================================================================================
 OMBAR FL-AI Studio  -  FastAPI Backend Server  (Port 8080)
================================================================================
Responsibilities:
  * Receive natural-language prompts from the web dashboard (Vercel / localhost)
  * Translate prompts into MCP tool-calls via ai_engine.py
  * Forward those calls to the FL Studio MCP daemon on 127.0.0.1:9787
  * Stream live status / logs back to the browser over WebSocket
  * Serve the static frontend (index.html / app.js / style.css)

Design notes:
  * CORS is deliberately permissive (regex=".*") so a Vercel deployment can
    call a localhost backend WITHOUT triggering ERR_CONNECTION_REFUSED-style
    CORS blocks.  Tighten `ALLOWED_ORIGINS` for production if you wish.
  * Every JSON body is parsed defensively: a malformed body is never allowed
    to crash the server (no SyntaxError ever leaks to the client).  When the
    body is not valid JSON we fall back to treating the raw text as the prompt.
  * The MCP daemon is optional at startup: the server boots even when FL
    Studio / the MCP daemon is offline, and reports the status on /api/status.
================================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles

# Local modules (same folder)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mcp_bridge import MCPBridge, MCPConnectionError  # noqa: E402
from ai_engine import AIEngine  # noqa: E402

# --------------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "9787"))
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8080"))

# Logging must be configured BEFORE the frontend resolution below uses `log`.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ombar.server")

# Import the self-contained embedded dashboard (served as fallback when the
# external frontend/ folder cannot be located).
from dashboard import DASHBOARD_HTML  # noqa: E402


def _resolve_frontend_dir() -> tuple[Optional[Path], list[str]]:
    """Search several candidate locations for the frontend folder.

    Returns (found_path_or_None, list_of_searched_paths).
    This makes the server robust against flat extractions or being copied
    into a different parent folder.
    """
    env_dir = os.environ.get("FRONTEND_DIR")
    candidates: list[Path] = []
    if env_dir:
        candidates.append(Path(env_dir).resolve())
    candidates.extend([
        HERE.parent / "frontend",          # ombar-flai-studio/backend -> ../frontend
        HERE / "frontend",                 # backend/frontend (flat layout)
        HERE.parent.parent / "frontend",   # one level higher
        Path.cwd() / "frontend",           # current working dir
        Path.cwd() / "ombar-flai-studio" / "frontend",
    ])
    searched = [str(c) for c in candidates]
    for c in candidates:
        if (c / "index.html").exists():
            return c, searched
    return None, searched


FRONTEND_DIR, FRONTEND_SEARCHED = _resolve_frontend_dir()
EMBEDDED_MODE = FRONTEND_DIR is None
if EMBEDDED_MODE:
    log.warning("Frontend folder not found. Searched: %s", FRONTEND_SEARCHED)
    log.warning("Serving EMBEDDED dashboard instead (fully functional).")
else:
    log.info("Frontend folder found: %s", FRONTEND_DIR)

# Origins allowed by CORS.  "*" + a permissive regex covers Vercel previews,
# localhost dev servers and even file:// opened HTML.
ALLOWED_ORIGINS = [
    "*",
    "null",  # browsers send the literal string "null" for file:// origin
]

# --------------------------------------------------------------------------- #
#  App + middleware
# --------------------------------------------------------------------------- #
app = FastAPI(title="OMBAR FL-AI Studio API", version="1.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=".*",            # accept ANY origin incl. *.vercel.app
    allow_credentials=False,            # must be False when origin is "*"
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# --------------------------------------------------------------------------- #
#  Shared state
# --------------------------------------------------------------------------- #
bridge = MCPBridge(host=MCP_HOST, port=MCP_PORT)
engine = AIEngine(bridge=bridge)


class ConnectionManager:
    """Minimal WebSocket fan-out for live status / log streaming."""

    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead: List[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def emit(event: str, payload: Dict[str, Any]) -> None:
    """Fire-and-forget broadcast helper (safe to call from sync code)."""
    msg = {"ts": datetime.now().isoformat(timespec="seconds"),
           "event": event, "payload": payload}
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(msg))
    except RuntimeError:
        # No running loop (e.g. called during startup) - just log.
        log.info("[emit:%s] %s", event, payload)


# Attach the emitter so ai_engine / mcp_bridge can push live logs.
engine.set_emitter(emit)
bridge.set_emitter(emit)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
async def _read_body_safe(request: Request) -> str:
    """Read raw request body as text, never raising."""
    try:
        raw = await request.body()
    except Exception as exc:  # pragma: no cover
        log.warning("Failed to read body: %s", exc)
        return ""
    return raw.decode("utf-8", errors="ignore").strip()


def _safe_json(text: str) -> Dict[str, Any]:
    """Parse JSON defensively.  Returns {} for empty / invalid input."""
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            return {"prompt": data}
        return {"raw": data}
    except json.JSONDecodeError:
        # Not JSON - treat the whole blob as a natural-language prompt.
        return {"prompt": text}


# --------------------------------------------------------------------------- #
#  Routes - health & status
# --------------------------------------------------------------------------- #
@app.get("/")
async def root():
    """Serve the dashboard.

    Priority:
      1. external frontend/index.html  (if the folder was located)
      2. embedded DASHBOARD_HTML       (self-contained fallback - ALWAYS works)
    """
    if FRONTEND_DIR is not None:
        index = FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
    # Embedded fallback - a complete dashboard, not a bare text message.
    return PlainTextResponse(DASHBOARD_HTML, media_type="text/html")


@app.get("/api/paths")
async def paths():
    """Diagnostic: show where the frontend was searched for / found."""
    return {
        "ok": True,
        "embedded": EMBEDDED_MODE,
        "frontend_dir": str(FRONTEND_DIR) if FRONTEND_DIR else None,
        "searched": FRONTEND_SEARCHED,
        "hint": ("Set env FRONTEND_DIR=<path> or place the frontend/ folder "
                 "next to backend/ to use the full external UI."),
    }


@app.get("/api/status")
async def status():
    """Report backend + MCP daemon + FL Studio reachability."""
    mcp_ok = bridge.is_reachable()
    fl_ok = False
    tools: List[str] = []
    if mcp_ok:
        try:
            tools = await bridge.list_tools()
            fl_ok = True
        except MCPConnectionError as exc:
            log.warning("MCP reachable but tools/list failed: %s", exc)
    return {
        "ok": True,
        "server": "running",
        "version": "1.2.0",
        "time": datetime.now().isoformat(timespec="seconds"),
        "mcp": {
            "host": MCP_HOST,
            "port": MCP_PORT,
            "reachable": mcp_ok,
        },
        "fl_studio": {"connected": fl_ok},
        "tools": tools,
    }


@app.get("/api/tools")
async def list_tools():
    try:
        tools = await bridge.list_tools()
        return {"ok": True, "tools": tools}
    except MCPConnectionError as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": str(exc)},
        )


# --------------------------------------------------------------------------- #
#  Routes - prompt ingestion (the heart of the app)
# --------------------------------------------------------------------------- #
@app.post("/api/prompt")
async def receive_prompt(request: Request):
    """
    Accept a natural-language prompt from the dashboard.

    Body MAY be JSON:  {"prompt": "...", "context": {...}}
    Or plain text:     "buat beat hip-hop 90 bpm"
    Or malformed:      we still extract whatever we can, never 500 on syntax.
    """
    text = await _read_body_safe(request)
    if not text:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Empty request body"},
        )

    payload = _safe_json(text)
    prompt = (payload.get("prompt")
              or payload.get("text")
              or payload.get("q")
              or "").strip()
    ctx = payload.get("context") or {}

    if not prompt:
        return JSONResponse(
            status_code=400,
            content={"ok": False,
                     "error": "No 'prompt' field found in payload"},
        )

    log.info("PROMPT >> %s", prompt)
    emit("prompt.received", {"prompt": prompt, "context": ctx})

    try:
        plan = engine.plan(prompt, context=ctx)
        emit("plan.ready", {"plan": plan})

        results = await engine.execute(plan)
        emit("plan.done", {"results": results})

        return {
            "ok": True,
            "prompt": prompt,
            "plan": plan,
            "results": results,
        }
    except MCPConnectionError as exc:
        log.error("MCP connection error: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"ok": False,
                     "error": f"MCP daemon not reachable: {exc}",
                     "hint": "Start the MCP daemon (9787) and FL Studio."},
        )
    except Exception as exc:
        log.exception("Unexpected error while handling prompt")
        return JSONResponse(
            status_code=500,
            content={"ok": False,
                     "error": str(exc),
                     "trace": traceback.format_exc(limit=3)},
        )


@app.post("/api/command")
async def direct_command(request: Request):
    """Send a single MCP tool-call directly: {"tool":"set_bpm","args":{"bpm":90}}."""
    text = await _read_body_safe(request)
    payload = _safe_json(text)
    tool = payload.get("tool") or payload.get("command")
    args = payload.get("args") or payload.get("params") or {}
    if not tool:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Missing 'tool' field"},
        )
    try:
        result = await bridge.call_tool(tool, args)
        return {"ok": True, "tool": tool, "args": args, "result": result}
    except MCPConnectionError as exc:
        return JSONResponse(status_code=503,
                            content={"ok": False, "error": str(exc)})


# --------------------------------------------------------------------------- #
#  WebSocket - live stream
# --------------------------------------------------------------------------- #
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    emit("ws.connected", {"clients": len(manager.active)})
    try:
        while True:
            data = await ws.receive_text()
            # Allow the client to push prompts over WS too.
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"prompt": data}
            prompt = (msg.get("prompt") or msg.get("text") or "").strip()
            if prompt:
                log.info("WS PROMPT >> %s", prompt)
                emit("prompt.received", {"prompt": prompt, "via": "ws"})
                plan = engine.plan(prompt, context=msg.get("context") or {})
                emit("plan.ready", {"plan": plan})
                results = await engine.execute(plan)
                emit("plan.done", {"results": results})
    except WebSocketDisconnect:
        manager.disconnect(ws)
        emit("ws.disconnected", {"clients": len(manager.active)})
    except Exception as exc:
        log.exception("WS error")
        manager.disconnect(ws)


# --------------------------------------------------------------------------- #
#  Static frontend
# --------------------------------------------------------------------------- #
if FRONTEND_DIR is not None and FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# --------------------------------------------------------------------------- #
#  Startup / shutdown
# --------------------------------------------------------------------------- #
@app.on_event("startup")
async def _startup():
    log.info("OMBAR FL-AI Studio backend starting on :%d (v1.5.0)", SERVER_PORT)
    log.info("MCP target => %s:%d", MCP_HOST, MCP_PORT)
    reachable = bridge.is_reachable()
    log.info("MCP daemon reachable: %s", reachable)
    if not reachable:
        log.warning("MCP daemon offline - backend still boots. "
                    "Start it with launchers/start_mcp_daemon.bat")
    else:
        # PRE-WARM: establish + initialize the TCP connection and fetch the
        # tool list NOW, so the first user prompt doesn't pay the handshake
        # cost (~500ms). The pipelined reader loop also starts here.
        try:
            tools = await bridge.list_tools()
            log.info("MCP connection pre-warmed: %d tools ready (instant mode)",
                     len(tools))
            emit("mcp.prewarmed", {"tools": len(tools)})
        except MCPConnectionError as exc:
            log.warning("Pre-warm failed (will retry on first prompt): %s", exc)
    emit("server.start", {"mcp_reachable": reachable, "prewarmed": reachable})


@app.on_event("shutdown")
async def _shutdown():
    log.info("Backend shutting down.")
    bridge.close()


# --------------------------------------------------------------------------- #
#  Entry point  (python server.py)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",          # bind all interfaces (LAN + tunnel reach)
        port=SERVER_PORT,
        reload=False,
        log_level="info",
        access_log=True,
    )
