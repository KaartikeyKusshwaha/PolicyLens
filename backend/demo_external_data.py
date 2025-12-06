"""
Quick demo of external data sources
Shows FATF data which doesn't require network calls
"""

from services.external_data_sources import FATFConnector, ExternalDataManager
import json

print("\n" + "="*60)
print("EXTERNAL DATA SOURCES QUICK DEMO")
print("="*60)

# Demo 1: FATF High-Risk Countries
print("\n📍 FATF High-Risk Jurisdictions (Call for Action):")
print("-" * 60)

fatf = FATFConnector()
high_risk = fatf.fetch_high_risk_jurisdictions()

print(f"Source: {high_risk['source']}")
print(f"Last Updated: {high_risk['last_manual_update']}")
print(f"Total: {high_risk['count']} countries\n")

for country in high_risk['data']:
    print(f"  🚩 {country['country']}")
    print(f"     Status: {country['status']}")
    print(f"     Risk: {country['risk_level']}\n")

# Demo 2: FATF Monitored Countries
print("\n📊 FATF Jurisdictions Under Increased Monitoring:")
print("-" * 60)

monitored = fatf.fetch_monitored_jurisdictions()
print(f"Total: {monitored['count']} countries\n")

for country in monitored['data'][:10]:  # Show first 10
    print(f"  ⚠️  {country['country']} ({country['risk_level']})")

print(f"\n  ... and {monitored['count'] - 10} more countries")

# Demo 3: Convert to Policy Format
print("\n\n📄 Converting to Policy Document Format:")
print("-" * 60)

manager = ExternalDataManager()
policy_text = manager._convert_fatf_to_policy(high_risk, monitored)

print(f"Generated policy document: {len(policy_text)} characters")
print("\nPolicy Preview (first 500 chars):")
print("-" * 60)
print(policy_text[:500] + "...")

# Demo 4: Example Usage in Transaction Evaluation
print("\n\n💳 Example: Transaction Evaluation Integration:")
print("-" * 60)

test_transactions = [
    {"country": "Iran", "expected": "HIGH RISK - Call for Action"},
    {"country": "Nigeria", "expected": "MEDIUM RISK - Increased Monitoring"},
    {"country": "United States", "expected": "LOW RISK - No issues"},
]

high_risk_countries = [c['country'] for c in high_risk['data']]
monitored_countries = [c['country'] for c in monitored['data']]

print("\nTransaction Risk Assessment:")
for txn in test_transactions:
    country = txn['country']
    
    if country in high_risk_countries or any(country in hr for hr in high_risk_countries):
        risk = "🚨 HIGH RISK"
        action = "BLOCK - Call for Action"
    elif country in monitored_countries:
        risk = "⚠️  MEDIUM RISK"
        action = "ENHANCED DUE DILIGENCE"
    else:
        risk = "✅ LOW RISK"
        action = "PROCEED"
    
    print(f"\n  Country: {country}")
    print(f"  Risk Level: {risk}")
    print(f"  Action: {action}")

print("\n" + "="*60)
print("✅ External Data Integration Working!")
print("="*60)
print("\nNext Steps:")
print("1. Start backend: python -m uvicorn main:app --reload")
print("2. Scheduler will auto-fetch data daily/weekly")
print("3. Use API: POST /api/external-data/fetch?source=FATF")
print("4. Check status: GET /api/external-data/scheduler/status")
print("\n")
