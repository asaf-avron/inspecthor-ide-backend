#!/bin/bash
# Inspecthor - Docker Development Script
# Starts all services (database, backend, frontend) with Docker Compose

echo "🚀 Starting Inspecthor with Docker..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your configuration."
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "📦 Building and starting services..."
echo "   - PostgreSQL database (port 5432)"
echo "   - Backend API (port 8000)"
echo "   - Frontend IDE (port 3000)"
echo ""

# Build and start all services
docker-compose up --build

# Note: Use Ctrl+C to stop all services
