import json
from pathlib import Path
from scripts.build_realm import realm
from keel.bootstrap import demo_users


def test_realm_matches_seed_identities_and_browser_requires_pkce():
    configured = json.loads(Path("infra/keel-realm.json").read_text())
    assert configured == realm()
    assert {user["id"] for user in configured["users"]} == {
        user["id"] for user in demo_users()
    }
    console = next(
        client
        for client in configured["clients"]
        if client["clientId"] == "keel-console"
    )
    assert console["attributes"]["pkce.code.challenge.method"] == "S256"
    assert not console["directAccessGrantsEnabled"]
    assert console["redirectUris"] == ["http://localhost:5294/"]
