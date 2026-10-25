#!/bin/bash
# Docker Test Runner - Starts all test databases and runs full test suite

set -e  # Exit on error

echo "========================================="
echo "IA Modules - Full Database Test Suite"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose not found${NC}"
    echo "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Get script directory (tests/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${YELLOW}Step 1: Starting test databases...${NC}"
docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d

echo ""
echo -e "${YELLOW}Step 2: Waiting for databases to be healthy...${NC}"

# Wait for PostgreSQL
echo -n "Waiting for PostgreSQL..."
timeout 60 bash -c 'until docker exec ia_modules_test_postgres pg_isready -U testuser > /dev/null 2>&1; do sleep 1; echo -n "."; done' || {
    echo -e "${RED}PostgreSQL failed to start${NC}"
    docker-compose -f docker-compose.test.yml logs postgres
    exit 1
}
echo -e " ${GREEN}✓${NC}"

# Wait for MySQL
echo -n "Waiting for MySQL..."
timeout 60 bash -c 'until docker exec ia_modules_test_mysql mysqladmin ping -h localhost -u testuser -ptestpass --silent > /dev/null 2>&1; do sleep 1; echo -n "."; done' || {
    echo -e "${RED}MySQL failed to start${NC}"
    docker-compose -f docker-compose.test.yml logs mysql
    exit 1
}
echo -e " ${GREEN}✓${NC}"

# Wait for MSSQL
echo -n "Waiting for MSSQL..."
timeout 90 bash -c 'until docker exec ia_modules_test_mssql /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P TestPass123! -Q "SELECT 1" > /dev/null 2>&1; do sleep 2; echo -n "."; done' || {
    echo -e "${RED}MSSQL failed to start${NC}"
    docker-compose -f docker-compose.test.yml logs mssql
    exit 1
}
echo -e " ${GREEN}✓${NC}"

# Wait for Redis
echo -n "Waiting for Redis..."
timeout 30 bash -c 'until docker exec ia_modules_test_redis redis-cli ping > /dev/null 2>&1; do sleep 1; echo -n "."; done' || {
    echo -e "${RED}Redis failed to start${NC}"
    docker-compose -f docker-compose.test.yml logs redis
    exit 1
}
echo -e " ${GREEN}✓${NC}"

echo ""
echo -e "${GREEN}All databases are ready!${NC}"
echo ""

# Set environment variables for tests
export TEST_POSTGRESQL_URL="postgresql://testuser:testpass@localhost:5434/ia_modules_test"
export TEST_MYSQL_URL="mysql://testuser:testpass@localhost:3306/ia_modules_test"
export TEST_MSSQL_URL="mssql://testuser:TestPass123!@localhost:1433/ia_modules_test"
export TEST_REDIS_URL="redis://localhost:6379/0"

echo -e "${YELLOW}Step 3: Running test suite...${NC}"
echo ""
echo "Environment:"
echo "  PostgreSQL: $TEST_POSTGRESQL_URL"
echo "  MySQL: $TEST_MYSQL_URL"
echo "  MSSQL: $TEST_MSSQL_URL"
echo "  Redis: $TEST_REDIS_URL"
echo ""

# Navigate to project root for pytest
cd "$SCRIPT_DIR/.."

# Run tests
if pytest tests/ -v --tb=short "$@"; then
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}All tests passed!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    TEST_EXIT_CODE=0
else
    echo ""
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}Some tests failed${NC}"
    echo -e "${RED}=========================================${NC}"
    TEST_EXIT_CODE=1
fi

echo ""
echo -e "${YELLOW}Cleanup Options:${NC}"
echo "  Keep databases running: docker-compose -f $SCRIPT_DIR/docker-compose.test.yml ps"
echo "  Stop databases: docker-compose -f $SCRIPT_DIR/docker-compose.test.yml stop"
echo "  Remove databases: docker-compose -f $SCRIPT_DIR/docker-compose.test.yml down -v"
echo ""

read -p "Stop and remove test databases? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Stopping and removing databases...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v
    echo -e "${GREEN}Cleanup complete${NC}"
else
    echo -e "${YELLOW}Databases left running for further testing${NC}"
fi

exit $TEST_EXIT_CODE
