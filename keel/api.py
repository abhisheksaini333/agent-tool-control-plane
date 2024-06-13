"""Identity-scoped HTTP API; no endpoint accepts caller or tenant authority."""
from copy import deepcopy
import time
from typing import Annotated, Any
from fastapi import Depends, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, StrictStr, StrictInt
from .auth import AuthenticationError
from .policy import PolicyUnavailable
from .inventory import Inventory
from .http_boundary import HttpBoundary


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: StrictStr = Field(min_length=1, max_length=128)
    version: StrictStr = Field(min_length=1, max_length=20)
    arguments: dict[str, Any]


class ManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: StrictStr = Field(min_length=1, max_length=128)
    version: StrictStr = Field(min_length=1, max_length=20)
    handler: StrictStr = Field(min_length=1, max_length=40)
    description: StrictStr = Field(max_length=2000)
    input_schema: dict[str, Any] = Field(alias="schema")


class ActivationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: StrictStr = Field(min_length=1, max_length=20)


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: StrictInt = Field(ge=1)


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    revision: StrictInt = Field(ge=1)


def create_app(control, verifier, settings, clock=None):
    now = clock or time.time
    control.clock = now
    app = FastAPI(
        title="Keel tool control plane",
        docs_url="/api/docs" if settings.local_demo else None,
        redoc_url=None,
    )
    app.add_middleware(HttpBoundary)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
        allow_credentials=False,
    )
    bearer = HTTPBearer(auto_error=False)

    def actor(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
    ):
        if not credentials or credentials.scheme.lower() != "bearer":
            raise AuthenticationError("Sign in to continue")
        identity = verifier.verify(credentials.credentials)
        if identity.tenant not in settings.tenants:
            raise AuthenticationError("Tenant is not configured")
        return control.accounts.effective(identity)

    @app.exception_handler(AuthenticationError)
    async def authentication_error(request, error):
        return JSONResponse(
            {
                "error": "authentication_required",
                "message": "Sign in with a valid API session",
            },
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(PermissionError)
    async def permission_error(request, error):
        return JSONResponse(
            {"error": "permission_denied", "message": str(error)}, status_code=403
        )

    @app.exception_handler(LookupError)
    async def missing(request, error):
        return JSONResponse(
            {"error": "not_found", "message": "Request not found"}, status_code=404
        )

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse(
            {"error": "request_conflict", "message": str(error)}, status_code=409
        )

    @app.exception_handler(PolicyUnavailable)
    async def policy_unavailable(request, error):
        return JSONResponse(
            {
                "error": "policy_unavailable",
                "message": "Policy service unavailable; retry later",
            },
            status_code=503,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": "Request fields do not match the endpoint contract",
            },
            status_code=422,
        )

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "keel-api"}

    @app.get("/api/me")
    def me(identity=Depends(actor)):
        return identity.record()

    @app.get("/api/requests")
    def requests(limit: int = 100, identity=Depends(actor)):
        return [public_request(item) for item in control.list_requests(identity, limit)]

    @app.get("/api/requests/{request_id}")
    def request(request_id: str, identity=Depends(actor)):
        return public_request(control.get(identity, request_id))

    @app.post("/api/requests", status_code=201)
    def submit(
        body: Submission,
        identity=Depends(actor),
        idempotency_key: Annotated[str, Header(max_length=128)] = "",
    ):
        return public_request(
            control.submit(
                identity,
                body.tool,
                body.version,
                body.arguments,
                idempotency_key,
                now(),
            )
        )

    @app.post("/api/requests/{request_id}/approval")
    def approve(request_id: str, body: ApprovalInput, identity=Depends(actor)):
        return public_request(
            control.approve(identity, request_id, body.binding, body.revision, now())
        )

    @app.post("/api/requests/{request_id}/cancel")
    def cancel(request_id: str, body: RevisionInput, identity=Depends(actor)):
        return public_request(
            control.cancel(identity, request_id, body.revision, now())
        )

    @app.post("/api/requests/{request_id}/revoke")
    def revoke(request_id: str, body: RevisionInput, identity=Depends(actor)):
        return public_request(
            control.revoke(identity, request_id, body.revision, now())
        )

    def public_request(request):
        result = deepcopy(request)
        result["tool"] = public_tool(result["tool"])
        if result["lease"]:
            result["lease"].pop("token", None)
        return result

    def public_tool(tool):
        return {
            key: tool[key]
            for key in ("name", "version", "description", "schema", "risk", "digest")
        }

    @app.get("/api/tools")
    def tools(identity=Depends(actor)):
        if not identity.roles:
            raise PermissionError("Tool catalog permission required")
        active = control.store.list(identity.tenant, "active_tools")
        return [
            public_tool(
                control.registry.get(identity.tenant, item["name"], item["version"])
            )
            for item in active
            if item["enabled"]
        ]

    @app.get("/api/registry")
    def registry(identity=Depends(actor)):
        if not identity.roles & {"administrator", "auditor"}:
            raise PermissionError("Registry inspection permission required")
        return {
            "versions": [
                public_tool(item)
                for item in control.store.list(identity.tenant, "tools")
            ],
            "activations": control.store.list(identity.tenant, "active_tools"),
        }

    @app.post("/api/registry", status_code=201)
    def publish(body: ManifestInput, identity=Depends(actor)):
        return public_tool(
            control.registry.publish(identity, body.model_dump(by_alias=True))
        )

    @app.post("/api/registry/{name}/activate")
    def activate(name: str, body: ActivationInput, identity=Depends(actor)):
        return control.registry.activate(identity, name, body.version)

    @app.post("/api/registry/{name}/disable")
    def disable(name: str, identity=Depends(actor)):
        return control.registry.disable(identity, name)

    @app.get("/api/requests/{request_id}/audit")
    def request_audit(request_id: str, identity=Depends(actor)):
        control.get(identity, request_id)
        return [
            event
            for event in control.audit.list(identity.tenant)
            if event["request_id"] == request_id
        ]

    @app.get("/api/audit")
    def audit(identity=Depends(actor)):
        if not identity.roles & {"auditor", "administrator"}:
            raise PermissionError("Tenant audit permission required")
        return control.audit.list(identity.tenant)[-200:]

    @app.get("/api/inventory")
    def inventory(identity=Depends(actor)):
        if not identity.roles:
            raise PermissionError("Inventory inspection permission required")
        return Inventory(control.store).list(identity.tenant)

    return app
