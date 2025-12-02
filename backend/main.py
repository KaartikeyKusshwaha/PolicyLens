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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global milvus_service, embedding_service, llm_service, document_processor, compliance_engine, storage_service, metrics_service
    
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
    
    metrics_service = MetricsService()
    logger.info("✓ Metrics service initialized")
    
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


@app.get("/")
async def root():
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
    """Upload and process a new policy document"""
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
                latency_ms=result["processing_time_ms"]
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
            metrics_service.record_query(latency_ms)
        
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


@app.get("/api/policies/stats")
async def get_policy_stats():
    """Get statistics about loaded policies"""
    try:
        if not milvus_service or not milvus_service.connected:
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "sources": {},
                "topics": {},
                "error": "Milvus not connected"
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
async def generate_audit_report(trace_id: str):
    """Generate audit report for a specific decision"""
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
        
        return audit_report
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating audit report for {trace_id}: {e}")
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
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend for all non-API routes"""
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Serve index.html for all other routes (SPA routing)
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
