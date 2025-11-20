# DevSyncSalesAI Run Script for Windows
Write-Host "=================================="
Write-Host "DevSyncSalesAI Startup"
Write-Host "=================================="
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
    Write-Host "✅ Virtual environment created"
}

# Activate virtual environment
Write-Host "Activating virtual environment..."
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..."
pip install -q -r requirements.txt

# Set Python path
$env:PYTHONPATH = "$PWD;$PWD\backend"

# Initialize database (SQLite for local testing)
Write-Host ""
Write-Host "Initializing database..."
$env:DATABASE_URL = "sqlite:///./devsync_sales.db"

# Start the FastAPI server
Write-Host ""
Write-Host "=================================="
Write-Host "Starting DevSyncSalesAI API Server"
Write-Host "=================================="
Write-Host ""
Write-Host "API will be available at: http://localhost:8000"
Write-Host "API Documentation: http://localhost:8000/docs"
Write-Host "Health Check: http://localhost:8000/health"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server"
Write-Host ""

# Run uvicorn
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
