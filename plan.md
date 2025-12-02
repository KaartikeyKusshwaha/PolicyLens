# PolicyLens Implementation Plan

## Tech Stack
- **Vector DB**: Milvus
- **LLM**: OpenAI/Claude/Llama 3
- **Embedding**: OpenAI text-embedding-3-large or SentenceTransformers (bge-large/MiniLM)
- **Backend**: FastAPI or Node
- **Frontend**: React + Tailwind
- **Monitoring**: Prometheus + Logs/Trace IDs
- **Deployment**: Docker/Kubernetes

## Phase 1: Data Ingestion & Source Integration

### External Data Sources
| Source | Type | Method |
|--------|------|--------|
| OFAC Sanctions | JSON/CSV | API/scheduled import |
| FATF High-Risk Countries | CSV/PDF | Scraping + parsing |
| RBI Circulars | PDF/HTML | Scraping + scheduled fetch |
| EU AML Directives | PDF | Connector + OCR |
| Transaction Systems | Live stream | Kafka/REST Webhooks |

### Steps
1. Build connectors for SharePoint/Google Drive/file storage
2. Monitor folders for new/updated files
3. Extract text using pdfplumber/Tika/Tesseract OCR for scanned docs
4. Normalize content: remove formatting noise, detect sections/headings
5. Store raw text + metadata: source path, version, policy type, date
6. Set up transaction event stream listener (Kafka/REST)

## Phase 2: Chunking, Embedding & Milvus Indexing

### Milvus Schema
```
- embedding: vector
- text: string
- doc_id: string
- version: string
- topic: string (AML/KYC/etc.)
- source: string (SharePoint/RBI/OFAC)
- valid_from: date
- valid_to: date
- is_active: boolean
```

### Steps
1. Split documents into overlapping chunks (300-800 tokens) preserving headings
2. Generate embeddings using chosen model
3. Insert into Milvus with all metadata fields
4. Apply indexing strategy (HNSW or IVF_FLAT)
5. Create collection for historical case vectors

## Phase 3: RAG Engine for Transaction Evaluation

### Workflow
1. Convert transaction/query to embedding
2. Query Milvus with semantic similarity + metadata filters (`topic="AML" AND is_active=true`)
3. Retrieve top-k relevant policy chunks
4. Construct LLM prompt with:
   - Retrieved policy text
   - Citations (doc + section)
   - Transaction details
5. LLM generates:
   - Verdict (Flag/Needs Review/Acceptable)
   - Reasoning
   - Policy citations
   - Risk score justification

### Implementation
1. Build RAG pipeline with retrieval + prompt construction
2. Implement LLM call handler with retry logic
3. Parse and structure LLM response
4. Store decision with full trace

## Phase 4: Policy Change Detection & Sentinel

### Steps
1. Monitor source locations for document updates (file hash/timestamp)
2. On change detected:
   - Extract new version
   - Reprocess and generate new chunks
   - Mark old Milvus entries as `is_active=false`
   - Insert new chunks with updated version
3. Compute semantic diff to detect rule changes
4. Identify impacted transactions based on policy chunks used
5. Trigger re-evaluation workflow for affected transactions
6. Generate change impact report

## Phase 5: Risk Scoring & Case-Based Reasoning

### Steps
1. Store past flagged outcomes as case vectors in Milvus
2. For each new decision:
   - Run similarity search against historical cases
   - Retrieve top-k similar cases
3. Calculate composite risk score from:
   - Policy confidence from RAG
   - Case similarity scores
   - Metadata checks (amount thresholds, country risk, etc.)
   - Historical pattern matching
4. Assign numeric risk score (0-100 scale)

## Phase 6: Explainability & Audit Output

### Components
1. Structured reasoning chain with:
   - Final decision
   - Highlighted relevant rules with citations
   - Similar case references
   - Confidence levels
   - Complete retrieval trace
2. Generate downloadable PDF/JSON reports
3. Include prompt + response for full auditability
4. Create explainability panel UI component
5. Implement audit log storage

## Phase 7: Human Feedback Loop

### Steps
1. Build override/annotation interface
2. Capture feedback data:
   - Policy chunk used
   - Incorrect reasoning generated
   - Manual correction provided
   - Override justification
3. Store feedback in catalog format
4. Use feedback to:
   - Re-rank search relevance
   - Update prompt templates
   - Improve scoring heuristics
   - Fine-tune retrieval parameters
5. Periodic model retraining/adjustment

## Phase 8: API & Integration Layer

### Endpoints
1. POST `/ingest/document` - Upload policy document
2. POST `/evaluate/transaction` - Real-time transaction check
3. GET `/policies` - List active policies
4. POST `/policies/update` - Trigger policy update
5. GET `/decisions/{id}` - Retrieve decision details
6. POST `/feedback` - Submit human override
7. GET `/audit/report` - Generate audit report

## Phase 9: UI Development

### Features
1. **Smart Compliance Assistant**: Query interface with RAG responses
2. **Policy Management**: Upload, view, version policies
3. **Transaction Dashboard**: Real-time evaluation feed
4. **Policy Change Alerts**: Sentinel notifications
5. **Explainability Panel**: Interactive decision breakdown
6. **Case Similarity Viewer**: Show similar historical cases
7. **Feedback Interface**: Override and annotate decisions
8. **Audit Report Generator**: Downloadable compliance reports

## Phase 10: Testing & Demo Scenarios

### Test Cases
1. Load initial policy set and verify indexing
2. Submit test transaction → verify automated analysis
3. Update policy document → verify re-evaluation triggers
4. Test explainability with citations
5. Submit feedback → verify learning loop
6. Generate audit report
7. Test external data source integration (OFAC/FATF)
8. Stress test with high transaction volume

## Demo Flow
1. Show policy library loading dynamically
2. Trigger new transaction → automated risk decision
3. Update a policy → show instant outcome change for similar transactions
4. Display transparent reasoning with citations
5. Export audit-ready report

## Monitoring & Observability

### Metrics
1. Retrieval accuracy and latency
2. LLM response time
3. Decision throughput
4. Policy update lag
5. Re-evaluation queue depth
6. Feedback incorporation rate
7. Error rates and trace IDs

### Implementation
1. Set up Prometheus metrics collection
2. Implement structured logging
3. Add trace IDs to all requests
4. Create monitoring dashboard
5. Set up alerting for failures