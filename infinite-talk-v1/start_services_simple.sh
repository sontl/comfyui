#!/usr/bin/env bash
set -u

# Simple, robust startup script for infinitetalk with ultra-fast downloads
VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto"}

# Enable HuggingFace faster download backends globally
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HUB_ENABLE_HF_XET=1

# Model URLs
TEXT_ENCODER_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors?download=true"
VAE_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors?download=true"
#WAN_21_URL="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_1-I2V-14B-720p_fp8_e4m3fn_scaled_KJ.safetensors"
WAN_21_URL="https://huggingface.co/sontl/wan21-lightspeed/resolve/main/dasiwaWan21_lightspeedI2v14B480p.safetensors"
#WAN_21_INFINITE_MULTI_URL="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/InfiniteTalk/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors"
#WAN_21_INFINITE_SINGLE_URL="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/InfiniteTalk/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors"
#LIGHTX2V_LORA_URL="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors"
WAN_21_INFINITE_SINGLE_URL="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors"
CLIP_VISION_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors"
MELBAND_ROFOMER_URL="https://huggingface.co/Kijai/MelBandRoFormer_comfy/resolve/main/MelBandRoformer_fp16.safetensors"
CHINESE_WAV2VEC2_REPO="TencentGameMate/chinese-wav2vec2-base"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# Prevent multiple instances
if [ -f "/tmp/infinitetalk.lock" ]; then
    log "Another instance is running. Exiting."
    exit 0
fi
echo $$ > /tmp/infinitetalk.lock
trap "rm -f /tmp/infinitetalk.lock" EXIT

log "=== Infinitetalk Simple Startup ==="

# Step 1: Verify ComfyUI installation
log "Step 1: Verifying ComfyUI installation..."
if [ ! -f "${COMFY_DIR}/main.py" ]; then
    log "FATAL: ComfyUI not found. This should be pre-installed in the Docker image."
    exit 1
fi

log "ComfyUI installation verified."

# Step 2: Download models with fast HF CLI + space-safe fallback
log "Step 2: Starting fast parallel model downloads..."

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
            --user-agent="Mozilla/5.0 (compatible; InfiniteTalk/2.2)" \
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
        --user-agent "Mozilla/5.0 (compatible; InfiniteTalk/2.2)" \
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

# Download entire HuggingFace repository
download_hf_repo() {
    local repo_id="$1"
    local target_dir="$2"
    local name="$3"
    
    # Check if repo already exists and has content
    if [ -d "$target_dir" ] && [ "$(ls -A "$target_dir" 2>/dev/null)" ]; then
        log "✓ Repository already exists: $name"
        return 0
    fi
    
    mkdir -p "$target_dir"
    
    # Enable faster downloads
    export HF_HUB_ENABLE_HF_TRANSFER=1
    export HF_HUB_ENABLE_HF_XET=1
    
    # Try modern hf command first (fastest)
    if command -v hf > /dev/null 2>&1; then
        log "⬇ Downloading full repository via HF CLI (ultra-fast): $name"
        
        if HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_ENABLE_HF_XET=1 hf download \
            "$repo_id" \
            --local-dir "$target_dir" \
            --quiet 2>/dev/null; then
            log "✓ Downloaded repository: $name (via HF CLI ultra-fast)"
            return 0
        fi
        
        log "⚠ HF CLI ultra-fast failed for $name, trying legacy..."
    fi
    
    # Try legacy huggingface-cli
    if command -v huggingface-cli > /dev/null 2>&1; then
        log "⬇ Downloading full repository via HF CLI (legacy): $name"
        
        if HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_ENABLE_HF_XET=1 \
           PYTHONWARNINGS="ignore::FutureWarning" huggingface-cli download \
            "$repo_id" \
            --local-dir "$target_dir" \
            --quiet 2>/dev/null; then
            log "✓ Downloaded repository: $name (via HF CLI legacy)"
            return 0
        fi
        
        log "⚠ HF CLI legacy failed for $name"
    fi
    
    # Fallback: use git clone
    if command -v git > /dev/null 2>&1; then
        log "⬇ Cloning repository via git (fallback): $name"
        
        if git clone "https://huggingface.co/$repo_id" "$target_dir" 2>/dev/null; then
            log "✓ Cloned repository: $name (via git)"
            return 0
        fi
    fi
    
    log "✗ Failed to download repository: $name"
    return 1
}

# Enhanced parallel download manager with bandwidth control
download_all_models_parallel() {
    local max_concurrent=${1:-3}  # Limit concurrent downloads to avoid overwhelming network
    
    log "🚀 Starting parallel downloads (max $max_concurrent concurrent)..."
    
    # Array of download tasks
    declare -a DOWNLOAD_TASKS=(
        "$TEXT_ENCODER_URL|${COMFY_DIR}/models/text_encoders/umt5_xxl_fp16.safetensors|Text Encoder"
        "$VAE_URL|${COMFY_DIR}/models/vae/wan_2.1_vae.safetensors|VAE Model"
        "$WAN_21_URL|${COMFY_DIR}/models/diffusion_models/Wan2_1-I2V-14B-720p_fp8_e4m3fn_scaled_KJ.safetensors|Wan 2.1 Model"  #TODO change the name, still working for now
      #  "$WAN_21_INFINITE_MULTI_URL|${COMFY_DIR}/models/diffusion_models/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors|Wan 2.1 Infinite Multi Model"
        "$WAN_21_INFINITE_SINGLE_URL|${COMFY_DIR}/models/diffusion_models/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors|Wan 2.1 Infinite Single Model" #TODO change the name, still working for now
      # "$LIGHTX2V_LORA_URL|${COMFY_DIR}/models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors|Lightx2v LoRA"
        "$CLIP_VISION_URL|${COMFY_DIR}/models/clip_vision/clip_vision.safetensors|CLIP Vision"
        "$MELBAND_ROFOMER_URL|${COMFY_DIR}/models/diffusion_models/MelBandRoformer_fp16.safetensors|Melband RoFormer Model"
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

download_all_models_parallel 3  # Use 3 concurrent to balance speed and stability

# Download Chinese Wav2Vec2 repository
log "Step 2.5: Downloading Chinese Wav2Vec2 repository..."
download_hf_repo "$CHINESE_WAV2VEC2_REPO" "${COMFY_DIR}/models/transformers/TencentGameMate/chinese-wav2vec2-base" "Chinese Wav2Vec2 Base"

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