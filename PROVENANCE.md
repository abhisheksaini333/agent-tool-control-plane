# Dependency and protocol provenance

The HTTP/JSON implementation targets Python3.10 and the exact33package profile in `requirements.lock`. Every selected package and artifact was verified against its PyPI release JSON before the lock was committed; all are available by January1,2024. FastAPI0.104.1, Pydantic2.5.3, HTTPX0.25.2, psycopg2-binary2.9.9, redis5.0.1, jsonschema4.20.0, PyJWT2.8.0, cryptography41.0.7 and pytest7.4.3 are direct/runtime dependencies. Installation: `python3.10 -m venv .venv` followed by `.venv/bin/pip install -r requirements.lock`.

OPA0.60.0 uses its versioned Rego/HTTP API: [official release](https://github.com/open-policy-agent/opa/releases/tag/v0.60.0), December21,2023. The local verification binary is the original darwin/arm64 artifact with the publisher's SHA256 checked. Node20.10.0 is from the [official November22,2023 release](https://nodejs.org/en/blog/release/v20.10.0). No MCP adapter is included.

Platform-specific Linux image artifacts receive a separate installation and release audit before container acceptance. Exact image/source identifiers and additional UI dependencies are recorded as those integrations are introduced.

PostgreSQL uses the existing `postgres:13.5-alpine` image, [server13.5 released November11,2021](https://www.postgresql.org/docs/release/13.5/). The actual container reports13.5. It is a reproducible local demonstration baseline, not a recommendation to deploy an unsupported old database. Runtime image IDs and digests are captured with the acceptance evidence.

The dependency-free worker is built from `python:3.10.11-slim-bullseye` at manifest `sha256:fd86924ba14682eb11a3c244f60a35b5dfe3267cbf26d883fb5c14813ce926f1`. The cached ARM64 base was created May23,2023; actual worker execution is verified under Docker. No packages are installed into this worker image.
