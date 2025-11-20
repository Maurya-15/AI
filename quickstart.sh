#!/bin/bash

# DevSyncSalesAI Quick Start Script
# This script helps you get started quickly

echo "=================================="
echo "DevSyncSalesAI Quick Start"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys before proceeding!"
    echo ""
    read -p "Press Enter when you've configured .env file..."
fi

# Initialize database
echo ""
echo "Initializing database..."
python -c "from app.db import init_db; init_db()"
echo "✅ Database initialized"

# Seed test data
echo ""
read -p "Do you want to seed test data? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python backend/scripts/seed_leads.py
    echo "✅ Test data seeded"
fi

# Run tests
echo ""
read -p "Do you want to run tests? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pytest -v
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Start API: uvicorn app.main:app --reload"
echo "2. View docs: http://localhost:8000/docs"
echo "3. Test campaign: python backend/scripts/run_once.py"
echo "4. Or use Docker: docker-compose up -d"
echo ""
echo "📖 Read OPERATOR_GUIDE.md for detailed instructions"
echo ""
