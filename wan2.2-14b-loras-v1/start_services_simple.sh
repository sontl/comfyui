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

# Optimized download function for HuggingFace safetensors files
download_model_optimized() {
    local url="$1"
    local path="$2"
    local name="$3"
    local dir=$(dirname "$path")
    
    mkdir -p "$dir"
    
    # Check if file exists and is valid
    if [ -f "$path" ]; then
        # Verify file is not corrupted (has reasonable size)
        local size=$(stat -f%z "$path" 2>/dev/null || stat -c%s "$path" 2>/dev/null || echo "0")
        if [ "$size" -gt 1000000 ]; then  # > 1MB means likely valid
            log "✓ Model already exists: $name"
            return 0
        else
            log "⚠ Incomplete file detected, removing: $name"
            rm -f "$path"
        fi
    fi
    
    log "⬇ Starting download: $name"
    
    # Try aria2c first (best performance)
    if command -v aria2c > /dev/null 2>&1; then
        aria2c \
            --max-connection-per-server=16 \
            --split=16 \
            --min-split-size=5M \
            --max-concurrent-downloads=4 \
            --continue=true \
            --auto-file-renaming=false \
            --allow-overwrite=true \
            --max-tries=10 \
            --retry-wait=2 \
            --timeout=120 \
            --connect-timeout=60 \
            --lowest-speed-limit=100K \
            --max-download-limit=0 \
            --optimize-concurrent-downloads=true \
            --file-allocation=none \
            --disk-cache=64M \
            --piece-length=5M \
            --stream-piece-selector=inorder \
            --enable-http-pipelining=true \
            --http-accept-gzip=true \
            --dir="$dir" \
            --out="$(basename "$path")" \
            --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
            --header="Accept-Encoding: gzip, deflate" \
            "$url" 2>&1 | grep -v "Download Progress" && {
            log "✓ Downloaded: $name"
            return 0
        }
        
        log "⚠ aria2c failed for $name, trying axel..."
    fi
    
    # Try axel (alternative fast downloader)
    if command -v axel > /dev/null 2>&1; then
        axel \
            -n 16 \
            -a \
            --output="$path" \
            --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
            --header="Accept-Encoding: gzip, deflate" \
            "$url" 2>&1 | grep -v "%" && {
            log "✓ Downloaded: $name (via axel)"
            return 0
        }
        
        log "⚠ axel failed for $name, trying curl..."
    fi
    
    # Fallback to curl with optimizations
    curl -L \
        --retry 5 \
        --retry-delay 3 \
        --retry-max-time 3600 \
        --connect-timeout 60 \
        --max-time 3600 \
        --speed-limit 102400 \
        --speed-time 30 \
        --tcp-fastopen \
        --compressed \
        --parallel \
        --parallel-max 4 \
        --keepalive-time 60 \
        --no-buffer \
        -C - \
        --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
        --header "Accept-Encoding: gzip, deflate, br" \
        --header "Connection: keep-alive" \
        --progress-bar \
        -o "$path" \
        "$url" 2>&1 && {
        log "✓ Downloaded: $name (via curl)"
        return 0
    }
    
    log "✗ Failed to download: $name"
    return 1
}

# Alternative: Use HuggingFace CLI (often fastest for HF models)
download_with_hf_cli() {
    local url="$1"
    local path="$2"
    local name="$3"
    
    # Extract repo and filename from URL
    # URL format: https://huggingface.co/ORG/REPO/resolve/main/PATH/FILE
    if [[ $url =~ huggingface\.co/([^/]+)/([^/]+)/resolve/([^/]+)/(.+) ]]; then
        local org="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        local branch="${BASH_REMATCH[3]}"
        local file_path="${BASH_REMATCH[4]%\?*}"  # Remove query params
        
        local repo_id="${org}/${repo}"
        
        if command -v huggingface-cli > /dev/null 2>&1; then
            log "⬇ Downloading via HF CLI: $name"
            
            # Use huggingface-cli download (supports resume and is optimized)
            huggingface-cli download \
                "$repo_id" \
                "$file_path" \
                --revision "$branch" \
                --local-dir "$(dirname "$path")" \
                --local-dir-use-symlinks False \
                --resume-download && {
                
                # Move file to correct location if needed
                local downloaded_file="$(dirname "$path")/$file_path"
                if [ -f "$downloaded_file" ] && [ "$downloaded_file" != "$path" ]; then
                    mv "$downloaded_file" "$path"
                fi
                
                log "✓ Downloaded: $name (via HF CLI)"
                return 0
            }
        fi
    fi
    
    # Fallback to optimized download
    download_model_optimized "$url" "$path" "$name"
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

# if [ ! -d "${COMFY_DIR}/custom_nodes/ComfyUI-WAN" ]; then
#     log "⚠ WAN custom node not found. Attempting to install at runtime..."
#     cd "${COMFY_DIR}/custom_nodes"
#     git clone --depth 1 https://github.com/Kijai/ComfyUI-WAN.git ComfyUI-WAN || {
#         log "⚠ Failed to clone WAN custom node. ComfyUI will run without it."
#     }
#     if [ -d "ComfyUI-WAN" ] && [ -f "ComfyUI-WAN/requirements.txt" ]; then
#         source "${VENV_COMFY}/bin/activate"
#         cd ComfyUI-WAN
#         pip install --no-cache-dir -r requirements.txt || log "⚠ WAN requirements install failed"
#         deactivate
#         cd "${COMFY_DIR}"
#     fi
# else
#     log "✓ WAN custom node found."
# fi

log "ComfyUI installation verified."

# Step 2: Download models with optimized parallel downloads
log "Step 2: Starting optimized parallel model downloads..."
download_all_models_parallel 3  # Use 3 concurrent downloads for optimal performance

# Step 3: Start ComfyUI
log "Step 3: Starting ComfyUI..."
cd "${COMFY_DIR}"
source "${VENV_COMFY}/bin/activate"

log "🚀 Launching ComfyUI with args: $COMFY_LAUNCH_ARGS"
exec python main.py $COMFY_LAUNCH_ARGS