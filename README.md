# PolicyLens - AI-Powered Compliance Intelligence System

🚀 **Production-ready RAG-based compliance evaluation system with automated regulatory data integration**

AI-powered system that analyzes financial transactions against AML/KYC policies using Retrieval-Augmented Generation (RAG), vector search, and LLMs. Automatically fetches and integrates data from OFAC, FATF, and RBI.

## ✨ Key Features

### Core Capabilities
- **🔍 Real-time Transaction Evaluation** - Instant compliance checking with risk scoring (0-100)
- **📚 Policy Management** - Upload, version, and track compliance documents (PDF/DOCX/TXT)
- **🤖 Smart Query Assistant** - Natural language Q&A over policy database
- **📊 Risk Scoring** - Multi-factor analysis with explainable AI
- **🔄 Policy Change Detection** - Automatic impact analysis and re-evaluation
- **📝 Audit Reports** - Downloadable PDF/JSON compliance reports
- **💬 Human Feedback Loop** - Override decisions with annotations

### External Data Integration (NEW)
- **🌐 OFAC Sanctions** - US Treasury SDN list (11,000+ entities) - Daily updates
- **🗺️ FATF Jurisdictions** - High-risk countries (3) + Monitored (26) - Weekly updates  
- **🏦 RBI Circulars** - Indian regulatory updates - Daily updates
- **⏰ Automated Scheduler** - Background data fetching (no manual intervention)
- **🔌 Zero API Keys** - All external sources are free public data

## 🏗️ Architecture

```
Frontend (React) → Backend API (FastAPI) → Vector DB (Milvus)
                                         → LLM Service (OpenRouter/Groq)
                                         → External Data (OFAC/FATF/RBI)
                                         → Storage Service (JSON)
```

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Milvus** (optional - runs in demo mode without it)
- **LLM API Key** (OpenRouter/Groq - free tier available)

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Create .env file
echo "openai_api_key=your_api_key_here" > .env

# Start server
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Backend will be available at:** `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

**Frontend will be available at:** `http://localhost:3000`

### 3. With Docker (Full Stack)

```bash
docker-compose up -d
```

This starts:
- Milvus vector database
- Backend API
- Frontend UI

## 📱 User Interface

Access these pages at `http://localhost:3000`:

1. **Dashboard** - System overview and metrics
2. **Evaluate Transaction** - Submit transactions for compliance review
3. **Decision History** - Browse past evaluations with filters
4. **Policies** - View and manage policy documents
5. **External Data Sources** - Monitor OFAC/FATF/RBI data fetching
6. **Query Assistant** - Ask questions about policies
7. **Metrics** - System statistics and performance
8. **Feedback** - Review and annotate decisions
9. **Upload Policy** - Add new compliance documents

## 🔌 API Endpoints

### Transaction Evaluation
```bash
POST /api/transactions/evaluate
GET  /api/decisions
GET  /api/decisions/{id}
```

### Policy Management
```bash
POST /api/policies/upload
POST /api/policies/upload-file
GET  /api/policies
POST /api/policies/{id}/update
GET  /api/policies/changes
```

### External Data (NEW)
```bash
POST /api/external-data/fetch?source=OFAC|FATF|RBI
POST /api/external-data/sync
GET  /api/external-data/scheduler/status
POST /api/external-data/scheduler/trigger
GET  /api/external-data/history
```

### Audit & Reports
```bash
GET  /api/audit/report/{trace_id}?format=pdf
POST /api/feedback
GET  /api/metrics
```

## 🤖 External Data Integration

### Automated Schedule
- **OFAC**: Daily at 2:00 AM
- **FATF**: Weekly on Monday at 3:00 AM
- **RBI**: Daily at 4:00 AM
- **Full Sync**: Weekly on Sunday at 1:00 AM

### Manual Fetch
```bash
# Fetch FATF data (instant - no API call)
curl -X POST http://localhost:8000/api/external-data/fetch?source=FATF

# Check scheduler status
curl http://localhost:8000/api/external-data/scheduler/status

# Trigger full sync
curl -X POST http://localhost:8000/api/external-data/sync
```

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern async Python framework
- **Milvus** - Vector database for semantic search
- **Sentence-Transformers** - Local embeddings (no API cost)
- **OpenRouter/Groq** - LLM inference
- **APScheduler** - Background job scheduling
- **BeautifulSoup** - Web scraping for RBI
- **ReportLab** - PDF generation

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **Lucide Icons** - Icon library

### Data Sources
- **OFAC** - US Treasury sanctions lists
- **FATF** - Financial Action Task Force risk data
- **RBI** - Reserve Bank of India circulars

## ⚙️ Configuration

### Backend (.env)
```bash
# LLM Configuration
openai_api_key=your_api_key
api_base_url=https://api.groq.com/openai/v1
llm_model=llama-3.1-8b-instant

# Milvus
milvus_host=localhost
milvus_port=19530

# Models
embedding_model=all-MiniLM-L6-v2
```

### Frontend (vite.config.js)
```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

## 📊 System Status

**Implementation Completion: 92%**

✅ Complete RAG pipeline  
✅ Transaction evaluation  
✅ Policy management  
✅ Change detection  
✅ External data integration  
✅ Automated scheduler  
✅ Full UI (11 pages)  
✅ Audit reports  
✅ Risk scoring  
⏳ Feedback-based learning (8%)

## 🎯 Use Cases

1. **AML Compliance** - Screen transactions against sanctions lists
2. **KYC Verification** - Check customer countries against risk jurisdictions  
3. **Regulatory Updates** - Auto-fetch latest compliance rules
4. **Audit Trail** - Generate compliance reports for regulators
5. **Policy Analysis** - Query complex policy documents in natural language

## 📝 Example Usage

### Evaluate a Transaction
```python
import requests

transaction = {
    "transaction_id": "TXN-001",
    "from_country": "United States",
    "to_country": "Iran",
    "amount": 50000,
    "currency": "USD"
}

response = requests.post(
    "http://localhost:8000/api/transactions/evaluate",
    json=transaction
)

result = response.json()
print(f"Verdict: {result['verdict']}")
print(f"Risk Score: {result['risk_score']}")
print(f"Reasoning: {result['reasoning']}")
```

**Expected Output:**
```
Verdict: FLAG
Risk Score: 0.95
Reasoning: Transaction involves Iran, a FATF high-risk jurisdiction under 
           "Call for Action". Enhanced due diligence required.
```

## 🔐 Security Notes

- Store API keys in `.env` files (never commit)
- Use HTTPS in production
- Implement rate limiting for external data fetching
- Regular security audits of dependencies

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR.

## 📞 Support

For issues or questions:
- Open a GitHub issue
- Check `/docs` endpoint for API documentation
- Review logs in `backend/data/` directory

---

**Built with ❤️ for compliance automation**

Create `backend/.env`:
```env
OPENAI_API_KEY=sk-...
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

System works without API key using rule-based fallback and local embeddings.

## License

MIT
