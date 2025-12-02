# 📄 PolicyLens - AI-Powered Compliance Intelligence System

PolicyLens is a production-ready MVP that automatically analyzes financial transactions against AML rules and organizational policies using Retrieval-Augmented Generation (RAG) and vector search with Milvus.

![PolicyLens Demo](https://img.shields.io/badge/Status-MVP-success)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![React](https://img.shields.io/badge/React-18.2-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688)

## 🎯 Features

### ✅ Implemented in This MVP

- **Smart Compliance Assistant**: RAG-based policy analysis with explainable decisions
- **Transaction Evaluation**: Real-time compliance checking with risk scoring
- **Policy Management**: Upload, version, and index compliance documents
- **Case-Based Reasoning**: Leverage historical decisions for consistency
- **Query Assistant**: Natural language Q&A over compliance policies
- **Explainability**: Full decision traces with policy citations
- **Vector Search**: Semantic similarity using Milvus + embeddings
- **Risk Scoring**: Multi-factor risk assessment with confidence levels
- **Demo Mode**: Works without Milvus for quick testing
- **Modern UI**: React + Tailwind CSS dashboard

## 🏗️ Architecture

```
┌─────────────────┐
│   React UI      │  ← User Interface (Port 3000)
└────────┬────────┘
         │
    ┌────▼─────────────────────────────────────────┐
    │         FastAPI Backend (Port 8000)          │
    │  ┌──────────────────────────────────────┐   │
    │  │  Document Processor                   │   │
    │  │  - Chunking   - Embedding             │   │
    │  └──────────────────────────────────────┘   │
    │  ┌──────────────────────────────────────┐   │
    │  │  Compliance Engine                    │   │
    │  │  - RAG      - Risk Scoring            │   │
    │  └──────────────────────────────────────┘   │
    └────────┬─────────────────────┬───────────────┘
             │                     │
    ┌────────▼────────┐   ┌────────▼─────────┐
    │  Milvus Vector  │   │  OpenAI API      │
    │  Database       │   │  (LLM + Embed)   │
    │  (Port 19530)   │   └──────────────────┘
    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (recommended)
- OpenAI API key (optional for demo)

### Option 1: Docker (Recommended)

1. **Clone and setup**:
```bash
cd "d:\Coding Files\Web Dev\Web Development Files\Hackathon"
```

2. **Configure environment**:
```bash
# Copy example env file
cp backend/.env.example backend/.env

# Edit backend/.env and add your OpenAI API key (optional)
# If no API key, system runs with rule-based fallback
notepad backend/.env
```

3. **Start all services**:
```bash
docker-compose up -d
```

4. **Access the application**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Local Development

#### Backend Setup

1. **Create Python virtual environment**:
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start Milvus** (optional - system works without it):
```bash
# Download and run Milvus standalone
# See: https://milvus.io/docs/install_standalone-docker.md
```

5. **Run backend**:
```bash
python -m uvicorn main:app --reload --port 8000
```

#### Frontend Setup

1. **Install dependencies**:
```bash
cd frontend
npm install
```

2. **Start development server**:
```bash
npm run dev
```

3. **Open browser**: http://localhost:3000

## 📖 Usage Guide

### 1. Upload Policy Documents

Navigate to **Upload Policy** and either:
- Click "Load Sample Policy" for a pre-filled AML policy
- Enter your own policy content
- Select source (Internal, OFAC, FATF, RBI, EU AML)
- Choose topic (AML, KYC, Sanctions, Fraud)

The system will:
- Chunk the document into ~600 word segments
- Generate embeddings for each chunk
- Store in Milvus vector database
- Make it searchable

### 2. Evaluate Transactions

Navigate to **Evaluate Transaction**:
- Click "Generate Random" for test data, or
- Fill in transaction details manually
- Click "Evaluate Transaction"

You'll receive:
- **Verdict**: FLAG / NEEDS_REVIEW / ACCEPTABLE
- **Risk Score**: 0.0 - 1.0 with risk level
- **Reasoning**: AI-generated explanation
- **Policy Citations**: Relevant rules with relevance scores
- **Similar Cases**: Historical transactions for context
- **Processing Time**: Performance metrics

### 3. Query Assistant

Navigate to **Query Assistant**:
- Ask natural language questions about policies
- Get AI-powered answers with citations
- Filter by topic (AML, KYC, etc.)
- View source documents for each answer

Example queries:
- "What are the transaction thresholds for AML reporting?"
- "Which countries are considered high-risk?"
- "What documentation is required for enhanced due diligence?"

## 🔧 Configuration

### Backend Configuration (`backend/.env`)

```env
# OpenAI API (required for full functionality)
OPENAI_API_KEY=sk-...

# Milvus Connection
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Model Configuration
EMBEDDING_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4-turbo-preview
LLM_TEMPERATURE=0.1

# RAG Configuration
CHUNK_SIZE=600
CHUNK_OVERLAP=100
TOP_K_RESULTS=5

# Risk Thresholds
HIGH_RISK_THRESHOLD=0.75
MEDIUM_RISK_THRESHOLD=0.45
```

### Alternative: Local Embeddings

To use local embeddings instead of OpenAI:
```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

The system will automatically use `sentence-transformers` for embeddings.

## 🧪 Testing

### Test Backend API

```bash
# Health check
curl http://localhost:8000/

# Upload a policy
curl -X POST http://localhost:8000/api/policies/upload \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Policy",
    "content": "This is test policy content with AML rules...",
    "source": "internal",
    "topic": "aml",
    "version": "1.0"
  }'

# Evaluate transaction
curl -X POST http://localhost:8000/api/transactions/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "transaction": {
      "transaction_id": "TXN001",
      "amount": 50000,
      "currency": "USD",
      "sender": "John Doe",
      "receiver": "Acme Corp",
      "sender_country": "Iran",
      "receiver_country": "USA",
      "timestamp": "2025-12-02T00:00:00Z"
    }
  }'
```

### Interactive API Documentation

Visit http://localhost:8000/docs for Swagger UI with all endpoints.

## 📊 How It Works

### 1. Document Ingestion Pipeline

```
Document → Section Detection → Chunking (600 words)
              ↓
         Embedding Generation (OpenAI/Local)
              ↓
         Vector Storage (Milvus)
              ↓
         Indexed & Searchable
```

### 2. Transaction Evaluation Flow

```
Transaction → Create Embedding
              ↓
         Vector Search (Top-K policies)
              ↓
         Retrieve Similar Cases
              ↓
         LLM Analysis (GPT-4)
              ↓
         Risk Score Calculation
              ↓
    Decision + Citations + Reasoning
              ↓
         Store as Case for CBR
```

### 3. Risk Scoring Algorithm

```python
risk_score = weighted_sum(
    policy_relevance,      # How relevant are matched policies?
    case_similarity,       # How similar to past flagged cases?
    amount_threshold,      # Transaction amount factors
    country_risk,          # Jurisdiction risk levels
    pattern_anomaly        # Behavioral patterns
)
```

## 🎨 Frontend Features

### Dashboard
- System health monitoring
- Policy statistics
- Quick actions
- Getting started guide

### Transaction Evaluator
- Form with validation
- Random test data generator
- Real-time evaluation
- Comprehensive result display

### Policy Manager
- Upload interface
- Sample policy templates
- Metadata tagging
- Version management

### Query Assistant
- Natural language search
- Sample question templates
- Cited answers
- Relevance scoring

## 🔐 Security Considerations

⚠️ **This is an MVP for demonstration purposes**. For production:

- Add authentication & authorization
- Implement rate limiting
- Secure API keys in secret management
- Enable HTTPS/TLS
- Implement audit logging
- Add data encryption
- Set up network isolation
- Configure CORS properly

## 🛠️ Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Milvus**: Vector database for embeddings
- **OpenAI**: LLM (GPT-4) and embeddings
- **Sentence-Transformers**: Local embedding option
- **Pydantic**: Data validation
- **Uvicorn**: ASGI server

### Frontend
- **React 18**: UI framework
- **React Router**: Navigation
- **Tailwind CSS**: Styling
- **Vite**: Build tool
- **Axios**: HTTP client
- **Lucide React**: Icons

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Orchestration
- **Minio**: Object storage for Milvus
- **etcd**: Metadata store for Milvus

## 📁 Project Structure

```
Hackathon/
├── backend/
│   ├── services/
│   │   ├── milvus_service.py       # Vector DB operations
│   │   ├── embedding_service.py    # Embedding generation
│   │   ├── llm_service.py          # LLM calls
│   │   ├── document_processor.py   # Chunking & indexing
│   │   └── compliance_engine.py    # RAG evaluation
│   ├── main.py                     # FastAPI app
│   ├── models.py                   # Pydantic models
│   ├── config.py                   # Configuration
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── Alert.jsx
│   │   │   └── RiskBadge.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── EvaluateTransaction.jsx
│   │   │   ├── UploadPolicy.jsx
│   │   │   ├── QueryAssistant.jsx
│   │   │   └── Policies.jsx
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🐛 Troubleshooting

### Milvus Connection Issues

If Milvus fails to connect:
- Check Docker containers: `docker-compose ps`
- View logs: `docker-compose logs milvus`
- The system works in demo mode without Milvus

### OpenAI API Errors

Without an API key:
- System uses rule-based fallback
- Embeddings use local model
- Decisions are based on heuristics

### Port Already in Use

```bash
# Change ports in docker-compose.yml or:
docker-compose down
# Kill process using the port
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## 🚀 Future Enhancements

- [ ] PostgreSQL for structured data
- [ ] Real-time transaction streaming (Kafka)
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Custom model fine-tuning
- [ ] Sanctions list integration (OFAC API)
- [ ] Automated policy updates
- [ ] Regulatory report generation
- [ ] Human-in-the-loop workflows
- [ ] Performance optimization

## 📝 License

MIT License - Feel free to use for your hackathon or project.

## 🤝 Contributing

This is a hackathon MVP. Contributions welcome:
1. Fork the repo
2. Create feature branch
3. Commit changes
4. Push and create PR

## 📧 Support

For issues or questions:
- Check API docs: http://localhost:8000/docs
- Review logs: `docker-compose logs -f`
- Check this README

## 🎉 Demo Credentials

No authentication required for MVP. System runs in open mode.

---

**Built with ❤️ for compliance automation**

Made for hackathon demonstration - showcasing RAG, vector search, and AI-powered decision-making in financial compliance.
