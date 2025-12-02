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
Write-Host "1. Start all services (Docker - Recommended)" -ForegroundColor White
Write-Host "2. Start backend only (Local development)" -ForegroundColor White
Write-Host "3. Start frontend only (Local development)" -ForegroundColor White
Write-Host "4. Stop all services" -ForegroundColor White
Write-Host "5. View logs" -ForegroundColor White
Write-Host "6. Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter your choice (1-6)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Starting all services with Docker Compose..." -ForegroundColor Yellow
        docker-compose up -d
        
        Write-Host ""
        Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        
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
    
    "2" {
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
    
    "3" {
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
    
    "4" {
        Write-Host ""
        Write-Host "Stopping all services..." -ForegroundColor Yellow
        docker-compose down
        Write-Host "✓ All services stopped" -ForegroundColor Green
    }
    
    "5" {
        Write-Host ""
        Write-Host "Showing logs (Ctrl+C to exit)..." -ForegroundColor Yellow
        docker-compose logs -f
    }
    
    "6" {
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
