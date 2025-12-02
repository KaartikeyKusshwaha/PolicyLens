# PolicyLens API Testing Examples

# Health Check
Invoke-RestMethod -Uri "http://localhost:8000/" -Method Get

# Upload Sample Policy
$policy = @{
    title = "AML Transaction Monitoring Policy"
    content = @"
# Transaction Thresholds
All transactions exceeding USD 10,000 must be reported.
Transactions above USD 50,000 require enhanced due diligence.

# High-Risk Countries
Transactions involving Iran, North Korea, or Syria are prohibited.

# Suspicious Activity Indicators
- Unusual patterns inconsistent with customer profile
- Transactions with no apparent economic purpose
- Frequent just-below-threshold transactions
"@
    source = "internal"
    topic = "aml"
    version = "1.0"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/policies/upload" `
    -Method Post `
    -ContentType "application/json" `
    -Body $policy

# Evaluate High-Risk Transaction
$transaction = @{
    transaction = @{
        transaction_id = "TXN001"
        amount = 75000
        currency = "USD"
        sender = "John Doe"
        receiver = "Shell Company Ltd"
        sender_country = "Iran"
        receiver_country = "USA"
        description = "Business payment"
        timestamp = (Get-Date).ToString("o")
    }
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "http://localhost:8000/api/transactions/evaluate" `
    -Method Post `
    -ContentType "application/json" `
    -Body $transaction

Write-Host "Verdict: $($result.decision.verdict)" -ForegroundColor Cyan
Write-Host "Risk Score: $($result.decision.risk_score)" -ForegroundColor Yellow
Write-Host "Reasoning: $($result.decision.reasoning)" -ForegroundColor White

# Query Assistant
$query = @{
    query = "What are the transaction reporting thresholds?"
    topic = "aml"
} | ConvertTo-Json

$answer = Invoke-RestMethod -Uri "http://localhost:8000/api/query" `
    -Method Post `
    -ContentType "application/json" `
    -Body $query

Write-Host "Answer: $($answer.answer)" -ForegroundColor Green

# Get Policy Stats
Invoke-RestMethod -Uri "http://localhost:8000/api/policies/stats" -Method Get
