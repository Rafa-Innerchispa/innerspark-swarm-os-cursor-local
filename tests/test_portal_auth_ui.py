from pathlib import Path

PORTAL = Path(__file__).resolve().parents[1] / "portal_server.py"


def test_portal_login_uses_central_oauth_and_recovery_ui():
    source = PORTAL.read_text(encoding="utf-8")
    assert "Continuar con InnerOS OAuth" in source
    assert "/auth/oauth/start" in source
    assert "code_challenge_method" in source
    assert "togglePassword" in source
    assert "Olvidé mi contraseña" in source
    assert "/api/auth/reset-password" in source
    assert "¿Qué usuario uso?" in source


def test_portal_credentials_use_central_password_verifier():
    source = PORTAL.read_text(encoding="utf-8")
    assert "oauth_store.verify_and_upgrade_password" in source
    assert "authenticate_central_user(username, password)" in source
