from __future__ import annotations

import os
from typing import AsyncIterator

import httpx
import pymongo
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse

app = FastAPI(title="Ralphi IA File Browser SSO Gateway")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
MONGO_DB = os.getenv("PORTAL_AUTH_DB", "hackathon_autopilot")
BACKEND = os.getenv("FILEBROWSER_BACKEND", "http://127.0.0.1:18081").rstrip("/")
LOGIN_URL = os.getenv("PORTAL_LOGIN_URL", "http://192.168.1.4:2002/login")
AUTH_HEADER = os.getenv("FILEBROWSER_AUTH_HEADER", "X-Remote-User")

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def _username_for_session(token: str | None) -> str | None:
    if not token:
        return None
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
    try:
        row = client[MONGO_DB].sessions.find_one({"session_token": token}, {"username": 1})
        username = str((row or {}).get("username") or "").strip()
        return username or None
    finally:
        client.close()


@app.get("/_sso/health")
async def health(request: Request):
    username = _username_for_session(request.cookies.get("session_token"))
    return {"ok": True, "authenticated": bool(username), "username": username}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "PROPFIND"],
)
async def proxy(path: str, request: Request):
    username = _username_for_session(request.cookies.get("session_token"))
    if not username:
        return RedirectResponse(LOGIN_URL, status_code=303)

    query = request.url.query
    target = f"{BACKEND}/{path}"
    if query:
        target = f"{target}?{query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP | {"host", "content-length", "cookie"}
    }
    headers[AUTH_HEADER] = username
    headers["X-Forwarded-Host"] = request.headers.get("host", "192.168.1.4:8081")
    headers["X-Forwarded-Proto"] = request.url.scheme

    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    upstream_request = client.build_request(
        request.method,
        target,
        headers=headers,
        content=request.stream(),
    )
    upstream = await client.send(upstream_request, stream=True)

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP
    }

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        body(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=None,
    )
