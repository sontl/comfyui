#!/usr/bin/env bash
set -u

# Simple, robust startup script for infinitetalk 
VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto"}

# Model URLs
TEXT_ENCODER_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors?download=true"
VAE_URL="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors?download=true"
WAN_21_URL="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_1-I2V-14B-720p_fp8_e4m3fn_scaled_KJ.safetensors"
WAN_21_INFINITE_MULTI_URL="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/InfiniteTalk/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors"
WAN_21_INFINITE_SINGLE_URL="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/InfiniteTalk/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors"
LIGHTX2V_LORA_URL="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors"
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

# Step 2: Download models (async parallel downloads)
log "Step 2: Starting parallel model downloads..."

# Fast async download function with progress tracking
download_model_async() {
    local url="$1"
    local path="$2"
    local name="$3"
    local dir=$(dirname "$path")
    
    mkdir -p "$dir"
    
    if [ -f "$path" ]; then
        log "✓ Model already exists: $name"
        return 0
    fi
    
    log "⬇ Starting download: $name"
    
    # Use aria2c with optimized settings for HuggingFace
    if command -v aria2c > /dev/null 2>&1; then
        aria2c \
            --max-connection-per-server=16 \
            --split=16 \
            --min-split-size=1M \
            --max-concurrent-downloads=4 \
            --continue=true \
            --auto-file-renaming=false \
            --allow-overwrite=true \
            --retry-wait=3 \
            --max-tries=5 \
            --timeout=60 \
            --connect-timeout=30 \
            --dir="$dir" \
            --out="$(basename "$path")" \
            --user-agent="Mozilla/5.0 (compatible; Infinitetalk/2.2)" \
            "$url" 2>/dev/null && {
            log "✓ Downloaded: $name"
            return 0
        } || {
            log "⚠ aria2c failed for $name, trying curl..."
            curl -L \
                --retry 3 \
                --retry-delay 2 \
                --connect-timeout 30 \
                --max-time 1800 \
                --user-agent "Mozilla/5.0 (compatible; Infinitetalk/2.2)" \
                --progress-bar \
                -o "$path" \
                "$url" 2>/dev/null && {
                log "✓ Downloaded: $name (via curl)"
                return 0
            } || {
                log "✗ Failed to download: $name"
                return 1
            }
        }
    else
        curl -L \
            --retry 3 \
            --retry-delay 2 \
            --connect-timeout 30 \
            --max-time 1800 \
            --user-agent "Mozilla/5.0 (compatible; InfiniteTalk/2.2)" \
            --progress-bar \
            -o "$path" \
            "$url" 2>/dev/null && {
            log "✓ Downloaded: $name"
            return 0
        } || {
            log "✗ Failed to download: $name"
            return 1
        }
    fi
}

# Start all downloads in parallel
log "🚀 Launching parallel downloads..."

download_model_async "$TEXT_ENCODER_URL" "${COMFY_DIR}/models/text_encoders/umt5_xxl_fp16.safetensors" "Text Encoder" &
TEXT_PID=$!

download_model_async "$VAE_URL" "${COMFY_DIR}/models/vae/wan_2.1_vae.safetensors" "VAE Model" &
VAE_PID=$!

download_model_async "$WAN_21_URL" "${COMFY_DIR}/models/checkpoints/Wan2_1-I2V-14B-720p_fp8_e4m3fn_scaled_KJ.safetensors" "Wan 2.1 Model" &
WAN21_PID=$!

download_model_async "$WAN_21_INFINITE_MULTI_URL" "${COMFY_DIR}/models/checkpoints/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors" "Wan 2.1 Infinite Multi Model" &
WAN21_INFINITE_MULTI_PID=$!

download_model_async "$WAN_21_INFINITE_SINGLE_URL" "${COMFY_DIR}/models/checkpoints/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors" "Wan 2.1 Infinite Single Model" & 
WAN21_INFINITE_SINGLE_PID=$!

download_model_async "$LIGHTX2V_LORA_URL" "${COMFY_DIR}/models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors" "Lightx2v LoRA" &
LIGHTX2V_LORA_PID=$!

# Wait for all downloads to complete
log "⏳ Waiting for downloads to complete..."
DOWNLOAD_SUCCESS=true

wait $TEXT_PID || DOWNLOAD_SUCCESS=false  
wait $VAE_PID || DOWNLOAD_SUCCESS=false
wait $WAN21_PID || DOWNLOAD_SUCCESS=false
wait $WAN21_INFINITE_MULTI_PID || DOWNLOAD_SUCCESS=false
wait $WAN21_INFINITE_SINGLE_PID || DOWNLOAD_SUCCESS=false
wait $LIGHTX2V_LORA_PID || DOWNLOAD_SUCCESS=false

if [ "$DOWNLOAD_SUCCESS" = true ]; then
    log "🎉 All models downloaded successfully!"
else
    log "⚠ Some downloads failed, but continuing startup..."
fi

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