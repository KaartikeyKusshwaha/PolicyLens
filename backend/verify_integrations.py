"""
PolicyLens — Integration Verification Script
Tests:
  1. Config loading (.env -> settings)
  2. Groq API key validity (live chat completion call)
  3. World Bank Governance API (free, no key)
  4. FATF connector enrichment (FATF lists + WB scores)
  5. OFAC SDN list fetch (treasury.gov)

Run from the backend/ directory:
    python verify_integrations.py
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "OK"
FAIL = "FAIL"
WARN = "WARN"

results = []

def section(title: str):
    print(f"\n{'-'*60}")
    print(f"  {title}")
    print(f"{'-'*60}")

def ok(msg: str):
    print(f"  [OK]   {msg}")
    results.append(("PASS", msg))

def fail(msg: str):
    print(f"  [FAIL] {msg}")
    results.append(("FAIL", msg))

def warn(msg: str):
    print(f"  [WARN] {msg}")
    results.append(("WARN", msg))


# ──────────────────────────────────────────────────────────────
# 1. Config / .env
# ──────────────────────────────────────────────────────────────
section("1. Config & .env")
try:
    from config import settings
    ok(f"Settings loaded — model: {settings.llm_model}")
    ok(f"API base URL : {settings.api_base_url}")

    key = settings.openai_api_key or ""
    has_real_key = bool(key) and "placeholder" not in key.lower() and not key.startswith("sk-your")
    if has_real_key:
        ok(f"OPENAI_API_KEY is set (starts with: {key[:8]}...)")
    else:
        fail("OPENAI_API_KEY is empty or placeholder — add your Groq key to .env")
except Exception as exc:
    fail(f"Could not load config: {exc}")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────
# 2. Groq API — live chat completion
# ──────────────────────────────────────────────────────────────
section("2. Groq API (live LLM call)")
try:
    from openai import OpenAI
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.api_base_url,
    )
    t0 = time.time()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "You are a compliance assistant. Respond in JSON."},
            {"role": "user",   "content": 'Reply with {"status": "ok", "message": "Groq is working"}'}
        ],
        max_tokens=64,
        temperature=0,
    )
    elapsed = round(time.time() - t0, 2)
    content = resp.choices[0].message.content.strip()
    ok(f"Response received in {elapsed}s")
    ok(f"Model used    : {resp.model}")
    try:
        parsed = json.loads(content)
        ok(f"JSON response : {parsed}")
    except Exception:
        ok(f"Raw response  : {content}")
except Exception as exc:
    fail(f"Groq API call failed: {type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────────────────────
# 3. World Bank Governance API
# ──────────────────────────────────────────────────────────────
section("3. World Bank Governance API (free, no key)")
try:
    import requests
    WB_URL = (
        "https://api.worldbank.org/v2/country/all/indicator/"
        "GOV_WGI_RL.EST?format=json&per_page=50&mrv=1"
    )
    t0 = time.time()
    r = requests.get(WB_URL, timeout=20, headers={"User-Agent": "PolicyLens/1.0"})
    r.raise_for_status()
    elapsed = round(time.time() - t0, 2)
    payload = r.json()
    if isinstance(payload, list) and len(payload) == 2:
        entries = [e for e in (payload[1] or []) if e.get("value") is not None]
        ok(f"World Bank responded in {elapsed}s")
        ok(f"Countries with Rule of Law scores: {len(entries)}")
        for e in entries[:3]:
            ok(f"  {e['country']['value']:30s}  RL={round(e['value'], 3)}")
    else:
        warn(f"Unexpected World Bank response shape: {str(payload)[:200]}")
except Exception as exc:
    fail(f"World Bank API failed: {type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────────────────────
# 4. FATFConnector — enriched lists
# ──────────────────────────────────────────────────────────────
section("4. FATFConnector (FATF lists + World Bank enrichment)")
try:
    from services.external_data_sources import FATFConnector
    fatf = FATFConnector()

    high = fatf.fetch_high_risk_jurisdictions()
    ok(f"High-risk (Call for Action) count : {high['count']}")
    for entry in high["data"]:
        wb = f"  WB RL={entry['world_bank_rule_of_law']}" if "world_bank_rule_of_law" in entry else "  (no WB score)"
        ok(f"  {entry['country']}{wb}")

    monitored = fatf.fetch_monitored_jurisdictions()
    ok(f"Grey list (Increased Monitoring) count: {monitored['count']}")

    enrichment = fatf.fetch_world_bank_risk_enrichment()
    ok(f"Additional WB-flagged countries (not on FATF): {enrichment['additional_risk_countries']}")
    if enrichment["data"]:
        for e in enrichment["data"][:3]:
            ok(f"  ISO3={e['iso3']}  RL={e['rule_of_law_score']}  ({e['risk_level']})")
except Exception as exc:
    fail(f"FATFConnector failed: {type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────────────────────
# 5. OFAC SDN list
# ──────────────────────────────────────────────────────────────
section("5. OFAC SDN List (treasury.gov / SLS)")
try:
    from services.external_data_sources import OFACConnector
    ofac = OFACConnector()
    t0 = time.time()
    sdn = ofac.fetch_sdn_list(format="csv")
    elapsed = round(time.time() - t0, 2)
    if sdn.get("status") == "unavailable":
        warn(f"OFAC SDN blocked (403) in {elapsed}s — OFAC now requires browser access")
        warn(f"  Reason: {sdn.get('reason', '')[:120]}")
    else:
        ok(f"OFAC SDN fetched in {elapsed}s")
        ok(f"Entries returned : {sdn['count']} (of ~{sdn.get('total_available', '?')} scanned)")
        if sdn["data"]:
            sample = sdn["data"][0]
            ok(f"Sample entry     : {sample['name']} | Program: {sample['program']}")
except Exception as exc:
    fail(f"OFAC fetch raised exception: {type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  SUMMARY")
print(f"{'='*60}")
passed = sum(1 for s, _ in results if s == "PASS")
failed = sum(1 for s, _ in results if s == "FAIL")
warned = sum(1 for s, _ in results if s == "WARN")
print(f"  Passed  : {passed}")
if warned:
    print(f"  Warnings: {warned}")
if failed:
    print(f"  Failed  : {failed}")
    for s, m in results:
        if s == "FAIL":
            print(f"    -> {m}")
print("=" * 60)
print()
sys.exit(0 if failed == 0 else 1)
