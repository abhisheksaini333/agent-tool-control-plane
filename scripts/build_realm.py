"""Generate the local Keycloak realm from the same demo user identities."""
import json
from pathlib import Path
from keel.bootstrap import demo_users


def realm():
    mappers = [
        {
            "name": "api-audience",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {
                "included.client.audience": "keel-api",
                "access.token.claim": "true",
            },
        },
        {
            "name": "tenant",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {
                "user.attribute": "tenant",
                "claim.name": "tenant",
                "jsonType.label": "String",
                "access.token.claim": "true",
                "id.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        },
        {
            "name": "realm-roles",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {
                "claim.name": "realm_access.roles",
                "jsonType.label": "String",
                "multivalued": "true",
                "access.token.claim": "true",
            },
        },
    ]
    clients = [
        {
            "clientId": "keel-console",
            "publicClient": True,
            "enabled": True,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "redirectUris": ["http://localhost:5294/"],
            "webOrigins": ["http://localhost:5294"],
            "attributes": {"pkce.code.challenge.method": "S256"},
            "protocolMappers": mappers,
        },
        {
            "clientId": "keel-demo-cli",
            "publicClient": True,
            "enabled": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": True,
            "protocolMappers": mappers,
        },
    ]
    users = [
        {
            "id": user["id"],
            "username": user["username"],
            "enabled": True,
            "emailVerified": True,
            "firstName": user["display_name"],
            "email": user["username"] + "@example.test",
            "attributes": {"tenant": [user["tenant"]]},
            "realmRoles": user["roles"],
            "credentials": [
                {"type": "password", "value": "keel-demo-password", "temporary": False}
            ],
        }
        for user in demo_users()
    ]
    return {
        "realm": "keel",
        "enabled": True,
        "displayName": "Keel local workspace",
        "sslRequired": "none",
        "registrationAllowed": False,
        "resetPasswordAllowed": False,
        "bruteForceProtected": True,
        "accessTokenLifespan": 300,
        "roles": {
            "realm": [
                {"name": name}
                for name in ["operator", "approver", "administrator", "auditor"]
            ]
        },
        "clients": clients,
        "users": users,
    }


if __name__ == "__main__":
    Path("infra/keel-realm.json").write_text(json.dumps(realm(), indent=2) + "\n")
