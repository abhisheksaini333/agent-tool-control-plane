"""Local account permissions are rechecked independently of token freshness."""
from .identity import Actor


class Accounts:
    def __init__(self, store):
        self.store = store

    def provision(self, tenant, subject, roles, display_name=None):
        actor = Actor(tenant, subject, frozenset(roles))
        with self.store.transaction():
            previous = self.store.get(tenant, "accounts", subject)
            account = {
                **actor.record(),
                "display_name": display_name or subject,
                "enabled": True,
                "generation": (previous["generation"] if previous else 0) + 1,
            }
            self.store.put(tenant, "accounts", subject, account)
        return account

    def revoke(self, tenant, subject):
        with self.store.transaction():
            account = self.store.get(tenant, "accounts", subject)
            if not account:
                raise ValueError("Unknown account")
            account.update(enabled=False, generation=account["generation"] + 1)
            self.store.put(tenant, "accounts", subject, account)

    def current(self, tenant, subject):
        account = self.store.get(tenant, "accounts", subject)
        if not account or not account["enabled"]:
            raise PermissionError("Account is unavailable")
        return Actor(tenant, subject, frozenset(account["roles"]))

    def effective(self, token_actor):
        current = self.current(token_actor.tenant, token_actor.subject)
        return Actor(current.tenant, current.subject, current.roles & token_actor.roles)
