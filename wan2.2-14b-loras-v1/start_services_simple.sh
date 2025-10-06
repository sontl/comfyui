#!/usr/bin/env bash
set -u

# WAN 2.2-14B LoRAs Simple Startup Script with Optimized Downloads
VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto"}

# Model URLs
TEXT_ENCODER_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors?download=true"
VAE_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors?download=true"
HIGH_NOISE_LORA_URL="https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors"
LOW_NOISE_LORA_URL="https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors"
HIGH_NOISE_14B_FP8_UPSCALED="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
LOW_NOISE_14B_FP8_UPSCALED="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# Prevent multiple instances
if [ -f "/tmp/wan14b.lock" ]; then
    log "Another instance is running. Exiting."
    exit 0
fi
echo $$ > /tmp/wan14b.lock
trap "rm -f /tmp/wan14b.lock" EXIT

log "=== WAN 2.2-14B LoRAs Simple Startup ==="

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
            --user-agent="Mozilla/5.0 (compatible; WAN2.2/14B)" \
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
        --user-agent "Mozilla/5.0 (compatible; WAN2.2/14B)" \
        --progress-bar \
        -o "$path" \
        "$url" 2>/dev/null && {
        log "✓ Downloaded: $name (curl fallback)"
        return 0
    }
    
    log "✗ Failed to download: $name"
    return 1
}

# Fast HuggingFace CLI download with space-safe fallback
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
        
        # Try modern hf command first (fastest)
        if command -v hf > /dev/null 2>&1; then
            log "⬇ Fast download via HF CLI: $name"
            
            # Create a temporary directory to avoid conflicts
            local temp_dir="${target_dir}/.tmp_$$"
            mkdir -p "$temp_dir"
            
            # Download to temp directory first
            if hf download \
                "$repo_id" \
                "$file_path" \
                --revision "$branch" \
                --local-dir "$temp_dir" \
                --quiet 2>/dev/null; then
                
                # Move file to final location
                local downloaded_file="$temp_dir/$file_path"
                if [ -f "$downloaded_file" ]; then
                    mv "$downloaded_file" "$path" && {
                        rm -rf "$temp_dir"
                        log "✓ Downloaded: $name (via HF CLI)"
                        return 0
                    }
                fi
            fi
            
            # Cleanup temp directory on failure
            rm -rf "$temp_dir"
            log "⚠ HF CLI failed for $name, trying legacy..."
        fi
        
        # Try legacy huggingface-cli
        if command -v huggingface-cli > /dev/null 2>&1; then
            log "⬇ Downloading via HF CLI (legacy): $name"
            
            local temp_dir="${target_dir}/.tmp_legacy_$$"
            mkdir -p "$temp_dir"
            
            if PYTHONWARNINGS="ignore::FutureWarning" huggingface-cli download \
                "$repo_id" \
                "$file_path" \
                --revision "$branch" \
                --local-dir "$temp_dir" \
                --quiet 2>/dev/null; then
                
                local downloaded_file="$temp_dir/$file_path"
                if [ -f "$downloaded_file" ]; then
                    mv "$downloaded_file" "$path" && {
                        rm -rf "$temp_dir"
                        log "✓ Downloaded: $name (via HF CLI legacy)"
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
    local max_concurrent=${1:-4}  # Limit concurrent downloads to avoid overwhelming network
    
    log "🚀 Starting parallel downloads (max $max_concurrent concurrent)..."
    
    # Array of download tasks
    declare -a DOWNLOAD_TASKS=(
        "$TEXT_ENCODER_URL|${COMFY_DIR}/models/text_encoders/umt5_xxl_fp16.safetensors|Text Encoder"
        "$VAE_URL|${COMFY_DIR}/models/vae/wan_2.1_vae.safetensors|VAE Model"
        "$HIGH_NOISE_LORA_URL|${COMFY_DIR}/models/loras/high_noise_model.safetensors|High Noise LoRA"
        "$LOW_NOISE_LORA_URL|${COMFY_DIR}/models/loras/low_noise_model.safetensors|Low Noise LoRA"
        "$HIGH_NOISE_14B_FP8_UPSCALED|${COMFY_DIR}/models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors|High Noise Model"
        "$LOW_NOISE_14B_FP8_UPSCALED|${COMFY_DIR}/models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors|Low Noise Model"
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

# Step 1: Verify ComfyUI installation
log "Step 1: Verifying ComfyUI installation..."
if [ ! -f "${COMFY_DIR}/main.py" ]; then
    log "FATAL: ComfyUI not found. This should be pre-installed in the Docker image."
    exit 1
fi

log "ComfyUI installation verified."

# Step 2: Download models with fast HF CLI + space-safe fallback
log "Step 2: Starting fast parallel model downloads..."
download_all_models_parallel 2  # Use 3 concurrent to avoid space issues

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