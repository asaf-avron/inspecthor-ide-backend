#!/bin/bash
# Development script to run the Guardian Gateway backend API

echo "Starting Guardian Gateway API on port 8000..."
cd "$(dirname "$0")"

echo ""
echo "Guardian Gateway API is running:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the service"

# Start backend
python -m api.main

