#!/bin/bash
# Pre-commit hook: validates gallery data files against artwork collection
# This script is version-controlled in _scripts/ and symlinked to .git/hooks/pre-commit

set -e

echo "Validating gallery data..."
python3 _scripts/validate_galleries.py

echo "Gallery validation passed."
