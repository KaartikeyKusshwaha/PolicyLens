from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import uuid
from datetime import datetime
from typing import Optional
import os

from models import (
    PolicyDocument, Transaction, PolicySource, PolicyTopic,
    TransactionEvaluationRequest, TransactionEvaluationResponse,
    PolicyUploadRequest, QueryRequest, QueryResponse, FeedbackRequest
)
from services.milvus_service import MilvusService
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService
from services.document_processor import DocumentProcessor
from services.compliance_engine import ComplianceEngine
from services.storage_service import StorageService
from services.metrics_service import MetricsService
from services.policy_sentinel import PolicySentinel
from services.report_generator import ReportGenerator
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
milvus_service = None
embedding_service = None
llm_service = None
document_processor = None
compliance_engine = None
storage_service = None
metrics_service = None
policy_sentinel = None
report_generator = None
batch_processor = None
risk_scorer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global milvus_service, embedding_service, llm_service, document_processor, compliance_engine, storage_service, metrics_service, policy_sentinel, report_generator, batch_processor, risk_scorer
    
    logger.info("Starting PolicyLens API...")
    
    # Initialize services
    try:
        milvus_service = MilvusService(host=settings.milvus_host, port=settings.milvus_port)
        milvus_service.connect()
        logger.info("✓ Milvus connected")
    except Exception as e:
        logger.warning(f"⚠ Milvus connection failed: {e}. Running in demo mode.")
        milvus_service = MilvusService()  # Will fail gracefully
    
    embedding_service = EmbeddingService()
    logger.info("✓ Embedding service initialized")
    
    llm_service = LLMService()
    logger.info("✓ LLM service initialized")
    
    document_processor = DocumentProcessor(embedding_service, milvus_service)
    logger.info("✓ Document processor initialized")
    
    compliance_engine = ComplianceEngine(embedding_service, milvus_service, llm_service)
    logger.info("✓ Compliance engine initialized")
    
    storage_service = StorageService()
    logger.info("✓ Storage service initialized")
    
    # Initialize policy sentinel for change detection
    policy_sentinel = PolicySentinel(milvus_service, storage_service)
    logger.info("✓ Policy sentinel initialized")
    
    # Initialize report generator
    report_generator = ReportGenerator()
    logger.info("✓ Report generator initialized")
    
    # Initialize metrics with storage and Milvus services
    demo_mode = not (milvus_service and milvus_service.connected)
    metrics_service = MetricsService(
        storage_service=storage_service,
        milvus_service=milvus_service,
        demo_mode=demo_mode
    )
    logger.info("✓ Metrics service initialized")
    
    # Initialize batch processor
    from services.batch_processor import BatchProcessor
    batch_processor = BatchProcessor(compliance_engine, storage_service)
    logger.info("✓ Batch processor initialized")
    
    # Initialize risk scorer
    from services.risk_scorer import RiskScorer
    risk_scorer = RiskScorer(milvus_service, embedding_service, storage_service)
    logger.info("✓ Risk scorer initialized")
    
    logger.info("🚀 PolicyLens API ready!")
    
    yield
    
    # Cleanup
    if milvus_service and milvus_service.connected:
        milvus_service.disconnect()
    logger.info("Shutdown complete")


app = FastAPI(
    title="PolicyLens API",
    description="AI-powered compliance intelligence system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    storage_stats = storage_service.get_statistics() if storage_service else {}
    return {
        "service": "PolicyLens API",
        "version": "1.0.0",
        "status": "operational",
        "milvus_connected": milvus_service.connected if milvus_service else False,
        "storage": storage_stats
    }


@app.post("/api/policies/upload")
async def upload_policy(policy_request: PolicyUploadRequest):
    """Upload and process a new policy document (JSON format)"""
    try:
        doc_id = str(uuid.uuid4())
        
        document = PolicyDocument(
            doc_id=doc_id,
            title=policy_request.title,
            content=policy_request.content,
            source=policy_request.source,
            topic=policy_request.topic,
            version=policy_request.version,
            metadata=policy_request.metadata
        )
        
        chunks = document_processor.process_document(document)
        
        # Track metrics
        if metrics_service:
            metrics_service.record_policy_upload()
        
        return {
            "doc_id": doc_id,
            "title": document.title,
            "chunks_created": len(chunks),
            "status": "processed",
            "message": "Policy document uploaded and indexed successfully"
        }
    
    except Exception as e:
        logger.error(f"Error uploading policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/policies/upload-file")
async def upload_policy_file(
    file: UploadFile = File(...),
    title: str = None,
    source: str = "UPLOADED",
    topic: str = "GENERAL",
    version: str = "1.0"
):
    """Upload and process a policy document from file (PDF, DOCX, TXT)"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Extract text from file
        extracted_text = document_processor.extract_text_from_file(file_content, file.filename)
        
        if not extracted_text or len(extracted_text.strip()) < 100:
            raise HTTPException(status_code=400, detail="Extracted text is too short or empty")
        
        # Create document
        doc_id = str(uuid.uuid4())
        doc_title = title or file.filename.rsplit('.', 1)[0]
        
        document = PolicyDocument(
            doc_id=doc_id,
            title=doc_title,
            content=extracted_text,
            source=source,
            topic=topic,
            version=version,
            metadata={"original_filename": file.filename, "file_size": len(file_content)}
        )
        
        # Process and store
        chunks = document_processor.process_document(document)
        
        # Track metrics
        if metrics_service:
            metrics_service.record_policy_upload()
        
        return {
            "doc_id": doc_id,
            "title": doc_title,
            "filename": file.filename,
            "text_length": len(extracted_text),
            "chunks_created": len(chunks),
            "status": "processed",
            "message": f"Policy document '{file.filename}' uploaded and indexed successfully"
        }
    
    except Exception as e:
        logger.error(f"Error uploading policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transactions/evaluate", response_model=TransactionEvaluationResponse)
async def evaluate_transaction(request: TransactionEvaluationRequest):
    """Evaluate a transaction against compliance policies"""
    try:
        result = compliance_engine.evaluate_transaction(request.transaction)
        
        # Store decision for retrieval
        if storage_service:
            storage_service.store_decision(
                trace_id=result["trace_id"],
                decision_data={
                    "transaction": request.transaction.model_dump(),
                    "decision": result["decision"].model_dump(),
                    "trace_id": result["trace_id"],
                    "processing_time_ms": result["processing_time_ms"]
                }
            )
        
        # Track metrics
        if metrics_service:
            metrics_service.record_evaluation(
                verdict=result["decision"].verdict.value,
                risk_level=result["decision"].risk_level.value,
                latency_ms=result["processing_time_ms"],
                transaction_id=request.transaction.transaction_id
            )
        
        return TransactionEvaluationResponse(
            decision=result["decision"],
            trace_id=result["trace_id"],
            processing_time_ms=result["processing_time_ms"]
        )
    
    except Exception as e:
        logger.error(f"Error evaluating transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query", response_model=QueryResponse)
async def query_compliance(request: QueryRequest):
    """Answer a compliance-related query"""
    try:
        import time
        start_time = time.time()
        
        result = compliance_engine.answer_compliance_query(
            query=request.query,
            topic=request.topic.value if request.topic else None
        )
        
        # Track metrics
        if metrics_service:
            latency_ms = (time.time() - start_time) * 1000
            metrics_service.record_query(latency_ms, request.query)
        
        return QueryResponse(
            query=result["query"],
            answer=result["answer"],
            citations=result["citations"],
            confidence=result["confidence"]
        )
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """Submit human feedback for a compliance decision"""
    try:
        # Store feedback persistently
        if storage_service:
            storage_service.store_feedback(feedback.model_dump())
        
        # Track metrics
        if metrics_service:
            metrics_service.record_feedback()
        
        logger.info(
            f"Feedback received for transaction {feedback.transaction_id}: "
            f"Corrected to {feedback.corrected_verdict}"
        )
        
        return {
            "status": "success",
            "message": "Feedback recorded successfully",
            "transaction_id": feedback.transaction_id
        }
    
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policies")
async def list_policies():
    """Get list of all policies"""
    try:
        if not milvus_service or not milvus_service.connected:
            # Return demo policies in demo mode
            demo_policies = [
                {
                    "doc_id": "demo_doc_aml",
                    "title": "AML Transaction Monitoring Guidelines",
                    "source": "INTERNAL",
                    "topic": "AML",
                    "version": "1.0",
                    "description": "Guidelines for monitoring transactions for anti-money laundering compliance",
                    "chunks": 5
                },
                {
                    "doc_id": "demo_doc_sanctions",
                    "title": "Sanctions Compliance Policy",
                    "source": "OFAC",
                    "topic": "SANCTIONS",
                    "version": "2.1",
                    "description": "Policy for screening transactions against sanctions lists",
                    "chunks": 4
                },
                {
                    "doc_id": "demo_doc_kyc",
                    "title": "Know Your Customer (KYC) Requirements",
                    "source": "INTERNAL",
                    "topic": "KYC",
                    "version": "1.5",
                    "description": "Customer identification and verification requirements",
                    "chunks": 6
                }
            ]
            return {
                "policies": demo_policies,
                "total": len(demo_policies),
                "mode": "demo"
            }
        
        # Query Milvus for actual policy documents
        policies = milvus_service.get_all_documents()
        return {
            "policies": policies,
            "total": len(policies),
            "mode": "live"
        }
    
    except Exception as e:
        logger.error(f"Error listing policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policies/stats")
async def get_policy_stats():
    """Get statistics about loaded policies"""
    try:
        if not milvus_service or not milvus_service.connected:
            return {
                "total_documents": 3,
                "total_chunks": 15,
                "sources": {"INTERNAL": 2, "OFAC": 1},
                "topics": {"AML": 1, "SANCTIONS": 1, "KYC": 1},
                "mode": "demo"
            }
        
        # Query Milvus for actual statistics
        from pymilvus import Collection
        collection = Collection(milvus_service.collection_name)
        collection.load()
        
        total_chunks = collection.num_entities
        
        # Get cases collection stats
        cases_collection = Collection(milvus_service.cases_collection_name)
        cases_collection.load()
        total_cases = cases_collection.num_entities
        
        return {
            "total_chunks": total_chunks,
            "total_cases": total_cases,
            "collection_name": milvus_service.collection_name,
            "message": "Real-time stats from Milvus"
        }
    
    except Exception as e:
        logger.error(f"Error getting policy stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/policies/{doc_id}/update")
async def update_policy(doc_id: str, policy_request: PolicyUploadRequest):
    """Update an existing policy and trigger change detection"""
    try:
        # Get old document content
        old_docs = milvus_service.get_all_documents() if milvus_service.connected else []
        old_doc = next((d for d in old_docs if d["doc_id"] == doc_id), None)
        
        if not old_doc:
            raise HTTPException(status_code=404, detail=f"Policy {doc_id} not found")
        
        # Create new version
        new_doc_id = f"{doc_id}_v{policy_request.version}"
        
        new_document = PolicyDocument(
            doc_id=new_doc_id,
            title=policy_request.title,
            content=policy_request.content,
            source=policy_request.source,
            topic=policy_request.topic,
            version=policy_request.version,
            metadata=policy_request.metadata
        )
        
        # Process new document
        chunks = document_processor.process_document(new_document)
        
        # Detect changes (simplified - in production, fetch old content from storage)
        change_data = policy_sentinel.detect_policy_change(
            doc_id, 
            new_doc_id, 
            old_doc.get("title", ""), 
            policy_request.content
        )
        
        # Identify impacted decisions
        impacted_decisions = policy_sentinel.identify_impacted_decisions(doc_id)
        
        # Generate impact report
        impact_report = policy_sentinel.generate_change_impact_report(change_data, impacted_decisions)
        
        # Trigger re-evaluation if significant change
        if change_data.get("change_magnitude", 0) > 0.10:
            re_eval_queue = policy_sentinel.trigger_re_evaluation(impacted_decisions)
        else:
            re_eval_queue = {"message": "Change too minor to trigger re-evaluation"}
        
        # Deactivate old version
        milvus_service.deactivate_document_chunks(doc_id)
        
        return {
            "doc_id": new_doc_id,
            "old_doc_id": doc_id,
            "status": "updated",
            "chunks_created": len(chunks),
            "change_detection": change_data,
            "impact_report": impact_report,
            "re_evaluation": re_eval_queue
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policies/changes")
async def get_policy_changes(limit: int = 10):
    """Get recent policy changes"""
    try:
        changes = policy_sentinel.get_recent_changes(limit=limit)
        return {
            "changes": changes,
            "count": len(changes)
        }
    except Exception as e:
        logger.error(f"Error retrieving policy changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policies/impact-reports")
async def get_impact_reports(limit: int = 10):
    """Get recent change impact reports"""
    try:
        reports = policy_sentinel.get_impact_reports(limit=limit)
        return {
            "reports": reports,
            "count": len(reports)
        }
    except Exception as e:
        logger.error(f"Error retrieving impact reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/decisions/{trace_id}")
async def get_decision(trace_id: str):
    """Retrieve a decision by trace ID"""
    try:
        if not storage_service:
            raise HTTPException(status_code=503, detail="Storage service unavailable")
        
        decision = storage_service.get_decision(trace_id)
        
        if not decision:
            raise HTTPException(status_code=404, detail=f"Decision not found: {trace_id}")
        
        return decision
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving decision {trace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/decisions")
async def list_decisions(limit: int = 50, skip: int = 0):
    """List recent decisions"""
    try:
        if not storage_service:
            raise HTTPException(status_code=503, detail="Storage service unavailable")
        
        decisions = storage_service.list_decisions(limit=limit, skip=skip)
        
        return {
            "decisions": decisions,
            "count": len(decisions),
            "limit": limit,
            "skip": skip
        }
    
    except Exception as e:
        logger.error(f"Error listing decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/report/{trace_id}")
async def generate_audit_report(trace_id: str, format: str = "json"):
    """Generate audit report for a specific decision (JSON or PDF)"""
    from fastapi.responses import Response
    
    try:
        if not storage_service:
            raise HTTPException(status_code=503, detail="Storage service unavailable")
        
        decision_data = storage_service.get_decision(trace_id)
        
        if not decision_data:
            raise HTTPException(status_code=404, detail=f"Decision not found: {trace_id}")
        
        # Build comprehensive audit report
        decision = decision_data.get("decision", {})
        transaction = decision_data.get("transaction", {})
        
        audit_report = {
            "report_generated_at": datetime.now().isoformat(),
            "trace_id": trace_id,
            "transaction_details": transaction,
            "compliance_decision": {
                "verdict": decision.get("verdict"),
                "risk_level": decision.get("risk_level"),
                "risk_score": decision.get("risk_score"),
                "confidence": decision.get("confidence"),
                "reasoning": decision.get("reasoning"),
                "timestamp": decision.get("timestamp")
            },
            "policy_citations": decision.get("policy_citations", []),
            "similar_cases": decision.get("similar_cases", []),
            "processing_metrics": {
                "processing_time_ms": decision_data.get("processing_time_ms"),
                "stored_at": decision_data.get("stored_at")
            },
            "audit_trail": {
                "system_version": "1.0.0",
                "model_used": settings.llm_model,
                "embedding_model": settings.embedding_model
            }
        }
        
        # Return PDF if requested
        if format.lower() == "pdf":
            pdf_bytes = report_generator.generate_decision_report(decision_data)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=audit_report_{trace_id}.pdf"}
            )
        
        # Default: return JSON
        return audit_report
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating audit report for {trace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/impact-report/{report_id}")
async def get_impact_report_pdf(report_id: str, format: str = "json"):
    """Get policy change impact report (JSON or PDF)"""
    from fastapi.responses import Response
    
    try:
        # Get the impact report
        reports = policy_sentinel.get_impact_reports(limit=100)
        report = next((r for r in reports if r.get("report_id") == report_id), None)
        
        if not report:
            raise HTTPException(status_code=404, detail=f"Impact report not found: {report_id}")
        
        # Return PDF if requested
        if format.lower() == "pdf":
            pdf_bytes = report_generator.generate_impact_report(report)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={report_id}.pdf"}
            )
        
        # Default: return JSON
        return report
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving impact report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics"""
    try:
        if not metrics_service:
            raise HTTPException(status_code=503, detail="Metrics service unavailable")
        
        return metrics_service.get_metrics()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics/latency")
async def get_latency_metrics(operation_type: Optional[str] = None, hours: int = 24):
    """Get persisted latency statistics from storage
    
    Args:
        operation_type: Filter by operation type ('evaluation' or 'query'). If None, returns all.
        hours: Number of hours to look back (default: 24)
    """
    try:
        if not metrics_service:
            raise HTTPException(status_code=503, detail="Metrics service unavailable")
        
        # Get persisted latency stats
        if operation_type:
            stats = metrics_service.get_persisted_latency_stats(operation_type, hours)
            return {
                "operation_type": operation_type,
                "hours": hours,
                "statistics": stats
            }
        else:
            # Get stats for all operation types
            eval_stats = metrics_service.get_persisted_latency_stats("evaluation", hours)
            query_stats = metrics_service.get_persisted_latency_stats("query", hours)
            
            return {
                "hours": hours,
                "evaluation": eval_stats,
                "query": query_stats,
                "total_operations": eval_stats["count"] + query_stats["count"]
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving latency metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback")
async def list_feedback(limit: int = 50):
    """List recent feedback submissions"""
    try:
        if not storage_service:
            raise HTTPException(status_code=503, detail="Storage service unavailable")
        
        feedback_list = storage_service.list_all_feedback(limit=limit)
        
        return {
            "feedback": feedback_list,
            "count": len(feedback_list)
        }
    
    except Exception as e:
        logger.error(f"Error listing feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files (frontend build)
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    # Mount assets directory
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Serve frontend - needs to be added AFTER all API routes
    from fastapi.responses import HTMLResponse
    
    @app.get("/", response_class=HTMLResponse)
    async def serve_root():
        """Serve frontend root"""
        index_path = os.path.join(frontend_dist, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def serve_frontend(full_path: str):
        """Serve frontend for all non-API routes (SPA routing)"""
        # Don't intercept API routes
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Check if it's a file request
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # For all other routes, serve index.html (SPA routing)
        index_path = os.path.join(frontend_dist, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()


# Batch Re-evaluation Endpoints
@app.post("/api/batch/reevaluate")
async def reevaluate_all(filter_by: Optional[dict] = None):
    """
    Re-evaluate all stored decisions with current policies
    
    Optional filters:
    - verdict: Filter by verdict (FLAG, REVIEW, CLEAR)
    - date_from: ISO date string
    - date_to: ISO date string
    """
    try:
        if not batch_processor:
            raise HTTPException(status_code=503, detail="Batch processor not initialized")
        
        result = await batch_processor.reevaluate_all_decisions(filter_by)
        return result
    except Exception as e:
        logger.error(f"Batch re-evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/batch/candidates")
async def get_reevaluation_candidates(
    days_old: int = 30,
    verdict: Optional[str] = None
):
    """
    Get list of decisions that should be re-evaluated
    
    Args:
        days_old: Consider decisions older than this many days (default: 30)
        verdict: Filter by verdict (FLAG, REVIEW, CLEAR)
    """
    try:
        if not batch_processor:
            raise HTTPException(status_code=503, detail="Batch processor not initialized")
        
        candidates = batch_processor.get_reevaluation_candidates(days_old, verdict)
        return {
            "candidates": candidates,
            "total": len(candidates),
            "filters": {
                "days_old": days_old,
                "verdict": verdict
            }
        }
    except Exception as e:
        logger.error(f"Failed to get candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch/reevaluate-by-policy/{policy_id}")
async def reevaluate_by_policy(policy_id: str):
    """
    Re-evaluate decisions affected by a specific policy
    
    Args:
        policy_id: ID of the policy that changed
    """
    try:
        if not batch_processor:
            raise HTTPException(status_code=503, detail="Batch processor not initialized")
        
        result = batch_processor.reevaluate_by_policy(policy_id)
        return result
    except Exception as e:
        logger.error(f"Policy-based re-evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch/impact-report")
async def generate_impact_report(reevaluation_summary: dict):
    """
    Generate human-readable impact report from re-evaluation results
    
    Args:
        reevaluation_summary: Result from reevaluate_all endpoint
    """
    try:
        if not batch_processor:
            raise HTTPException(status_code=503, detail="Batch processor not initialized")
        
        report = batch_processor.generate_impact_report(reevaluation_summary)
        return {
            "report": report,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Impact report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Risk Scoring Endpoints
@app.get("/api/risk/statistics")
async def get_risk_statistics():
    """
    Get comprehensive risk statistics across all decisions
    
    Returns:
        Statistics including total cases, verdict distribution, average risk scores
    """
    try:
        if not risk_scorer:
            raise HTTPException(status_code=503, detail="Risk scorer not initialized")
        
        stats = risk_scorer.get_risk_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get risk statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
