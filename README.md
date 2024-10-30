# Keel · Agent tool control plane

Keel gives tool calls a controlled path from request to execution. An operator chooses a typed tool version, an independent reviewer approves effects, and a constrained worker returns a verified result. Every completed action has a durable receipt and an audit trail.

The included inventory simulator demonstrates an actual effect: reserving stock. PostgreSQL commits the reservation and receipt in one transaction. Text hashing and report signing demonstrate tools that do not change business state.

## What you can do

- Sign in through Keycloak using authorization code with PKCE. Permissions combine verified tenant/user claims with current local account state.
- Request a registered, versioned JSON contract. OPA decides whether the caller may invoke it and whether independent approval is required.
- Review exact arguments, caller, tool version, expiry and immutable request binding. Cancel a request or revoke approval before its effect commits.
- Execute trusted handlers in Docker with denied network access, a read-only root filesystem, non-root identity, bounded CPU/memory/processes and a deadline.
- Inspect receipts, worker limits and scoped audit events. Administrators can publish immutable versions and explicitly activate or disable them.
- Recover abandoned leases without letting an old worker commit, retry transient failures within a fixed budget, and reject repeated or altered approvals.

This is an HTTP/JSON control plane. It does not implement MCP, load arbitrary tool code or execute user-supplied commands.

## Local launch

Requirements: Python3.10, Node20.10, Docker with Compose, and OPA0.60.0. Use the original OPA binary for your OS from the [official release](https://github.com/open-policy-agent/opa/releases/tag/v0.60.0) and verify its published checksum. Run the host processes as a normal user with Docker access; the runner refuses UID0. The pinned dependencies and image provenance are in [PROVENANCE.md](PROVENANCE.md).

From the repository root:

```sh
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix web ci --ignore-scripts --no-audit --no-fund
npm --prefix web run build
docker compose -p keel-control up -d
docker build -t keel-worker:local worker
```

Start OPA in a terminal and leave it running:

```sh
opa run --server --addr 127.0.0.1:8295 --log-level error policy/control.rego
```

When the Keycloak realm is available at `http://localhost:8294/realms/keel/.well-known/openid-configuration`, seed the explicit demonstration. This generates private per-tool keys under ignored `.runtime/credentials`; rerunning seed preserves existing accounts, stock, tool activation and keys.

```sh
export KEEL_LOCAL_DEMO=1
.venv/bin/python -m keel.cli seed
.venv/bin/python -m keel.cli check
.venv/bin/python -m keel.cli serve
```

In another terminal, from the same directory:

```sh
KEEL_LOCAL_DEMO=1 .venv/bin/python -m keel.cli worker
```

In one more terminal:

```sh
npm --prefix web start
```

Open **http://localhost:5294/**. Use `localhost` for the console because the OIDC redirect is registered to that exact origin. Initial Keycloak startup can take a few minutes, especially when its AMD64 image runs under ARM64 emulation.

| Demo login | Person / tenant | Permissions |
| --- | --- | --- |
| `alice` | Alice Chen / acme | Request tools; inspect and cancel own requests |
| `bob` | Bob Rivera / acme | Independently approve and revoke approvals |
| `clara` | Clara Okafor / acme | Administer registry; inspect workspace audit |
| `auditor` | Morgan Lee / acme | Read workspace requests, registry and audit |
| `north-operator` | north | Request tools in the separate tenant |
| `north-reviewer` | north | Approve within north |
| `north-admin` | north | Administer north |

All demonstration accounts use `keel-demo-password`. These accounts, the password-grant test client and the Compose credentials are for the loopback demonstration only. The browser client does not permit password grant.

Try a full action: sign in as Alice, create an `inventory.reserve` request for one unit of `KIT-EDGE`, then sign out. Sign in as Bob, select that request, inspect its exact arguments, check the review acknowledgment and approve. The worker produces a signed intent; the service commits one reservation and displays the receipt. Signing out ends the Keycloak session as well as clearing browser memory.

## Verification

Fast deterministic contracts:

```sh
.venv/bin/python -m pytest -q
npm --prefix web test
npm --prefix web run build
opa test policy -v
```

With the local stack running:

```sh
export OPA_BIN="$(command -v opa)"
export KEEL_DOCKER_TESTS=1
export KEEL_TEST_DATABASE_URL=postgresql://keel:keel-local-only@127.0.0.1:56484/keel
export KEEL_TEST_REDIS_URL=redis://127.0.0.1:6394/0
export KEEL_TEST_OIDC_ISSUER=http://localhost:8294/realms/keel
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.verify_isolation --output .runtime/isolation.json
.venv/bin/python -m scripts.verify_api --output .runtime/api-acceptance.json
```

The API acceptance script creates one simulated reservation each time it runs. Actual database tests use disposable schemas. Container probes intentionally trigger an OOM and deadline failures inside isolated test workers.

Install the browser for the pinned Playwright version with `(cd web && npx playwright install chromium)`, then run `npm --prefix web run test:browser`. On macOS, an existing Chrome installation can be selected using `CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'`. Browser tests create requests and a disabled temporary tool version; they preserve their audit records. Failed-test traces may include demo tokens, so keep `web/test-results` private and uncommitted.

GitHub Actions runs contracts and builds on pushes and pull requests. Its manually enabled integration job exercises the actual stack through `scripts/ci-integration.sh`. That script needs free local ports and owns a separate Compose project; do not run it alongside an existing Keel stack on the same ports. Hosted CI execution is distinct from the retained local acceptance evidence.

## Design and operations

See [architecture](docs/architecture.md), [operator runbook](docs/operations.md), [API contracts](docs/api.md) and [verification evidence](docs/verification.md).

Keel is a bounded local implementation. Mutations serialize through a PostgreSQL advisory transaction lock; it is not a throughput benchmark or a highly available deployment. Docker administration and the host runner are privileged trust boundaries. Exactly-once effect claims apply to the included transactional simulator, not arbitrary external APIs. A production deployment needs maintained dependencies, managed identity and secrets, encrypted transport, durable backups, external audit anchoring and an explicit operational capacity review.
