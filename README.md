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
- Python 3.11+
- Node.js 18+
- OpenAI API key (optional)

### Backend Setup

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Tech Stack

**Backend**: FastAPI, Milvus, OpenAI, Sentence-Transformers  
**Frontend**: React 18, Vite, Tailwind CSS, React Router  
**Infrastructure**: Docker, Docker Compose

## Configuration

Create `backend/.env`:
```env
OPENAI_API_KEY=sk-...
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

System works without API key using rule-based fallback and local embeddings.

## License

MIT
