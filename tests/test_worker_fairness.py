from helpers import ALICE, BOB, MANIFEST, submit
from test_worker_loop import approved_control, FixtureRunner
from keel.identity import Actor
from keel.inventory import Inventory
from keel.worker import Worker


def test_busy_tenant_does_not_starve_another_tenants_queue():
    control, first = approved_control()
    another = submit(control, "more-acme", 100.5)
    control.approve(BOB, another["id"], another["binding"], 1, 101)
    admin = Actor("north", "admin", frozenset({"administrator"}))
    operator = Actor("north", "operator", frozenset({"operator"}))
    approver = Actor("north", "approver", frozenset({"approver"}))
    for actor in [admin, operator, approver]:
        control.accounts.provision(actor.tenant, actor.subject, actor.roles)
    control.registry.publish(admin, MANIFEST)
    control.registry.activate(admin, MANIFEST["name"], MANIFEST["version"])
    Inventory(control.store).provision("north", "SKU-1", 10)
    request = control.submit(
        operator,
        MANIFEST["name"],
        MANIFEST["version"],
        {"sku": "SKU-1", "quantity": 1},
        "north-one",
        100,
    )
    control.approve(approver, request["id"], request["binding"], 1, 101)
    worker = Worker(control, FixtureRunner(), ["acme", "north"], clock=lambda: 102)
    assert worker.once() and worker.once()
    assert (
        control.store.get("north", "requests", request["id"])["status"] == "completed"
    )
    assert control.store.get("acme", "requests", another["id"])["status"] == "queued"
