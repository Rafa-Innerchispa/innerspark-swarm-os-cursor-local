import os
import json
import uuid
import hashlib
import logging
import re
import shutil
import socket
import sys
from datetime import datetime, timezone
from fastapi import FastAPI, Form, Cookie, Depends, HTTPException, status, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import pymongo
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

RAPHIIA_ROOT = os.environ.get("RAPHIIA_ROOT", "/home/rlopez/projects/raphiia-openai")
if RAPHIIA_ROOT not in sys.path:
    sys.path.insert(0, RAPHIIA_ROOT)

from raphiia_openai import portal_bridge  # noqa: E402
from raphiia_openai import settings as _portal_settings  # noqa: E402
if not hasattr(_portal_settings, "PORTAL_LEGACY_URL"):
    _portal_settings.PORTAL_LEGACY_URL = "http://192.168.1.4:8800"
try:
    from raphiia_openai.ops_routes import router as ops_router  # noqa: E402
except ImportError as exc:
    logging.warning("ops_routes unavailable in portal candidate: %s", exc)
    ops_router = None
from inneros_core_runtime import oauth_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Ralphi IA Control Center")
if ops_router is not None:
    app.include_router(ops_router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.join(BASE_DIR, "portal")
SERVICES_JSON = os.path.join(PORTAL_DIR, "services.json")
SERVICES_BACKUP_DIR = os.path.join(PORTAL_DIR, "backups")

ACTIVE_SESSIONS = {}
OAUTH_FLOWS = {}
PORTAL_OAUTH_CLIENT_ID = os.environ.get("PORTAL_OAUTH_CLIENT_ID", "ralfia_portal_control_center")
PORTAL_OAUTH_REDIRECT_URI = os.environ.get("PORTAL_OAUTH_REDIRECT_URI", "http://192.168.1.4:2002/auth/oauth/callback")
OAUTH_ISSUER = os.environ.get("RALFIA_OAUTH_ISSUER", "https://auth.pcdoctor.ai").rstrip("/")

def get_db():
    try:
        # Use hackathon_autopilot to share the users collection
        client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        return client["hackathon_autopilot"]
    except Exception as e:
        logging.error(f"Error connecting to MongoDB: {e}")
        return None

async def get_current_user(session_token: str = Cookie(None)):
    if not session_token:
        return None
    db = get_db()
    if db is not None:
        try:
            sess = db.sessions.find_one({"session_token": session_token})
            if sess:
                return sess["username"]
        except Exception as e:
            logging.error(f"Error verifying session: {e}")
    return None

def get_user_record(username: str | None):
    if not username:
        return None
    db = get_db()
    if db is not None:
        try:
            return db.users.find_one({"username": username}, {"password_hash": 0})
        except Exception as e:
            logging.error(f"Error querying user record: {e}")
    return None

def is_admin_user(username: str | None) -> bool:
    user = get_user_record(username)
    role = (user or {}).get("role", "")
    return username in {"admin", "rlopez"} or role == "admin"


def authenticate_central_user(username: str, password: str):
    db = get_db()
    if db is None:
        return None
    user = db.users.find_one({"username": username})
    if not user or user.get("oauth_enabled") is False:
        return None
    if not oauth_store.verify_and_upgrade_password(user, password, db):
        return None
    return user


def owner_account_hints():
    db = get_db()
    if db is None:
        return []
    return list(db.users.find(
        {"oauth_enabled": True, "role": "admin"},
        {"username": 1, "display_name": 1, "google_email": 1, "_id": 0},
    ))

def load_services_config():
    if os.path.exists(SERVICES_JSON):
        with open(SERVICES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"featured": [], "services": []}

def save_services_config(config: dict):
    os.makedirs(SERVICES_BACKUP_DIR, exist_ok=True)
    if os.path.exists(SERVICES_JSON):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        shutil.copy2(SERVICES_JSON, os.path.join(SERVICES_BACKUP_DIR, f"services.{stamp}.json"))
    tmp_path = f"{SERVICES_JSON}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, SERVICES_JSON)

def port_is_open(host: str, port: int, timeout: float = 0.45) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False

def service_items(config: dict):
    for item in config.get("featured", []):
        yield item
    for item in config.get("services", []):
        yield item

def safe_service_payload(payload: dict) -> dict:
    service_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(payload.get("id", "")).strip().lower()).strip("-")
    if not service_id:
        raise HTTPException(status_code=400, detail="ID invalido")
    name = str(payload.get("name", "")).strip()
    desc = str(payload.get("desc", "")).strip()
    section = str(payload.get("section", "")).strip() or "Servicios"
    if not name or not desc:
        raise HTTPException(status_code=400, detail="Nombre y descripcion son obligatorios")
    try:
        port = int(payload.get("port"))
    except Exception:
        raise HTTPException(status_code=400, detail="Puerto invalido")
    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="Puerto fuera de rango")
    company = str(payload.get("company", "both")).strip()
    if company not in {"both", "pcdoctor", "innerchispa"}:
        company = "both"
    path = str(payload.get("path", "")).strip()
    if path and not path.startswith("/"):
        path = f"/{path}"
    item = {
        "id": service_id,
        "section": section,
        "company": company,
        "name": name,
        "desc": desc,
        "port": port,
        "path": path,
        "icon": str(payload.get("icon", "▣")).strip() or "▣",
    }
    if payload.get("web") is False:
        item["web"] = False
    public_url = str(payload.get("public_url", "") or payload.get("publicUrl", "")).strip()
    if public_url:
        item["public_url"] = public_url
    return item

@app.get("/projects")
async def projects_redirect(user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/#project-panel")

@app.get("/", response_class=HTMLResponse)
async def get_portal(user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    index_path = os.path.join(PORTAL_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Inject username
            content = content.replace("<h1>Ralphi IA v2.0</h1>", f"<h1>Ralphi IA v2.0 <span style='font-size:1rem;font-weight:normal;color:#8b5cf6;'>(Usuario: {user})</span></h1>")
            response = HTMLResponse(content=content)
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(user: str = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/")
    hints = owner_account_hints()
    hint_text = " · ".join(
        f"{item.get('display_name') or item.get('username')} ({item.get('username')})"
        for item in hints if item.get("username")
    ) or "Cuenta InnerOS habilitada para OAuth"
    login_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Iniciar Sesión — Ralphi IA</title>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
      <style>
        :root {{--bg:#05070a;--surface:rgba(255,255,255,.03);--border:rgba(255,255,255,.08);--accent:#5bd8ff;--text:#f1f5f9;--muted:#94a3b8}}
        *{{box-sizing:border-box;margin:0;padding:0}} body{{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;position:relative;overflow:hidden}}
        body::before{{content:"";position:absolute;width:420px;height:420px;background:radial-gradient(circle,rgba(91,216,255,.22),transparent 70%);top:5%;left:15%;filter:blur(50px)}}
        body::after{{content:"";position:absolute;width:380px;height:380px;background:radial-gradient(circle,rgba(139,92,246,.18),transparent 70%);bottom:5%;right:10%;filter:blur(50px)}}
        .splash{{text-align:center;margin-bottom:1.75rem;position:relative;z-index:10}} .splash h1{{font-size:2.4rem;font-weight:800;background:linear-gradient(92deg,#5bd8ff,#78a8ff,#c4a5ff);-webkit-background-clip:text;background-clip:text;color:transparent}}
        .splash .tag{{color:#5bd8ff;font-size:1.05rem;margin-top:.35rem;font-weight:600}} .splash .ver{{display:inline-block;margin-top:.65rem;font-size:.72rem;font-weight:700;letter-spacing:.12em;padding:5px 12px;border-radius:999px;border:1px solid rgba(91,216,255,.35);color:#5bd8ff;background:rgba(91,216,255,.08)}}
        .container{{background:var(--surface);border:1px solid var(--border);padding:2.5rem;border-radius:20px;width:100%;max-width:420px;backdrop-filter:blur(20px);box-shadow:0 10px 40px rgba(0,0,0,.5);position:relative;z-index:10}}
        h2{{font-size:1.8rem;margin-bottom:.5rem;text-align:center}} .subtitle{{color:var(--muted);text-align:center;font-size:.88rem;margin-bottom:1.2rem}}
        .hint{{margin-bottom:1.15rem;padding:.75rem .85rem;border:1px solid rgba(91,216,255,.18);border-radius:10px;background:rgba(91,216,255,.05);color:var(--muted);font-size:.79rem;line-height:1.45}} .hint strong{{color:var(--accent)}}
        .oauth-btn{{display:flex;align-items:center;justify-content:center;width:100%;padding:.9rem;border-radius:10px;background:#f8fbff;color:#051018;text-decoration:none;font-weight:800;margin-bottom:1rem}}
        .divider{{display:flex;align-items:center;gap:.7rem;color:#64748b;font-size:.72rem;margin:1rem 0}} .divider::before,.divider::after{{content:"";height:1px;background:var(--border);flex:1}}
        .form-group{{margin-bottom:1.1rem}} label{{font-size:.82rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;display:block;margin-bottom:.4rem}}
        input{{width:100%;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:10px;padding:.8rem 1rem;color:#fff;font-size:.95rem;outline:none}} input:focus{{border-color:var(--accent)}}
        .password-wrap{{position:relative}} .password-wrap input{{padding-right:3rem}} .eye{{position:absolute;right:.5rem;top:50%;transform:translateY(-50%);width:auto;background:transparent;color:var(--muted);box-shadow:none;border:none;margin:0;padding:.45rem .6rem;font-size:1rem}}
        button{{width:100%;background:linear-gradient(135deg,#24617f,#5bd8ff);color:#041018;border:none;padding:.9rem;border-radius:10px;font-weight:700;font-size:1rem;cursor:pointer;margin-top:.4rem}}
        .links{{display:flex;justify-content:space-between;gap:1rem;margin-top:1rem;font-size:.8rem}} .links a{{color:var(--accent);text-decoration:none}} .hidden{{display:none!important}}
        .recovery{{margin-top:1.2rem;padding-top:1.2rem;border-top:1px solid var(--border)}} .note{{color:var(--muted);font-size:.74rem;line-height:1.45;margin-top:.85rem}}
      </style>
    </head>
    <body>
      <div class="splash"><h1>Ralphi IA</h1><p class="tag">your second brain</p><span class="ver">VERSION 2.0</span></div>
      <div class="container">
        <h2>Iniciar sesión</h2><p class="subtitle">Control Center · acceso unificado de InnerOS</p>
        <div class="hint"><strong>Cuenta central detectada:</strong><br>{hint_text}</div>
        <a class="oauth-btn" href="/auth/oauth/start">Continuar con InnerOS OAuth</a>
        <div class="divider">o usar credenciales centrales</div>
        <form action="/api/auth/login" method="POST">
          <div class="form-group"><label for="user">Usuario InnerOS</label><input type="text" id="user" name="username" autocomplete="username" required placeholder="Ej. rafagye"></div>
          <div class="form-group"><label for="pass">Contraseña</label><div class="password-wrap"><input type="password" id="pass" name="password" autocomplete="current-password" required placeholder="Ingresa tu contraseña"><button class="eye" type="button" onclick="togglePassword('pass',this)" aria-label="Mostrar contraseña">👁</button></div></div>
          <button type="submit">Entrar al Ecosistema</button>
        </form>
        <div class="links"><a href="#" onclick="toggleRecovery(true);return false;">Olvidé mi contraseña</a><a href="#" onclick="showAccountHelp();return false;">¿Qué usuario uso?</a></div>
        <div id="recovery" class="recovery hidden">
          <p class="subtitle">Restablecer contraseña central</p>
          <form action="/api/auth/reset-password" method="POST">
            <div class="form-group"><label for="reset-user">Usuario</label><input type="text" id="reset-user" name="username" autocomplete="username" required placeholder="Ej. rafagye"></div>
            <div class="form-group"><label for="reset-email">Correo asociado</label><input type="email" id="reset-email" name="recovery_email" autocomplete="email" required></div>
            <div class="form-group"><label for="reset-pass">Nueva contraseña</label><div class="password-wrap"><input type="password" id="reset-pass" name="new_password" minlength="12" autocomplete="new-password" required placeholder="Mínimo 12 caracteres"><button class="eye" type="button" onclick="togglePassword('reset-pass',this)">👁</button></div></div>
            <button type="submit">Restablecer contraseña</button>
          </form>
          <p class="note">El restablecimiento solo funciona desde la red local y exige que el correo coincida con la cuenta central.</p>
        </div>
      </div>
      <script>
        function togglePassword(id,btn){{const i=document.getElementById(id);const show=i.type==='password';i.type=show?'text':'password';btn.textContent=show?'🙈':'👁'}}
        function toggleRecovery(show){{document.getElementById('recovery').classList.toggle('hidden',!show)}}
        function showAccountHelp(){{alert('Usa tu usuario central de InnerOS. Cuenta administradora detectada: {hint_text}')}}
      </script>
    </body></html>
    """
    return HTMLResponse(content=login_html)

@app.get("/auth/oauth/start")
async def oauth_start():
    import base64, secrets
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    OAUTH_FLOWS[state] = {"verifier": verifier}
    params = {"response_type":"code","client_id":PORTAL_OAUTH_CLIENT_ID,"redirect_uri":PORTAL_OAUTH_REDIRECT_URI,"scope":"openid profile email ralfia:read","state":state,"code_challenge":challenge,"code_challenge_method":"S256"}
    return RedirectResponse(url=f"{OAUTH_ISSUER}/authorize?{urlencode(params)}")

@app.get("/auth/oauth/callback")
async def oauth_callback(code: str, state: str):
    flow = OAUTH_FLOWS.pop(state, None)
    if not flow:
        return HTMLResponse("<h3>Flujo OAuth inválido o vencido. <a href='/login'>Volver</a></h3>", status_code=400)
    token_data = urlencode({"grant_type":"authorization_code","code":code,"client_id":PORTAL_OAUTH_CLIENT_ID,"redirect_uri":PORTAL_OAUTH_REDIRECT_URI,"code_verifier":flow["verifier"]}).encode()
    token_req = UrlRequest(f"{OAUTH_ISSUER}/token", data=token_data, headers={"Content-Type":"application/x-www-form-urlencoded"}, method="POST")
    with urlopen(token_req, timeout=10) as response:
        token_payload = json.loads(response.read().decode())
    access_token = token_payload.get("access_token", "")
    user_req = UrlRequest(f"{OAUTH_ISSUER}/userinfo", headers={"Authorization":f"Bearer {access_token}"})
    with urlopen(user_req, timeout=10) as response:
        profile = json.loads(response.read().decode())
    username = profile.get("preferred_username") or profile.get("email")
    if not username:
        return HTMLResponse("<h3>OAuth no devolvió usuario válido. <a href='/login'>Volver</a></h3>", status_code=401)
    db = get_db()
    session_token = str(uuid.uuid4())
    db.sessions.update_one({"username":username},{"$set":{"session_token":session_token}},upsert=True)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_token", value=session_token, httponly=True, samesite="lax")
    return response

@app.post("/api/auth/login")
async def login(username: str = Form(...), password: str = Form(...)):
    db = get_db()
    if db is not None:
        try:
            user = authenticate_central_user(username, password)
            if user:
                session_token = str(uuid.uuid4())
                db.sessions.update_one(
                    {"username": username},
                    {"$set": {"session_token": session_token}},
                    upsert=True
                )
                response = RedirectResponse(url="/", status_code=303)
                response.set_cookie(key="session_token", value=session_token, httponly=True)
                return response
            else:
                return HTMLResponse(content="<h3>Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a></h3>", status_code=401)
        except Exception as e:
            return HTMLResponse(content=f"<h3>Error: {e}</h3>", status_code=500)
    return HTMLResponse(content="<h3>Sin conexión a DB.</h3>", status_code=500)

@app.post("/api/auth/reset-password")
async def reset_password(request: Request, username: str = Form(...), recovery_email: str = Form(...), new_password: str = Form(...)):
    client_host = request.client.host if request.client else ""
    if not (client_host.startswith("192.168.") or client_host in {"127.0.0.1", "::1"}):
        raise HTTPException(status_code=403, detail="Password reset is LAN-only")
    if len(new_password) < 12:
        return HTMLResponse("<h3>La nueva contraseña debe tener al menos 12 caracteres. <a href='/login'>Volver</a></h3>", status_code=400)
    db = get_db()
    if db is None:
        return HTMLResponse("<h3>Sin conexión a DB.</h3>", status_code=500)
    user = db.users.find_one({"username": username})
    expected_email = str((user or {}).get("google_email") or "").strip().lower()
    if not user or not expected_email or expected_email != recovery_email.strip().lower():
        return HTMLResponse("<h3>No se pudo validar el usuario y correo. <a href='/login'>Volver</a></h3>", status_code=400)
    db.users.update_one({"_id":user["_id"]},{"$set":{"password_hash":oauth_store.hash_password(new_password),"password_upgraded_at":datetime.now(timezone.utc).isoformat()}})
    db.sessions.delete_many({"username":username})
    return HTMLResponse("<h3>Contraseña restablecida. <a href='/login'>Iniciar sesión</a></h3>")

@app.post("/api/auth/register")
async def register(username: str = Form(...), password: str = Form(...)):
    db = get_db()
    if db is not None:
        try:
            existing = db.users.find_one({"username": username})
            if existing:
                return HTMLResponse(content="<h3>El usuario ya existe. <a href='/login'>Intentar de nuevo</a></h3>", status_code=400)
            
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            new_user = {
                "username": username,
                "password_hash": password_hash,
                "role": "user"
            }
            db.users.insert_one(new_user)
            
            session_token = str(uuid.uuid4())
            db.sessions.update_one(
                {"username": username},
                {"$set": {"session_token": session_token}},
                upsert=True
            )
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(key="session_token", value=session_token, httponly=True)
            return response
        except Exception as e:
            return HTMLResponse(content=f"<h3>Error: {e}</h3>", status_code=500)
    return HTMLResponse(content="<h3>Sin conexión a DB.</h3>", status_code=500)

@app.post("/api/auth/logout")
async def logout(session_token: str = Cookie(None)):
    db = get_db()
    if db is not None and session_token:
        try:
            db.sessions.delete_one({"session_token": session_token})
        except Exception as e:
            logging.error(f"Error deleting session: {e}")
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_token")
    return response

@app.get("/services.json")
async def get_services(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    response = JSONResponse(content=load_services_config())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.get("/api/portal/overview")
async def portal_overview(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    record = get_user_record(user) or {"username": user}
    config = load_services_config()
    mongo_summary = {"ok": False, "counts": {}}
    latest_ideas = []
    latest_pipeline = []
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1200)
        db = client["pcdoctor_swarm"]
        collections = [
            "clients",
            "ideas",
            "editorial_pipeline",
            "raphiia_openai_conversations",
            "raphiia_openai_messages",
            "chat_messages",
        ]
        mongo_summary = {
            "ok": True,
            "db": "pcdoctor_swarm",
            "counts": {name: db[name].count_documents({}) for name in collections},
        }
        latest_ideas = [
            {
                "_id": str(doc.get("_id")),
                "title": doc.get("title", ""),
                "status": doc.get("status", ""),
                "created_at": doc.get("created_at", ""),
                "tags": doc.get("tags", []),
                "body": (doc.get("body") or doc.get("content") or "")[:240],
            }
            for doc in db["ideas"].find({}, {"title": 1, "status": 1, "created_at": 1, "tags": 1, "body": 1, "content": 1})
            .sort("created_at", -1)
            .limit(6)
        ]
        latest_pipeline = [
            {
                "_id": str(doc.get("_id")),
                "title": doc.get("title", ""),
                "status": doc.get("status", ""),
                "channel": doc.get("channel", ""),
                "created_at": doc.get("created_at", ""),
                "markdown": (doc.get("markdown") or doc.get("body") or "")[:240],
            }
            for doc in db["editorial_pipeline"].find({}, {"title": 1, "status": 1, "channel": 1, "created_at": 1, "markdown": 1, "body": 1})
            .sort("created_at", -1)
            .limit(6)
        ]
    except Exception as e:
        mongo_summary = {"ok": False, "error": str(e), "counts": {}}
    content = {
        "portal_ok": True,
        "user": {
            "username": user,
            "role": record.get("role", "user"),
            "is_admin": is_admin_user(user),
        },
        "service_count": len(list(service_items(config))),
        "mcp_hint": "127.0.0.1:8102/mcp",
        "mongo": mongo_summary,
        "latest_ideas": latest_ideas,
        "latest_pipeline": latest_pipeline,
    }
    content = portal_bridge.enrich_portal_overview(content)
    response = JSONResponse(content=content)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.get("/api/services/status")
async def services_status(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    config = load_services_config()
    enriched = portal_bridge.services_health_enriched(config)
    response = JSONResponse(content=enriched)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.post("/api/services")
async def add_service(payload: dict = Body(...), user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Solo admin puede registrar servicios")
    item = safe_service_payload(payload)
    target = "featured" if payload.get("target") == "featured" else "services"
    config = load_services_config()
    config.setdefault("featured", [])
    config.setdefault("services", [])
    existing_ids = {entry.get("id") for entry in service_items(config)}
    if item["id"] in existing_ids:
        raise HTTPException(status_code=409, detail="Ya existe un servicio con ese ID")
    config[target].append(item)
    save_services_config(config)
    return JSONResponse(content={"ok": True, "service": item, "target": target})

@app.get("/assets/{filename}")
async def get_assets(filename: str):
    from fastapi.responses import FileResponse
    asset_path = os.path.join(PORTAL_DIR, "assets", filename)
    if os.path.exists(asset_path):
        return FileResponse(asset_path)
    return HTMLResponse(content="Not Found", status_code=404)

@app.get("/api/users")
async def get_users_list(user: str = Depends(get_current_user)):
    if not user:
         raise HTTPException(status_code=401, detail="No autorizado")
    db = get_db()
    usernames = []
    if db is not None:
        try:
            users = db.users.find({}, {"username": 1, "_id": 0})
            usernames = [u["username"] for u in users]
        except Exception as e:
            logging.error(f"Error querying users: {e}")
    return JSONResponse(content=usernames)


@app.get("/api/system/resources")
async def api_system_resources(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    return JSONResponse(content=portal_bridge.system_resources())


@app.get("/api/ports/registry")
async def api_ports_registry(
    user: str = Depends(get_current_user),
    operational_only: bool = True,
    all_ports: bool = False,
):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    return JSONResponse(
        content=portal_bridge.ports_registry(operational_only=not all_ports and operational_only)
    )


@app.get("/api/oauth/users")
async def api_oauth_users(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Solo admin")
    return JSONResponse(content=portal_bridge.oauth_users_payload())


@app.get("/api/oauth/clients")
async def api_oauth_clients(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Solo admin")
    return JSONResponse(content=portal_bridge.oauth_clients_payload())


@app.post("/api/oauth/users/{username}/revoke")
async def api_oauth_revoke_user(username: str, user: str = Depends(get_current_user)):
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Solo admin")
    return JSONResponse(content=portal_bridge.revoke_user_tokens(username))


@app.post("/api/oauth/tokens/revoke-all")
async def api_oauth_revoke_all(user: str = Depends(get_current_user)):
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Solo admin")
    return JSONResponse(content=portal_bridge.revoke_all_oauth_tokens())


@app.post("/api/oauth/users")
async def api_oauth_save_user(payload: dict = Body(...), user: str = Depends(get_current_user)):
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Solo admin")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Sin DB")
    username = str(payload.get("username", "")).strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    patch = {
        "role": payload.get("role", "user"),
        "oauth_enabled": bool(payload.get("oauth_enabled")),
        "oauth_scopes": payload.get("oauth_scopes") or [],
    }
    password = payload.get("password")
    if password:
        patch["password_hash"] = hashlib.sha256(str(password).encode()).hexdigest()
    db.users.update_one({"username": username}, {"$set": patch, "$setOnInsert": {"username": username}}, upsert=True)
    return JSONResponse(content={"ok": True, "user": {"username": username, **patch}})


@app.get("/api/ops/summary")
async def api_ops_summary(user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    return JSONResponse(content=portal_bridge.ops_overview_payload())
