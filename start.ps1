# PolicyLens Quick Start Script
Write-Host "================================" -ForegroundColor Cyan
Write-Host "PolicyLens MVP Quick Start" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env exists
Write-Host ""
Write-Host "Checking configuration..." -ForegroundColor Yellow
if (!(Test-Path "backend\.env")) {
    Write-Host "Creating backend/.env from template..." -ForegroundColor Yellow
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "✓ Configuration file created" -ForegroundColor Green
    Write-Host "⚠ IMPORTANT: Edit backend/.env to add your OpenAI API key for full functionality" -ForegroundColor Yellow
    Write-Host "  (System will work in demo mode without API key)" -ForegroundColor Gray
} else {
    Write-Host "✓ Configuration file exists" -ForegroundColor Green
}

# Ask user what they want to do
Write-Host ""
Write-Host "What would you like to do?" -ForegroundColor Cyan
Write-Host "1. Quick Start (Docker + Auto-open browser)" -ForegroundColor Green
Write-Host "2. Start all services (Docker only)" -ForegroundColor White
Write-Host "3. Start backend only (Local development)" -ForegroundColor White
Write-Host "4. Start frontend only (Local development)" -ForegroundColor White
Write-Host "5. Stop all services" -ForegroundColor White
Write-Host "6. View logs" -ForegroundColor White
Write-Host "7. Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter your choice (1-7)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "🚀 Quick Start - Starting PolicyLens..." -ForegroundColor Green
        Write-Host ""
        
        # Stop any existing containers
        Write-Host "[1/4] Cleaning up existing services..." -ForegroundColor Yellow
        docker-compose down 2>$null
        
        # Start all services
        Write-Host "[2/4] Starting Docker containers..." -ForegroundColor Yellow
        docker-compose up -d
        
        # Wait for services to be ready
        Write-Host "[3/4] Waiting for services to initialize (30 seconds)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
        
        # Health check
        Write-Host "[4/4] Verifying services..." -ForegroundColor Yellow
        try {
            $health = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 5 | ConvertFrom-Json
            Write-Host "  ✓ Backend: Online" -ForegroundColor Green
            if ($health.milvus_connected) {
                Write-Host "  ✓ Milvus Vector DB: Connected" -ForegroundColor Green
            } else {
                Write-Host "  ⚠ Milvus Vector DB: Not connected (demo mode)" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "  ⚠ Backend: Still initializing..." -ForegroundColor Yellow
        }
        
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  ✓ PolicyLens is running!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Cyan
        Write-Host "  Backend:   http://localhost:8000" -ForegroundColor Cyan
        Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Opening browser..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
        Start-Process "http://localhost:3000"
        Write-Host ""
        Write-Host "Useful commands:" -ForegroundColor Gray
        Write-Host "  View logs:  docker-compose logs -f" -ForegroundColor Gray
        Write-Host "  Stop all:   docker-compose down" -ForegroundColor Gray
        Write-Host ""
    }
    
    "2" {
        Write-Host ""
        Write-Host "Starting all services with Docker Compose..." -ForegroundColor Yellow
        docker-compose up -d
        
        Write-Host ""
        Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
        
        Write-Host ""
        Write-Host "================================" -ForegroundColor Green
        Write-Host "✓ PolicyLens is running!" -ForegroundColor Green
        Write-Host "================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Access the application:" -ForegroundColor Cyan
        Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
        Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
        Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
        Write-Host ""
        Write-Host "To view logs: docker-compose logs -f" -ForegroundColor Gray
        Write-Host "To stop:      docker-compose down" -ForegroundColor Gray
        Write-Host ""
    }
    
    "3" {
        Write-Host ""
        Write-Host "⚠ Note: This requires Milvus to be running (Option 2 first)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Starting backend locally..." -ForegroundColor Yellow
        Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
        
        Set-Location backend
        
        if (!(Test-Path "venv")) {
            python -m venv venv
        }
        
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        .\venv\Scripts\Activate.ps1
        
        Write-Host "Installing dependencies..." -ForegroundColor Yellow
        pip install -r requirements.txt -q
        
        Write-Host ""
        Write-Host "✓ Backend starting on http://localhost:8000" -ForegroundColor Green
        python -m uvicorn main:app --reload --port 8000
    }
    
    "4" {
        Write-Host ""
        Write-Host "Starting frontend locally..." -ForegroundColor Yellow
        
        Set-Location frontend
        
        if (!(Test-Path "node_modules")) {
            Write-Host "Installing dependencies..." -ForegroundColor Yellow
            npm install
        }
        
        Write-Host ""
        Write-Host "✓ Frontend starting on http://localhost:3000" -ForegroundColor Green
        npm run dev
    }
    
    "5" {
        Write-Host ""
        Write-Host "Stopping all services..." -ForegroundColor Yellow
        docker-compose down
        Get-Process python,node -ErrorAction SilentlyContinue | Stop-Process -Force
        Write-Host "✓ All services stopped" -ForegroundColor Green
    }
    
    "6" {
        Write-Host ""
        Write-Host "Showing logs (Ctrl+C to exit)..." -ForegroundColor Yellow
        docker-compose logs -f
    }
    
    "7" {
        Write-Host ""
        Write-Host "Goodbye!" -ForegroundColor Cyan
        exit 0
    }
    
    default {
        Write-Host ""
        Write-Host "Invalid choice. Please run the script again." -ForegroundColor Red
        exit 1
    }
}
