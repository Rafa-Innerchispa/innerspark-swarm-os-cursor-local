from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_filebrowser_backend_is_loopback_only():
    compose = (ROOT / "docker" / "filebrowser-compose.yml").read_text()
    assert '127.0.0.1:18081:80' in compose
    assert '"8081:80"' not in compose


def test_sso_gateway_uses_portal_session_and_trusted_header():
    source = (ROOT / "filebrowser_sso_gateway.py").read_text()
    assert 'session_token' in source
    assert 'hackathon_autopilot' in source
    assert 'X-Remote-User' in source
    assert 'http://127.0.0.1:18081' in source
    assert 'http://192.168.1.4:2002/login' in source
