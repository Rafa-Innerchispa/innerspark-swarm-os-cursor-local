from crewai import LLM

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from tools.crew_tools import (
    find_client_tool,
    inventory_search_tool,
    save_inspection_findings_tool,
    save_quote_tool,
    save_report_tool,
    sri_lookup_tool,
    upsert_client_tool,
)


def get_llm() -> LLM:
    return LLM(model=f"ollama/{OLLAMA_MODEL}", base_url=OLLAMA_BASE_URL, temperature=0.2)


def build_agents(llm):
    director = {
        "role": "Director de Operaciones PC Doctor",
        "goal": "Coordinar el flujo de inspección de campo hasta informe y cotización",
        "backstory": "Supervisas técnicos en urbanizaciones y aseguras trazabilidad completa.",
        "tools": [],
        "llm": llm,
        "verbose": True,
    }

    campo = {
        "role": "Agente de Campo",
        "goal": "Estructurar notas de visita, hallazgos y tareas pendientes",
        "backstory": "Interpretas dictados de técnicos sobre cables, cámaras y switches.",
        "tools": [save_inspection_findings_tool],
        "llm": llm,
        "verbose": True,
    }

    cliente = {
        "role": "Agente de Cliente",
        "goal": "Validar RUC, consultar SRI y crear/actualizar cliente en MongoDB",
        "backstory": "Eres experto en onboarding de clientes institucionales en Ecuador.",
        "tools": [sri_lookup_tool, find_client_tool, upsert_client_tool],
        "llm": llm,
        "verbose": True,
    }

    bitacora = {
        "role": "Agente de Bitácora",
        "goal": "Mantener registro ordenado de hallazgos y pendientes por inspección",
        "backstory": "Nada se pierde: cada observación queda documentada.",
        "tools": [save_inspection_findings_tool],
        "llm": llm,
        "verbose": True,
    }

    informes = {
        "role": "Agente de Informes Técnicos",
        "goal": "Redactar informes formales según Playbook PC Doctor",
        "backstory": "Conviertes hallazgos de campo en informes listos para PDF-first.",
        "tools": [save_report_tool],
        "llm": llm,
        "verbose": True,
    }

    cotizador = {
        "role": "Agente Cotizador",
        "goal": "Armar cotización con inventario, subtotal, IVA y total",
        "backstory": "Cruzas diagnóstico técnico con precios de materiales y servicios.",
        "tools": [inventory_search_tool, save_quote_tool],
        "llm": llm,
        "verbose": True,
    }

    revisor = {
        "role": "Agente Revisor (Gatekeeper)",
        "goal": "Detectar campos vacíos, placeholders y inconsistencias antes de enviar",
        "backstory": "Aplicas gates del Playbook V2: sin @today, sin N/A inventado.",
        "tools": [],
        "llm": llm,
        "verbose": True,
    }

    comunicaciones = {
        "role": "Agente de Comunicaciones",
        "goal": "Preparar resumen para correo y aviso operativo",
        "backstory": "Redactas mensajes claros para cliente y equipo interno.",
        "tools": [],
        "llm": llm,
        "verbose": True,
    }

    return {
        "director": director,
        "campo": campo,
        "cliente": cliente,
        "bitacora": bitacora,
        "informes": informes,
        "cotizador": cotizador,
        "revisor": revisor,
        "comunicaciones": comunicaciones,
    }
