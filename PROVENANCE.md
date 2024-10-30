# Dependency and protocol provenance

The HTTP/JSON implementation targets Python3.10 and the exact33package profile in `requirements.lock`. Every selected package and artifact was verified against its PyPI release JSON before the lock was committed; all are available by January1,2024. FastAPI0.104.1, Pydantic2.5.3, HTTPX0.25.2, psycopg2-binary2.9.9, redis5.0.1, jsonschema4.20.0, PyJWT2.8.0, cryptography41.0.7 and pytest7.4.3 are direct/runtime dependencies. Installation: `python3.10 -m venv .venv` followed by `.venv/bin/pip install -r requirements.lock`.

OPA0.60.0 uses its versioned Rego/HTTP API: [official release](https://github.com/open-policy-agent/opa/releases/tag/v0.60.0), December21,2023. The local verification binary is the original darwin/arm64 artifact with the publisher's SHA256 checked. Node20.10.0 is from the [official November22,2023 release](https://nodejs.org/en/blog/release/v20.10.0). No MCP adapter is included.

Platform-specific Linux image artifacts receive a separate installation and release audit before container acceptance. Exact image/source identifiers and additional UI dependencies are recorded as those integrations are introduced.

PostgreSQL uses the existing `postgres:13.5-alpine` image, [server13.5 released November11,2021](https://www.postgresql.org/docs/release/13.5/). The actual container reports13.5. It is a reproducible local demonstration baseline, not a recommendation to deploy an unsupported old database. Runtime image IDs and digests are captured with the acceptance evidence.

The dependency-free worker is built from `python:3.10.11-slim-bullseye` at manifest `sha256:fd86924ba14682eb11a3c244f60a35b5dfe3267cbf26d883fb5c14813ce926f1`. The cached ARM64 base was created May23,2023; actual worker execution is verified under Docker. No packages are installed into this worker image.

Redis uses the cached `redis:7.0.11-alpine` artifact, created before January1,2024. Its actual server version and image digest are captured in acceptance evidence. Admission counters are disposable; PostgreSQL retains all execution and receipt state.

Keycloak18.0.2 uses image digest `sha256:b4841a7b8401fd209bfcddf10773cdfa7c7cfde4bf7e87780663226be5587ee2`, created June24,2022. The local AMD64 image runs under Docker emulation on ARM64. Actual issued tokens passed RSA/issuer/audience verification. The console uses authorization code with S256 PKCE; a separate demo-only CLI client supports integration checks.

The console uses React18.2.0, TypeScript4.9.5 and esbuild0.17.14, with Playwright1.31.2 for browser acceptance. The complete38-version npm lock, including every optional platform binary, was independently checked against npm publication times before commit; all are available before January1,2024. Node20.10.0 runs the build and the dependency-free static server.

The CI workflow pins `actions/checkout` v4.1.1 (`b4ffde65f46336ab88eb53be808477a3936bae11`, October17,2023), `actions/setup-python` v4.7.1 (`65d7f2d534ac1bc67fcd62888c5f4f3d2cb2b236`, October2,2023), and `actions/setup-node` v3.8.1 (`5e21ff4d9bc1a8cf6de233a3057d20ec6b3fb69d`, August17,2023). Sources: [checkout release](https://github.com/actions/checkout/releases/tag/v4.1.1), [Python action release](https://github.com/actions/setup-python/releases/tag/v4.7.1), [Node action release](https://github.com/actions/setup-node/releases/tag/v3.8.1). All33 resolved LinuxAMD64/Python3.10 wheel artifacts were separately checked against their exact PyPI upload timestamps and hashes. The worker's pinned Python digest is a multi-platform manifest including AMD64 and ARM64. CI checks the OPA LinuxAMD64 static binary against publisher SHA256 `7d7cb45d9e6390646e603456503ca1232180604accc646de823e4d2c363dbeb0`.
