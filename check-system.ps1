# PolicyLens System Check
Write-Host "================================" -ForegroundColor Cyan
Write-Host "PolicyLens System Requirements Check" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.(\d+)") {
        $minorVersion = [int]$matches[1]
        if ($minorVersion -ge 11) {
            Write-Host "✓ Python $pythonVersion" -ForegroundColor Green
        } else {
            Write-Host "✗ Python version too old. Need Python 3.11+" -ForegroundColor Red
            $allGood = $false
        }
    }
} catch {
    Write-Host "✗ Python not found" -ForegroundColor Red
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    $allGood = $false
}

# Check Node.js
Write-Host ""
Write-Host "Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    if ($nodeVersion -match "v(\d+)\.") {
        $majorVersion = [int]$matches[1]
        if ($majorVersion -ge 18) {
            Write-Host "✓ Node.js $nodeVersion" -ForegroundColor Green
        } else {
            Write-Host "✗ Node.js version too old. Need Node.js 18+" -ForegroundColor Red
            $allGood = $false
        }
    }
} catch {
    Write-Host "✗ Node.js not found" -ForegroundColor Red
    Write-Host "  Download from: https://nodejs.org/" -ForegroundColor Yellow
    $allGood = $false
}

# Check Docker
Write-Host ""
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker info 2>&1 | Out-Null
    $dockerVersion = docker --version
    Write-Host "✓ $dockerVersion" -ForegroundColor Green
    
    # Check if Docker is running
    try {
        docker ps | Out-Null
        Write-Host "✓ Docker is running" -ForegroundColor Green
    } catch {
        Write-Host "⚠ Docker is installed but not running" -ForegroundColor Yellow
        Write-Host "  Please start Docker Desktop" -ForegroundColor Yellow
    }
} catch {
    Write-Host "✗ Docker not found" -ForegroundColor Red
    Write-Host "  Download from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    $allGood = $false
}

# Check Docker Compose
Write-Host ""
Write-Host "Checking Docker Compose..." -ForegroundColor Yellow
try {
    $composeVersion = docker-compose --version 2>&1
    Write-Host "✓ $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠ Docker Compose not found (usually included with Docker Desktop)" -ForegroundColor Yellow
}

# Check if ports are available
Write-Host ""
Write-Host "Checking port availability..." -ForegroundColor Yellow

$ports = @{
    "3000" = "Frontend"
    "8000" = "Backend API"
    "19530" = "Milvus"
}

foreach ($port in $ports.Keys) {
    $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Host "⚠ Port $port ($($ports[$port])) is already in use" -ForegroundColor Yellow
    } else {
        Write-Host "✓ Port $port ($($ports[$port])) is available" -ForegroundColor Green
    }
}

# Check directory structure
Write-Host ""
Write-Host "Checking project structure..." -ForegroundColor Yellow

$requiredFiles = @(
    "backend\main.py",
    "backend\requirements.txt",
    "frontend\package.json",
    "frontend\src\App.jsx",
    "docker-compose.yml"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✓ $file" -ForegroundColor Green
    } else {
        Write-Host "✗ $file missing" -ForegroundColor Red
        $allGood = $false
    }
}

# Check if .env exists
Write-Host ""
Write-Host "Checking configuration..." -ForegroundColor Yellow
if (Test-Path "backend\.env") {
    Write-Host "✓ backend/.env exists" -ForegroundColor Green
    
    # Check if OpenAI key is set
    $envContent = Get-Content "backend\.env" -Raw
    if ($envContent -match "OPENAI_API_KEY=sk-") {
        Write-Host "✓ OpenAI API key is configured" -ForegroundColor Green
    } else {
        Write-Host "⚠ OpenAI API key not set (system will run in demo mode)" -ForegroundColor Yellow
        Write-Host "  Add your key to backend/.env for full functionality" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠ backend/.env not found" -ForegroundColor Yellow
    Write-Host "  Run: Copy-Item backend\.env.example backend\.env" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✓ All requirements satisfied!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You're ready to run PolicyLens!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Run: .\start.ps1" -ForegroundColor White
    Write-Host "2. Choose option 1 (Start all services)" -ForegroundColor White
    Write-Host "3. Open: http://localhost:3000" -ForegroundColor White
} else {
    Write-Host "✗ Some requirements are missing" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install the missing components above" -ForegroundColor Yellow
}
Write-Host "================================" -ForegroundColor Cyan
