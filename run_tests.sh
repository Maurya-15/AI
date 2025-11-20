#!/bin/bash

# DevSyncSalesAI Test Runner
# Comprehensive test execution script

echo "=================================="
echo "DevSyncSalesAI Test Suite"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest not found. Installing...${NC}"
    pip install pytest pytest-asyncio pytest-cov hypothesis
fi

echo -e "${YELLOW}Running all tests...${NC}"
echo ""

# Run all tests with coverage
pytest --cov=app --cov-report=term-missing --cov-report=html -v

TEST_EXIT_CODE=$?

echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
fi

echo ""
echo "Test breakdown:"
echo "- Configuration: 5 tests"
echo "- Database: 9 tests"
echo "- Audit: 11 tests"
echo "- Scrapers: 14 tests"
echo "- Verification: 13 tests"
echo "- Personalization: 8 tests"
echo "- Email: 19 tests"
echo "- Opt-out: 6 tests"
echo ""
echo "Total: 85 tests"
echo ""

# Run property tests separately
echo -e "${YELLOW}Running property-based tests only...${NC}"
pytest -m property -v

echo ""
echo "Coverage report generated in htmlcov/index.html"
echo ""

exit $TEST_EXIT_CODE
