#!/bin/bash
# Script to organize documentation files
# Moves docs from root to docs/ directory

echo "Organizing Guardian Gateway documentation..."

# Create docs directories if they don't exist
mkdir -p docs/api

# Move API implementation plan to docs
if [ -f "api-implementation-plan.md" ]; then
    mv api-implementation-plan.md docs/api/
    echo "✓ Moved api-implementation-plan.md to docs/api/"
fi

# Move dev script to scripts/
if [ -f "dev-backend.sh" ]; then
    cp dev-backend.sh scripts/
    echo "✓ Copied dev-backend.sh to scripts/"
fi

echo "✓ Documentation organized!"
echo ""
echo "Documentation structure:"
echo "  docs/"
echo "    ├── README.md"
echo "    ├── ARCHITECTURE.md"
echo "    ├── SECURITY.md"
echo "    └── api/"
echo "        └── API_IMPLEMENTATION_PLAN.md"
echo ""
echo "  scripts/"
echo "    └── dev-backend.sh"
