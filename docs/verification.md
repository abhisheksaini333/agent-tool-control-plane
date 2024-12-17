# Verification and practical limits

The local acceptance run exercised the running product, including real identity, policy, storage and constrained worker processes. The final backend suite passed **133 tests with no skips in23.71seconds**. The console passed **8 Node contracts**, its formatting check and strict TypeScript/production build. **6 actual browser journeys passed in26.8seconds**, and **5 OPA policy tests passed**.

## Acceptance matrix

| Capability | Proof |
| --- | --- |
| Typed registry and strict canonical arguments | Unit contracts reject unknown fields, invalid numeric/string bounds, unsupported schema features and immutable-version edits |
| Actual identity and current roles | Real Keycloak tokens pass RSA/issuer/audience checks; API and registry tests reject invalid tokens, cross-tenant reads and revoked local administrators |
| Policy before dispatch | Actual OPA process tests allow/deny/independent approval; malformed or unavailable decisions fail closed |
| Exact human approval | API and domain tests reject edited arguments/bindings, wrong reviewer, self-approval, stale revisions, expired/revoked approval and replay |
| One simulated effect | Actual signed Docker intent commits stock and receipt in PostgreSQL; repeated approval and identical submission do not create another effect |
| Worker ownership and recovery | Separate claimant process exits abruptly after durable claim; replacement gets fence2 and old completion is denied. PostgreSQL concurrent-claim and transaction-fault tests preserve one effect |
| Cancellation and revocation | Domain race tests prevent completion after cancellation/revocation; browser cancellation produces an audit event and no receipt |
| CPU, memory, deadline, network | Real Docker probes measure cgroup limits, throttling, OOM termination, deadline cleanup, denied egress and read-only root |
| Scoped credentials | Real container sees one selected key file, no key in environment, no other aliases and no Docker socket; HMAC and protocol binding are independently verified |
| Browser session lifecycle | Real PKCE login, memory-only tokens, issuer logout and a credential prompt for the next user |
| Operator/reviewer workflow | Alice requests inventory; Bob acknowledges exact arguments and approves; verified receipt and completion audit render without page errors |
| Registry console | Administrator publishes, activates and disables a new immutable contract; auditor can inspect but cannot mutate |
| Browser recovery | An intentionally lost successful POST response retries the same request ID; delayed polling cannot overwrite new selection;390px mobile view has no horizontal overflow |
| Backup/restore | Consistent PostgreSQL snapshot restores67 identical document rows into a new disposable DB;2 receipts and2 reservations remain linked and tenant audit chains verify |
| Restart persistence | PostgreSQL, API and worker restart preserves both pre-existing receipt IDs and exact stock values without repeating an effect |

The restore and restart checks ran before the final browser suite, which created another legitimate simulated reservation and cancellation. Their counts describe the captured snapshot, not a perpetual fixed database size. Failed earlier browser probes also leave their own pending/terminal requests and audit records; acceptance does not erase history to make the workspace appear empty.

## Measured sandbox behavior

The verification host is an Apple M3 Pro with11 logical CPUs and18GiB RAM. Docker runs Linux containers using cgroupv2. The host application was validated with Python3.10.21, Node20.10.0 and Chrome154.0.8037.92; workers use the pinned Python3.10.11 image, and CI targets Python3.10.11. These are the actual validation environments.

| Probe | Observed result |
| --- | --- |
| CPU limit | `cpu.max = 25000 100000`;0.748CPU seconds over3.002wall seconds;30 throttled periods |
| Memory limit |67,108,864bytes; deliberate allocation ended with `OOMKilled=true`, exit137 |
| Process/file limits |32 processes and64 open file descriptors configured and observed |
| Deadline | Sleep probe terminated with `worker_timeout` after approximately3.038seconds including cleanup |
| Network | Outbound socket failed with errno101; Docker network mode `none` |
| Root filesystem | Write attempt failed with errno30; read-only root enabled |
| Privileges | UID501, effective capabilities0, `no_new_privileges=1` |
| Credentials | Only `/run/credential/key`; no credential environment value, sibling key alias or Docker socket |

These are bounded local measurements, not a throughput/SLA benchmark. Worker startup contributes to elapsed time, and the receipt's memory/CPU fields report configured limits. A host crash can require orphan-container cleanup. The threat boundary and database serialization limits are described in [architecture](architecture.md).

## Reproduce restore verification

With the local PostgreSQL container running:

```sh
KEEL_LOCAL_DEMO=1 .venv/bin/python -m scripts.verify_restore \
  --backup .runtime/backups/keel-check.dump \
  --output .runtime/restore-report.json
```

Choose a new backup filename for each run; the helper refuses to overwrite an existing file and creates it with0600 permissions. It exports a repeatable-read snapshot, dumps that snapshot, restores only into a generated `keel_restore_<uuid>` database, compares document fingerprints, checks audit chains and receipt/effect links, then drops only that generated target. The source database is never replaced. The private dump remains for operator retention. If a restore step fails, the helper still attempts to remove its own generated database.

To reproduce the actual process-death and PostgreSQL transaction checks:

```sh
KEEL_TEST_DATABASE_URL=postgresql://keel:keel-local-only@127.0.0.1:56484/keel \
  .venv/bin/python -m pytest -q tests/test_process_recovery.py tests/test_postgres.py
```

The crash test uses a deliberately shortened0.1-second lease to exercise real process death without a minute-long test delay. Production leases remain60seconds. Its policy/result fixtures isolate durable ownership behavior; the separate `test_real_execution.py` and browser/API acceptance prove actual OPA and Docker execution.

## Evidence and limits

The verification commands and assertions are committed in `tests/`, `web/e2e/`, `policy/` and `scripts/`. Generated logs, screenshots, JSON reports and private database dumps remain outside source control. Browser acceptance uses real Keycloak and the actual service; deterministic policy/runner fixtures are restricted to tests.

A bounded independent review found a revoked-administrator registry race, which was reproduced and fixed by checking current account authority inside the mutation transaction. A later independent authentication review found no confirmed defect in the inspected PKCE, token verification, refresh and logout paths. Reviews and passing tests are bounded evidence, not a general security certification.

GitHub Actions is configured with immutable action SHAs, exact dependency locks and an opt-in actual-stack job. A hosted workflow run has not been claimed. No external business provider, cloud production deployment, scale target, arbitrary untrusted-code sandbox or MCP conformance has been verified. Exactly-once effects are limited to the included PostgreSQL transaction boundary.
