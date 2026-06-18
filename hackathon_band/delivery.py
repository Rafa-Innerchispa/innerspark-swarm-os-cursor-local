"""Entrega del reporte: WhatsApp + email."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hackathon_band import config
from hackathon_band.console_log import log as clog
from hackathon_band.email_notify import send_report_emails
from hackathon_band.phone_utils import parse_phone_list
from hackathon_band.whatsapp_notify import build_whatsapp_message, public_report_download_url


def deliver_report(
    question: str,
    report_path: str,
    report_markdown: str,
    *,
    memory_hits: list[dict[str, Any]] | None = None,
    memory_hits_count: int = 0,
    lang: str = "en",
    extra_phones: list[str] | None = None,
    extra_emails: list[str] | None = None,
) -> None:
    _deliver_whatsapp(
        question,
        report_path,
        report_markdown,
        memory_hits=memory_hits,
        memory_hits_count=memory_hits_count,
        lang=lang,
        extra_phones=extra_phones,
    )
    send_report_emails(
        question,
        report_markdown,
        report_path,
        extra_emails=extra_emails,
        memory_hits=memory_hits,
        memory_hits_count=memory_hits_count,
        lang=lang,
    )


def _deliver_whatsapp(
    question: str,
    report_path: str,
    report_markdown: str,
    *,
    memory_hits: list[dict[str, Any]] | None = None,
    memory_hits_count: int = 0,
    lang: str = "en",
    extra_phones: list[str] | None = None,
) -> None:
    evo_key = config.EVOLUTION_API_KEY
    evo_inst = config.EVOLUTION_INSTANCE
    recipients = parse_phone_list(config.HACKATHON_WHATSAPP_TO, *(extra_phones or []))

    if not evo_key:
        clog("info", "whatsapp", "Evolution API not configured — skipped")
        return

    if not recipients:
        clog("info", "whatsapp", "No phone recipients configured")
        return

    clog("info", "whatsapp", f"Sending to {len(recipients)} number(s): {', '.join(r[:6]+'…' for r in recipients)}")

    try:
        from tools.evolution_api import send_whatsapp, send_whatsapp_document

        text = build_whatsapp_message(
            question,
            report_markdown,
            hits=memory_hits,
            memory_hits_count=memory_hits_count,
            lang=lang,
        )
        download_url = public_report_download_url()
        doc_caption = (
            "Reporte Band of Agents — PC Doctor"
            if lang == "es"
            else "Band of Agents report — PC Doctor"
        )

        sent = 0
        for num in recipients:
            try:
                result = send_whatsapp(num, text, instance=evo_inst or None, skip_existence_check=True)
                if result.get("status") != "sent":
                    clog(
                        "error",
                        "whatsapp",
                        f"{num}: {result.get('message') or result.get('check') or result}",
                    )
                    continue
                sent += 1
                clog("success", "whatsapp", f"Summary → {result.get('number', num)}")
                if Path(report_path).is_file():
                    doc = send_whatsapp_document(
                        num,
                        report_path,
                        caption=doc_caption,
                        instance=evo_inst or None,
                        file_name="PCDoctor_Band_Report.md",
                        skip_existence_check=True,
                    )
                    if doc.get("status") == "sent":
                        clog("success", "whatsapp", f"Attachment → {num}")
                    else:
                        clog("error", "whatsapp", f"Attachment {num}: {doc.get('message', doc)[:120]}")
            except Exception as exc:
                clog("error", "whatsapp", f"{num}: {exc}")
        if sent:
            clog("success", "whatsapp", f"{sent}/{len(recipients)} OK — {download_url}")
    except Exception as exc:
        clog("error", "whatsapp", f"Delivery failed: {exc}")
