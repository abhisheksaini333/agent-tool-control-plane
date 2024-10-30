#!/usr/bin/env bash
# Run only against this repository's loopback demonstration stack.
set -euo pipefail
: "${OPA_BIN:?Set OPA_BIN to an absolute path to OPA0.60.0}"
project="${KEEL_COMPOSE_PROJECT:-keel-ci}"
processes=()
cleanup() {
  for process in "${processes[@]}"; do kill -TERM "$process" 2>/dev/null || true; done
  docker compose -p "$project" stop >/dev/null
}
trap cleanup EXIT INT TERM
export KEEL_LOCAL_DEMO=1
mkdir -p .runtime/ci
chmod 700 .runtime .runtime/ci

docker compose -p "$project" up -d
docker build -t keel-worker:local worker
"$OPA_BIN" run --server --addr 127.0.0.1:8295 --log-level error policy/control.rego >.runtime/ci/opa.log 2>&1 &
processes+=("$!")
python - <<'PY'
import time, httpx
for _ in range(180):
    try:
        response = httpx.get('http://localhost:8294/realms/keel/.well-known/openid-configuration',timeout=2,trust_env=False)
        if response.status_code == 200:
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise SystemExit('Keycloak did not become ready within the startup budget')
PY
python -m keel.cli seed
python -m keel.cli serve >.runtime/ci/api.log 2>&1 &
processes+=("$!")
python -m keel.cli worker >.runtime/ci/worker.log 2>&1 &
processes+=("$!")
(cd web && exec node server.mjs) >.runtime/ci/web.log 2>&1 &
processes+=("$!")
python - <<'PY'
import time, httpx
for _ in range(30):
    try:
        if httpx.get('http://127.0.0.1:5484/ready',timeout=5,trust_env=False).status_code == 200:
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise SystemExit('API readiness check failed')
PY
export KEEL_TEST_DATABASE_URL=postgresql://keel:keel-local-only@127.0.0.1:56484/keel
export KEEL_TEST_REDIS_URL=redis://127.0.0.1:6394/0
export KEEL_TEST_OIDC_ISSUER=http://localhost:8294/realms/keel
export KEEL_DOCKER_TESTS=1
python -m pytest -q
python -m scripts.verify_api --output .runtime/ci/api-acceptance.json
python -m scripts.verify_isolation --output .runtime/ci/isolation.json
npm --prefix web run test:browser
