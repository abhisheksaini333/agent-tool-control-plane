"""Identity-scoped HTTP API; no endpoint accepts caller or tenant authority."""
import time
from typing import Annotated, Any
from fastapi import Depends, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from .auth import AuthenticationError
from .policy import PolicyUnavailable


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: StrictStr = Field(min_length=1, max_length=128)
    version: StrictStr = Field(min_length=1, max_length=20)
    arguments: dict[str, Any]


def create_app(control, verifier, settings, clock=None):
    now = clock or time.time
    control.clock = now
    app = FastAPI(
        title="Keel tool control plane",
        docs_url="/api/docs" if settings.local_demo else None,
        redoc_url=None,
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
        return control.list_requests(identity, limit)

    @app.get("/api/requests/{request_id}")
    def request(request_id: str, identity=Depends(actor)):
        return control.get(identity, request_id)

    @app.post("/api/requests", status_code=201)
    def submit(
        body: Submission,
        identity=Depends(actor),
        idempotency_key: Annotated[str, Header(max_length=128)] = "",
    ):
        return control.submit(
            identity, body.tool, body.version, body.arguments, idempotency_key, now()
        )

    return app
