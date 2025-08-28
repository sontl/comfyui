#!/usr/bin/env bash
set -euo pipefail

VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto"}

# FastWAN 2.2-5B Model URLs - optimized for fastest download
declare -A MODEL_URLS=(
    ["models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"]="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"
    ["models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"]="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    ["models/vae/wan2.2_vae.safetensors"]="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors"
    ["models/loras/Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors"]="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/FastWan/Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors"
)

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

download_model() {
    local model_path="$1"
    local model_url="$2"
    local full_path="${COMFY_DIR}/${model_path}"
    local dir_path=$(dirname "${full_path}")
    
    mkdir -p "${dir_path}"
    
    if [[ -f "${full_path}" ]]; then
        log "Model already exists: ${model_path}"
        return 0
    fi
    
    log "Downloading ${model_path}..."
    
    # Use aria2c for fastest parallel downloads
    if command -v aria2c &> /dev/null; then
        aria2c \
            --max-connection-per-server=16 \
            --split=16 \
            --min-split-size=1M \
            --max-concurrent-downloads=4 \
            --continue=true \
            --auto-file-renaming=false \
            --allow-overwrite=true \
            --dir="${dir_path}" \
            --out="$(basename "${full_path}")" \
            "${model_url}" || {
            log "aria2c failed for ${model_path}, falling back to curl..."
            curl -L -C - -o "${full_path}" "${model_url}"
        }
    else
        curl -L -C - -o "${full_path}" "${model_url}"
    fi
    
    if [[ -f "${full_path}" ]]; then
        log "Successfully downloaded: ${model_path}"
    else
        log "Failed to download: ${model_path}"
        return 1
    fi
}

download_models_parallel() {
    log "Starting parallel model downloads..."
    local pids=()
    
    for model_path in "${!MODEL_URLS[@]}"; do
        download_model "${model_path}" "${MODEL_URLS[$model_path]}" &
        pids+=($!)
    done
    
    log "Waiting for downloads to complete..."
    local failed=0
    for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
            ((failed++))
        fi
    done
    
    if [[ $failed -eq 0 ]]; then
        log "All model downloads completed successfully."
    else
        log "Warning: $failed download(s) failed."
    fi
}

setup_comfyui() {
    log "Setting up ComfyUI..."
    
    if [ -f "${COMFY_DIR}/main.py" ]; then
        log "Found existing ComfyUI in ${COMFY_DIR}."
        cd "${COMFY_DIR}"
    else
        log "ComfyUI not found; cloning..."
        mkdir -p "$(dirname "${COMFY_DIR}")"
        if git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "${COMFY_DIR}"; then
            log "ComfyUI clone complete."
            cd "${COMFY_DIR}"
        else
            log "Failed to clone ComfyUI."
            return 1
        fi
    fi

    # Install ComfyUI requirements
    if [ -f "requirements.txt" ]; then
        log "Installing ComfyUI requirements..."
        source "${VENV_COMFY}/bin/activate"
        pip install --no-cache-dir -r requirements.txt || log "Warning: ComfyUI requirements install failed."
        deactivate
    fi

    # Clone FastWAN custom node if not exists
    if [ ! -d "custom_nodes/fastwan-moviegen" ]; then
        log "Cloning FastWAN custom node..."
        git clone --depth 1 https://github.com/FNGarvin/fastwan-moviegen.git custom_nodes/fastwan-moviegen || \
          log "Warning: Failed to clone FastWAN custom node"
    fi

    # Install custom node dependencies
    if [ -d "custom_nodes/fastwan-moviegen" ] && [ -f "custom_nodes/fastwan-moviegen/requirements.txt" ]; then
        log "Installing FastWAN custom node requirements..."
        source "${VENV_COMFY}/bin/activate"
        cd custom_nodes/fastwan-moviegen
        pip install --no-cache-dir -r requirements.txt || log "Warning: FastWAN node requirements install failed."
        cd "${COMFY_DIR}"
        deactivate
    fi
}

start_services() {
    log "Starting services..."
    
    # Set environment variables
    export TORCH_INDUCTOR_FORCE_DISABLE_FP8="1"
    export CUDA_VISIBLE_DEVICES="0"
    export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512"
    
    source "${VENV_COMFY}/bin/activate"
    
    # Start API wrapper
    log "Starting API wrapper..."
    cd /workspace
    cp /workspace/workflow_api.json /workspace/ComfyUI/ 2>/dev/null || true
    python3 api_wrapper.py &
    API_PID=$!
    log "API wrapper PID: ${API_PID}"
    
    # Start ComfyUI
    log "Starting ComfyUI..."
    cd "${COMFY_DIR}"
    python main.py ${COMFY_LAUNCH_ARGS} &
    COMFY_PID=$!
    log "ComfyUI PID: ${COMFY_PID}"
    
    deactivate
    
    # Start Caddy
    log "Starting Caddy..."
    caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
    CADDY_PID=$!
    log "Caddy PID: ${CADDY_PID}"
    
    # Optional Tailscale
    if [[ "${ENABLE_TAILSCALE:-false}" == "true" ]]; then
        log "Starting Tailscale..."
        TS_STATE_DIR="/workspace/tailscale"
        TS_STATE_FILE="${TS_STATE_DIR}/tailscaled.state"
        TS_SOCKET_FILE="/var/run/tailscale/tailscaled.sock"
        
        mkdir -p "${TS_STATE_DIR}"
        mkdir -p "$(dirname "${TS_SOCKET_FILE}")"
        
        tailscaled \
          --state="${TS_STATE_FILE}" \
          --socket="${TS_SOCKET_FILE}" \
          --tun=userspace-networking &
        TAILSCALED_PID=$!
        sleep 4
        
        TS_UP_ARGS=("--hostname=${RUNPOD_POD_HOSTNAME:-comfy-pod}" "--accept-dns=false")
        if [[ -n "${TAILSCALE_AUTHKEY:-}" ]]; then
          TS_UP_ARGS+=("--auth-key=${TAILSCALE_AUTHKEY}")
        fi
        
        if tailscale --socket="${TS_SOCKET_FILE}" up "${TS_UP_ARGS[@]}"; then
          log "Tailscale started successfully."
        else
          log "Tailscale 'up' command failed or already up. Continuing..."
        fi
    fi
}

# Main execution
log "FastWAN 2.2-5B Network Storage Setup Starting..."

# Run setup and downloads in parallel for maximum speed
log "Starting parallel setup and downloads..."
setup_comfyui &
SETUP_PID=$!

download_models_parallel &
DOWNLOAD_PID=$!

# Wait for both to complete
wait $SETUP_PID || log "Warning: ComfyUI setup had issues"
wait $DOWNLOAD_PID || log "Warning: Model downloads had issues"

log "Setup and downloads complete. Starting services..."
start_services

# Setup cleanup
PIDS_TO_KILL=()
[[ -n "${COMFY_PID:-}" ]] && PIDS_TO_KILL+=("${COMFY_PID}")
[[ -n "${API_PID:-}" ]] && PIDS_TO_KILL+=("${API_PID}")
[[ -n "${CADDY_PID:-}" ]] && PIDS_TO_KILL+=("${CADDY_PID}")
[[ -n "${TAILSCALED_PID:-}" ]] && PIDS_TO_KILL+=("${TAILSCALED_PID}")

cleanup() {
  log "Terminating services..."
  if [[ ${#PIDS_TO_KILL[@]} -gt 0 ]]; then
    kill -SIGTERM "${PIDS_TO_KILL[@]}" 2>/dev/null || true
    sleep 5
    for pid in "${PIDS_TO_KILL[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        log "PID $pid still alive; sending SIGKILL."
        kill -SIGKILL "$pid" 2>/dev/null || true
      fi
    done
  fi
  if [[ -n "${TAILSCALED_PID:-}" ]] && kill -0 "${TAILSCALED_PID}" 2>/dev/null; then
    tailscale --socket="${TS_SOCKET_FILE}" logout || true
  fi
  log "Shutdown complete."
  exit 0
}

trap cleanup SIGTERM SIGINT

log "Startup complete!"
log "ComfyUI available at: http://localhost:8188"
log "API available at: http://localhost:8189"
log "API docs available at: http://localhost:8189/docs"

# Wait for main services
PIDS_TO_WAIT=()
[[ -n "${COMFY_PID:-}" ]] && PIDS_TO_WAIT+=("${COMFY_PID}")
[[ -n "${API_PID:-}" ]] && PIDS_TO_WAIT+=("${API_PID}")

if [[ ${#PIDS_TO_WAIT[@]} -gt 0 ]]; then
  wait -n "${PIDS_TO_WAIT[@]}"
  log "A primary process exited; shutting down..."
  cleanup
else
  log "No services are running; exiting."
fi