"""Composition root for explicit PostgreSQL, OPA, OIDC and Redis services."""
from contextlib import ExitStack
import redis
from .accounts import Accounts
from .admission import RedisAdmission
from .auth import JwtVerifier
from .control import Control
from .policy import OpaPolicy
from .postgres import PostgresStore


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        self.resources = ExitStack()
        try:
            self.store = PostgresStore(settings.database_url)
            self.resources.callback(self.store.close)
            self.policy = OpaPolicy(settings.opa_url)
            self.resources.callback(self.policy.close)
            self.verifier = JwtVerifier(settings.issuer, settings.audience)
            self.resources.callback(self.verifier.close)
            self.redis = redis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=2, socket_timeout=2
            )
            self.resources.callback(self.redis.close)
            self.control = Control(self.store, self.policy)
            self.admission = RedisAdmission(self.redis)
        except BaseException:
            self.resources.close()
            raise

    def checks(self):
        checks = {}
        operations = {
            "database": lambda: self.store.get("system", "meta", "health"),
            "admission": self.redis.ping,
            "policy": lambda: self.policy.client.get(
                self.settings.opa_url + "/health", timeout=2
            ).raise_for_status(),
            "identity": lambda: self.verifier.client.get(
                self.verifier.url, timeout=2
            ).raise_for_status(),
        }
        for name, operation in operations.items():
            try:
                operation()
                checks[name] = True
            except Exception:
                checks[name] = False
        return checks

    def close(self):
        self.resources.close()
