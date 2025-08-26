
#!/usr/bin/env bash
set -euo pipefail

VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch"}

echo "[services] Starting Tailscale..."
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
  echo "[services] Tailscale started successfully."
else
  echo "[services] Tailscale 'up' command failed or already up. Continuing..."
fi

echo "[services] Setting up ComfyUI..."
source "${VENV_COMFY}/bin/activate"

export TORCH_INDUCTOR_FORCE_DISABLE_FP8="1"
echo "[services] Forcing TORCH_INDUCTOR_FORCE_DISABLE_FP8=${TORCH_INDUCTOR_FORCE_DISABLE_FP8}"

COMFY_PID=""

install_node_deps() {
  local NODES_DIR_PATH="$1"
  local ACTION_DESCRIPTION="$2"

  if [ -d "${NODES_DIR_PATH}" ]; then
    echo "[services] Checking custom node dependencies in ${NODES_DIR_PATH} (${ACTION_DESCRIPTION})..."
    while IFS= read -r -d '' NODE_DIR; do
      if [ -f "${NODE_DIR}/requirements.txt" ]; then
        NODE_NAME=$(basename "${NODE_DIR}")
        echo "[services] Installing deps for node: ${NODE_NAME}"
        ( cd "${NODE_DIR}" && "${VENV_COMFY}/bin/pip" install -r requirements.txt ) || \
          echo "[services] Warning: pip install failed for ${NODE_NAME}"
      fi
    done < <(find "${NODES_DIR_PATH}" -mindepth 1 -maxdepth 1 -type d -print0)
  else
    echo "[services] Custom nodes dir not found at ${NODES_DIR_PATH}."
  fi
}

if [ -f "${COMFY_DIR}/main.py" ]; then
  echo "[services] Found existing ComfyUI in ${COMFY_DIR}."
  cd "${COMFY_DIR}"

  if [ -f "requirements.txt" ]; then
    echo "[services] Ensuring ComfyUI requirements are present..."
    "${VENV_COMFY}/bin/pip" install --no-cache-dir -r requirements.txt || \
      echo "[services] Warning: ComfyUI requirements install failed."
  fi

  install_node_deps "${COMFY_DIR}/custom_nodes" "Existing"

  echo "[services] Launching ComfyUI: ${COMFY_LAUNCH_ARGS}"
  TORCH_INDUCTOR_FORCE_DISABLE_FP8="1" python main.py ${COMFY_LAUNCH_ARGS} &
  COMFY_PID=$!
  echo "[services] ComfyUI PID: ${COMFY_PID}"
else
  echo "[services] ComfyUI not found; cloning into ${COMFY_DIR}..."
  mkdir -p "$(dirname "${COMFY_DIR}")"
  if git clone https://github.com/comfyanonymous/ComfyUI.git "${COMFY_DIR}"; then
    echo "[services] Clone complete."
    cd "${COMFY_DIR}"
    if [ -f "requirements.txt" ]; then
      echo "[services] Installing ComfyUI requirements..."
      "${VENV_COMFY}/bin/pip" install --no-cache-dir -r requirements.txt || \
        echo "[services] Warning: ComfyUI requirements install failed."
    fi

    install_node_deps "${COMFY_DIR}/custom_nodes" "New clone"

    echo "[services] Launching ComfyUI: ${COMFY_LAUNCH_ARGS}"
    python main.py ${COMFY_LAUNCH_ARGS} &
    COMFY_PID=$!
    echo "[services] ComfyUI PID: ${COMFY_PID}"
  else
    echo "[services] Failed to clone ComfyUI. Please place it at ${COMFY_DIR}."
  fi
fi

deactivate
echo "[services] ComfyUI setup complete."

JUPYTER_PID=""
if [[ "${ENABLE_JUPYTER:-false}" == "true" ]]; then
  echo "[services] Starting JupyterLab..."
  source "${VENV_COMFY}/bin/activate"
  if ! command -v jupyter-lab &> /dev/null; then
      echo "[services] Warning: ENABLE_JUPYTER is true, but jupyterlab is not installed."
      echo "[services] Please rebuild your container with '--build-arg WITH_JUPYTER=true'"
  else
      JUPYTER_TOKEN='runpod'
      echo "[services] JupyterLab available at: /jupyter/?token=${JUPYTER_TOKEN}"
      jupyter-lab --ip=127.0.0.1 --port=8888 --no-browser \
                  --ServerApp.base_url=/jupyter \
                  --ServerApp.token="${JUPYTER_TOKEN}" --ServerApp.password='' \
                  --notebook-dir=/workspace --allow-root &
      JUPYTER_PID=$!
      echo "[services] JupyterLab PID: ${JUPYTER_PID}"
  fi
  deactivate
else
  echo "[services] JupyterLab disabled."
fi

echo "[services] Starting Caddy..."
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!
echo "[services] Caddy PID: ${CADDY_PID}"

PIDS_TO_KILL=()
[[ -n "${TAILSCALED_PID}" ]] && PIDS_TO_KILL+=("${TAILSCALED_PID}")
[[ -n "${COMFY_PID}"     ]] && PIDS_TO_KILL+=("${COMFY_PID}")
[[ -n "${JUPYTER_PID}"   ]] && PIDS_TO_KILL+=("${JUPYTER_PID}")
[[ -n "${CADDY_PID}"     ]] && PIDS_TO_KILL+=("${CADDY_PID}")

PIDS_TO_WAIT=()
[[ -n "${COMFY_PID}"   ]] && PIDS_TO_WAIT+=("${COMFY_PID}")
[[ -n "${JUPYTER_PID}" ]] && PIDS_TO_WAIT+=("${JUPYTER_PID}")
if [[ ${#PIDS_TO_WAIT[@]} -eq 0 && -n "${CADDY_PID}" ]]; then
  PIDS_TO_WAIT+=("${CADDY_PID}")
fi

cleanup() {
  echo "[services] Terminating services..."
  if [[ ${#PIDS_TO_KILL[@]} -gt 0 ]]; then
    kill -SIGTERM "${PIDS_TO_KILL[@]}" 2>/dev/null || true
    sleep 5
    for pid in "${PIDS_TO_KILL[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        echo "[services] PID $pid still alive; sending SIGKILL."
        kill -SIGKILL "$pid" 2>/dev/null || true
      fi
    done
  fi
  if [[ -n "${TAILSCALED_PID}" ]] && kill -0 "${TAILSCALED_PID}" 2>/dev/null; then
    tailscale --socket="${TS_SOCKET_FILE}" logout || true
  fi
  echo "[services] Shutdown complete."
  exit 0
}

trap cleanup SIGTERM SIGINT

echo "[services] Startup complete. Waiting on: ${PIDS_TO_WAIT[*]:-none}"
if [[ ${#PIDS_TO_WAIT[@]} -gt 0 ]]; then
  wait -n "${PIDS_TO_WAIT[@]}"
  echo "[services] A primary process exited; shutting down..."
  cleanup
else
  if [[ -n "${CADDY_PID}" && -n "${TAILSCALED_PID}" ]]; then
    wait "${CADDY_PID}" "${TAILSCALED_PID}"
  elif [[ -n "${CADDY_PID}" ]]; then
    wait "${CADDY_PID}"
  elif [[ -n "${TAILSCALED_PID}" ]]; then
    wait "${TAILSCALED_PID}"
  else
    echo "[services] No services are running; exiting."
  fi
fi