from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uuid
from datetime import datetime
from typing import Optional

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global milvus_service, embedding_service, llm_service, document_processor, compliance_engine
    
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
    return {
        "service": "PolicyLens API",
        "version": "1.0.0",
        "status": "operational",
        "milvus_connected": milvus_service.connected if milvus_service else False
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
        result = compliance_engine.answer_compliance_query(
            query=request.query,
            topic=request.topic.value if request.topic else None
        )
        
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
        # Store feedback for future model improvement
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
        # This would query Milvus for actual stats
        # For MVP, return mock data
        return {
            "total_documents": 0,
            "total_chunks": 0,
            "sources": {
                "internal": 0,
                "ofac": 0,
                "fatf": 0,
                "rbi": 0,
                "eu_aml": 0
            },
            "topics": {
                "aml": 0,
                "kyc": 0,
                "sanctions": 0,
                "fraud": 0
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting policy stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
