import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.crew import run_inspection_flow
from config import API_HOST, API_PORT
from tools.file_reader import read_file
from tools.media_store import save_upload
from tools.mongo import ensure_indexes, get_inspection, seed_inventory_if_empty, update_inspection
from tools.n8n_webhook import notify
from tools.ruc_api import lookup_ruc, normalize_tax_id
from tools.transcribe import transcribe_audio_file

app = FastAPI(
    title="InnerSpark Swarm-OS (Cursor Local)",
    description="Agentes PC Doctor — inspección, informe, cotización",
    version="0.1.0",
)


class InspectionStart(BaseModel):
    input: str = Field(..., description="Notas de campo, dictado o texto del técnico")
    inspection_id: str | None = None


class SendNotification(BaseModel):
    channel: str = "email"
    to: str = ""
    subject: str = ""
    body: str = ""
    inspection_id: str = ""


class RucLookup(BaseModel):
    id: str = Field(..., description="RUC (13) o cédula (10)")


class FileAnalyze(BaseModel):
    path: str = Field(..., description="Ruta local del archivo ya subido")
    question: str = ""


@app.on_event("startup")
def startup():
    ensure_indexes()
    seed_inventory_if_empty()


@app.get("/status")
def status():
    from config import RUC_API_PASS, RUC_API_USER, WHISPER_URL

    return {
        "status": "online",
        "project": "innerspark-swarm-os-cursor-local",
        "ruc_api_configured": bool(RUC_API_USER and RUC_API_PASS),
        "whisper_url": WHISPER_URL,
        "agents": [
            "director",
            "campo",
            "cliente",
            "bitacora",
            "informes",
            "cotizador",
            "revisor",
            "comunicaciones",
        ],
    }


@app.post("/inspection/start")
def inspection_start(body: InspectionStart):
    if not body.input.strip():
        raise HTTPException(400, "input vacío")
    try:
        result = run_inspection_flow(body.input, inspection_id=body.inspection_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/inspection/{inspection_id}")
def inspection_get(inspection_id: str):
    doc = get_inspection(inspection_id)
    if not doc:
        raise HTTPException(404, "inspección no encontrada")
    return doc


@app.post("/inspection/{inspection_id}/upload")
async def inspection_upload(inspection_id: str, file: UploadFile = File(...)):
    if not get_inspection(inspection_id):
        raise HTTPException(404, "inspección no encontrada")
    content = await file.read()
    entry = save_upload(inspection_id, file.filename or "upload.bin", content)
    return {"saved": entry}


@app.post("/inspection/{inspection_id}/upload-audio")
async def inspection_upload_audio(inspection_id: str, file: UploadFile = File(...)):
    """Sube audio, transcribe con Whisper local y agrega texto a la inspección."""
    insp = get_inspection(inspection_id)
    if not insp:
        raise HTTPException(404, "inspección no encontrada")
    content = await file.read()
    entry = save_upload(inspection_id, file.filename or "audio.wav", content)
    try:
        tr = transcribe_audio_file(entry["path"])
    except Exception as e:
        raise HTTPException(502, f"Whisper no disponible: {e}") from e
    merged = (insp.get("raw_input") or "").strip()
    if merged:
        merged += "\n\n[TRANSCRIPCIÓN AUDIO]\n" + tr["text"]
    else:
        merged = tr["text"]
    update_inspection(
        inspection_id,
        {"raw_input": merged, "transcription": tr},
    )
    return {"saved": entry, "transcription": tr, "raw_input": merged}


@app.post("/inspection/{inspection_id}/analyze-file")
def inspection_analyze_file(inspection_id: str, body: FileAnalyze):
    """Lee PDF/texto/imagen local y agrega extracción a la inspección."""
    insp = get_inspection(inspection_id)
    if not insp:
        raise HTTPException(404, "inspección no encontrada")
    try:
        extracted = read_file(body.path, question=body.question)
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    annex = f"\n\n[ARCHIVO {extracted.get('kind', 'file')}]\n{extracted.get('text', '')}"
    merged = (insp.get("raw_input") or "") + annex
    files_read = insp.get("files_read", [])
    files_read.append(extracted)
    update_inspection(inspection_id, {"raw_input": merged.strip(), "files_read": files_read})
    return {"extracted": extracted, "raw_input": merged.strip()}


@app.post("/ruc/lookup")
def ruc_lookup(body: RucLookup):
    norm = normalize_tax_id(body.id)
    data = lookup_ruc(body.id)
    return {"normalized": norm, "result": data}


@app.post("/inspection/{inspection_id}/notify")
def inspection_notify(inspection_id: str, body: SendNotification):
    if not get_inspection(inspection_id):
        raise HTTPException(404, "inspección no encontrada")
    payload = {
        "channel": body.channel,
        "to": body.to,
        "subject": body.subject,
        "body": body.body,
        "inspection_id": inspection_id,
    }
    return notify(payload)


@app.post("/inspection/quick")
def inspection_quick(body: InspectionStart):
    """Crea ID y devuelve sin ejecutar crew (útil para subir fotos antes)."""
    from tools.crew_tools import start_inspection_record

    text = body.input.strip() or "inspección en campo"
    iid = start_inspection_record(text, inspection_id=body.inspection_id)
    return {"inspection_id": iid, "status": "open"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=False)
