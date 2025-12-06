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
        # External Data Cache Collection
        external_data_collection = "external_data_cache"
        if not utility.has_collection(external_data_collection):
            fields = [
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50, is_primary=True),
                FieldSchema(name="data_json", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="cached_at", dtype=DataType.INT64),
                FieldSchema(name="records_count", dtype=DataType.INT64),
                FieldSchema(name="dummy_vector", dtype=DataType.FLOAT_VECTOR, dim=1),  # Required by Milvus
            ]
            schema = CollectionSchema(fields=fields, description="External data source cache")
            collection = Collection(name=external_data_collection, schema=schema)
            
            # Create index on dummy_vector field (required for loading)
            index_params = {
                "index_type": "FLAT",
                "metric_type": "L2",
                "params": {}
            }
            collection.create_index(field_name="dummy_vector", index_params=index_params)
            collection.load()
            logger.info(f"Created and loaded collection: {external_data_collection}")
        
        # Policy Chunks Collection
        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4000),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
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
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
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
            logger.warning("Not connected to Milvus - skipping chunk insertion")
            return
        
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
            logger.warning("Not connected to Milvus - returning demo policies")
            return self._get_demo_policies()
        
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
            logger.warning("Not connected to Milvus - skipping case insertion")
            return
        
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
            logger.warning("Not connected to Milvus - returning demo cases")
            return self._get_demo_cases()
        
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
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get list of all unique documents from Milvus"""
        if not self.connected:
            logger.warning("Not connected to Milvus - returning empty list")
            return []
        
        try:
            collection = Collection(self.collection_name)
            collection.load()
            
            # Query all chunks to aggregate by document
            results = collection.query(
                expr="is_active == true",
                output_fields=["doc_id", "doc_title", "source", "topic", "version"],
                limit=16384  # Max limit
            )
            
            # Aggregate by doc_id
            docs_dict = {}
            for result in results:
                doc_id = result["doc_id"]
                if doc_id not in docs_dict:
                    docs_dict[doc_id] = {
                        "doc_id": doc_id,
                        "title": result["doc_title"],
                        "source": result["source"].upper(),
                        "topic": result["topic"].upper(),
                        "version": result["version"],
                        "chunks": 0
                    }
                docs_dict[doc_id]["chunks"] += 1
            
            # Add descriptions based on title/topic
            for doc in docs_dict.values():
                if "CTR" in doc["title"]:
                    doc["description"] = "Currency Transaction Report filing requirements"
                elif "SAR" in doc["title"]:
                    doc["description"] = "Suspicious Activity Report filing requirements"
                elif "CDD" in doc["title"] or "Customer Due Diligence" in doc["title"]:
                    doc["description"] = "Customer identification and verification requirements"
                elif "Recordkeeping" in doc["title"]:
                    doc["description"] = "BSA recordkeeping and retention requirements"
                elif "International" in doc["title"]:
                    doc["description"] = "International AML standards and high-risk jurisdictions"
                elif "BSA/AML" in doc["title"]:
                    doc["description"] = "Bank Secrecy Act compliance program requirements"
                elif "AML" in doc["title"]:
                    doc["description"] = "Anti-money laundering transaction monitoring guidelines"
                elif "Sanctions" in doc["title"]:
                    doc["description"] = "Sanctions screening and compliance policy"
                elif "KYC" in doc["title"]:
                    doc["description"] = "Know Your Customer identification requirements"
                elif "Fraud" in doc["title"]:
                    doc["description"] = "Fraud detection and prevention guidelines"
                elif "PEP" in doc["title"]:
                    doc["description"] = "Politically Exposed Persons screening requirements"
                else:
                    doc["description"] = doc["title"]
            
            return list(docs_dict.values())
            
        except Exception as e:
            logger.error(f"Error getting documents from Milvus: {e}")
            return []
    
    def deactivate_document_chunks(self, doc_id: str):
        """Mark all chunks from a document as inactive"""
        if not self.connected:
            logger.warning("Not connected to Milvus - skipping deactivation")
            return
        
        # Note: Milvus doesn't support direct updates, so we'd need to query and reinsert
        # For MVP, we'll log this operation
        logger.info(f"Deactivating chunks for document: {doc_id}")
    
    def _get_demo_policies(self) -> List[Dict[str, Any]]:
        """Return demo policy data when Milvus is not available"""
        return [
            {
                "chunk_id": "demo_chunk_1",
                "doc_id": "demo_doc_aml",
                "text": "Transactions exceeding USD 10,000 must be reported to the compliance team within 24 hours. Enhanced due diligence is required for amounts above USD 50,000.",
                "doc_title": "AML Transaction Monitoring Guidelines",
                "section": "Transaction Thresholds",
                "source": "internal",
                "topic": "aml",
                "version": "1.0",
                "relevance_score": 0.92
            },
            {
                "chunk_id": "demo_chunk_2",
                "doc_id": "demo_doc_sanctions",
                "text": "Transactions involving sanctioned jurisdictions (Iran, North Korea, Syria, Crimea) are prohibited without explicit regulatory approval. All transactions must be screened against OFAC sanctions lists.",
                "doc_title": "Sanctions Compliance Policy",
                "section": "Prohibited Jurisdictions",
                "source": "ofac",
                "topic": "sanctions",
                "version": "2.1",
                "relevance_score": 0.88
            },
            {
                "chunk_id": "demo_chunk_3",
                "doc_id": "demo_doc_kyc",
                "text": "Customer verification must include: government-issued ID, proof of address, and beneficial ownership disclosure for entities. Enhanced KYC is mandatory for high-risk customers and PEPs.",
                "doc_title": "Know Your Customer (KYC) Requirements",
                "section": "Identity Verification",
                "source": "internal",
                "topic": "kyc",
                "version": "1.5",
                "relevance_score": 0.75
            }
        ]
    
    def _get_demo_cases(self) -> List[Dict[str, Any]]:
        """Return demo case data when Milvus is not available"""
        return [
            {
                "case_id": "case_001",
                "transaction_id": "TXN_DEMO_001",
                "decision": "flag",
                "reasoning": "Large transaction to high-risk jurisdiction without proper documentation",
                "risk_score": 0.87,
                "timestamp": datetime(2025, 11, 15, 10, 30),
                "similarity_score": 0.91
            },
            {
                "case_id": "case_002",
                "transaction_id": "TXN_DEMO_002",
                "decision": "acceptable",
                "reasoning": "Standard transaction below threshold with verified parties",
                "risk_score": 0.12,
                "timestamp": datetime(2025, 11, 20, 14, 15),
                "similarity_score": 0.73
            }
        ]
    
    def store_external_data(self, source: str, data: Dict[str, Any], records_count: int) -> bool:
        """Store external data in Milvus"""
        if not self.connected:
            logger.warning("Not connected to Milvus - skipping external data storage")
            return False
        
        try:
            import json
            collection = Collection("external_data_cache")
            
            # Ensure collection is loaded
            if not utility.loading_progress("external_data_cache").get("loading_progress", "0%") == "100%":
                collection.load()
            
            # Delete existing entry for this source
            expr = f'source == "{source}"'
            collection.delete(expr)
            
            # Insert new data (including dummy vector required by Milvus)
            entities = [
                [source],
                [json.dumps(data, default=str)],
                [int(datetime.now().timestamp())],
                [records_count],
                [[0.0]]  # Dummy vector - required by Milvus schema
            ]
            
            collection.insert(entities)
            collection.flush()
            logger.info(f"Stored external data for {source} in Milvus")
            return True
            
        except Exception as e:
            logger.error(f"Error storing external data in Milvus: {e}")
            return False
    
    def get_external_data(self, source: str, ttl_hours: int = 24) -> Optional[Dict[str, Any]]:
        """Get cached external data from Milvus"""
        if not self.connected:
            logger.warning("Not connected to Milvus - cannot retrieve external data")
            return None
        
        # Ensure collection is loaded
        try:
            collection = Collection("external_data_cache")
            if not utility.loading_progress("external_data_cache").get("loading_progress", "0%") == "100%":
                collection.load()
        except Exception as e:
            logger.error(f"Error loading collection: {e}")
            return None
        
        try:
            import json
            from datetime import timedelta
            
            collection = Collection("external_data_cache")
            collection.load()
            
            # Query for the source
            expr = f'source == "{source}"'
            results = collection.query(expr=expr, output_fields=["data_json", "cached_at", "records_count"])
            
            if not results:
                return None
            
            result = results[0]
            cached_at = datetime.fromtimestamp(result["cached_at"])
            
            # Check if cache is still valid
            if datetime.now() - cached_at < timedelta(hours=ttl_hours):
                data = json.loads(result["data_json"])
                logger.info(f"Retrieved cached external data for {source} from Milvus")
                return data
            else:
                logger.info(f"Cache expired for {source} in Milvus")
                return None
                
        except Exception as e:
            logger.error(f"Error getting external data from Milvus: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from Milvus"""
        if self.connected:
            connections.disconnect(alias="default")
            self.connected = False
            logger.info("Disconnected from Milvus")
