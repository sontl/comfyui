#!/usr/bin/env bash
set -u

# Simple, robust startup script for qwenImageEdit with ultra-fast downloads
VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto"}

# Enable HuggingFace faster download backends globally
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HUB_ENABLE_HF_XET=1

# Model URLs
VAE_URL="https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors?download=true"
QWEN_NUNCHAKU_URL="https://huggingface.co/nunchaku-tech/nunchaku-qwen-image-edit-2509/resolve/main/svdq-int4_r128-qwen-image-edit-2509-lightningv2.0-8steps.safetensors"
QWEN_CLIP="https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors?download=true"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# Prevent multiple instances
if [ -f "/tmp/qwenImageEdit.lock" ]; then
    log "Another instance is running. Exiting."
    exit 0
fi
echo $$ > /tmp/qwenImageEdit.lock
trap "rm -f /tmp/qwenImageEdit.lock" EXIT

log "=== qwenImageEdit Simple Startup ==="

# Step 1: Verify ComfyUI installation
log "Step 1: Verifying ComfyUI installation..."
if [ ! -f "${COMFY_DIR}/main.py" ]; then
    log "FATAL: ComfyUI not found. This should be pre-installed in the Docker image."
    exit 1
fi

log "ComfyUI installation verified."

# Step 2: Download models with fast HF CLI + space-safe fallback
log "Step 2: Starting fast parallel model downloads..."
download_all_models_parallel 2  # Use 2 concurrent to avoid space issues

# Space-efficient fallback download (no disk cache issues)
download_model_fallback() {
    local url="$1"
    local path="$2"
    local name="$3"
    local dir=$(dirname "$path")
    
    mkdir -p "$dir"
    
    log "⬇ Fallback download: $name"
    
    # Use aria2c with minimal, space-safe settings
    if command -v aria2c > /dev/null 2>&1; then
        aria2c \
            --max-connection-per-server=16 \
            --split=8 \
            --min-split-size=1M \
            --continue=true \
            --auto-file-renaming=false \
            --allow-overwrite=true \
            --retry-wait=3 \
            --max-tries=5 \
            --timeout=60 \
            --connect-timeout=30 \
            --dir="$dir" \
            --out="$(basename "$path")" \
            --user-agent="Mozilla/5.0 (compatible; qwenImageEdit/2.2)" \
            "$url" 2>/dev/null && {
            log "✓ Downloaded: $name (fallback)"
            return 0
        }
    fi
    
    # Final fallback to curl
    curl -L \
        --retry 3 \
        --retry-delay 2 \
        --connect-timeout 30 \
        --max-time 1800 \
        --user-agent "Mozilla/5.0 (compatible; qwenImageEdit/2.2)" \
        --progress-bar \
        -o "$path" \
        "$url" 2>/dev/null && {
        log "✓ Downloaded: $name (curl fallback)"
        return 0
    }
    
    log "✗ Failed to download: $name"
    return 1
}

# Fast HuggingFace CLI download with hf_transfer and hf_xet optimization
download_with_hf_cli() {
    local url="$1"
    local path="$2"
    local name="$3"
    
    # Check if file already exists
    if [ -f "$path" ]; then
        local size=$(stat -f%z "$path" 2>/dev/null || stat -c%s "$path" 2>/dev/null || echo "0")
        if [ "$size" -gt 1000000 ]; then  # > 1MB means likely valid
            log "✓ Model already exists: $name"
            return 0
        else
            log "⚠ Incomplete file detected, removing: $name"
            rm -f "$path"
        fi
    fi
    
    # Extract repo and filename from URL
    # URL format: https://huggingface.co/ORG/REPO/resolve/main/PATH/FILE
    if [[ $url =~ huggingface\.co/([^/]+)/([^/]+)/resolve/([^/]+)/(.+) ]]; then
        local org="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        local branch="${BASH_REMATCH[3]}"
        local file_path="${BASH_REMATCH[4]%\?*}"  # Remove query params
        
        local repo_id="${org}/${repo}"
        local target_dir="$(dirname "$path")"
        
        # Enable faster downloads
        export HF_HUB_ENABLE_HF_TRANSFER=1
        export HF_HUB_ENABLE_HF_XET=1
        
        # Try modern hf command first (fastest with hf_transfer/hf_xet)
        if command -v hf > /dev/null 2>&1; then
            log "⬇ Ultra-fast download via HF CLI (hf_transfer + hf_xet): $name"
            
            # Create a temporary directory to avoid conflicts
            local temp_dir="${target_dir}/.tmp_$$"
            mkdir -p "$temp_dir"
            
            # Download to temp directory first with faster backends
            if HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_ENABLE_HF_XET=1 hf download \
                "$repo_id" \
                "$file_path" \
                --revision "$branch" \
                --local-dir "$temp_dir" \
                --quiet 2>/dev/null; then
                
                # Find the downloaded file (it will be in the full path structure)
                local downloaded_file=$(find "$temp_dir" -name "$(basename "$path")" -type f | head -1)
                if [ -f "$downloaded_file" ]; then
                    mv "$downloaded_file" "$path" && {
                        rm -rf "$temp_dir"
                        log "✓ Downloaded: $name (via HF CLI ultra-fast)"
                        return 0
                    }
                fi
            fi
            
            # Cleanup temp directory on failure
            rm -rf "$temp_dir"
            log "⚠ HF CLI ultra-fast failed for $name, trying legacy..."
        fi
        
        # Try legacy huggingface-cli with faster backends
        if command -v huggingface-cli > /dev/null 2>&1; then
            log "⬇ Downloading via HF CLI (legacy with hf_transfer): $name"
            
            local temp_dir="${target_dir}/.tmp_legacy_$$"
            mkdir -p "$temp_dir"
            
            if HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_ENABLE_HF_XET=1 \
               PYTHONWARNINGS="ignore::FutureWarning" huggingface-cli download \
                "$repo_id" \
                "$file_path" \
                --revision "$branch" \
                --local-dir "$temp_dir" \
                --quiet 2>/dev/null; then
                
                # Find the downloaded file (it will be in the full path structure)
                local downloaded_file=$(find "$temp_dir" -name "$(basename "$path")" -type f | head -1)
                if [ -f "$downloaded_file" ]; then
                    mv "$downloaded_file" "$path" && {
                        rm -rf "$temp_dir"
                        log "✓ Downloaded: $name (via HF CLI legacy with hf_transfer)"
                        return 0
                    }
                fi
            fi
            
            rm -rf "$temp_dir"
            log "⚠ HF CLI legacy failed for $name, using fallback..."
        fi
    fi
    
    # Fallback to space-safe download
    download_model_fallback "$url" "$path" "$name"
}

# Enhanced parallel download manager with bandwidth control
download_all_models_parallel() {
    local max_concurrent=${1:-3}  # Limit concurrent downloads to avoid overwhelming network
    
    log "🚀 Starting parallel downloads (max $max_concurrent concurrent)..."
    
    # Array of download tasks
    declare -a DOWNLOAD_TASKS=(
        "$VAE_URL|${COMFY_DIR}/models/vae/qwen_image_vae.safetensors|VAE Model"
        "$QWEN_NUNCHAKU_URL|${COMFY_DIR}/models/diffusion_models/svdq-int4_r128-qwen-image-edit-2509-lightningv2.0-8steps.safetensors|Qwen Nunchaku Model"
        "$QWEN_CLIP|${COMFY_DIR}/models/clip/qwen_2.5_vl_7b_fp8_scaled.safetensors|CLIP Vision"
    )
    
    local active_jobs=0
    declare -a job_pids=()
    
    for task in "${DOWNLOAD_TASKS[@]}"; do
        IFS='|' read -r url path name <<< "$task"
        
        # Wait if we have too many concurrent downloads
        while [ $active_jobs -ge $max_concurrent ]; do
            # Check if any job finished
            for i in "${!job_pids[@]}"; do
                if ! kill -0 "${job_pids[$i]}" 2>/dev/null; then
                    unset 'job_pids[i]'
                    ((active_jobs--))
                fi
            done
            job_pids=("${job_pids[@]}")  # Reindex array
            sleep 1
        done
        
        # Start download
        download_with_hf_cli "$url" "$path" "$name" &
        job_pids+=($!)
        ((active_jobs++))
    done
    
    # Wait for all remaining jobs
    log "⏳ Waiting for downloads to complete..."
    local success=true
    for pid in "${job_pids[@]}"; do
        wait "$pid" || success=false
    done
    
    if [ "$success" = true ]; then
        log "🎉 All models downloaded successfully!"
        return 0
    else
        log "⚠ Some downloads failed, but continuing..."
        return 1
    fi
}

# Step 3: Start services
log "Step 3: Starting services..."

# Set environment variables
export TORCH_INDUCTOR_FORCE_DISABLE_FP8="1"
export CUDA_VISIBLE_DEVICES="0"
export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512"

source "${VENV_COMFY}/bin/activate"

# Copy workflow file
cp /workspace/workflow_api.json "${COMFY_DIR}/" 2>/dev/null || true

# Start API wrapper
log "Starting API wrapper..."
cd /workspace
python3 api_wrapper.py &
API_PID=$!
log "API wrapper started (PID: $API_PID)"

# Start ComfyUI
log "Starting ComfyUI..."
cd "${COMFY_DIR}"
python main.py ${COMFY_LAUNCH_ARGS} &
COMFY_PID=$!
log "ComfyUI started (PID: $COMFY_PID)"

deactivate

# Start Caddy
if [ -f "/etc/caddy/Caddyfile" ]; then
    log "Starting Caddy..."
    caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
    CADDY_PID=$!
    log "Caddy started (PID: $CADDY_PID)"
fi

# Setup cleanup
cleanup() {
    log "Shutting down services..."
    [ -n "${API_PID:-}" ] && kill -TERM "$API_PID" 2>/dev/null || true
    [ -n "${COMFY_PID:-}" ] && kill -TERM "$COMFY_PID" 2>/dev/null || true
    [ -n "${CADDY_PID:-}" ] && kill -TERM "$CADDY_PID" 2>/dev/null || true
    sleep 5
    [ -n "${API_PID:-}" ] && kill -KILL "$API_PID" 2>/dev/null || true
    [ -n "${COMFY_PID:-}" ] && kill -KILL "$COMFY_PID" 2>/dev/null || true
    [ -n "${CADDY_PID:-}" ] && kill -KILL "$CADDY_PID" 2>/dev/null || true
    log "Shutdown complete."
    exit 0
}

trap cleanup SIGTERM SIGINT

log "=== Startup Complete ==="
log "ComfyUI: http://localhost:8188"
log "API: http://localhost:8189"
log "API Docs: http://localhost:8189/docs"

# Wait for services
if [ -n "${COMFY_PID:-}" ] && [ -n "${API_PID:-}" ]; then
    wait -n "$COMFY_PID" "$API_PID"
    log "A service exited. Shutting down..."
    cleanup
else
    log "No services started. Exiting."
    exit 1
fi