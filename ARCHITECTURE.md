# PolicyLens - Technical Architecture Document

## System Overview

PolicyLens is a RAG-based compliance intelligence system that combines vector search, LLM reasoning, and case-based learning to automate AML/KYC transaction evaluations.

## Core Components

### 1. Document Ingestion Pipeline

**Purpose**: Transform unstructured compliance documents into searchable vector embeddings.

**Flow**:
```
Raw Document → Section Detection → Text Chunking → Embedding Generation → Vector Storage
```

**Implementation** (`document_processor.py`):
- **Chunking Strategy**: Overlapping 600-word chunks with 100-word overlap
- **Section Detection**: Regex patterns for headers (Section X, Article Y, etc.)
- **Metadata Preservation**: Document source, topic, version, validity dates
- **Embedding**: OpenAI text-embedding-3-large (1536 dims) or local MiniLM

**Key Features**:
- Preserves document structure and context
- Handles multiple document formats
- Version-aware indexing
- Deactivation of outdated policies

### 2. Vector Database (Milvus)

**Purpose**: Fast semantic similarity search over policy chunks.

**Collections**:

#### Policy Chunks Collection
```python
{
    "chunk_id": VARCHAR(100),        # Primary key
    "doc_id": VARCHAR(100),          # Document reference
    "text": VARCHAR(4000),           # Chunk content
    "embedding": FLOAT_VECTOR(1536), # Vector representation
    "doc_title": VARCHAR(500),
    "section": VARCHAR(200),
    "source": VARCHAR(50),           # OFAC, FATF, RBI, etc.
    "topic": VARCHAR(50),            # AML, KYC, sanctions
    "version": VARCHAR(50),
    "is_active": BOOL,
    "valid_from": INT64
}
```

**Index**: HNSW (Hierarchical Navigable Small World)
- Metric: COSINE similarity
- Parameters: M=16, efConstruction=200

#### Compliance Cases Collection
```python
{
    "case_id": VARCHAR(100),
    "transaction_id": VARCHAR(100),
    "embedding": FLOAT_VECTOR(1536),
    "decision": VARCHAR(50),
    "reasoning": VARCHAR(4000),
    "risk_score": FLOAT,
    "timestamp": INT64
}
```

### 3. RAG Evaluation Engine

**Purpose**: Retrieve relevant policies and generate compliance decisions.

**Workflow** (`compliance_engine.py`):

```
1. Transaction Input
   ↓
2. Generate Transaction Embedding
   ↓
3. Vector Search (Top-K policies)
   ├─ Filter: is_active=true
   ├─ Filter: topic (optional)
   └─ Return: Top 5 most relevant
   ↓
4. Retrieve Similar Historical Cases
   └─ Vector similarity to past decisions
   ↓
5. Construct LLM Prompt
   ├─ Transaction details
   ├─ Retrieved policies
   ├─ Similar cases
   └─ Task instructions
   ↓
6. LLM Analysis (GPT-4)
   ├─ Verdict: FLAG | NEEDS_REVIEW | ACCEPTABLE
   ├─ Risk Level: HIGH | MEDIUM | LOW | ACCEPTABLE
   ├─ Risk Score: 0.0 - 1.0
   ├─ Reasoning: Detailed explanation
   └─ Confidence: Model confidence
   ↓
7. Post-Processing
   ├─ Format citations
   ├─ Calculate final risk score
   └─ Store as new case
   ↓
8. Return Decision + Explainability
```

### 4. LLM Service

**Models Used**:
- **GPT-4-turbo-preview**: Transaction evaluation and query answering
- **text-embedding-3-large**: High-quality embeddings (1536 dims)

**Prompt Engineering**:

**Transaction Evaluation Prompt**:
```
You are a compliance analyst evaluating financial transactions against AML/KYC policies.

Transaction Details:
[Transaction info]

Relevant Policies:
[Retrieved policy chunks with citations]

Similar Historical Cases:
[Past decisions with similarity scores]

Task:
Analyze and provide:
1. Verdict (FLAG/NEEDS_REVIEW/ACCEPTABLE)
2. Risk Level (HIGH/MEDIUM/LOW/ACCEPTABLE)
3. Risk Score (0.0-1.0)
4. Reasoning with policy citations
5. Confidence level

Output: JSON
```

**Fallback Logic**:
When LLM unavailable, uses rule-based heuristics:
- Amount thresholds (>$10k, >$50k)
- High-risk country detection
- Policy relevance scores
- Simple additive risk scoring

### 5. Risk Scoring Algorithm

**Multi-Factor Score Calculation**:

```python
risk_score = weighted_sum([
    policy_match_score * 0.4,      # How well policies match
    case_similarity_score * 0.3,   # Similar to past risky cases?
    amount_factor * 0.15,          # Transaction size risk
    country_risk * 0.15            # Jurisdiction risk
])

# Thresholds
HIGH_RISK:       score >= 0.75
MEDIUM_RISK:     0.45 <= score < 0.75
LOW_RISK:        score < 0.45
```

**Components**:
- **Policy Match**: Average relevance of top-K retrieved policies
- **Case Similarity**: Cosine similarity to flagged historical cases
- **Amount Factor**: Logarithmic scale of transaction amount
- **Country Risk**: Binary/categorical risk by jurisdiction

### 6. API Architecture (FastAPI)

**Endpoints**:

```
GET  /                          → Health check
POST /api/policies/upload       → Upload & process policy
POST /api/transactions/evaluate → Evaluate transaction
POST /api/query                 → Answer compliance query
POST /api/feedback              → Submit human feedback
GET  /api/policies/stats        → Policy statistics
```

**Request/Response Models** (Pydantic):
- Type validation
- Automatic OpenAPI docs
- JSON serialization
- Data transformation

**Middleware**:
- CORS for cross-origin requests
- Error handling
- Request logging
- Response time tracking

### 7. Frontend Architecture (React)

**Component Structure**:
```
App.jsx
├── Navbar
└── Routes
    ├── Dashboard         → System overview
    ├── EvaluateTransaction → Transaction form + results
    ├── UploadPolicy      → Policy ingestion
    ├── QueryAssistant    → Q&A interface
    └── Policies          → Policy management
```

**State Management**:
- Local component state (useState)
- No global state library needed for MVP
- API calls via Axios service layer

**Styling**:
- Tailwind CSS utility classes
- Custom component styles
- Responsive design (mobile-friendly)
- Dark mode ready (not implemented)

**Key Features**:
- Real-time API communication
- Form validation
- Loading states
- Error handling with user feedback
- Sample data generation

## Data Flow Examples

### Example 1: Policy Upload

```
User uploads policy
    ↓
Frontend POST /api/policies/upload
    ↓
Backend receives document
    ↓
DocumentProcessor.process_document()
    ├─ Detect sections
    ├─ Create chunks (600 words)
    ├─ Generate embeddings
    └─ Store in Milvus
    ↓
Return: {doc_id, chunks_created, status}
    ↓
Frontend displays success
```

### Example 2: Transaction Evaluation

```
User submits transaction
    ↓
Frontend POST /api/transactions/evaluate
    ↓
ComplianceEngine.evaluate_transaction()
    ├─ Create transaction embedding
    ├─ Search Milvus for policies (top-5)
    ├─ Search Milvus for similar cases (top-3)
    ├─ Call LLM with context
    ├─ Parse LLM response
    ├─ Format citations
    ├─ Store as new case
    └─ Return decision
    ↓
Frontend displays results
    ├─ Verdict badge
    ├─ Risk score visualization
    ├─ Reasoning text
    ├─ Policy citations (expandable)
    └─ Similar cases (expandable)
```

## Performance Characteristics

**Latency Breakdown** (typical transaction evaluation):
- Transaction embedding: ~50ms
- Vector search (policies): ~100ms
- Vector search (cases): ~50ms
- LLM call: ~2-5 seconds
- Post-processing: ~10ms
- **Total**: ~2-5.2 seconds

**Throughput**:
- Sequential: ~10-15 transactions/minute
- With proper batching: ~100+ transactions/minute
- Limited primarily by LLM API rate limits

**Scalability**:
- Milvus: Handles millions of vectors efficiently
- Stateless backend: Horizontal scaling ready
- Frontend: Static files, CDN-deployable

## Security Considerations

**Current (MVP)**:
- No authentication
- Open CORS
- API keys in environment variables
- HTTP (not HTTPS)

**Production Requirements**:
- JWT-based authentication
- Role-based access control (RBAC)
- API key rotation
- HTTPS/TLS encryption
- Rate limiting
- Input sanitization
- Audit logging
- Network segmentation
- Secret management (Vault, AWS Secrets Manager)

## Deployment Architecture

**Docker Compose Stack**:
```
┌─────────────────────────────────────────┐
│              Load Balancer              │
└───────────┬─────────────────────────────┘
            │
    ┌───────┴────────┐
    │                │
┌───▼────┐      ┌────▼───┐
│Frontend│      │Backend │
│(React) │      │(FastAPI)│
└────────┘      └────┬───┘
                     │
            ┌────────┴─────────┐
            │                  │
       ┌────▼─────┐      ┌────▼────┐
       │  Milvus  │      │ OpenAI  │
       │ (Vector) │      │  API    │
       └──┬───┬───┘      └─────────┘
          │   │
    ┌─────┘   └─────┐
┌───▼───┐       ┌───▼───┐
│ etcd  │       │ MinIO │
└───────┘       └───────┘
```

**Volume Persistence**:
- `etcd-data`: Milvus metadata
- `minio-data`: Vector storage
- `milvus-data`: Index files

## Monitoring & Observability

**Current (MVP)**:
- Console logging
- Processing time tracking
- Trace IDs for request tracking

**Production Additions**:
- Prometheus metrics
- Grafana dashboards
- ELK stack for logs
- APM (Application Performance Monitoring)
- Alert manager
- Health checks

## Error Handling Strategy

**Graceful Degradation**:
1. **Milvus Down**: Use rule-based fallback
2. **OpenAI API Error**: Use local embeddings + heuristics
3. **LLM Timeout**: Return cached similar case
4. **Network Issues**: Retry with exponential backoff

**Error Types**:
- **400 Bad Request**: Invalid input data
- **500 Internal Server Error**: System failure
- **503 Service Unavailable**: Dependency down
- **429 Too Many Requests**: Rate limit hit

## Testing Strategy

**Unit Tests** (to be added):
- Service layer functions
- Data validation
- Risk scoring logic

**Integration Tests**:
- API endpoint tests
- Database operations
- LLM mocking

**E2E Tests**:
- Full user workflows
- UI interaction testing
- Performance testing

## Future Enhancements

### Phase 2: Data Persistence
- PostgreSQL for transaction history
- Redis for caching
- Elasticsearch for full-text search

### Phase 3: Advanced Analytics
- Compliance dashboard
- Trend analysis
- Anomaly detection
- Regulatory reporting

### Phase 4: Production Hardening
- Multi-tenancy
- Advanced RBAC
- Audit trails
- Disaster recovery

### Phase 5: ML Improvements
- Model fine-tuning
- Active learning from feedback
- Ensemble models
- Explainability enhancements

## Conclusion

PolicyLens MVP demonstrates a production-feasible architecture for AI-powered compliance automation. The system successfully integrates:
- RAG for knowledge retrieval
- Vector search for semantic matching
- LLM reasoning for decision-making
- Case-based learning for consistency
- Full explainability for audit trails

The modular design allows for incremental improvements and scaling as requirements grow.
