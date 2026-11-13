"""
================================================================================
 OMBAR FL-AI Studio  -  MCP Bridge  (TCP client for 127.0.0.1:9787)
================================================================================
This module is a thin async client that speaks line-delimited JSON-RPC 2.0
with the FL Studio MCP daemon (the flstudio-mcp project running on TCP 9787).

Protocol (one JSON object per line, terminated by "\n"):

  ->  {"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":
       {"name":"ombar-flai","version":"1.2.0"}}}
  <-  {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",
       "capabilities":{"tools":{}},"serverInfo":{"name":"flstudio-mcp",...}}}

  ->  {"jsonrpc":"2.0","id":2,"method":"tools/list"}
  <-  {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"set_bpm",...}]}}

  ->  {"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"set_bpm","arguments":{"bpm":90}}}
  <-  {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text",
       "text":"BPM set to 90"}]}}

If the upstream MCP daemon uses a different framing (raw JSON without
newlines, or a single-line protocol), set FRAMING = "raw" to read until the
first balanced "}" instead of until "\n".
================================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("ombar.mcp")

FRAMING = "newline"          # "newline" or "raw"
READ_TIMEOUT = 8.0           # seconds for a single request/response
CONNECT_TIMEOUT = 2.0        # seconds to establish the TCP connection
CLIENT_INFO = {"name": "ombar-flai", "version": "1.2.0"}
PROTOCOL_VERSION = "2024-11-05"


class MCPConnectionError(RuntimeError):
    """Raised when the MCP daemon cannot be reached or responds badly."""


class MCPBridge:
    """Async, reusable JSON-RPC client for the FL Studio MCP daemon."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9787) -> None:
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._id = 0
        self._initialized = False
        self._tools_cache: Optional[List[str]] = None
        self._lock = asyncio.Lock()
        self._emit: Optional[Callable[[str, Dict[str, Any]], None]] = None

    # -- emitter hook (so server.py can stream events to the browser) -------- #
    def set_emitter(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        self._emit = fn

    def _emit_event(self, event: str, payload: Dict[str, Any]) -> None:
        if self._emit:
            try:
                self._emit(event, payload)
            except Exception:
                pass

    # -- reachability -------------------------------------------------------- #
    def is_reachable(self) -> bool:
        """Synchronous TCP probe - used by /api/status without blocking."""
        try:
            with socket.create_connection(
                (self.host, self.port), timeout=CONNECT_TIMEOUT
            ):
                return True
        except OSError:
            return False

    # -- low level connect --------------------------------------------------- #
    async def _connect(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise MCPConnectionError(
                f"Cannot connect to MCP daemon at {self.host}:{self.port} "
                f"({exc.__class__.__name__}). Is FL Studio + the MCP daemon "
                f"running?"
            ) from exc
        await self._initialize()

    async def _initialize(self) -> None:
        """Perform the MCP initialize handshake once per connection."""
        if self._initialized:
            return
        resp = await self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        })
        server_info = resp.get("result", {}).get("serverInfo", {})
        log.info("MCP initialized: server=%s v%s",
                 server_info.get("name", "?"),
                 server_info.get("version", "?"))
        # Optional notification (no response expected)
        await self._notify("notifications/initialized", {})
        self._initialized = True
        self._emit_event("mcp.connected", {"server": server_info})

    async def _close(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._initialized = False

    def close(self) -> None:
        """Sync close used at app shutdown."""
        if self._writer is None:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._close())
            else:
                loop.run_until_complete(self._close())
        except Exception:
            pass

    # -- framing ------------------------------------------------------------- #
    async def _send(self, obj: Dict[str, Any]) -> None:
        assert self._writer is not None
        data = json.dumps(obj, ensure_ascii=False) + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()

    async def _recv(self) -> Dict[str, Any]:
        assert self._reader is not None
        if FRAMING == "newline":
            line = await asyncio.wait_for(self._reader.readline(), READ_TIMEOUT)
            if not line:
                raise MCPConnectionError("MCP daemon closed the connection.")
            text = line.decode("utf-8", errors="ignore").strip()
        else:
            # raw framing: read until a balanced JSON object
            buf = ""
            depth = 0
            while True:
                ch = (await asyncio.wait_for(
                    self._reader.read(1), READ_TIMEOUT)).decode("utf-8",
                                                                 errors="ignore")
                if not ch:
                    raise MCPConnectionError("MCP daemon closed early.")
                buf += ch
                depth += ch.count("{") - ch.count("}")
                if depth <= 0 and "{" in buf:
                    break
            text = buf.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPConnectionError(f"Bad JSON from MCP: {exc}") from exc

    async def _request(self, method: str,
                       params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with self._lock:
            await self._connect()
            self._id += 1
            req_id = self._id
            payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
            if params is not None:
                payload["params"] = params
            self._emit_event("mcp.request", {"method": method, "params": params})
            try:
                await self._send(payload)
                resp = await self._recv()
            except MCPConnectionError:
                # retry once on a broken socket
                await self._close()
                await self._connect()
                await self._send(payload)
                resp = await self._recv()
            self._emit_event("mcp.response", {"method": method, "resp": resp})
            if "error" in resp:
                err = resp["error"]
                raise MCPConnectionError(
                    f"MCP error {err.get('code')}: {err.get('message')}"
                )
            return resp

    async def _notify(self, method: str,
                      params: Optional[Dict[str, Any]] = None) -> None:
        async with self._lock:
            await self._connect()
            payload = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                payload["params"] = params
            await self._send(payload)

    # -- public API ---------------------------------------------------------- #
    async def list_tools(self) -> List[str]:
        if self._tools_cache is not None:
            return self._tools_cache
        resp = await self._request("tools/list")
        tools = resp.get("result", {}).get("tools", []) or []
        names = [t.get("name", "") for t in tools if isinstance(t, dict)]
        self._tools_cache = names
        self._emit_event("mcp.tools", {"count": len(names), "names": names})
        return names

    async def call_tool(self, name: str,
                        arguments: Optional[Dict[str, Any]] = None
                        ) -> Dict[str, Any]:
        resp = await self._request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        result = resp.get("result", {})
        # Normalise the MCP content array into a friendlier shape.
        content = result.get("content", [])
        if isinstance(content, list) and content:
            texts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
            if texts:
                result["text"] = "\n".join(texts)
        return result

    async def call_tool_safe(self, name: str,
                             arguments: Optional[Dict[str, Any]] = None
                             ) -> Dict[str, Any]:
        """call_tool but never raises - returns an error dict instead."""
        try:
            return await self.call_tool(name, arguments)
        except MCPConnectionError as exc:
            return {"ok": False, "error": str(exc)}
