# Docker Test Runner (PowerShell) - Starts all test databases and runs full test suite

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "IA Modules - Full Database Test Suite" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if docker-compose is available
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "Error: docker-compose not found" -ForegroundColor Red
    Write-Host "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
}

# Navigate to tests directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "Step 1: Starting test databases..." -ForegroundColor Yellow
docker-compose -f docker-compose.test.yml up -d

Write-Host ""
Write-Host "Step 2: Waiting for databases to be healthy..." -ForegroundColor Yellow

# Function to wait for container health
function Wait-ForContainer {
    param(
        [string]$ContainerName,
        [string]$DisplayName,
        [scriptblock]$HealthCheck,
        [int]$TimeoutSeconds = 60
    )

    Write-Host "Waiting for $DisplayName..." -NoNewline
    $elapsed = 0
    $interval = 2

    while ($elapsed -lt $TimeoutSeconds) {
        try {
            if (& $HealthCheck) {
                Write-Host " OK" -ForegroundColor Green
                return $true
            }
        } catch {
            # Ignore errors during health check
        }

        Write-Host "." -NoNewline
        Start-Sleep -Seconds $interval
        $elapsed += $interval
    }

    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "$DisplayName failed to start" -ForegroundColor Red
    docker-compose -f docker-compose.test.yml logs $ContainerName
    return $false
}

# Wait for PostgreSQL
$pgReady = Wait-ForContainer -ContainerName "postgres" -DisplayName "PostgreSQL" -HealthCheck {
    $result = docker exec ia_modules_test_postgres pg_isready -U testuser 2>$null
    return $LASTEXITCODE -eq 0
}

# Wait for MySQL
$mysqlReady = Wait-ForContainer -ContainerName "mysql" -DisplayName "MySQL" -HealthCheck {
    $result = docker exec ia_modules_test_mysql mysqladmin ping -h localhost -u testuser -ptestpass --silent 2>$null
    return $LASTEXITCODE -eq 0
}

# Wait for MSSQL
$mssqlReady = Wait-ForContainer -ContainerName "mssql" -DisplayName "MSSQL" -TimeoutSeconds 90 -HealthCheck {
    $result = docker exec ia_modules_test_mssql /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P "TestPass123!" -Q "SELECT 1" 2>$null
    return $LASTEXITCODE -eq 0
}

# Wait for Redis
$redisReady = Wait-ForContainer -ContainerName "redis" -DisplayName "Redis" -TimeoutSeconds 30 -HealthCheck {
    $result = docker exec ia_modules_test_redis redis-cli ping 2>$null
    return $LASTEXITCODE -eq 0
}

if (-not ($pgReady -and $mysqlReady -and $mssqlReady -and $redisReady)) {
    Write-Host "Some databases failed to start. Exiting." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All databases are ready!" -ForegroundColor Green
Write-Host ""

# Set environment variables for tests
$env:TEST_POSTGRESQL_URL = "postgresql://testuser:testpass@localhost:5434/ia_modules_test"
$env:TEST_MYSQL_URL = "mysql://testuser:testpass@localhost:3306/ia_modules_test"
$env:TEST_MSSQL_URL = "mssql://testuser:TestPass123!@localhost:1433/ia_modules_test"
$env:TEST_REDIS_URL = "redis://localhost:6379/0"

Write-Host "Step 3: Running test suite..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Environment:"
Write-Host "  PostgreSQL: $env:TEST_POSTGRESQL_URL"
Write-Host "  MySQL: $env:TEST_MYSQL_URL"
Write-Host "  MSSQL: $env:TEST_MSSQL_URL"
Write-Host "  Redis: $env:TEST_REDIS_URL"
Write-Host ""

# Run tests from project root
Set-Location (Join-Path $scriptPath "..")
$testArgs = @("tests/", "-v", "--tb=short") + $args
if (pytest @testArgs) {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "All tests passed!" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Green
    $testExitCode = 0
} else {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host "Some tests failed" -ForegroundColor Red
    Write-Host "=========================================" -ForegroundColor Red
    $testExitCode = 1
}

Write-Host ""
Write-Host "Cleanup Options:" -ForegroundColor Yellow
Write-Host "  Keep databases running: docker-compose -f tests/docker-compose.test.yml ps"
Write-Host "  Stop databases: docker-compose -f tests/docker-compose.test.yml stop"
Write-Host "  Remove databases: docker-compose -f tests/docker-compose.test.yml down -v"
Write-Host ""

$cleanup = Read-Host "Stop and remove test databases? [y/N]"
if ($cleanup -eq "y" -or $cleanup -eq "Y") {
    Write-Host "Stopping and removing databases..." -ForegroundColor Yellow
    Set-Location $scriptPath
    docker-compose -f docker-compose.test.yml down -v
    Write-Host "Cleanup complete" -ForegroundColor Green
} else {
    Write-Host "Databases left running for further testing" -ForegroundColor Yellow
}

exit $testExitCode
