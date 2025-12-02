"""
Load sample AML/KYC policies into the system for demo purposes
Run this script after starting the backend server
"""

import requests
import json
from sample_policies import get_sample_policies


API_URL = "http://localhost:8000"


def load_sample_policies():
    """Load all sample policies into the system"""
    
    print("=" * 60)
    print("PolicyLens - Sample Policy Loader")
    print("=" * 60)
    print()
    
    # Check if API is available
    try:
        response = requests.get(f"{API_URL}/")
        if response.status_code != 200:
            print("❌ Backend API is not responding. Please start the server first.")
            return
        
        api_info = response.json()
        print(f"✓ Connected to {api_info['service']} v{api_info['version']}")
        print(f"✓ Milvus connected: {api_info['milvus_connected']}")
        print()
        
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        print("Please ensure the backend server is running on http://localhost:8000")
        return
    
    # Load sample policies
    policies = get_sample_policies()
    print(f"Loading {len(policies)} sample policies...")
    print()
    
    successful = 0
    failed = 0
    
    for i, policy in enumerate(policies, 1):
        try:
            print(f"[{i}/{len(policies)}] Uploading: {policy['title'][:50]}...")
            
            response = requests.post(
                f"{API_URL}/api/policies/upload",
                json=policy,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"    ✓ Uploaded successfully ({result['chunks_created']} chunks created)")
                print(f"      Doc ID: {result['doc_id']}")
                successful += 1
            else:
                print(f"    ❌ Failed: {response.status_code} - {response.text}")
                failed += 1
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            failed += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    print(f"  ✓ Successfully loaded: {successful}")
    if failed > 0:
        print(f"  ❌ Failed: {failed}")
    print("=" * 60)
    print()
    
    # Get stats
    try:
        response = requests.get(f"{API_URL}/api/policies/stats")
        if response.status_code == 200:
            stats = response.json()
            print("Current System Stats:")
            print(f"  Total chunks in Milvus: {stats.get('total_chunks', 0)}")
            print(f"  Total cases stored: {stats.get('total_cases', 0)}")
    except:
        pass
    
    print()
    print("🎉 Sample policies loaded successfully!")
    print("You can now:")
    print("  1. Evaluate transactions against these policies")
    print("  2. Query the compliance assistant")
    print("  3. View policy statistics")
    print()


if __name__ == "__main__":
    load_sample_policies()
