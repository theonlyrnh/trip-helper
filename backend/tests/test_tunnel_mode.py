from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def tunnel_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "tunnel",
        "app_domain": "trip.ninghui.ren",
        "database_url": "sqlite:////tmp/trip-helper-tunnel.db",
        "storage_root": "/tmp/trip-helper-tunnel-storage",
        "session_secret": "tunnel-session-secret",
        "bootstrap_token": "tunnel-bootstrap-token",
        "cookie_secure": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_tunnel_mode_is_deployed_and_keeps_sqlite_on_a100() -> None:
    settings = tunnel_settings()

    assert settings.is_tunnel is True
    assert settings.is_production is False
    assert settings.is_deployed is True
    assert settings.allowed_hosts == ["trip.ninghui.ren"]


def test_tunnel_deployment_contract_is_explicitly_acceptance_only() -> None:
    example = Path("deploy/a100/.env.tunnel.example").read_text(encoding="utf-8")
    assert "TUNNEL_ACCEPTANCE_ONLY=true" in example
    assert "TASKS_EAGER=true" in example
    assert "Production" in example


@pytest.mark.parametrize(
    ("field", "value"),
    [("cookie_secure", False), ("bootstrap_token", None), ("session_secret", "SESSION_SECRET")],
)
def test_tunnel_mode_rejects_insecure_public_configuration(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match="deployment configuration"):
        tunnel_settings(**{field: value})
