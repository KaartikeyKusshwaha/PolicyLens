import asyncio
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agents import AgentEngine
from auth import Credentials, Hub, Invite, Join, PasswordReset, Setup
from config import ROOT, Settings
from intelligence import Intelligence, SOURCES
from models import (
    Answer,
    Assessment,
    EvaluationRequest,
    PolicyInput,
    QueryInput,
    ReviewInput,
)
from operations import Operations, audit
from product_models import NamedWorkspace
from providers import extract_document, problem, verify_citations
from store import Store, now
from database import INTEGRITY_ERRORS, STORAGE_ERRORS, encryption_status
from runtime import InstallationLock
from retention_api import router as retention_router

logger = logging.getLogger("policylens")


def require_roles(request, *roles):
    if request.state.user["role"] not in roles:
        raise problem(
            403, "role_required", "Your workspace role does not allow this action."
        )


def create_app(settings=None, transport=None, *, start_worker=True):
    settings = settings or Settings()

    @asynccontextmanager
    async def application_state(app):
        app.state.settings = settings
        app.state.hub = Hub(settings)
        with app.state.hub.connect() as db:
            registered_paths = [
                row[0] for row in db.execute("SELECT db_path FROM organizations")
            ]
        if any(not Path(path).is_file() for path in registered_paths):
            raise RuntimeError(
                "A registered workspace database is missing. Restore the installation before starting; no replacement workspace database was created."
            )
        app.state.store = Store(settings.database_path, settings)
        Operations(app.state.store)
        if app.state.hub.needs_setup():
            logger.warning(
                "First workspace setup required. Bootstrap key file: %s",
                app.state.hub.bootstrap_file,
            )
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "PolicyLens/3.0"},
        ) as client:
            app.state.client = client
            app.state.providers = Intelligence(settings, app.state.store, client)
            app.state.engine = AgentEngine(app.state.hub, settings, client)
            app.state.checkpoints = app.state.engine.checkpoints
            app.state.sync_locks = {}
            worker = (
                asyncio.create_task(app.state.engine.loop()) if start_worker else None
            )
            app.state.worker = worker
            yield
            if worker:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker

    @asynccontextmanager
    async def lifespan(app):
        with InstallationLock(settings.database_path.parent):
            async with application_state(app):
                yield

    public_deployment = settings.deployment_mode == "public"
    app = FastAPI(
        title="PolicyLens Operations",
        version="3.0.0",
        lifespan=lifespan,
        docs_url=None if public_deployment else "/docs",
        redoc_url=None if public_deployment else "/redoc",
        openapi_url=None if public_deployment else "/openapi.json",
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            v.strip() for v in settings.allowed_hosts.split(",") if v.strip()
        ],
    )
    public = {
        "/api/health",
        "/api/ready",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/password-reset",
        "/api/auth/setup",
        "/api/auth/join",
    }

    @app.middleware("http")
    async def security(request, call_next):
        path = request.url.path
        writing = request.method not in ("GET", "HEAD", "OPTIONS")
        try:
            if (
                public_deployment
                and request.url.scheme != "https"
                and path not in ("/api/health", "/api/ready")
            ):
                raise problem(
                    403,
                    "https_required",
                    "Public deployments require HTTPS. Configure your trusted reverse proxy before signing in.",
                )
            if (
                request.headers.get("content-length", "").isdigit()
                and int(request.headers["content-length"]) > 6_000_000
            ):
                raise problem(413, "request_too_large", "Request body exceeds 6 MB.")
            if (
                writing
                and path.startswith("/api/")
                and not path.startswith("/api/webhooks/")
            ):
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 6_000_000:
                        raise problem(
                            413, "request_too_large", "Request body exceeds 6 MB."
                        )
                request._body = bytes(body)
            if path.startswith("/api/") and not path.startswith("/api/webhooks/"):
                origin = request.headers.get("origin")
                if (
                    writing
                    and origin
                    and (
                        urlparse(origin).netloc != request.headers.get("host")
                        or urlparse(origin).scheme != request.url.scheme
                    )
                ):
                    raise problem(
                        403, "origin_denied", "Cross-origin mutations are not allowed."
                    )
                if writing and request.headers.get("sec-fetch-site") == "cross-site":
                    raise problem(
                        403, "origin_denied", "Cross-site mutations are not allowed."
                    )
                authorization = request.headers.get("authorization", "")
                if path.startswith("/api/toolkit/") or authorization.startswith(
                    "Bearer "
                ):
                    token = (
                        authorization[7:] if authorization.startswith("Bearer ") else ""
                    )
                    user = app.state.hub.agent_keys.authenticate(token)
                    if not path.startswith("/api/toolkit/"):
                        with app.state.hub.store(user["org_id"]).connect() as db:
                            audit(
                                db,
                                user["id"],
                                "agent_route_denied",
                                {"path": path[:160], "method": request.method},
                            )
                        raise problem(
                            403,
                            "agent_route_denied",
                            "Agent keys can use only the governed toolkit endpoints.",
                        )
                else:
                    user = app.state.hub.authenticate(
                        request.cookies.get("policylens_session")
                    )
                request.state.user = user
                if path not in public:
                    if not user:
                        raise problem(
                            401, "authentication_required", "Sign in to your workspace."
                        )
                    if (
                        writing
                        and not user.get("agent_key")
                        and not hmac.compare_digest(
                            request.headers.get("x-csrf-token", "").encode(),
                            user["csrf"].encode(),
                        )
                    ):
                        raise problem(
                            403,
                            "csrf_required",
                            "Refresh your session before submitting this action.",
                        )
                    if (
                        writing
                        and user["role"] == "auditor"
                        and not path.startswith("/api/auth/")
                    ):
                        raise problem(
                            403, "read_only_role", "Auditor access is read-only."
                        )
                if user:
                    request.state.store = app.state.hub.store(user["org_id"])
                    request.state.ops = Operations(request.state.store)
                    request.state.providers = Intelligence(
                        settings, request.state.store, app.state.client
                    )
                    if user.get("agent_key"):
                        with request.state.store.connect() as db:
                            audit(
                                db,
                                user["id"],
                                "tool_request_received",
                                {
                                    "path": path[:160],
                                    "method": request.method,
                                    "key_id": user["agent_key"],
                                },
                            )
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        except STORAGE_ERRORS:
            if path != "/api/ready":
                raise
            response = JSONResponse({"status": "not_ready"}, status_code=503)
        agent_user = getattr(request.state, "user", None)
        if (
            agent_user
            and agent_user.get("agent_key")
            and response.status_code >= 400
            and getattr(request.state, "store", None) is not None
        ):
            with request.state.store.connect() as db:
                audit(
                    db,
                    agent_user["id"],
                    "tool_http_rejected",
                    {"path": path[:160], "status": response.status_code},
                )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        if path not in ("/docs", "/redoc", "/docs/oauth2-redirect"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; connect-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
                "object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            )
        if public_deployment and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.exception("Request failed: %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "internal_error",
                    "message": "The operation failed. Check server logs; no substitute result was generated.",
                }
            },
        )

    def set_session(response, user_id, org_id):
        token, user = app.state.hub.session(user_id, org_id)
        response.set_cookie(
            "policylens_session",
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=settings.session_hours * 3600,
            path="/",
        )
        return user

    app.state.set_session = set_session

    @app.get("/api/auth/status")
    def auth_status():
        return {
            "setup_required": app.state.hub.needs_setup(),
            "registration": "invite_only",
            "bootstrap_file": "backend/data/.bootstrap-token",
        }

    @app.post("/api/auth/setup", status_code=201)
    def setup(data: Setup, request: Request):
        app.state.hub.throttle(
            "setup:" + (request.client.host if request.client else "unknown")
        )
        user_id, org_id = app.state.hub.setup(data)
        result = JSONResponse({}, status_code=201)
        user = set_session(result, user_id, org_id)
        result.body = JSONResponse(user).body
        result.headers["content-length"] = str(len(result.body))
        return result

    @app.post("/api/auth/login")
    def login(data: Credentials, request: Request):
        app.state.hub.throttle(
            "login:" + (request.client.host if request.client else "unknown")
        )
        user_id, org_id = app.state.hub.login(data)
        result = JSONResponse({})
        user = set_session(result, user_id, org_id)
        result.body = JSONResponse(user).body
        result.headers["content-length"] = str(len(result.body))
        return result

    @app.post("/api/auth/join", status_code=201)
    def join(data: Join, request: Request):
        app.state.hub.throttle(
            "join:" + (request.client.host if request.client else "unknown")
        )
        user_id, org_id = app.state.hub.join(data)
        result = JSONResponse({}, status_code=201)
        user = set_session(result, user_id, org_id)
        result.body = JSONResponse(user).body
        result.headers["content-length"] = str(len(result.body))
        return result

    @app.post("/api/auth/password-reset")
    def reset_password(data: PasswordReset, request: Request):
        app.state.hub.throttle(
            "reset:" + (request.client.host if request.client else "unknown")
        )
        app.state.hub.throttle("reset-email:" + data.email)
        result = JSONResponse(app.state.hub.reset_password(data))
        result.delete_cookie("policylens_session", path="/")
        return result

    @app.get("/api/auth/me")
    def me(request: Request):
        return request.state.user

    @app.post("/api/auth/logout")
    def logout(request: Request):
        app.state.hub.logout(request.cookies.get("policylens_session"))
        result = JSONResponse({"signed_out": True})
        result.delete_cookie("policylens_session", path="/")
        return result

    @app.get("/api/auth/workspaces")
    def workspaces(request: Request):
        return app.state.hub.organizations(request.state.user["id"])

    @app.post("/api/auth/workspaces", status_code=201)
    def new_workspace(data: NamedWorkspace, request: Request):
        require_roles(request, "admin")
        org_id = app.state.hub.create_workspace(request.state.user["id"], data.name)
        return {"id": org_id, "name": data.name}

    @app.post("/api/auth/workspaces/{org_id}/switch")
    def switch_workspace(org_id: str, request: Request):
        app.state.hub.switch(
            request.cookies["policylens_session"], request.state.user["id"], org_id
        )
        return {"switched": True}

    @app.get("/api/team")
    def team(request: Request):
        return app.state.hub.team(request.state.user["org_id"])

    @app.post("/api/team/invites", status_code=201)
    def invite(data: Invite, request: Request):
        require_roles(request, "admin")
        result = app.state.hub.invite(request.state.user["org_id"], data)
        with request.state.store.connect() as db:
            audit(
                db,
                request.state.user["id"],
                "member_invited",
                {"email": result["email"], "role": result["role"]},
            )
        return result

    @app.get("/api/health")
    def health(request: Request):
        base = {"status": "ok", "version": "3.0.0", "storage": "sqlite_fts5"}
        if not request.state.user:
            return base
        provider = request.state.providers
        return {
            **base,
            "ai": {
                "status": "configured" if provider.ai_configured else "needs_key",
                "model": settings.groq_model,
            },
            "sanctions": provider.sanctions_status(),
            "api_docs_enabled": not public_deployment,
            "database_encryption": encryption_status(settings),
            "external_checkpoints": app.state.checkpoints.status(
                request.state.user["org_id"]
            ),
            "agent_worker": "disabled"
            if app.state.worker is None
            else "failed"
            if app.state.worker.done()
            else "running",
        }

    @app.get("/api/ready")
    def readiness():
        worker = app.state.worker
        try:
            with app.state.hub.connect() as db:
                db.execute("SELECT 1 FROM organizations LIMIT 1").fetchone()
            if worker is not None and worker.done():
                return JSONResponse({"status": "not_ready"}, status_code=503)
            if (
                settings.checkpoint_directory is not None
                and app.state.checkpoints.errors
            ):
                return JSONResponse({"status": "not_ready"}, status_code=503)
        except STORAGE_ERRORS:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    @app.get("/api/dashboard")
    def dashboard(request: Request):
        store = request.state.store
        return {
            **store.dashboard(),
            "policies": len(store.policies()),
            "recent": store.decisions(6),
            "health": health(request),
            "operations": request.state.ops.analytics(),
        }

    @app.get("/api/policies")
    def policies(request: Request):
        return request.state.store.policies()

    def record_policy(data, request, policy_id=None):
        try:
            result = request.state.store.save_policy(data, policy_id)
        except ValueError as exc:
            raise problem(409, "version_conflict", str(exc)) from exc
        with request.state.store.connect() as db:
            audit(
                db,
                request.state.user["id"],
                "policy_updated" if policy_id else "policy_added",
                {"policy_id": result["id"], "version": result["version"]},
            )
        return result

    @app.post("/api/policies", status_code=201)
    def add_policy(data: PolicyInput, request: Request):
        return record_policy(data, request)

    @app.post("/api/policies/file", status_code=201)
    async def upload_policy(
        request: Request,
        file: UploadFile = File(...),
        title: str = Form(...),
        topic: str = Form("general"),
        version: str = Form("1.0"),
        source_url: str = Form(""),
    ):
        try:
            content = await file.read(5_000_001)
            if len(content) > 5_000_000:
                raise problem(413, "file_too_large", "Files are limited to 5 MB.")
            text = await run_in_threadpool(
                extract_document, content, file.filename or ""
            )
            data = PolicyInput(
                title=title,
                content=text,
                topic=topic,
                version=version,
                source_url=source_url,
            )
        except ValidationError as exc:
            raise problem(
                422,
                "invalid_document",
                "Use a title and 50–300,000 characters of selectable policy text. Scanned PDFs need OCR before upload.",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise problem(
                422,
                "unreadable_document",
                "Could not read the file. Use an unencrypted text-based PDF, DOCX, or UTF-8 TXT file.",
            ) from exc
        finally:
            await file.close()
        return record_policy(data, request)

    @app.get("/api/policies/{policy_id}")
    def policy(policy_id: str, request: Request):
        result = request.state.store.policy(policy_id)
        if not result:
            raise problem(404, "not_found", "Policy not found.")
        return result

    @app.put("/api/policies/{policy_id}")
    def update_policy(policy_id: str, data: PolicyInput, request: Request):
        policy(policy_id, request)
        return record_policy(data, request, policy_id)

    @app.get("/api/sources")
    def sources(request: Request):
        provider = request.state.providers
        return {
            "groq": {
                "status": "configured" if provider.ai_configured else "needs_key",
                "model": settings.groq_model,
                "url": "https://console.groq.com/docs/rate-limits",
            },
            "ofac": provider.status("ofac"),
            "feeds": [provider.status(s) for s in SOURCES],
            "enabled_sources": provider.selected_sources(),
            "frankfurter": {"status": "on_demand", "url": "https://frankfurter.dev/"},
            "gleif": {
                "status": "on_demand",
                "url": "https://www.gleif.org/en/lei-data/gleif-api/",
            },
            "max_age_hours": settings.sanctions_max_age_hours,
        }

    @app.post("/api/sources/{source_id}/sync")
    async def sync_source(source_id: str, request: Request):
        require_roles(request, "admin", "analyst")
        lock = app.state.sync_locks.setdefault(
            request.state.user["org_id"] + ":" + source_id, asyncio.Lock()
        )
        if lock.locked():
            raise problem(409, "sync_in_progress", "A source sync is already running.")
        async with lock:
            return await request.state.providers.sync(source_id)

    @app.post("/api/query")
    async def query(data: QueryInput, request: Request):
        provider = request.state.providers
        provider.require_ai()
        chunks = request.state.store.search(data.query, data.topic)
        if not chunks:
            raise problem(
                409,
                "no_policy_evidence",
                "No matching policy evidence was found. Add a relevant policy or use terms from your documents.",
            )
        result = await provider.complete(
            Answer,
            {
                "task": "Answer using only supplied policies. State when they do not establish an answer.",
                "question": data.query,
                "policies": chunks,
            },
        )
        result["citations"] = verify_citations(result, chunks)
        return result

    @app.post("/api/transactions/evaluate", status_code=201)
    async def evaluate(data: EvaluationRequest, request: Request):
        started = time.perf_counter()
        store, provider = request.state.store, request.state.providers
        provider.require_ai()
        txn = data.transaction
        if store.has_transaction(txn.transaction_id):
            raise problem(
                409,
                "duplicate_transaction",
                "This transaction ID already has an assessment. Open Decision history.",
            )
        chunks = store.search(
            f"{txn.description} {txn.sender_country} {txn.receiver_country} transaction transfer sanctions AML KYC"
        )
        if not chunks:
            raise problem(
                409,
                "no_policy_evidence",
                "Add relevant compliance policies before evaluating a transaction.",
            )
        screening = await run_in_threadpool(provider.screen, txn)
        exchange = await provider.exchange(txn.currency, txn.amount)
        assessment = await provider.complete(
            Assessment,
            {
                "task": "Assess against supplied policies. Identify missing facts and coverage limitations. Require human review of potential sanctions matches.",
                "transaction": txn.model_dump(mode="json"),
                "policies": chunks,
                "sanctions_screening": screening,
                "usd_reference": exchange,
            },
        )
        assessment["citations"] = verify_citations(assessment, chunks)
        if screening["matches"] and assessment["verdict"] == "acceptable":
            raise problem(
                502,
                "inconsistent_assessment",
                "The AI assessment conflicts with potential sanctions matches. No decision was recorded.",
            )
        result = {
            "id": str(uuid.uuid4()),
            "created_at": now(),
            "transaction": txn.model_dump(mode="json"),
            "assessment": assessment,
            "screening": screening,
            "exchange": exchange,
            "model": settings.groq_model,
            "processing_time_ms": round((time.perf_counter() - started) * 1000),
            "policy_evidence": chunks,
            "created_by": request.state.user["id"],
        }
        try:
            store.save_decision(result)
        except INTEGRITY_ERRORS as exc:
            raise problem(
                409,
                "duplicate_transaction",
                "Another request already assessed this transaction ID.",
            ) from exc
        with store.connect() as db:
            audit(
                db, request.state.user["id"], "assessment_created", {"id": result["id"]}
            )
        return result

    @app.get("/api/decisions")
    def decisions(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        return request.state.store.decisions(limit, offset)

    @app.get("/api/decisions/{decision_id}")
    def decision(decision_id: str, request: Request):
        record = request.state.store.decision(decision_id)
        if not record:
            raise problem(404, "not_found", "Assessment not found.")
        return {**record, "reviews": request.state.store.reviews(decision_id)}

    @app.get("/api/decisions/{decision_id}/export")
    def export(decision_id: str, request: Request):
        record = decision(decision_id, request)
        return JSONResponse(
            record,
            headers={
                "Content-Disposition": f'attachment; filename="policylens-{record["id"]}.json"'
            },
        )

    @app.post("/api/decisions/{decision_id}/reviews", status_code=201)
    def review(decision_id: str, data: ReviewInput, request: Request):
        require_roles(request, "admin", "reviewer")
        decision(decision_id, request)
        verified = data.model_copy(update={"reviewer": request.state.user["name"]})
        result = request.state.store.review(decision_id, verified)
        with request.state.store.connect() as db:
            audit(
                db,
                request.state.user["id"],
                "assessment_reviewed",
                {"id": decision_id, "review_id": result["id"], "verdict": data.verdict},
            )
        return result

    from product_api import router
    from access_api import router as access_router
    from mfa_api import router as mfa_router
    from toolkit_api import router as toolkit_router
    from checkpoint_api import router as checkpoint_router
    from evidence_api import router as evidence_router
    from traceability_api import router as traceability_router
    from control_code_api import router as control_code_router
    from adapter_api import router as adapter_router
    from control_tuning_api import router as control_tuning_router

    app.include_router(router)
    app.include_router(access_router)
    app.include_router(mfa_router)
    app.include_router(toolkit_router)
    app.include_router(checkpoint_router)
    app.include_router(evidence_router)
    app.include_router(traceability_router)
    app.include_router(control_code_router)
    app.include_router(adapter_router)
    app.include_router(retention_router)
    app.include_router(control_tuning_router)
    dist = ROOT.parent / "frontend" / "dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if public_deployment and path in (
            "docs",
            "redoc",
            "openapi.json",
            "docs/oauth2-redirect",
        ):
            raise problem(
                404, "not_found", "API documentation is disabled on public deployments."
            )
        if path == "api" or path.startswith("api/"):
            raise problem(404, "not_found", "API endpoint not found.")
        if not (dist / "index.html").is_file():
            raise problem(
                503,
                "frontend_not_built",
                "Run npm ci and npm run build in frontend, then restart the server.",
            )
        return FileResponse(dist / "index.html")

    return app


app = create_app()
