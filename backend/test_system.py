"""
Test the PolicyLens system with sample transactions
"""

import requests
import json
from datetime import datetime

API_URL = "http://localhost:8000"


def test_evaluation():
    """Test transaction evaluation"""
    
    print("=" * 60)
    print("Testing Transaction Evaluation")
    print("=" * 60)
    print()
    
    # Sample transaction - high-risk
    transaction = {
        "transaction_id": "TXN-DEMO-001",
        "amount": 75000,
        "currency": "USD",
        "sender": "John Smith",
        "receiver": "ABC Trading LLC",
        "sender_country": "USA",
        "receiver_country": "Iran",  # High-risk country
        "description": "Business payment for goods",
        "timestamp": datetime.now().isoformat()
    }
    
    print("Transaction Details:")
    print(json.dumps(transaction, indent=2))
    print()
    print("Evaluating...")
    print()
    
    response = requests.post(
        f"{API_URL}/api/transactions/evaluate",
        json={"transaction": transaction}
    )
    
    if response.status_code == 200:
        result = response.json()
        decision = result["decision"]
        
        print("✅ EVALUATION COMPLETE")
        print(f"Trace ID: {result['trace_id']}")
        print(f"Processing Time: {result['processing_time_ms']:.2f}ms")
        print()
        print("DECISION:")
        print(f"  Verdict: {decision['verdict']}")
        print(f"  Risk Level: {decision['risk_level']}")
        print(f"  Risk Score: {decision['risk_score']:.2f}")
        print(f"  Confidence: {decision['confidence']:.2f}")
        print()
        print("REASONING:")
        print(f"  {decision['reasoning']}")
        print()
        print(f"POLICY CITATIONS: {len(decision['policy_citations'])}")
        for i, citation in enumerate(decision['policy_citations'][:3], 1):
            print(f"  [{i}] {citation['doc_title']}")
            print(f"      Relevance: {citation['relevance_score']:.2f}")
        print()
        
        # Test decision retrieval
        print("Testing decision retrieval...")
        trace_id = result['trace_id']
        
        response2 = requests.get(f"{API_URL}/api/decisions/{trace_id}")
        if response2.status_code == 200:
            print("✅ Decision retrieved successfully")
        
        # Test audit report
        print("Generating audit report...")
        response3 = requests.get(f"{API_URL}/api/audit/report/{trace_id}")
        if response3.status_code == 200:
            print("✅ Audit report generated successfully")
        
        print()
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


def test_query():
    """Test compliance query"""
    
    print("=" * 60)
    print("Testing Compliance Query")
    print("=" * 60)
    print()
    
    query = "What are the requirements for large cash transactions?"
    print(f"Query: {query}")
    print()
    print("Searching policies...")
    print()
    
    response = requests.post(
        f"{API_URL}/api/query",
        json={"query": query, "top_k": 5}
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print("✅ QUERY COMPLETE")
        print()
        print("ANSWER:")
        print(f"  {result['answer']}")
        print()
        print(f"  Confidence: {result['confidence']:.2f}")
        print()
        print(f"CITATIONS: {len(result['citations'])}")
        for i, citation in enumerate(result['citations'][:3], 1):
            print(f"  [{i}] {citation['doc_title']}")
        print()
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


def test_metrics():
    """Display current metrics"""
    
    print("=" * 60)
    print("System Metrics")
    print("=" * 60)
    print()
    
    response = requests.get(f"{API_URL}/api/metrics")
    
    if response.status_code == 200:
        metrics = response.json()
        counters = metrics["counters"]
        decisions = metrics["decisions"]
        
        print("ACTIVITY COUNTERS:")
        print(f"  Total Evaluations: {counters['total_evaluations']}")
        print(f"  Total Queries: {counters['total_queries']}")
        print(f"  Policy Uploads: {counters['total_policy_uploads']}")
        print(f"  Feedback Submissions: {counters['total_feedback']}")
        print()
        
        if decisions['by_verdict']:
            print("DECISIONS BY VERDICT:")
            for verdict, count in decisions['by_verdict'].items():
                print(f"  {verdict}: {count}")
            print()
        
        if decisions['by_risk_level']:
            print("DECISIONS BY RISK LEVEL:")
            for level, count in decisions['by_risk_level'].items():
                print(f"  {level}: {count}")
            print()
        
        eval_latency = metrics['latency']['evaluation']
        if eval_latency['count'] > 0:
            print("EVALUATION LATENCY:")
            print(f"  Average: {eval_latency['avg_ms']:.2f}ms")
            print(f"  P95: {eval_latency['p95_ms']:.2f}ms")
            print()


def test_stats():
    """Display policy statistics"""
    
    print("=" * 60)
    print("Policy Statistics")
    print("=" * 60)
    print()
    
    response = requests.get(f"{API_URL}/api/policies/stats")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"Total Policy Chunks: {stats['total_chunks']}")
        print(f"Total Historical Cases: {stats['total_cases']}")
        print(f"Collection: {stats['collection_name']}")
    print()


if __name__ == "__main__":
    print()
    print("🚀 PolicyLens System Test")
    print()
    
    # Check API health
    try:
        response = requests.get(f"{API_URL}/")
        if response.status_code == 200:
            print("✅ API is running")
            print()
        else:
            print("❌ API not responding")
            exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        exit(1)
    
    # Run tests
    test_stats()
    test_evaluation()
    test_query()
    test_metrics()
    
    print("=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print()
