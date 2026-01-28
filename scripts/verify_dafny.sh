#!/bin/bash
# Verify Dafny files using Docker container
# Usage: ./scripts/verify_dafny.sh api/verification/models.dfy

set -e

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Check if files are provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <dafny_file1> [dafny_file2] ..."
    echo "Example: $0 api/verification/models.dfy api/verification/project_migration.dfy"
    exit 1
fi

# Run Dafny verification inside Docker container
echo "Verifying Dafny files via Docker container..."
docker-compose exec -T api dafny verify "$@"

echo "Verification complete."
