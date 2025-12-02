# 🚀 PolicyLens - Quick Reference Guide

## 📋 30-Second Setup

```powershell
# 1. Check your system
.\check-system.ps1

# 2. Configure (optional - add OpenAI key)
notepad backend\.env

# 3. Start everything
.\start.ps1
# Choose option 1

# 4. Open browser
http://localhost:3000
```

## 🎯 Quick Demo Flow

### 1. Upload a Policy (2 minutes)
- Navigate to **Upload Policy**
- Click **"Load Sample Policy"**
- Click **"Upload and Process Policy"**
- Wait ~5 seconds for processing

### 2. Evaluate a Transaction (2 minutes)
- Navigate to **Evaluate Transaction**
- Click **"Generate Random"**
- Click **"Evaluate Transaction"**
- Review the decision with:
  - Verdict badge
  - Risk score
  - AI reasoning
  - Policy citations
  - Similar cases

### 3. Ask a Question (1 minute)
- Navigate to **Query Assistant**
- Click any sample question
- Click **"Search Policies"**
- Read AI answer with citations

## 🔧 Common Commands

### Docker Operations
```powershell
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f milvus

# Restart a service
docker-compose restart backend

# Check status
docker-compose ps
```

### Local Development

**Backend**:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --port 8000
```

**Frontend**:
```powershell
cd frontend
npm run dev
```

## 🌐 URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | React UI |
| Backend | http://localhost:8000 | FastAPI API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Milvus | localhost:19530 | Vector DB |

## 📊 API Quick Test

```powershell
# Health check
curl http://localhost:8000/

# Run full test suite
.\test-api.ps1
```

## 🎨 Key Features Demo Points

### Feature: Smart Compliance Assistant
- **Demo**: Upload policy → Evaluate transaction → Show citations
- **Highlight**: RAG retrieval with semantic search

### Feature: Risk Scoring
- **Demo**: Generate random high-risk transaction (Iran, large amount)
- **Highlight**: Multi-factor risk calculation

### Feature: Explainability
- **Demo**: Click on policy citations
- **Highlight**: Full traceability with relevance scores

### Feature: Case-Based Reasoning
- **Demo**: Evaluate similar transactions
- **Highlight**: Similar cases section

### Feature: Query Assistant
- **Demo**: Ask "What are high-risk countries?"
- **Highlight**: Natural language Q&A with citations

## 🐛 Troubleshooting Quick Fixes

### "Port already in use"
```powershell
# Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### "Milvus connection failed"
```powershell
# Check Milvus status
docker-compose logs milvus

# Restart Milvus
docker-compose restart milvus
```

### "Module not found" (Backend)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### "Cannot find module" (Frontend)
```powershell
cd frontend
npm install
```

## 📝 Sample Test Data

### High-Risk Transaction
- Amount: $75,000
- Sender Country: Iran
- Receiver Country: USA
- Expected: **FLAG** verdict

### Medium-Risk Transaction
- Amount: $25,000
- Sender Country: Singapore
- Receiver Country: USA
- Expected: **NEEDS_REVIEW** verdict

### Low-Risk Transaction
- Amount: $5,000
- Sender Country: USA
- Receiver Country: UK
- Expected: **ACCEPTABLE** verdict

## 🎓 Architecture Quick Reference

```
User → React UI → FastAPI → Milvus + OpenAI → Response
                     ↓
              Services Layer:
              - Document Processor
              - Embedding Service
              - LLM Service
              - Compliance Engine
```

## 🔐 Security Notes (MVP)

⚠️ **Not for production use as-is**

Missing for production:
- Authentication
- HTTPS
- Rate limiting
- Input validation
- Audit logging

## 📦 File Count Summary

- **Backend**: 8 Python files + config
- **Frontend**: 13 React files + config
- **Infrastructure**: 3 Docker files
- **Documentation**: 4 markdown files
- **Scripts**: 3 PowerShell files
- **Total**: ~35 files

## ⚡ Performance Expectations

| Operation | Time |
|-----------|------|
| Policy upload | ~1-5s |
| Transaction eval | ~2-5s |
| Query answer | ~2-4s |
| Vector search | ~50-150ms |

## 🎯 Hackathon Presentation Tips

1. **Start with Impact**: Show the problem (manual compliance)
2. **Demo the Solution**: Live transaction evaluation
3. **Highlight Innovation**: RAG + Vector Search + LLM
4. **Show Explainability**: Citations and reasoning
5. **Technical Depth**: Architecture diagram
6. **Future Vision**: Scaling and enhancements

## 📞 Support Resources

- README.md - Full documentation
- ARCHITECTURE.md - Technical details
- IMPLEMENTATION_SUMMARY.md - What was built
- API Docs - http://localhost:8000/docs

## ✅ Pre-Demo Checklist

- [ ] System check passed (`.\check-system.ps1`)
- [ ] All services running (`docker-compose ps`)
- [ ] Sample policy uploaded
- [ ] Test transaction evaluated
- [ ] Query assistant tested
- [ ] Browser tabs open:
  - [ ] http://localhost:3000
  - [ ] http://localhost:8000/docs
- [ ] Demo data ready
- [ ] Architecture diagram visible

## 🎉 Success Indicators

✓ Services are green in Docker  
✓ Frontend loads without errors  
✓ Policy upload succeeds  
✓ Transaction evaluation returns decision  
✓ Query assistant answers questions  

---

**You're ready to present PolicyLens!** 🚀

Quick Start: `.\start.ps1` → Choose 1 → Open http://localhost:3000
