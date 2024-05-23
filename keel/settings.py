from dataclasses import dataclass, field
import os
from urllib.parse import urlparse
from .identity import identifier


def service_url(value, local_demo, origin=False):
    parsed = urlparse(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (
        local_demo and local and parsed.scheme == "http"
    ):
        raise ValueError("Service URLs require HTTPS outside the loopback demo")
    if (
        not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid service URL")
    if origin and parsed.path not in {"", "/"}:
        raise ValueError("Web origin must not include a path")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    local_demo: bool
    database_url: str = field(repr=False)
    redis_url: str = field(repr=False)
    issuer: str
    audience: str
    opa_url: str
    web_origin: str
    tenants: tuple[str, ...]
    credential_directory: str
    worker_image: str
    worker_timeout: float

    @classmethod
    def from_env(cls, environment=None):
        env = os.environ if environment is None else environment
        local = env.get("KEEL_LOCAL_DEMO") == "1"
        required = [
            "KEEL_DATABASE_URL",
            "KEEL_REDIS_URL",
            "KEEL_OIDC_ISSUER",
            "KEEL_OPA_URL",
            "KEEL_WEB_ORIGIN",
            "KEEL_TENANTS",
            "KEEL_CREDENTIAL_DIRECTORY",
        ]
        if not local and any(not env.get(key) for key in required):
            raise ValueError("Production settings must be supplied explicitly")
        tenants = tuple(dict.fromkeys(env.get("KEEL_TENANTS", "acme,north").split(",")))
        if not 1 <= len(tenants) <= 32:
            raise ValueError("Configure between one and32 tenants")
        for tenant in tenants:
            identifier(tenant, "configured tenant")
        timeout = float(env.get("KEEL_WORKER_TIMEOUT", "10"))
        if not 0.1 <= timeout <= 30:
            raise ValueError("Worker timeout must be between0.1 and30 seconds")
        database = env.get(
            "KEEL_DATABASE_URL",
            "postgresql://keel:keel-local-only@127.0.0.1:56484/keel",
        )
        redis = env.get("KEEL_REDIS_URL", "redis://127.0.0.1:6394/0")
        if urlparse(database).scheme not in {"postgres", "postgresql"} or urlparse(
            redis
        ).scheme not in {"redis", "rediss"}:
            raise ValueError("PostgreSQL and Redis URLs are required")
        return cls(
            local,
            database,
            redis,
            service_url(
                env.get("KEEL_OIDC_ISSUER", "http://localhost:8294/realms/keel"), local
            ),
            "keel-api",
            service_url(env.get("KEEL_OPA_URL", "http://127.0.0.1:8295"), local),
            service_url(
                env.get("KEEL_WEB_ORIGIN", "http://localhost:5294"), local, origin=True
            ),
            tenants,
            env.get("KEEL_CREDENTIAL_DIRECTORY", ".runtime/credentials"),
            env.get("KEEL_WORKER_IMAGE", "keel-worker:local"),
            timeout,
        )
