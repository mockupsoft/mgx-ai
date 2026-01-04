#!/bin/bash
#
# MGX-AI Load Test Runner
# 
# This script runs k6 load tests against the MGX-AI platform.
# Usage: ./run-load-tests.sh [scenario] [environment]
#
# Scenarios: ramp-up, sustained, spike, endurance, all
# Environments: local, staging, production
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SCENARIO="${1:-ramp-up}"
ENVIRONMENT="${2:-staging}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_DIR="${PROJECT_ROOT}/tests/load"
RESULTS_DIR="${PROJECT_ROOT}/load_test_results"
CONFIG_FILE="${TEST_DIR}/test-config.yaml"

# Ensure results directory exists
mkdir -p "${RESULTS_DIR}"

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v k6 &> /dev/null; then
        log_error "k6 is not installed. Please install from: https://k6.io/docs/getting-started/installation/"
        exit 1
    fi
    
    log_success "All dependencies installed"
}

# Load environment configuration
load_environment() {
    local env=$1
    log_info "Loading environment: ${env}"
    
    case $env in
        local)
            export BASE_URL="http://localhost:8000"
            export API_KEY="test-api-key-local"
            export WORKSPACE_ID="test-workspace-local"
            ;;
        staging)
            if [ -z "$STAGING_API_KEY" ]; then
                log_error "STAGING_API_KEY environment variable not set"
                exit 1
            fi
            export BASE_URL="https://staging.mgx-ai.example.com"
            export API_KEY="$STAGING_API_KEY"
            export WORKSPACE_ID="load-test-workspace"
            ;;
        production)
            log_warning "Running load tests against PRODUCTION!"
            read -p "Are you sure? (type 'yes' to continue): " confirm
            if [ "$confirm" != "yes" ]; then
                log_info "Aborted by user"
                exit 0
            fi
            
            if [ -z "$PROD_API_KEY" ]; then
                log_error "PROD_API_KEY environment variable not set"
                exit 1
            fi
            export BASE_URL="https://api.mgx-ai.example.com"
            export API_KEY="$PROD_API_KEY"
            export WORKSPACE_ID="prod-load-test-workspace"
            ;;
        *)
            log_error "Unknown environment: ${env}"
            log_info "Valid environments: local, staging, production"
            exit 1
            ;;
    esac
    
    log_success "Environment loaded: ${BASE_URL}"
}

# Pre-test validation
pre_test_validation() {
    log_info "Running pre-test validation..."
    
    # Health check
    log_info "Checking /health/ready endpoint..."
    if ! curl -s -f "${BASE_URL}/health/ready" > /dev/null; then
        log_error "API health check failed. Is the server running?"
        exit 1
    fi
    log_success "API is healthy"
    
    # Status check
    log_info "Checking /health/status endpoint..."
    local status=$(curl -s "${BASE_URL}/health/status")
    echo "$status" | jq '.' || echo "$status"
    
    log_success "Pre-test validation complete"
}

# Run a single test scenario
run_scenario() {
    local scenario=$1
    local script_file="${TEST_DIR}/${scenario}.js"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local results_file="${RESULTS_DIR}/${scenario}_${ENVIRONMENT}_${timestamp}"
    
    if [ ! -f "$script_file" ]; then
        log_error "Test script not found: ${script_file}"
        return 1
    fi
    
    log_info "Running scenario: ${scenario}"
    log_info "Script: ${script_file}"
    log_info "Environment: ${ENVIRONMENT}"
    log_info "Results: ${results_file}"
    log_info "---"
    
    # Run k6 with various output formats
    k6 run \
        --out json="${results_file}.json" \
        --out csv="${results_file}.csv" \
        --summary-export="${results_file}_summary.json" \
        "$script_file"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        log_success "Scenario completed: ${scenario}"
        
        # Generate HTML report if possible
        if command -v k6-to-html &> /dev/null; then
            log_info "Generating HTML report..."
            k6-to-html "${results_file}.json" --output "${results_file}.html"
            log_success "HTML report: ${results_file}.html"
        fi
    else
        log_error "Scenario failed: ${scenario} (exit code: ${exit_code})"
        return $exit_code
    fi
    
    log_info "---"
    return 0
}

# Post-test analysis
post_test_analysis() {
    log_info "Running post-test analysis..."
    
    # Wait for system to stabilize
    log_info "Waiting 30 seconds for system to stabilize..."
    sleep 30
    
    # Final health check
    log_info "Final health check..."
    local status=$(curl -s "${BASE_URL}/health/status")
    echo "$status" | jq '.' || echo "$status"
    
    # Check queue depth if available
    local queue_status=$(curl -s "${BASE_URL}/api/v1/metrics/queue" 2>/dev/null || echo "{}")
    if [ "$queue_status" != "{}" ]; then
        log_info "Queue status:"
        echo "$queue_status" | jq '.' || echo "$queue_status"
    fi
    
    log_success "Post-test analysis complete"
}

# Display help
show_help() {
    cat << EOF
MGX-AI Load Test Runner

Usage: $0 [scenario] [environment]

Scenarios:
  ramp-up     - Gradual load increase (0 → 1000 users, 10 min)
  sustained   - Sustained load (1000 users, 60 min)
  spike       - Spike testing (500 → 2000 → 500, 3 cycles)
  endurance   - Long-running test (500 users, 8 hours)
  all         - Run all scenarios sequentially

Environments:
  local       - Local development (http://localhost:8000)
  staging     - Staging environment
  production  - Production environment (use with caution!)

Environment Variables:
  STAGING_API_KEY   - API key for staging environment
  PROD_API_KEY      - API key for production environment

Examples:
  $0 ramp-up staging
  $0 sustained local
  $0 all staging
  
  STAGING_API_KEY=xxx $0 sustained staging

Results:
  Results are saved to: ${RESULTS_DIR}/
  
For more information, see: docs/load-testing/test-scenarios.md
EOF
}

# Main execution
main() {
    echo ""
    log_info "=== MGX-AI Load Test Runner ==="
    echo ""
    
    # Handle help
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_help
        exit 0
    fi
    
    # Check dependencies
    check_dependencies
    
    # Load environment
    load_environment "$ENVIRONMENT"
    
    # Pre-test validation
    pre_test_validation
    
    # Run scenarios
    if [ "$SCENARIO" = "all" ]; then
        log_info "Running all test scenarios..."
        log_warning "This will take approximately 10+ hours!"
        read -p "Continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log_info "Aborted by user"
            exit 0
        fi
        
        run_scenario "ramp-up" || log_warning "ramp-up scenario failed"
        sleep 60  # Wait between tests
        
        run_scenario "sustained" || log_warning "sustained scenario failed"
        sleep 60
        
        run_scenario "spike" || log_warning "spike scenario failed"
        sleep 60
        
        run_scenario "endurance" || log_warning "endurance scenario failed"
    else
        run_scenario "$SCENARIO"
    fi
    
    # Post-test analysis
    post_test_analysis
    
    log_success "Load test complete!"
    log_info "Results directory: ${RESULTS_DIR}"
    
    echo ""
    log_info "Next steps:"
    log_info "1. Review test results in ${RESULTS_DIR}"
    log_info "2. Analyze bottlenecks using docs/load-testing/bottleneck-analysis.md"
    log_info "3. Generate report using docs/load-testing/load-test-report.md"
    echo ""
}

# Run main function
main "$@"
