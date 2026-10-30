from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pnpm-workspace.yaml").exists() and (p / "platform").is_dir():
            return p
    return start


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("EOS_DATABASE_URL", "sqlite:///./eos.db"))
    jwt_secret: str = field(
        default_factory=lambda: os.environ.get("EOS_JWT_SECRET", "dev-only-change-me-dev-only-change-me-32b")
    )
    jwt_ttl_minutes: int = field(default_factory=lambda: int(os.environ.get("EOS_JWT_TTL_MINUTES", "720")))
    repo_root: Path = field(default_factory=lambda: Path(os.environ.get("EOS_REPO_ROOT", _find_repo_root(Path.cwd()))))
    dev_mode: bool = field(default_factory=lambda: os.environ.get("EOS_DEV_MODE", "true").lower() == "true")
    super_admin_email: str = field(default_factory=lambda: os.environ.get("EOS_SUPER_ADMIN_EMAIL", ""))
    super_admin_password: str = field(default_factory=lambda: os.environ.get("EOS_SUPER_ADMIN_PASSWORD", ""))
    payment_adapter: str = field(default_factory=lambda: os.environ.get("BILLING_PAYMENT_ADAPTER", "none"))
    registration_open: bool = field(
        default_factory=lambda: os.environ.get("TENANCY_REGISTRATION_OPEN", "true").lower() == "true"
    )
    # ADR-0005: a super admin approves an organisation's academic package before it goes live.
    auto_approve: bool = field(
        default_factory=lambda: os.environ.get("TENANCY_AUTO_APPROVE", "false").lower() == "true"
    )
    cors_origins: list[str] = field(
        default_factory=lambda: [o for o in os.environ.get("EOS_CORS_ORIGINS", "http://localhost:5173").split(",") if o]
    )
    # ADR-0006: Keycloak behind the public proxy. Empty means no OIDC: only the API's own tokens are accepted.
    # Realm issuers are `<base>/realms/<organisation slug>`.
    oidc_issuer_base: str = field(default_factory=lambda: os.environ.get("EOS_OIDC_ISSUER_BASE", "").rstrip("/"))
    oidc_client_id: str = field(default_factory=lambda: os.environ.get("EOS_OIDC_CLIENT_ID", "education-os-web"))
    # Slugs whose realm exists (comma-separated), or `*` once every organisation gets one at approval.
    oidc_realms: str = field(default_factory=lambda: os.environ.get("EOS_OIDC_REALMS", ""))
    oidc_jwks_ttl_seconds: int = field(default_factory=lambda: int(os.environ.get("EOS_OIDC_JWKS_TTL_SECONDS", "3600")))
    oidc_http_timeout: float = field(default_factory=lambda: float(os.environ.get("EOS_OIDC_HTTP_TIMEOUT", "5")))
    # The JWKS fetch runs inside a request: short, so a slow or unreachable Keycloak refuses quickly.
    oidc_jwks_timeout: float = field(default_factory=lambda: float(os.environ.get("EOS_OIDC_JWKS_TIMEOUT", "2")))

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
