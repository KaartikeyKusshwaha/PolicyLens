from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MilvusService:
    def __init__(self, host: str = "localhost", port: int = 19530):
        self.host = host
        self.port = port
        self.collection_name = "policy_chunks"
        self.cases_collection_name = "compliance_cases"
        self.connected = False
        
    def connect(self):
        """Connect to Milvus server"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            self.connected = True
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
            self._create_collections()
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            self.connected = False
            raise
    
    def _create_collections(self):
        """Create collections if they don't exist"""
        # Policy Chunks Collection
        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4000),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
                FieldSchema(name="doc_title", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="topic", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="version", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="is_active", dtype=DataType.BOOL),
                FieldSchema(name="valid_from", dtype=DataType.INT64),
            ]
            
            schema = CollectionSchema(fields=fields, description="Policy chunks with embeddings")
            collection = Collection(name=self.collection_name, schema=schema)
            
            # Create index
            index_params = {
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 200}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(f"Created collection: {self.collection_name}")
        
        # Compliance Cases Collection
        if not utility.has_collection(self.cases_collection_name):
            fields = [
                FieldSchema(name="case_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="transaction_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
                FieldSchema(name="decision", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="reasoning", dtype=DataType.VARCHAR, max_length=4000),
                FieldSchema(name="risk_score", dtype=DataType.FLOAT),
                FieldSchema(name="timestamp", dtype=DataType.INT64),
            ]
            
            schema = CollectionSchema(fields=fields, description="Historical compliance cases")
            collection = Collection(name=self.cases_collection_name, schema=schema)
            
            # Create index
            index_params = {
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 200}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(f"Created collection: {self.cases_collection_name}")
    
    def insert_policy_chunks(self, chunks: List[Dict[str, Any]]):
        """Insert policy chunks into Milvus"""
        if not self.connected:
            raise Exception("Not connected to Milvus")
        
        collection = Collection(self.collection_name)
        
        entities = [
            [chunk["chunk_id"] for chunk in chunks],
            [chunk["doc_id"] for chunk in chunks],
            [chunk["text"] for chunk in chunks],
            [chunk["embedding"] for chunk in chunks],
            [chunk["doc_title"] for chunk in chunks],
            [chunk.get("section", "") for chunk in chunks],
            [chunk["source"] for chunk in chunks],
            [chunk["topic"] for chunk in chunks],
            [chunk["version"] for chunk in chunks],
            [chunk["is_active"] for chunk in chunks],
            [int(chunk["valid_from"].timestamp()) for chunk in chunks],
        ]
        
        collection.insert(entities)
        collection.flush()
        logger.info(f"Inserted {len(chunks)} chunks into Milvus")
    
    def search_similar_policies(
        self, 
        query_embedding: List[float], 
        top_k: int = 5,
        topic: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Search for similar policy chunks"""
        if not self.connected:
            raise Exception("Not connected to Milvus")
        
        collection = Collection(self.collection_name)
        collection.load()
        
        # Build filter expression
        filter_expr = ""
        if active_only:
            filter_expr = "is_active == true"
        if topic:
            if filter_expr:
                filter_expr += f" && topic == '{topic}'"
            else:
                filter_expr = f"topic == '{topic}'"
        
        search_params = {"metric_type": "COSINE", "params": {"ef": 100}}
        
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr if filter_expr else None,
            output_fields=["chunk_id", "doc_id", "text", "doc_title", "section", "source", "topic", "version"]
        )
        
        output = []
        for hits in results:
            for hit in hits:
                output.append({
                    "chunk_id": hit.entity.get("chunk_id"),
                    "doc_id": hit.entity.get("doc_id"),
                    "text": hit.entity.get("text"),
                    "doc_title": hit.entity.get("doc_title"),
                    "section": hit.entity.get("section"),
                    "source": hit.entity.get("source"),
                    "topic": hit.entity.get("topic"),
                    "version": hit.entity.get("version"),
                    "relevance_score": float(hit.score)
                })
        
        return output
    
    def insert_compliance_case(self, case: Dict[str, Any]):
        """Insert a compliance case for case-based reasoning"""
        if not self.connected:
            raise Exception("Not connected to Milvus")
        
        collection = Collection(self.cases_collection_name)
        
        entities = [
            [case["case_id"]],
            [case["transaction_id"]],
            [case["embedding"]],
            [case["decision"]],
            [case["reasoning"]],
            [case["risk_score"]],
            [int(case["timestamp"].timestamp())],
        ]
        
        collection.insert(entities)
        collection.flush()
        logger.info(f"Inserted case {case['case_id']} into Milvus")
    
    def search_similar_cases(
        self, 
        query_embedding: List[float], 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search for similar historical cases"""
        if not self.connected:
            raise Exception("Not connected to Milvus")
        
        collection = Collection(self.cases_collection_name)
        collection.load()
        
        search_params = {"metric_type": "COSINE", "params": {"ef": 100}}
        
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["case_id", "transaction_id", "decision", "reasoning", "risk_score", "timestamp"]
        )
        
        output = []
        for hits in results:
            for hit in hits:
                output.append({
                    "case_id": hit.entity.get("case_id"),
                    "transaction_id": hit.entity.get("transaction_id"),
                    "decision": hit.entity.get("decision"),
                    "reasoning": hit.entity.get("reasoning"),
                    "risk_score": hit.entity.get("risk_score"),
                    "timestamp": datetime.fromtimestamp(hit.entity.get("timestamp")),
                    "similarity_score": float(hit.score)
                })
        
        return output
    
    def deactivate_document_chunks(self, doc_id: str):
        """Mark all chunks from a document as inactive"""
        if not self.connected:
            raise Exception("Not connected to Milvus")
        
        # Note: Milvus doesn't support direct updates, so we'd need to query and reinsert
        # For MVP, we'll log this operation
        logger.info(f"Deactivating chunks for document: {doc_id}")
    
    def disconnect(self):
        """Disconnect from Milvus"""
        connections.disconnect(alias="default")
        self.connected = False
        logger.info("Disconnected from Milvus")
