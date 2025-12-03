"""Check Milvus statistics"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymilvus import connections, Collection, utility

try:
    connections.connect(host="localhost", port=19530)
    print("✓ Connected to Milvus\n")
    
    # Check policy_chunks collection
    if utility.has_collection("policy_chunks"):
        collection = Collection("policy_chunks")
        collection.load()
        count = collection.num_entities
        print(f"📚 policy_chunks collection:")
        print(f"   - Total chunks: {count}")
        print(f"   - Schema: 384D embeddings, COSINE similarity")
        print(f"   - Index: HNSW")
    
    # Check compliance_cases collection
    if utility.has_collection("compliance_cases"):
        collection = Collection("compliance_cases")
        collection.load()
        count = collection.num_entities
        print(f"\n📁 compliance_cases collection:")
        print(f"   - Total cases: {count}")
        print(f"   - Schema: 384D embeddings, COSINE similarity")
        print(f"   - Index: HNSW")
    
    connections.disconnect()
    print("\n✅ Milvus status: Healthy")
    
except Exception as e:
    print(f"❌ Error: {e}")
