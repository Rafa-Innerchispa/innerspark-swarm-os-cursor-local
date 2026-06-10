"""CRUD REST /api/v1/* para admin Refine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from tools.companies import ensure_companies, seed_innerchispa_catalog
from tools.schema import ensure_client_hub, new_id

BRANDING_DIR = Path(__file__).resolve().parents[1] / "assets" / "branding"

router = APIRouter(prefix="/api/v1", tags=["admin"])


def _db():
    from tools.mongo import get_db

    return get_db()


def _now():
    return datetime.now(timezone.utc)


def _strip_id(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def _list_collection(
    collection: str,
    id_field: str,
    skip: int = 0,
    limit: int = 25,
    sort: str | None = None,
) -> dict:
    db = _db()
    cur = db[collection].find({}, {"_id": 0}).skip(skip).limit(min(limit, 200))
    if sort:
        cur = cur.sort(sort, -1)
    data = list(cur)
    total = db[collection].count_documents({})
    return {"data": data, "total": total}


# --- Clients DB04 ---
class ClientIn(BaseModel):
    name: str
    ruc: str | None = None
    city: str = ""
    address: str = ""
    email: str = ""
    phone: str = ""
    estado: str = "Cliente"


@router.get("/clients")
def list_clients(skip: int = 0, limit: int = 25):
    return _list_collection("clients", "client_id", skip, limit, "updated_at")


@router.get("/clients/{client_id}")
def get_client(client_id: str):
    doc = _db().clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "cliente no encontrado")
    return doc


@router.post("/clients")
def create_client(body: ClientIn):
    db = _db()
    client_id = new_id("cli")
    doc = {
        "client_id": client_id,
        **body.model_dump(),
        "hub_ready": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if body.ruc:
        db.clients.update_one({"ruc": body.ruc}, {"$set": doc}, upsert=True)
        doc = db.clients.find_one({"ruc": body.ruc}, {"_id": 0})
    else:
        db.clients.insert_one(doc)
        doc.pop("_id", None)
    ensure_client_hub(db, doc["client_id"], doc["name"])
    return _strip_id(doc)


@router.patch("/clients/{client_id}")
def update_client(client_id: str, body: dict[str, Any]):
    body["updated_at"] = _now()
    res = _db().clients.update_one({"client_id": client_id}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "cliente no encontrado")
    return get_client(client_id)


# --- Inventory DB26 ---
@router.get("/inventory-items")
def list_inventory(skip: int = 0, limit: int = 25, q: str | None = None):
    db = _db()
    filt = {}
    if q:
        filt = {"$or": [
            {"nombre": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
            {"item_code": {"$regex": q, "$options": "i"}},
        ]}
    data = list(db.inventory_items.find(filt, {"_id": 0}).skip(skip).limit(limit))
    total = db.inventory_items.count_documents(filt)
    return {"data": data, "total": total}


@router.get("/inventory-items/{item_code}")
def get_inventory_item(item_code: str):
    doc = _db().inventory_items.find_one({"item_code": item_code}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "ítem no encontrado")
    return doc


# --- Catalog DB13 ---
@router.get("/catalog-products")
def list_catalog(skip: int = 0, limit: int = 25):
    return _list_collection("catalog_products", "code", skip, limit)


# --- Suppliers DB25 ---
@router.get("/suppliers")
def list_suppliers(skip: int = 0, limit: int = 25):
    return _list_collection("suppliers", "supplier_id", skip, limit)


# --- Quotes DB27 ---
@router.get("/quotes")
def list_quotes(skip: int = 0, limit: int = 25):
    db = _db()
    data = list(db.quotes.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))
    total = db.quotes.count_documents({})
    return {"data": data, "total": total}


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: str):
    db = _db()
    doc = db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "cotización no encontrada")
    doc["lines"] = list(db.quote_lines.find({"quote_id": quote_id}, {"_id": 0}))
    return doc


# --- Visits DB42 ---
@router.get("/sop-visits")
def list_visits(skip: int = 0, limit: int = 25):
    return _list_collection("sop_visits", "visit_id", skip, limit, "created_at")


# --- Companies (multiempresa) ---
@router.get("/companies")
def list_companies():
    db = _db()
    ensure_companies(db)
    data = list(db.companies.find({"active": True}, {"_id": 0}))
    return {"data": data, "total": len(data)}


@router.get("/companies/{company_id}")
def get_company(company_id: str):
    doc = _db().companies.find_one({"company_id": company_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "empresa no encontrada")
    return doc


@router.patch("/companies/{company_id}")
def update_company(company_id: str, body: dict[str, Any]):
    allowed = {
        "brand_name", "legal_name", "tagline", "logo_file", "icon_file",
        "colors", "default_for_quotes", "active",
    }
    patch = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise HTTPException(400, "sin campos válidos")
    patch["updated_at"] = _now()
    res = _db().companies.update_one({"company_id": company_id}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(404, "empresa no encontrada")
    return get_company(company_id)


@router.post("/companies/seed-catalog")
def seed_catalog():
    """Crea servicios InnerChispa en catálogo si no existen."""
    db = _db()
    ensure_companies(db)
    n = seed_innerchispa_catalog(db)
    return {"inserted": n, "message": f"{n} servicios InnerChispa agregados al catálogo"}


@router.post("/companies/{company_id}/logo")
async def upload_company_logo(company_id: str, file: UploadFile = File(...)):
    company = _db().companies.find_one({"company_id": company_id})
    if not company:
        raise HTTPException(404, "empresa no encontrada")
    ext = Path(file.filename or "logo.png").suffix.lower() or ".png"
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        raise HTTPException(400, "formato no soportado")
    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"logo_{company['slug']}{ext}"
    dest = BRANDING_DIR / fname
    content = await file.read()
    dest.write_bytes(content)
    _db().companies.update_one(
        {"company_id": company_id},
        {"$set": {"logo_file": fname, "updated_at": _now()}},
    )
    return {"logo_file": fname, "url": f"/assets/branding/{fname}"}


# --- Meta ---
@router.get("/stats")
def admin_stats():
    db = _db()
    return {
        "clients": db.clients.count_documents({}),
        "inventory_items": db.inventory_items.count_documents({}),
        "catalog_products": db.catalog_products.count_documents({}),
        "suppliers": db.suppliers.count_documents({}),
        "quotes": db.quotes.count_documents({}),
        "sop_visits": db.sop_visits.count_documents({}),
    }
