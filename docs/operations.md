# Operator runbook

## Service ownership and readiness

Run all commands from the repository root. The local stack is intentionally loopback-only:

| Service | Port | Durable state |
| --- | --- | --- |
| API |5484 | PostgreSQL |
| Console |5294 | No stored tokens |
| Keycloak |8294 | `keel-control_keel-identity` volume |
| PostgreSQL |56484 | `keel-control_keel-data` volume |
| Redis |6394 | Disposable admission counters |
| OPA |8295 | Policy files under `policy/` |

`KEEL_LOCAL_DEMO=1 .venv/bin/python -m keel.cli check` prints dependency booleans without tokens or credentials. `/health` only proves that the API process answers; `/ready` also checks dependency connectivity. Neither proves a worker can execute, so periodically exercise the read-only `text.digest` tool and inspect its receipt.

The API and worker retain their PostgreSQL connections. After a database restart or connection failure, restart those host processes after PostgreSQL is healthy. Redis clients reconnect, and OPA/JWKS calls fail closed while unavailable. A worker catches polling failures and backs off, but a dead database connection still requires process restart.

## Safe stop and restart

Stop the worker with SIGTERM or Ctrl+C first. It marks cancellation through its own event, removes its current sandbox and leaves a bounded retry if it still owns the request. Stop the API, console and OPA processes you launched. Then:

```sh
docker compose -p keel-control stop
```

Containers and volumes are retained. Restart with `docker compose -p keel-control up -d`, then the OPA/API/worker/console commands in the README. Do not use `down -v` for a routine restart. Do not rerun seed to reset a demonstration: seed preserves existing data by design.

A killed worker may leave a request in `running`. Leave its durable lease intact; another worker can reclaim it after sixty seconds if current identity, approval and policy still permit it. An expired approval closes the request rather than silently extending authorization. The UI shows the final state and activity trail. Create a fresh request if a human still intends the action.

A completed receipt remains completed across restarts. Replaying submission with the same caller, key and body returns that request and does not reserve stock again. Do not manually set a completed request back to queued.

## Pending requests, revocation and failures

- A requester can cancel their pending/running request; an administrator can cancel within the tenant. The original reviewer or an administrator can revoke an outstanding approval. Both operations use the displayed revision and race atomically with effect completion.
- Disabling or reactivating a tool invalidates its earlier activation generation. The registry UI explains this before the administrator confirms. Already committed receipts remain unchanged.
- `retry_wait` means a bounded transient retry is scheduled. Three execution attempts are allowed. Pre-dispatch policy outages have their own five-failure budget with2/4/8/16-second delays. Auth changes and malformed worker results are terminal.
- `insufficient_inventory` means the approved action was valid but the simulator lacked stock. No stock or receipt was committed. Choose an available item/quantity and create a fresh request.
- Account revocation must reach both the identity provider and Keel's local account record. Locally disabling a Keel account increments its generation and immediately invalidates current API authority and outstanding approvals/requests at the next transaction check. The demonstration exposes account provisioning as a trusted operator API in `keel.accounts.Accounts`, not as a browser administrator feature.

## Inspecting abandoned containers

The host runner normally removes every sandbox. If the host process or Docker daemon died, inspect only Keel-labelled containers:

```sh
docker ps -a --filter label=app=keel-worker --format '{{.ID}} {{.Names}} {{.Status}}'
```

Match the container to your stopped worker and inspect it before removal. Never remove another running worker's container. Once the corresponding coordinator is stopped and the request lease has expired, remove that individual container with `docker rm -f <verified-container-id>`. This stops abandoned computation; the fenced database lease prevents it from creating a new effect even before cleanup. Investigate repeated `cleanup_pending` diagnostics as a Docker operational problem.

## Keys and policy changes

`keel.cli seed` generates separate private `report-signing` and `inventory-signing` files. Directory permissions are0700 and file permissions0600; symlinks and permissive files are rejected. The runner creates an ephemeral0400 copy of only the needed key for each worker. Keep keys out of Git, environment variables, tool arguments and copied logs.

Rotate a key during a maintenance window with workers stopped and existing requests settled or cancelled. A worker verifies against the key captured for its own invocation; changing the source file cannot revoke a key already mounted into a running container. Account/tool revocation is the mechanism for stopping outstanding authority before effect commit.

Change policy in `policy/control.rego`, increment its revision, run `opa test policy -v`, and restart/reload your OPA process. Retain the previous policy for rollback. A new revision invalidates requests created against the previous one; it does not alter receipts.

## Backups and restore boundaries

Back up PostgreSQL, Keycloak state and per-tool credential files separately. Database backups can include sensitive tool arguments and must be encrypted and access-controlled outside the source checkout. Never store backup contents or browser traces in a public repository.

For a consistent PostgreSQL backup, stop mutations and the worker, use the matching PostgreSQL client's `pg_dump --format=custom`, then validate restoration into a **new disposable database**. Compare all document rows and verify each tenant's audit chain. Restarting against a restored older database can replay work completed after that snapshot; reconcile external effects before any such cutover. This simulator can compare reservation/receipt IDs because both are in the same database transaction.

A restore verification is not permission to overwrite the running database. Retain the original volumes until the operator has explicitly chosen a cutover. The verification helper documented in `docs/verification.md` creates and removes only its uniquely named disposable target; the source database remains intact.

## Deployment limits

The Compose baseline uses development Keycloak and old pinned versions to make this demonstration reproducible. Before a real deployment, upgrade supported dependencies, configure TLS and managed identity, replace demo users/clients/passwords, secure the Docker host and credential storage, design tested backups, anchor audit externally and measure expected load. The global mutation lock and full document scans are deliberate bounded-demo choices. Multiple coordinators are fenced for correctness, but this is not a high-availability or throughput claim. Keep host clocks synchronized; lease and approval expiry depend on wall time.

The source contains no cloud deployment, managed secret provider, automatic key rotation, external payment/inventory API or MCP transport. The included effect receipt is exactly once only within the transactional simulator.
