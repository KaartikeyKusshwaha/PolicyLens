"""
Quick test to verify policies and query endpoints are working
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_policies():
    print("=" * 60)
    print("  TEST: GET /api/policies")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/policies", timeout=5)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total Policies: {data.get('total', 0)}")
        print(f"Mode: {data.get('mode', 'unknown')}")
        print(f"\nPolicies:")
        for p in data.get('policies', []):
            print(f"  - {p.get('title')} ({p.get('topic')})")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_query():
    print("\n" + "=" * 60)
    print("  TEST: POST /api/query")
    print("=" * 60)
    try:
        payload = {
            "query": "What are the transaction thresholds for AML reporting?",
            "topic": None,
            "top_k": 5
        }
        response = requests.post(f"{BASE_URL}/query", json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Confidence: {data.get('confidence', 0):.2f}")
        print(f"Answer Preview: {data.get('answer', '')[:150]}...")
        print(f"Citations: {len(data.get('citations', []))}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("\n🧪 PolicyLens Endpoint Test\n")
    test_policies()
    test_query()
    print("\n✅ All tests completed!\n")
