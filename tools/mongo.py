"""Acceso a MongoDB — fuente de verdad operativa PC Doctor."""

from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient

from config import MONGO_DB, MONGO_URI

_client: MongoClient | None = None


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client[MONGO_DB]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_indexes():
    db = get_db()
    db.clients.create_index("ruc", unique=True, sparse=True)
    db.inspections.create_index("inspection_id", unique=True)
    db.inventory.create_index("sku", unique=True, sparse=True)


def lookup_client_by_ruc(ruc: str) -> dict | None:
    return get_db().clients.find_one({"ruc": ruc}, {"_id": 0})


def create_client(data: dict) -> dict:
    db = get_db()
    doc = {
        "ruc": data["ruc"],
        "cedula": data.get("cedula"),
        "name": data.get("name", ""),
        "trade_name": data.get("trade_name", ""),
        "address": data.get("address", ""),
        "city": data.get("city", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "legal_rep": data.get("legal_rep", ""),
        "activity": data.get("activity", ""),
        "hub_ready": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    db.clients.update_one({"ruc": doc["ruc"]}, {"$set": doc}, upsert=True)
    return db.clients.find_one({"ruc": doc["ruc"]}, {"_id": 0})


def create_inspection(inspection_id: str, raw_input: str, ruc: str | None = None) -> dict:
    db = get_db()
    doc = {
        "inspection_id": inspection_id,
        "ruc": ruc,
        "raw_input": raw_input,
        "status": "open",
        "findings": [],
        "media": [],
        "pending_tasks": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    db.inspections.insert_one(doc)
    doc.pop("_id", None)
    return doc


def get_inspection(inspection_id: str) -> dict | None:
    return get_db().inspections.find_one({"inspection_id": inspection_id}, {"_id": 0})


def update_inspection(inspection_id: str, patch: dict) -> dict | None:
    patch["updated_at"] = _now()
    get_db().inspections.update_one({"inspection_id": inspection_id}, {"$set": patch})
    return get_inspection(inspection_id)


def save_findings(inspection_id: str, findings: list[dict], pending_tasks: list[str]) -> dict | None:
    return update_inspection(
        inspection_id,
        {"findings": findings, "pending_tasks": pending_tasks, "status": "documented"},
    )


def save_report(inspection_id: str, report: dict) -> dict:
    db = get_db()
    doc = {
        "inspection_id": inspection_id,
        **report,
        "created_at": _now(),
    }
    db.reports.update_one({"inspection_id": inspection_id}, {"$set": doc}, upsert=True)
    doc.pop("_id", None)
    return doc


def save_quote(inspection_id: str, quote: dict) -> dict:
    db = get_db()
    header = {
        "inspection_id": inspection_id,
        "client_ruc": quote.get("client_ruc"),
        "scope": quote.get("scope", ""),
        "subtotal": quote.get("subtotal", 0),
        "iva": quote.get("iva", 0),
        "total": quote.get("total", 0),
        "currency": "USD",
        "status": "draft",
        "created_at": _now(),
    }
    db.quote_headers.update_one({"inspection_id": inspection_id}, {"$set": header}, upsert=True)
    lines = quote.get("lines", [])
    if lines:
        db.quote_lines.delete_many({"inspection_id": inspection_id})
        for i, line in enumerate(lines, 1):
            db.quote_lines.insert_one(
                {
                    "inspection_id": inspection_id,
                    "line_no": i,
                    **line,
                }
            )
    return {**header, "lines": lines}


def search_inventory(query: str, limit: int = 10) -> list[dict]:
    db = get_db()
    regex = {"$regex": query, "$options": "i"}
    cur = db.inventory.find(
        {"$or": [{"name": regex}, {"sku": regex}, {"category": regex}]},
        {"_id": 0},
    ).limit(limit)
    return list(cur)


def seed_inventory_if_empty():
    db = get_db()
    if db.inventory.count_documents({}) > 0:
        return
    items = [
        {"sku": "CAM-IP-2MP", "name": "Cámara IP 2MP", "unit_price": 85.0, "category": "cctv"},
        {"sku": "CABLE-UTP", "name": "Cable UTP por metro", "unit_price": 0.8, "category": "cableado"},
        {"sku": "SW-8P", "name": "Switch 8 puertos", "unit_price": 45.0, "category": "red"},
        {"sku": "RACK-ORD", "name": "Ordenamiento de rack", "unit_price": 120.0, "category": "servicio"},
        {"sku": "MANO-OBRA", "name": "Mano de obra técnica (hora)", "unit_price": 25.0, "category": "servicio"},
    ]
    db.inventory.insert_many(items)


def log_action(agent: str, action: str, payload: dict[str, Any] | None = None):
    get_db().audit_log.insert_one(
        {
            "agent": agent,
            "action": action,
            "payload": payload or {},
            "at": _now(),
        }
    )
