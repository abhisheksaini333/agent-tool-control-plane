from dataclasses import dataclass
import re

ROLES = frozenset({"operator", "approver", "auditor", "administrator"})


def identifier(value, field="identifier"):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}", value
    ):
        raise ValueError(f"Invalid {field}")
    return value


@dataclass(frozen=True)
class Actor:
    tenant: str
    subject: str
    roles: frozenset[str]

    def __post_init__(self):
        identifier(self.tenant, "tenant")
        identifier(self.subject, "subject")
        if not isinstance(self.roles, frozenset) or self.roles - ROLES:
            raise ValueError("Invalid roles")

    def record(self):
        return {
            "tenant": self.tenant,
            "subject": self.subject,
            "roles": sorted(self.roles),
        }


def actor_from_claims(claims):
    """Only call after JWT signature, issuer, audience and time validation."""
    roles = claims.get("realm_access", {}).get("roles", [])
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise ValueError("Invalid role claims")
    return Actor(claims.get("tenant"), claims.get("sub"), frozenset(roles) & ROLES)
