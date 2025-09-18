#!/bin/bash

###############################################################################
# QWEN IMAGE EDIT NUNCHANKU API STARTUP SCRIPT
# Optimized startup script for the Qwen Image Edit Nunchanku API service
###############################################################################

set -e  # Exit on any error

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Signal handlers for graceful shutdown
cleanup() {
    log "Received shutdown signal, cleaning up..."
    
    # Kill background processes if they exist
    if [ ! -z "$API_PID" ]; then
        log "Stopping API server (PID: $API_PID)..."
        kill -TERM "$API_PID" 2>/dev/null || true
        wait "$API_PID" 2>/dev/null || true
    fi
    
    log "Cleanup completed"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${SCRIPT_DIR}"
VENV_PATH="${VENV_PATH:-/opt/venv}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${WORKSPACE_DIR}/models}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Instance lock to prevent multiple startups
LOCKFILE="/tmp/qwen_api_startup.lock"
if [ -f "$LOCKFILE" ]; then
    EXISTING_PID=$(cat "$LOCKFILE")
    if ps -p "$EXISTING_PID" > /dev/null 2>&1; then
        log "Another instance is already running (PID: $EXISTING_PID)"
        exit 0
    else
        log "Removing stale lock file"
        rm -f "$LOCKFILE"
    fi
fi

echo $$ > "$LOCKFILE"

log "=== Qwen Image Edit Nunchanku API Startup ==="
log "Workspace: $WORKSPACE_DIR"
log "Environment: $ENVIRONMENT"
log "API Host: $API_HOST:$API_PORT"
log "Model Cache: $MODEL_CACHE_DIR"
log "Log Level: $LOG_LEVEL"

# Step 1: Environment Setup
log "Step 1: Setting up environment..."

# Activate virtual environment if it exists
if [ -d "$VENV_PATH" ]; then
    log "Activating virtual environment: $VENV_PATH"
    export PATH="$VENV_PATH/bin:$PATH"
    export VIRTUAL_ENV="$VENV_PATH"
else
    log "No virtual environment found at $VENV_PATH, using system Python"
fi

# Set Python path
export PYTHONPATH="${WORKSPACE_DIR}:${PYTHONPATH}"
export PYTHONUNBUFFERED=1

# Step 2: Dependency Check
log "Step 2: Checking dependencies..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    error_exit "Python3 not found in PATH"
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log "Python version: $PYTHON_VERSION"

# Install dependencies if requirements file exists
if [ -f "$WORKSPACE_DIR/api_requirements.txt" ]; then
    log "Installing/updating Python dependencies..."
    pip install --no-cache-dir -r "$WORKSPACE_DIR/api_requirements.txt" || {
        log "Warning: Failed to install some dependencies, continuing..."
    }
else
    log "No requirements file found, skipping dependency installation"
fi

# Step 3: Model Cache Setup
log "Step 3: Setting up model cache..."

# Create model cache directory
mkdir -p "$MODEL_CACHE_DIR"
log "Model cache directory: $MODEL_CACHE_DIR"

# Check available disk space
AVAILABLE_SPACE=$(df -BG "$MODEL_CACHE_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 10 ]; then
    log "Warning: Low disk space available ($AVAILABLE_SPACE GB). Minimum 10GB recommended."
fi

# Step 4: GPU Check
log "Step 4: Checking GPU availability..."

# Check NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | head -1)
    log "GPU detected: $GPU_INFO"
    
    # Check GPU memory
    GPU_MEMORY=$(echo "$GPU_INFO" | cut -d',' -f2 | tr -d ' ')
    if [ "$GPU_MEMORY" -lt 6000 ]; then
        log "Warning: GPU has less than 6GB memory ($GPU_MEMORY MB). Performance may be limited."
    fi
else
    log "Warning: No NVIDIA GPU detected or nvidia-smi not available"
fi

# Check CUDA availability
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')" 2>/dev/null || {
    log "Warning: Could not check CUDA availability"
}

# Step 5: Configuration
log "Step 5: Setting up configuration..."

# Set environment variables
export API_HOST="$API_HOST"
export API_PORT="$API_PORT"
export MODEL_CACHE_DIR="$MODEL_CACHE_DIR"
export LOG_LEVEL="$LOG_LEVEL"
export ENVIRONMENT="$ENVIRONMENT"

# CUDA optimizations for RTX 4090
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-max_split_size_mb:512}"
export TORCH_INDUCTOR_FORCE_DISABLE_FP8="${TORCH_INDUCTOR_FORCE_DISABLE_FP8:-1}"

log "Environment variables configured"

# Step 6: Health Check Function
check_api_health() {
    local max_attempts=30
    local attempt=1
    
    log "Checking API health..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "http://${API_HOST}:${API_PORT}/health" > /dev/null 2>&1; then
            log "API health check passed"
            return 0
        fi
        
        log "Health check attempt $attempt/$max_attempts failed, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "API health check failed after $max_attempts attempts"
    return 1
}

# Step 7: Start API Service
log "Step 7: Starting Qwen Image Edit API..."

cd "$WORKSPACE_DIR"

# Check if main.py exists
if [ ! -f "main.py" ]; then
    error_exit "main.py not found in workspace directory"
fi

# Start the API server
log "Starting API server on $API_HOST:$API_PORT..."

python3 main.py &
API_PID=$!

log "API server started with PID: $API_PID"

# Wait a moment for the server to initialize
sleep 5

# Check if the process is still running
if ! ps -p "$API_PID" > /dev/null 2>&1; then
    error_exit "API server failed to start"
fi

# Step 8: Health Check
log "Step 8: Performing health check..."

if check_api_health; then
    log "=== Startup Complete ==="
    log "Qwen Image Edit Nunchanku API is running"
    log "API Endpoint: http://${API_HOST}:${API_PORT}"
    log "Health Check: http://${API_HOST}:${API_PORT}/health"
    log "API Documentation: http://${API_HOST}:${API_PORT}/docs"
    log "Process PID: $API_PID"
else
    log "Health check failed, stopping service..."
    kill -TERM "$API_PID" 2>/dev/null || true
    error_exit "Service failed to start properly"
fi

# Step 9: Monitor and Keep Running
log "Step 9: Monitoring service..."

# Function to monitor the API process
monitor_process() {
    while true; do
        if ! ps -p "$API_PID" > /dev/null 2>&1; then
            log "API process died unexpectedly, attempting restart..."
            
            # Try to restart
            python3 main.py &
            API_PID=$!
            
            sleep 5
            
            if ps -p "$API_PID" > /dev/null 2>&1; then
                log "API process restarted successfully (PID: $API_PID)"
            else
                error_exit "Failed to restart API process"
            fi
        fi
        
        sleep 30  # Check every 30 seconds
    done
}

# Monitor in background
monitor_process &
MONITOR_PID=$!

# Wait for the main process
wait "$API_PID"

# Clean up
log "API process ended, cleaning up..."
kill -TERM "$MONITOR_PID" 2>/dev/null || true
rm -f "$LOCKFILE"

log "=== Shutdown Complete ==="