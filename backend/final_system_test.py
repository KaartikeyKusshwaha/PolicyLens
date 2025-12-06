"""
POLICYLENS SYSTEM - FINAL COMPREHENSIVE TEST
"""
import requests
import time

BASE = "http://localhost:8000"
FRONTEND = "http://localhost:3000"

print("\n" + "="*70)
print(" "*20 + "POLICYLENS - SYSTEM TEST SUITE")
print("="*70)

results = []

# Test 1: Backend Health
print("\n[1/8] Backend Health Check...")
try:
    r = requests.get(f"{BASE}/api/health", timeout=5)
    if r.status_code == 200:
        print("      ✅ Backend API: ONLINE")
        results.append(("Backend API", True))
    else:
        print(f"      ❌ Backend API: Status {r.status_code}")
        results.append(("Backend API", False))
except Exception as e:
    print(f"      ❌ Backend API: {e}")
    results.append(("Backend API", False))

# Test 2: Frontend
print("\n[2/8] Frontend Health Check...")
try:
    r = requests.get(FRONTEND, timeout=5)
    if r.status_code == 200:
        print("      ✅ Frontend UI: ONLINE")
        results.append(("Frontend UI", True))
    else:
        print(f"      ❌ Frontend UI: Status {r.status_code}")
        results.append(("Frontend UI", False))
except Exception as e:
    print(f"      ❌ Frontend UI: {e}")
    results.append(("Frontend UI", False))

# Test 3: External Data Scheduler
print("\n[3/8] External Data Scheduler...")
try:
    r = requests.get(f"{BASE}/api/external-data/scheduler/status", timeout=5)
    if r.status_code == 200:
        data = r.json()
        if data.get('running'):
            jobs = len(data.get('jobs', []))
            print(f"      ✅ Data Scheduler: RUNNING ({jobs} jobs)")
            results.append(("Data Scheduler", True))
        else:
            print("      ❌ Data Scheduler: NOT RUNNING")
            results.append(("Data Scheduler", False))
    else:
        print(f"      ❌ Data Scheduler: Status {r.status_code}")
        results.append(("Data Scheduler", False))
except Exception as e:
    print(f"      ❌ Data Scheduler: {e}")
    results.append(("Data Scheduler", False))

# Test 4: External Data Fetch (FATF)
print("\n[4/8] External Data Fetch (FATF)...")
try:
    r = requests.post(f"{BASE}/api/external-data/fetch?source=FATF", timeout=10)
    if r.status_code == 200:
        data = r.json()
        high_risk = data.get('data', {}).get('high_risk', {}).get('count', 0)
        monitored = data.get('data', {}).get('monitored', {}).get('count', 0)
        print(f"      ✅ FATF Data: {high_risk} high-risk, {monitored} monitored")
        results.append(("FATF Data Fetch", True))
    else:
        print(f"      ❌ FATF Data: Status {r.status_code}")
        results.append(("FATF Data Fetch", False))
except Exception as e:
    print(f"      ❌ FATF Data: {e}")
    results.append(("FATF Data Fetch", False))

# Test 5: Policies API
print("\n[5/8] Policy Management API...")
try:
    r = requests.get(f"{BASE}/api/policies", timeout=5)
    if r.status_code == 200:
        policies = r.json()
        count = len(policies) if isinstance(policies, list) else 0
        print(f"      ✅ Policies API: {count} policies loaded")
        results.append(("Policies API", True))
    else:
        print(f"      ❌ Policies API: Status {r.status_code}")
        results.append(("Policies API", False))
except Exception as e:
    print(f"      ❌ Policies API: {e}")
    results.append(("Policies API", False))

# Test 6: Transaction Evaluation
print("\n[6/8] Transaction Evaluation...")
try:
    tx = {
        "transaction": {
            "transaction_id": "FINAL-TEST-001",
            "sender": "John Doe",
            "receiver": "Iranian Bank",
            "sender_country": "USA",
            "receiver_country": "Iran",
            "amount": 50000,
            "currency": "USD",
            "description": "Test transfer"
        }
    }
    r = requests.post(f"{BASE}/api/transactions/evaluate", json=tx, timeout=30)
    if r.status_code == 200:
        result = r.json()
        trace_id = result.get('trace_id', 'N/A')[:8]
        print(f"      ✅ Transaction Eval: SUCCESS (trace: {trace_id}...)")
        results.append(("Transaction Eval", True))
    else:
        print(f"      ❌ Transaction Eval: Status {r.status_code}")
        results.append(("Transaction Eval", False))
except Exception as e:
    print(f"      ❌ Transaction Eval: {e}")
    results.append(("Transaction Eval", False))

# Test 7: Decisions API
print("\n[7/8] Decision History API...")
try:
    r = requests.get(f"{BASE}/api/decisions", timeout=5)
    if r.status_code == 200:
        decisions = r.json()
        count = len(decisions) if isinstance(decisions, list) else 0
        print(f"      ✅ Decisions API: {count} decisions stored")
        results.append(("Decisions API", True))
    else:
        print(f"      ❌ Decisions API: Status {r.status_code}")
        results.append(("Decisions API", False))
except Exception as e:
    print(f"      ❌ Decisions API: {e}")
    results.append(("Decisions API", False))

# Test 8: Metrics
print("\n[8/8] System Metrics...")
try:
    r = requests.get(f"{BASE}/api/metrics", timeout=5)
    if r.status_code == 200:
        metrics = r.json()
        evals = metrics.get('total_evaluations', 0)
        queries = metrics.get('total_queries', 0)
        print(f"      ✅ Metrics: {evals} evaluations, {queries} queries")
        results.append(("Metrics API", True))
    else:
        print(f"      ❌ Metrics: Status {r.status_code}")
        results.append(("Metrics API", False))
except Exception as e:
    print(f"      ❌ Metrics: {e}")
    results.append(("Metrics API", False))

# Summary
print("\n" + "="*70)
print(" "*25 + "TEST SUMMARY")
print("="*70)

passed = sum(1 for _, status in results if status)
total = len(results)

for name, status in results:
    icon = "✅" if status else "❌"
    print(f"  {icon} {name:<25} {'PASS' if status else 'FAIL'}")

print("\n" + "-"*70)
print(f"  TOTAL: {passed}/{total} tests passed ({(passed/total)*100:.0f}%)")
print("-"*70)

if passed == total:
    print("\n  🎉 ALL SYSTEMS OPERATIONAL - POLICYLENS IS READY!")
else:
    print(f"\n  ⚠️  {total - passed} test(s) failed - Review errors above")

print("\n" + "="*70)
print("\n💡 Access Points:")
print(f"   Frontend:  {FRONTEND}")
print(f"   Backend:   {BASE}")
print(f"   API Docs:  {BASE}/docs")
print(f"   Data Mgmt: {FRONTEND}/external-data")
print("\n" + "="*70 + "\n")
