import asyncio
import logging
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from config import ROOT, Settings
from models import (
    Answer,
    Assessment,
    EvaluationRequest,
    PolicyInput,
    QueryInput,
    ReviewInput,
)
from providers import Providers, extract_document, problem, verify_citations
from store import Store, now

logger = logging.getLogger("policylens")


def create_app(settings=None, transport=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(settings.database_path)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "PolicyLens/2.0"},
        ) as client:
            app.state.providers = Providers(settings, app.state.store, client)
            app.state.sync_lock = asyncio.Lock()
            yield

    app = FastAPI(title="PolicyLens", version="2.0.0", lifespan=lifespan)

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

    @app.get("/api/health")
    def health():
        provider = app.state.providers
        with app.state.store.connect() as db:
            db.execute("SELECT 1").fetchone()
        return {
            "status": "ok",
            "version": "2.0.0",
            "storage": "sqlite_fts5",
            "ai": {
                "status": "configured" if provider.ai_configured else "needs_key",
                "model": settings.groq_model,
            },
            "sanctions": provider.sanctions_status(),
        }

    @app.get("/api/dashboard")
    def dashboard():
        store = app.state.store
        return {
            **store.dashboard(),
            "policies": len(store.policies()),
            "recent": store.decisions(6),
            "health": health(),
        }

    @app.get("/api/policies")
    def policies():
        return app.state.store.policies()

    @app.post("/api/policies", status_code=201)
    def add_policy(data: PolicyInput):
        return app.state.store.save_policy(data)

    @app.post("/api/policies/file", status_code=201)
    async def upload_policy(
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
                "The document needs a title, valid topic, and 50–300,000 characters of selectable text. Scanned PDFs need OCR before upload.",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise problem(
                422,
                "unreadable_document",
                "Could not read this file. Use an unencrypted, text-based PDF, DOCX, or UTF-8 TXT file.",
            ) from exc
        finally:
            await file.close()
        return app.state.store.save_policy(data)

    @app.get("/api/policies/{policy_id}")
    def policy(policy_id: str):
        result = app.state.store.policy(policy_id)
        if not result:
            raise problem(404, "not_found", "Policy not found.")
        return result

    @app.put("/api/policies/{policy_id}")
    def update_policy(policy_id: str, data: PolicyInput):
        policy(policy_id)
        try:
            return app.state.store.save_policy(data, policy_id)
        except ValueError as exc:
            raise problem(409, "version_conflict", str(exc)) from exc

    @app.get("/api/sources")
    def sources():
        return {
            "groq": {
                "status": "configured"
                if app.state.providers.ai_configured
                else "needs_key",
                "model": settings.groq_model,
                "url": "https://console.groq.com/docs/rate-limits",
            },
            "ofac": app.state.providers.sanctions_status(),
            "frankfurter": {
                "status": "on_demand",
                "url": "https://frankfurter.dev/",
                "description": "Live daily reference rates; fetched during non-USD evaluations.",
            },
            "max_age_hours": settings.sanctions_max_age_hours,
        }

    @app.post("/api/sources/ofac/sync")
    async def sync_ofac():
        if app.state.sync_lock.locked():
            raise problem(
                409, "sync_in_progress", "An OFAC sync is already in progress."
            )
        async with app.state.sync_lock:
            return await app.state.providers.sync_sanctions()

    @app.post("/api/query")
    async def query(data: QueryInput):
        provider = app.state.providers
        provider.require_ai()
        chunks = app.state.store.search(data.query, data.topic)
        if not chunks:
            raise problem(
                409,
                "no_policy_evidence",
                "No matching policy evidence was found. Add a relevant policy or use terms from your documents.",
            )
        result = await provider.complete(
            Answer,
            {
                "task": "Answer the question using only these policies. State when they do not establish the answer.",
                "question": data.query,
                "policies": chunks,
            },
        )
        result["citations"] = verify_citations(result, chunks)
        return result

    @app.post("/api/transactions/evaluate", status_code=201)
    async def evaluate(data: EvaluationRequest):
        started = time.perf_counter()
        store, provider = app.state.store, app.state.providers
        provider.require_ai()
        txn = data.transaction
        if store.has_transaction(txn.transaction_id):
            raise problem(
                409,
                "duplicate_transaction",
                "This transaction ID already has an assessment. Open it in Decision history.",
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
                "task": "Assess this transaction against the policies. Identify missing facts and coverage limitations. Require human review of potential sanctions matches.",
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
        }
        try:
            store.save_decision(result)
        except sqlite3.IntegrityError as exc:
            raise problem(
                409,
                "duplicate_transaction",
                "Another request already assessed this transaction ID. Open Decision history.",
            ) from exc
        return result

    @app.get("/api/decisions")
    def decisions(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        return app.state.store.decisions(limit, offset)

    @app.get("/api/decisions/{decision_id}")
    def decision(decision_id: str):
        record = app.state.store.decision(decision_id)
        if not record:
            raise problem(404, "not_found", "Assessment not found.")
        return {**record, "reviews": app.state.store.reviews(decision_id)}

    @app.get("/api/decisions/{decision_id}/export")
    def export(decision_id: str):
        record = decision(decision_id)
        return JSONResponse(
            record,
            headers={
                "Content-Disposition": f'attachment; filename="policylens-{record["id"]}.json"'
            },
        )

    @app.post("/api/decisions/{decision_id}/reviews", status_code=201)
    def review(decision_id: str, data: ReviewInput):
        decision(decision_id)
        return app.state.store.review(decision_id, data)

    # Built frontend and API share one origin. No CORS wildcard or hard-coded deployment URL.
    dist = ROOT.parent / "frontend" / "dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
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
