# HTTP API

The demonstration API listens on `http://127.0.0.1:5484`. All `/api` operations require a Keycloak bearer access token for audience `keel-api`, issued to the registered console or demo CLI client. The server derives tenant and subject from the token and intersects token roles with current local account roles. It does not accept impersonation headers.

The browser uses authorization code with PKCE. The demonstration CLI client supports password grant only to make local integration checks reproducible; do not enable it as an application login mechanism.

| Method and path | Contract / access |
| --- | --- |
| `GET /health` | Process liveness; no authentication |
| `GET /ready` | Database, Redis, OPA and identity connectivity;503 if a dependency check fails |
| `GET /api/me` | Effective identity, roles and tenant-local display name |
| `GET /api/tools` | Active immutable tool contracts; any configured role |
| `GET /api/inventory` | Simulated inventory in the caller's tenant |
| `POST /api/requests` | Operator submission; `Idempotency-Key` required |
| `GET /api/requests?limit=100` | Newest visible requests; maximum200 |
| `GET /api/requests/{id}` | Requester sees own; approver, auditor or administrator sees tenant requests |
| `POST /api/requests/{id}/approval` | Independent current approver; exact binding and displayed revision |
| `POST /api/requests/{id}/cancel` | Original requester or administrator; displayed revision |
| `POST /api/requests/{id}/revoke` | Original approver or administrator; displayed revision |
| `GET /api/requests/{id}/audit` | Same visibility as the request |
| `GET /api/audit` | Most recent200 tenant events; auditor or administrator |
| `GET /api/registry` | Versions, activation generations and installed handler names; auditor or administrator |
| `POST /api/registry` | Publish an immutable version; administrator |
| `POST /api/registry/{name}/activate` | Activate an existing version; administrator |
| `POST /api/registry/{name}/disable` | Disable a registered active tool; administrator |

OpenAPI is at `/api/docs` only in explicit local demo mode. Worker lease tokens and credential aliases are omitted from public request and catalog representations. Display names are presentation fields; exact immutable subject IDs remain the authority.

## Submit, approve, inspect

Submission body:

```json
{
  "tool": "inventory.reserve",
  "version": "1.0.0",
  "arguments": {"sku": "KIT-EDGE", "quantity": 1}
}
```

Send `Idempotency-Key: a-unique-caller-scoped-key`. Keep the same key and identical body after a lost response. The server returns the original request, including its completion if already finished. Reusing a key with changed content returns409. If intent changes, use a new key. Successful submission returns201; approval-required requests start in `awaiting_approval`.

The reviewer must inspect the returned request and send its **exact** `binding` and `revision`:

```json
{
  "binding": "<the full 64-character binding from the displayed request>",
  "revision": 1
}
```

Approval does not accept edited arguments. It queues the request and gives the approval a maximum five-minute lifetime. A second approval, stale revision, changed binding or self-approval is rejected. The worker still rechecks current authority before dispatch and before committing the effect.

Cancel/revoke body: `{"revision": 2}` using the current revision. A completed effect cannot be cancelled or revoked. The successful cancellation response means that this request has not committed its effect; the transaction lock serializes that decision with completion.

A completion receipt contains request ID, tenant, caller, tool/version, binding, argument digest, completion time, attempt, verified output and optional simulator effect. Worker `memory_bytes` and `nano_cpus` describe configured limits, not measured peak consumption. The Docker diagnostic script measures actual throttling separately.

## Publish a contract

```json
{
  "name": "text.digest",
  "version": "1.0.1",
  "handler": "sha256",
  "description": "Hash up to 1000 characters of text.",
  "schema": {
    "type": "object",
    "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 1000}},
    "required": ["text"],
    "additionalProperties": false
  }
}
```

A schema is a deliberately restricted, bounded JSON Schema subset: closed objects, bounded strings and arrays, primitive types and limited nesting. `$ref`, regex and composition features are excluded. The installed worker independently checks its handler contract. Publishing identical content at an existing version is idempotent; changing it is prohibited.

Activation body: `{"version":"1.0.1"}`. Every activation, even reactivating the same version, increments the generation and invalidates earlier requests for that tool at their next authorization check. Disabling also increments generation. Publishing alone leaves activation unchanged.

## Failure behavior

| Status | Meaning / response |
| --- | --- |
|401 | Missing, invalid or expired API session; sign in again |
|403 | Current identity, policy or reviewer permissions deny the operation |
|404 | Request absent or outside the caller's permitted tenant/visibility |
|409 | Revision, binding, version, input contract or idempotency conflict; inspect current state before retrying |
|422 | HTTP body fields do not match the endpoint contract |
|429 | Mutation rate exceeded; respect `Retry-After` |
|503 | Admission or policy service unavailable; changes fail closed |

The API accepts at most64KiB per request body and never echoes invalid field values in validation errors. Redis limits each caller to30 mutations per60-second window by default. GET inspection stays available during a Redis outage. OPA decisions fail closed. Unhandled infrastructure failures may return500; operators should inspect private service logs and restore dependencies rather than retrying with a new idempotency key.
