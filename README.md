# PolicyLens - AI-Powered Compliance Intelligence

AI system that analyzes financial transactions against AML rules using RAG, vector search, and GPT-4.

## Features

- **Transaction Evaluation**: Real-time compliance checking with risk scoring
- **Policy Management**: Upload and index compliance documents
- **Query Assistant**: Natural language Q&A over policies
- **RAG-based Analysis**: Retrieval-Augmented Generation with Milvus vector DB
- **Explainable Decisions**: Full traces with policy citations

## Quick Start

### Prerequisites
- **Docker Desktop** (recommended) - [Download](https://www.docker.com/products/docker-desktop/)
- Python 3.11+ (for local development)
- Node.js 18+ (for local development)
- OpenAI API key (optional - system works in demo mode without it)

### 🚀 Quick Start (Recommended)

**Using Docker Compose (All services in one command):**

```powershell
# Run the interactive startup script
.\start.ps1
# Choose Option 1: Quick Start (Docker + Auto-open browser)
```

The script will:
- Start Milvus vector database (etcd + MinIO + Milvus)
- Start FastAPI backend on port 8000
- Start React frontend on port 3000
- Run health checks
- Auto-open browser to http://localhost:3000

**Or manually with Docker Compose:**

```bash
docker-compose up -d
```

Wait 30 seconds for initialization, then access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 🛠️ Local Development Setup

**Backend Only (requires Docker for Milvus):**

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

**Frontend Only:**

```bash
cd frontend
npm install
npm run dev
```

### 🛑 Stop Services

```bash
docker-compose down
# Or use start.ps1 -> Option 5: Stop all services
```

## Tech Stack

**Backend**: FastAPI, Milvus, OpenAI, Sentence-Transformers  
**Frontend**: React 18, Vite, Tailwind CSS, React Router  
**Infrastructure**: Docker, Docker Compose

## Configuration

**Optional**: Create `backend/.env` for API keys:
```env
OPENAI_API_KEY=sk-...  # Optional - uses OpenRouter fallback
OPENROUTER_API_KEY=sk-or-v1-...  # Optional
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

✅ System works without API keys using rule-based fallback and local embeddings.

## Docker Services

The `docker-compose.yml` includes:
- **Milvus** (v2.3.3): Vector database on port 19530
- **etcd** (v3.5.5): Milvus metadata storage
- **MinIO**: Milvus object storage
- **Backend**: FastAPI on port 8000
- **Frontend**: React/Vite on port 3000

All services start together with `docker-compose up -d` or using `start.ps1`.

## Project Structure

```
PolicyLens/
├── backend/           # FastAPI backend
│   ├── services/      # Core services (Milvus, LLM, Compliance)
│   ├── models.py      # Pydantic models
│   ├── main.py        # FastAPI app
│   └── requirements.txt
├── frontend/          # React frontend
│   ├── src/
│   └── package.json
├── docker-compose.yml # Docker orchestration
└── start.ps1         # Interactive startup script
```

## License

MIT
