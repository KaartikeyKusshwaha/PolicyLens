# Milvus Setup Guide for PolicyLens

This guide will help you set up Milvus vector database for PolicyLens RAG system.

## Prerequisites

- Docker Desktop installed and running
- Python 3.13+ with all dependencies installed
- Backend environment configured (`.env` file with API keys)

## Step 1: Start Milvus with Docker Compose

Milvus requires three services: etcd (metadata), MinIO (object storage), and Milvus standalone.

```powershell
# Navigate to project root
cd "d:\Coding Files\Web Dev\Web Development Files\Hackathon"

# Start Milvus (will download images on first run, ~2-3 minutes)
docker-compose up -d milvus

# Check if services are running
docker-compose ps
```

You should see:
- `milvus-etcd` - Running
- `milvus-minio` - Running  
- `milvus-standalone` - Running (port 19530)

## Step 2: Wait for Milvus to be Ready

Milvus takes about 30-60 seconds to fully initialize after containers start.

```powershell
# Check Milvus logs
docker-compose logs -f milvus

# Wait until you see: "Milvus Proxy successfully started"
```

## Step 3: Initialize Milvus with Sample Policies

Once Milvus is running, populate it with sample compliance policies.

```powershell
# Navigate to backend directory
cd backend

# Run initialization script
python scripts/init_milvus.py
```

The script will:
1. Connect to Milvus on localhost:19530
2. Create two collections:
   - `policy_chunks` - Policy document chunks with embeddings
   - `compliance_cases` - Historical compliance decisions
3. Load 5 sample policies (AML, Sanctions, KYC, Fraud, PEP)
4. Generate embeddings using sentence-transformers
5. Insert 15+ policy chunks into Milvus
6. Run a test query to verify everything works

**Expected output:**
```
✅ Milvus initialization completed successfully!
Total chunks inserted: 15
Total policies: 5
```

## Step 4: Start the Backend Server

Now your backend will connect to Milvus instead of using demo policies.

```powershell
# Make sure you're in the backend directory
cd backend

# Start the server
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Look for these log messages:**
```
INFO - Connected to Milvus at localhost:19530
INFO - ✓ Embedding service initialized
INFO - ✓ LLM service initialized
INFO - 🚀 PolicyLens API ready!
```

**No more "Running in demo mode" warning!**

## Step 5: Test RAG System

Open http://localhost:8000 and try the Query Assistant:

**Test queries:**
- "What are the transaction thresholds for AML reporting?"
- "Which countries are prohibited for sanctions?"
- "What documents are required for KYC verification?"
- "What are the red flags for fraud detection?"
- "How should PEPs be handled?"

You should now get answers with **real policy citations** from Milvus!

## Troubleshooting

### Milvus Connection Error
```
ERROR - Failed to connect to Milvus
```

**Solutions:**
1. Check if Milvus is running: `docker-compose ps`
2. Check Milvus logs: `docker-compose logs milvus`
3. Restart Milvus: `docker-compose restart milvus`
4. Wait 60 seconds after restart

### Embedding Dimension Mismatch
If you see dimension errors, the collections were created with wrong dimensions.

**Fix:**
```powershell
# Stop everything
docker-compose down

# Remove volumes (deletes all data)
docker volume rm hackathon_milvus-data hackathon_etcd-data hackathon_minio-data

# Restart and reinitialize
docker-compose up -d milvus
# Wait 60 seconds
python scripts/init_milvus.py
```

### Port Already in Use
If port 19530 is taken:

```powershell
# Check what's using the port
netstat -ano | findstr :19530

# Stop the process or change Milvus port in docker-compose.yml
```

## Managing Milvus

### Stop Milvus
```powershell
docker-compose stop milvus etcd minio
```

### Start Milvus
```powershell
docker-compose start milvus etcd minio
```

### View Milvus Logs
```powershell
docker-compose logs -f milvus
```

### Reset Everything (Delete All Data)
```powershell
docker-compose down -v
# Then restart and reinitialize
```

## Adding More Policies

To add your own policies, modify `scripts/init_milvus.py`:

1. Add policy to `get_sample_policies()` function
2. Follow the same structure:
   - `doc_id`: Unique policy ID
   - `doc_title`: Policy name
   - `sections`: List of sections with title and text
   - `topic`: aml, kyc, sanctions, fraud, etc.
3. Run `python scripts/init_milvus.py` again

## Architecture

```
User Query
    ↓
Embedding Service (sentence-transformers)
    ↓
Query Vector (384 dimensions)
    ↓
Milvus Search (COSINE similarity)
    ↓
Top-K Policy Chunks Retrieved
    ↓
LLM Service (Groq API + Llama 3.1)
    ↓
Generated Answer with Citations
```

## Production Considerations

For production deployment:
1. Use Milvus cluster mode instead of standalone
2. Configure persistent volumes with backups
3. Set up Milvus authentication
4. Monitor Milvus metrics (port 9091)
5. Implement policy versioning and updates
6. Add batch processing for large document uploads
7. Configure index parameters for your query patterns

## Resources

- Milvus Documentation: https://milvus.io/docs
- Sentence Transformers: https://www.sbert.net/
- Project README: See main README.md for full architecture

---

**Status Check:**
- ✅ Milvus running: `docker-compose ps`
- ✅ Collections created: Run init script
- ✅ Backend connected: Check server logs
- ✅ RAG working: Test queries in UI
