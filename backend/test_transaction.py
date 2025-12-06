"""Test transaction evaluation"""
import requests
import json

# Test transaction
tx_data = {
    "transaction": {
        "transaction_id": "TEST-001",
        "sender": "John Doe",
        "receiver": "Iranian Bank Ltd",
        "sender_country": "USA",
        "receiver_country": "Iran",
        "amount": 50000,
        "currency": "USD",
        "description": "Wire transfer to sanctioned country"
    }
}

print("\n" + "="*60)
print("TRANSACTION EVALUATION TEST")
print("="*60)

print("\nTransaction Details:")
print(f"  ID: {tx_data['transaction']['transaction_id']}")
print(f"  From: {tx_data['transaction']['sender']} ({tx_data['transaction']['sender_country']})")
print(f"  To: {tx_data['transaction']['receiver']} ({tx_data['transaction']['receiver_country']})")
print(f"  Amount: {tx_data['transaction']['amount']} {tx_data['transaction']['currency']}")

print("\nEvaluating transaction...")

try:
    response = requests.post(
        'http://localhost:8000/api/transactions/evaluate',
        json=tx_data,
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n" + "="*60)
        print("EVALUATION RESULT")
        print("="*60)
        
        print(f"\n🎯 Verdict: {result.get('verdict')}")
        print(f"📊 Risk Score: {result.get('risk_score')}")
        print(f"⚠️  Risk Level: {result.get('risk_level')}")
        print(f"🔍 Trace ID: {result.get('trace_id')}")
        print(f"⏱️  Processing Time: {result.get('processing_time_ms')}ms")
        
        print(f"\n📝 Reasoning:")
        print(f"   {result.get('reasoning', 'N/A')}")
        
        citations = result.get('policy_citations', [])
        print(f"\n📚 Policy Citations ({len(citations)}):")
        for i, citation in enumerate(citations[:3], 1):
            print(f"   {i}. {citation.get('policy_id')} (relevance: {citation.get('relevance_score', 0):.2f})")
            print(f"      {citation.get('text', '')[:80]}...")
        
        similar_cases = result.get('similar_cases', [])
        print(f"\n🔄 Similar Historical Cases ({len(similar_cases)}):")
        for i, case in enumerate(similar_cases[:2], 1):
            print(f"   {i}. {case.get('case_id')} (similarity: {case.get('similarity_score', 0):.2f})")
            print(f"      Verdict: {case.get('verdict')}")
        
        print("\n✅ Transaction evaluation successful!")
        
    else:
        print(f"\n❌ Evaluation failed: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*60)
