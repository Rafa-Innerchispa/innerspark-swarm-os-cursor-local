"""Envío SMTP reutilizando credenciales de cuentas IMAP monitorizadas."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

from tools.email_providers import detect_provider


def smtp_settings_for_address(address: str) -> dict[str, Any]:
    """Deriva host/puerto SMTP a partir del dominio del buzón."""
    domain = address.strip().lower().split("@")[-1] if "@" in address else ""
    presets: dict[str, dict[str, Any]] = {
        "gmail.com": {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "use_tls": True},
        "googlemail.com": {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "use_tls": True},
        "hotmail.com": {"smtp_host": "smtp.office365.com", "smtp_port": 587, "use_tls": True},
        "outlook.com": {"smtp_host": "smtp.office365.com", "smtp_port": 587, "use_tls": True},
        "live.com": {"smtp_host": "smtp.office365.com", "smtp_port": 587, "use_tls": True},
        "msn.com": {"smtp_host": "smtp.office365.com", "smtp_port": 587, "use_tls": True},
        "yahoo.com": {"smtp_host": "smtp.mail.yahoo.com", "smtp_port": 587, "use_tls": True},
        "icloud.com": {"smtp_host": "smtp.mail.me.com", "smtp_port": 587, "use_tls": True},
        "me.com": {"smtp_host": "smtp.mail.me.com", "smtp_port": 587, "use_tls": True},
    }
    if domain in presets:
        return presets[domain]
    imap = detect_provider(address)
    host = imap.get("imap_host", "")
    smtp_host = host.replace("imap.", "smtp.", 1) if host.startswith("imap.") else f"smtp.{domain}"
    return {"smtp_host": smtp_host, "smtp_port": 587, "use_tls": True}


def send_smtp_email(
    *,
    smtp_host: str,
    smtp_port: int,
    user: str,
    password: str,
    to_addr: str,
    subject: str,
    body: str,
    from_name: str = "",
    from_addr: str | None = None,
    use_tls: bool = True,
) -> dict[str, Any]:
    """Envía un correo de texto plano vía SMTP."""
    if not smtp_host or not user or not password or not to_addr:
        return {"ok": False, "error": "Faltan credenciales SMTP o destinatario"}

    sender = from_addr or user
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, sender)) if from_name else sender
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(sender, [to_addr], msg.as_string())
        return {"ok": True, "to": to_addr, "subject": subject, "from": msg["From"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_via_account(acc: dict, *, to_addr: str, subject: str, body: str, from_name: str) -> dict[str, Any]:
    """Envía usando una fila de email_accounts (mismas credenciales IMAP)."""
    address = acc.get("address") or acc.get("imap_user") or ""
    smtp = smtp_settings_for_address(address)
    return send_smtp_email(
        smtp_host=smtp["smtp_host"],
        smtp_port=int(smtp.get("smtp_port", 587)),
        user=acc.get("imap_user") or address,
        password=acc.get("imap_password", ""),
        to_addr=to_addr,
        subject=subject,
        body=body,
        from_name=from_name,
        from_addr=address,
        use_tls=bool(smtp.get("use_tls", True)),
    )
