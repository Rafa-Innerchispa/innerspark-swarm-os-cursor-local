#!/usr/bin/env python3
"""Gateway :5188 — una URL ngrok pública; enruta InnerOS + Hackathon + API."""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urljoin

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

INNEROS = os.getenv("GATEWAY_INNEROS", "http://127.0.0.1:5173").rstrip("/")
HACKATHON = os.getenv("GATEWAY_HACKATHON", "http://127.0.0.1:5190").rstrip("/")
SWARM_API = os.getenv("GATEWAY_SWARM_API", "http://127.0.0.1:8100").rstrip("/")
PORT = int(os.getenv("PUBLIC_GATEWAY_PORT", "5188"))

app = FastAPI(title="Public Gateway", docs_url=None, redoc_url=None)
_client: httpx.AsyncClient | None = None


def _http_target(path: str) -> str:
    if path.startswith("/inneros") or path.startswith("/datacenter"):
        return INNEROS
    if path.startswith("/api/v1"):
        return SWARM_API
    if path.startswith("/api/"):
        return os.getenv("GATEWAY_HACKATHON_API", "http://127.0.0.1:8200").rstrip("/")
    return HACKATHON


def _ws_target(path: str) -> str:
    base = HACKATHON.replace("http://", "ws://").replace("https://", "wss://")
    return urljoin(base + "/", path.lstrip("/"))


@app.on_event("startup")
async def _startup() -> None:
    global _client
    _client = httpx.AsyncClient(follow_redirects=False, timeout=120.0)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _client:
        await _client.aclose()


@app.websocket("/ws/{rest:path}")
async def ws_proxy(websocket: WebSocket, rest: str) -> None:
    path = f"/ws/{rest}" if rest else "/ws"
    upstream_url = _ws_target(path)
    await websocket.accept()
    try:
        async with websockets.connect(upstream_url) as upstream:
            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if "text" in msg:
                            await upstream.send(msg["text"])
                        elif "bytes" in msg:
                            await upstream.send(msg["bytes"])
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception:
        await websocket.close()


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def http_proxy(full_path: str, request: Request) -> Response:
    assert _client is not None
    path = "/" + full_path if full_path else "/"
    upstream = _http_target(path)
    url = urljoin(upstream + "/", path.lstrip("/"))
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    body = await request.body()

    try:
        upstream_resp = await _client.request(request.method, url, headers=headers, content=body)
    except httpx.RequestError as exc:
        return Response(content=f"Gateway upstream error: {exc}", status_code=502)

    skip = {"transfer-encoding", "connection", "content-encoding"}
    out_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in skip}
    if request.method == "HEAD":
        return Response(status_code=upstream_resp.status_code, headers=out_headers)

    return StreamingResponse(
        upstream_resp.aiter_bytes(),
        status_code=upstream_resp.status_code,
        headers=out_headers,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
