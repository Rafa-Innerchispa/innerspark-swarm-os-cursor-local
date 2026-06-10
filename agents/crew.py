"""Orquestación CrewAI — flujo de inspección PC Doctor."""

import json
import re
import uuid
from typing import Any

from crewai import Agent, Crew, Process, Task
from langchain_ollama import ChatOllama

from agents.roles import build_agents, get_llm
from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from tools.crew_tools import get_inspection_context, start_inspection_record
from tools.mongo import (
    ensure_indexes,
    lookup_client_by_ruc,
    save_quote,
    save_report,
    seed_inventory_if_empty,
)
from tools.pdf_generator import export_quote, export_technical_report
from tools.ruc_api import lookup_ruc


def _extract_ruc(text: str) -> str | None:
    m = re.search(r"\b\d{13}\b", text)
    return m.group(0) if m else None


def _agent_from_spec(spec: dict) -> Agent:
    return Agent(
        role=spec["role"],
        goal=spec["goal"],
        backstory=spec["backstory"],
        tools=spec.get("tools") or [],
        llm=spec["llm"],
        verbose=spec.get("verbose", True),
        allow_delegation=False,
    )


def _parse_json_block(text: str, fallback: dict) -> dict:
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        pass
    return fallback


def _fallback_quote(findings: list[dict]) -> dict:
    lines = []
    for f in findings:
        item = f.get("item", "Servicio técnico")
        qty = float(f.get("qty", 1))
        price = float(f.get("estimated_unit_price", 25.0))
        lines.append({"name": item, "qty": qty, "unit_price": price})
    if not lines:
        lines = [{"name": "Inspección y diagnóstico", "qty": 1, "unit_price": 45.0}]
    subtotal = sum(l["qty"] * l["unit_price"] for l in lines)
    iva = round(subtotal * 0.15, 2)
    return {
        "scope": "Trabajos derivados de inspección en campo",
        "lines": lines,
        "subtotal": round(subtotal, 2),
        "iva": iva,
        "total": round(subtotal + iva, 2),
    }


def run_inspection_flow(raw_input: str, inspection_id: str | None = None) -> dict[str, Any]:
    """
    Ejecuta el flujo multi-agente.
    MVP: cliente → campo → informe → cotización → revisión → comunicaciones.
    """
    ensure_indexes()
    seed_inventory_if_empty()

    if not inspection_id:
        inspection_id = start_inspection_record(raw_input)

    ruc = _extract_ruc(raw_input)
    sri_data = lookup_ruc(ruc) if ruc else {}
    client = lookup_client_by_ruc(ruc) if ruc else None

    specs = build_agents(get_llm())
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2)

    # --- Fase 1: Cliente (si hay RUC) ---
    client_summary = client or sri_data
    if ruc and not client:
        cliente_agent = _agent_from_spec(specs["cliente"])
        t_cliente = Task(
            description=(
                f"RUC detectado: {ruc}. Consulta SRI, verifica si existe en MongoDB "
                f"y crea/actualiza el cliente. Input de campo: {raw_input}"
            ),
            expected_output="JSON del cliente guardado en MongoDB",
            agent=cliente_agent,
        )
        crew_cliente = Crew(agents=[cliente_agent], tasks=[t_cliente], process=Process.sequential, verbose=True)
        client_result = crew_cliente.kickoff()
        client_summary = _parse_json_block(str(client_result), sri_data)

    # --- Fase 2: Campo + hallazgos ---
    campo_agent = _agent_from_spec(specs["campo"])
    t_campo = Task(
        description=(
            f"Inspección ID: {inspection_id}. Analiza: {raw_input}. "
            "Extrae hallazgos técnicos (cámaras, cables, switches, rack) y tareas pendientes. "
            f"Usa save_inspection_findings_tool con inspection_id={inspection_id}. "
            'findings_json: array de objetos {{"item","severity","detail","qty"}}. '
            'pending_json: array de strings.'
        ),
        expected_output="Hallazgos guardados en MongoDB",
        agent=campo_agent,
    )
    crew_campo = Crew(agents=[campo_agent], tasks=[t_campo], process=Process.sequential, verbose=True)
    crew_campo.kickoff()

    ctx = get_inspection_context(inspection_id)
    findings = ctx.get("findings", [])

    # --- Fase 3: Informe técnico ---
    informes_agent = _agent_from_spec(specs["informes"])
    t_informe = Task(
        description=(
            f"Redacta informe técnico para inspección {inspection_id}. "
            f"Cliente: {json.dumps(client_summary, ensure_ascii=False)}. "
            f"Hallazgos: {json.dumps(findings, ensure_ascii=False)}. "
            "Guarda con save_report_tool un JSON con: summary, location, technician, "
            "findings_text, work_done, final_status, recommendations."
        ),
        expected_output="Informe guardado en MongoDB",
        agent=informes_agent,
    )
    crew_informe = Crew(agents=[informes_agent], tasks=[t_informe], process=Process.sequential, verbose=True)
    informe_result = crew_informe.kickoff()

    report = _parse_json_block(
        str(informe_result),
        {
            "summary": "Inspección de infraestructura en campo",
            "location": client_summary.get("address", ""),
            "technician": "Por confirmar",
            "findings_text": "; ".join(f.get("detail", "") for f in findings),
            "work_done": "Diagnóstico visual y levantamiento de hallazgos",
            "final_status": "Pendiente de aprobación de cotización",
            "recommendations": "Ejecutar trabajos cotizados y reordenar cableado",
        },
    )
    save_report(inspection_id, report)

    # --- Fase 4: Cotización ---
    cotizador_agent = _agent_from_spec(specs["cotizador"])
    t_cot = Task(
        description=(
            f"Cotiza inspección {inspection_id}. Busca ítems en inventario según hallazgos: "
            f"{json.dumps(findings, ensure_ascii=False)}. "
            "Calcula subtotal, IVA 15%, total. Guarda con save_quote_tool."
        ),
        expected_output="Cotización guardada en MongoDB",
        agent=cotizador_agent,
    )
    crew_cot = Crew(agents=[cotizador_agent], tasks=[t_cot], process=Process.sequential, verbose=True)
    cot_result = crew_cot.kickoff()
    quote = _parse_json_block(str(cot_result), _fallback_quote(findings))
    if ruc:
        quote["client_ruc"] = ruc
    save_quote(inspection_id, quote)

    # --- Fase 5: Revisión ---
    revisor_agent = _agent_from_spec(specs["revisor"])
    t_rev = Task(
        description=(
            f"Revisa informe y cotización. Reporte: {json.dumps(report, ensure_ascii=False)}. "
            f"Cotización: {json.dumps(quote, ensure_ascii=False)}. "
            "Lista problemas (placeholders, campos vacíos). Responde JSON: "
            '{"approved": bool, "issues": [str], "notes": str}'
        ),
        expected_output="JSON de revisión con approved true/false",
        agent=revisor_agent,
    )
    crew_rev = Crew(agents=[revisor_agent], tasks=[t_rev], process=Process.sequential, verbose=True)
    rev_result = crew_rev.kickoff()
    review = _parse_json_block(str(rev_result), {"approved": True, "issues": [], "notes": "MVP"})

    # --- Fase 6: Comunicaciones ---
    comm_agent = _agent_from_spec(specs["comunicaciones"])
    t_comm = Task(
        description=(
            f"Redacta borrador de correo para el cliente y aviso interno WhatsApp. "
            f"Cliente: {client_summary.get('name', '')}. Total cotización: {quote.get('total')}."
        ),
        expected_output="Texto de correo + mensaje WhatsApp corto",
        agent=comm_agent,
    )
    crew_comm = Crew(agents=[comm_agent], tasks=[t_comm], process=Process.sequential, verbose=True)
    comm_result = crew_comm.kickoff()

    client_doc = lookup_client_by_ruc(ruc) if ruc else client_summary
    report_path = export_technical_report(inspection_id, report, client_doc or {})
    quote_path = export_quote(inspection_id, quote, client_doc or {})

    return {
        "inspection_id": inspection_id,
        "client": client_doc,
        "findings": findings,
        "report": report,
        "quote": quote,
        "review": review,
        "communications_draft": str(comm_result),
        "exports": {"report_md": report_path, "quote_md": quote_path},
        "status": "completed",
    }
