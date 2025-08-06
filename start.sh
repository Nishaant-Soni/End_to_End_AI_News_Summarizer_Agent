#!/bin/bash

# AI News Summarizer Agent - Production Startup Script
set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if a port is available
check_port() {
    local port=$1
    local service=$2
    local max_attempts=30  # Should be quick now with pre-cached model
    local attempt=1
    
    log "Waiting for $service to be ready on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
            success "$service is ready on port $port"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts: $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    error "$service failed to start on port $port after $max_attempts attempts"
    return 1
}

# Function to validate environment
validate_environment() {
    log "Validating environment variables..."
    
    if [ -z "$NEWSAPI_KEY" ]; then
        error "NEWSAPI_KEY environment variable is required"
        exit 1
    fi
    
    if [ -z "$MODEL_NAME" ]; then
        warning "MODEL_NAME not set, using default: facebook/bart-large-cnn"
        export MODEL_NAME="facebook/bart-large-cnn"
    fi
    
    if [ -z "$CACHE_DIR" ]; then
        export CACHE_DIR="./cache"
    fi
    
    if [ -z "$HOST" ]; then
        export HOST="0.0.0.0"
    fi
    
    if [ -z "$PORT" ]; then
        export PORT="8000"
    fi
    
    success "Environment validation passed"
}

# Function to create necessary directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$CACHE_DIR"
    mkdir -p /tmp/streamlit
    
    success "Directories created"
}

# Function to start FastAPI backend
start_backend() {
    log "Starting FastAPI backend..."
    
    # First try to start backend and check for immediate errors
    log "Testing FastAPI backend startup..."
    
    # Test the backend first without backgrounding to catch startup errors
    timeout 10s uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers 1 \
        --log-level info \
        --access-log 2>&1 | head -20 &
    
    TEST_PID=$!
    sleep 5
    
    # Kill the test process
    kill $TEST_PID 2>/dev/null || true
    wait $TEST_PID 2>/dev/null || true
    
    log "Starting FastAPI backend in background..."
    
    # Start backend in background
    uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers 1 \
        --log-level info \
        --access-log \
        > /tmp/backend.log 2>&1 &
    
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/backend.pid
    
    # Give it a moment to start
    sleep 2
    
    # Check if the process is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        error "FastAPI backend process died immediately. Check logs:"
        cat /tmp/backend.log 2>/dev/null || echo "No log file found"
        exit 1
    fi
    
    # Wait for backend to be ready
    if check_port "$PORT" "FastAPI Backend"; then
        success "FastAPI backend started successfully (PID: $BACKEND_PID)"
    else
        error "Failed to start FastAPI backend. Backend logs:"
        cat /tmp/backend.log 2>/dev/null || echo "No log file found"
        exit 1
    fi
}

# Function to start Streamlit frontend
start_frontend() {
    log "Starting Streamlit frontend..."
    
    # Start frontend in background
    streamlit run frontend/streamlit_app.py \
        --server.port 8501 \
        --server.address 0.0.0.0 \
        --server.headless true \
        --browser.gatherUsageStats false \
        --logger.level info \
        > /tmp/frontend.log 2>&1 &
    
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /tmp/frontend.pid
    
    # Wait for frontend to be ready
    if check_port 8501 "Streamlit Frontend"; then
        success "Streamlit frontend started successfully (PID: $FRONTEND_PID)"
    else
        error "Failed to start Streamlit frontend"
        exit 1
    fi
}

# Function to handle graceful shutdown
shutdown_services() {
    log "Shutting down services gracefully..."
    
    # Kill backend if running
    if [ -f /tmp/backend.pid ]; then
        BACKEND_PID=$(cat /tmp/backend.pid)
        if kill -0 $BACKEND_PID 2>/dev/null; then
            log "Stopping FastAPI backend (PID: $BACKEND_PID)..."
            kill -TERM $BACKEND_PID
            wait $BACKEND_PID 2>/dev/null || true
        fi
        rm -f /tmp/backend.pid
    fi
    
    # Kill frontend if running
    if [ -f /tmp/frontend.pid ]; then
        FRONTEND_PID=$(cat /tmp/frontend.pid)
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            log "Stopping Streamlit frontend (PID: $FRONTEND_PID)..."
            kill -TERM $FRONTEND_PID
            wait $FRONTEND_PID 2>/dev/null || true
        fi
        rm -f /tmp/frontend.pid
    fi
    
    success "All services stopped"
    exit 0
}

# Set up signal handlers for graceful shutdown
trap shutdown_services SIGTERM SIGINT

# Main startup sequence
main() {
    log "Starting AI News Summarizer Agent..."
    log "======================================"
    
    # Validate environment
    validate_environment
    
    # Setup directories
    setup_directories
    
    # Start backend first
    start_backend
    
    # Wait a moment for backend to fully initialize
    sleep 3
    
    # Start frontend
    start_frontend
    
    # Display service information
    log "======================================"
    success "AI News Summarizer Agent is running!"
    log "Backend API: http://$HOST:$PORT"
    log "Frontend UI: http://$HOST:8501"
    log "API Docs: http://$HOST:$PORT/docs"
    log "======================================"
    
    # Monitor services
    while true; do
        # Check if backend is still running
        if [ -f /tmp/backend.pid ]; then
            BACKEND_PID=$(cat /tmp/backend.pid)
            if ! kill -0 $BACKEND_PID 2>/dev/null; then
                error "FastAPI backend process died unexpectedly"
                shutdown_services
            fi
        fi
        
        # Check if frontend is still running
        if [ -f /tmp/frontend.pid ]; then
            FRONTEND_PID=$(cat /tmp/frontend.pid)
            if ! kill -0 $FRONTEND_PID 2>/dev/null; then
                error "Streamlit frontend process died unexpectedly"
                shutdown_services
            fi
        fi
        
        sleep 10
    done
}

# Run main function
main "$@" 