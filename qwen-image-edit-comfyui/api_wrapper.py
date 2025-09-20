#!/usr/bin/env python3
"""
FastAPI wrapper for ComfyUI Qwen Image Edit workflow
Provides a simple REST API to edit images using text prompts
"""

import json
import os
import uuid
import asyncio
import time
from pathlib import Path
from typing import Optional
import urllib.request
import shutil

import requests
import websocket
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# Configuration
COMFYUI_URL = "http://localhost:8188"
WORKFLOW_PATH = "/workspace/workflow_api.json"
OUTPUT_DIR = "/workspace/ComfyUI/output"
INPUT_DIR = "/workspace/ComfyUI/input"
API_PORT = 8189

class EditImageRequest(BaseModel):
    image_url: str
    prompt: str
    negative_prompt: Optional[str] = ""
    seed: Optional[int] = None
    steps: Optional[int] = 8
    cfg: Optional[float] = 1.0
    megapixels: Optional[float] = 1.0

class EditImageResponse(BaseModel):
    job_id: str
    status: str
    message: str

app = FastAPI(
    title="Qwen Image Edit API",
    description="REST API wrapper for ComfyUI Qwen Image Edit workflow with Nunchaku optimization",
    version="1.0.0"
)

# Store job status
job_status = {}

def load_workflow():
    """Load the workflow JSON template"""
    try:
        with open(WORKFLOW_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Workflow file not found")

def download_file(url: str, filename: str) -> str:
    """Download file from URL to input directory"""
    input_path = Path(INPUT_DIR)
    input_path.mkdir(exist_ok=True)
    
    file_path = input_path / filename
    
    try:
        with urllib.request.urlopen(url) as response:
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(response, f)
        return filename
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download file from {url}: {str(e)}")

def modify_workflow(workflow, request: EditImageRequest):
    """Modify workflow with user parameters"""
    job_id = str(uuid.uuid4())
    
    # Download image file
    image_filename = f"image_{job_id}.jpg"
    downloaded_image = download_file(request.image_url, image_filename)
    
    # Update image input (node 78 - LoadImage)
    workflow["78"]["inputs"]["image"] = downloaded_image
    
    # Update text prompts (nodes 76 and 77 - TextEncodeQwenImageEdit)
    workflow["76"]["inputs"]["prompt"] = request.prompt
    workflow["77"]["inputs"]["prompt"] = request.negative_prompt
    
    # Update sampling parameters (node 3 - KSampler)
    if request.seed is not None:
        workflow["3"]["inputs"]["seed"] = request.seed
    else:
        # Generate random seed if not provided
        workflow["3"]["inputs"]["seed"] = int(time.time() * 1000000) % 2147483647
    
    workflow["3"]["inputs"]["steps"] = request.steps
    workflow["3"]["inputs"]["cfg"] = request.cfg
    
    # Update image scaling (node 93 - ImageScaleToTotalPixels)
    workflow["93"]["inputs"]["megapixels"] = request.megapixels
    
    # Update filename prefix for output (node 60 - SaveImage)
    workflow["60"]["inputs"]["filename_prefix"] = f"QwenEdit/api_{job_id}"
    
    return workflow, job_id

def queue_workflow(workflow, client_id: str):
    """Queue workflow in ComfyUI with the provided client_id"""
    try:
        payload = {"prompt": workflow, "client_id": client_id}
        response = requests.post(f"{COMFYUI_URL}/prompt", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue workflow: {str(e)}")

def wait_for_completion(prompt_id: str, job_id: str):
    """Wait for workflow completion using WebSocket.
    ComfyUI sends both JSON text frames and binary frames (e.g. previews). We must
    ignore non-text frames to avoid JSON decode errors.
    """
    try:
        ws_url = f"ws://localhost:8188/ws?clientId={job_id}"
        ws = websocket.create_connection(ws_url)

        job_status[job_id] = {"status": "processing", "progress": 0}

        while True:
            # Use low-level frame API to detect text vs binary frames
            frame = ws.recv_frame()
            if frame is None:
                continue

            if frame.opcode == websocket.ABNF.OPCODE_TEXT:
                try:
                    data = json.loads(frame.data)
                except Exception as e:
                    # Skip malformed text frames
                    continue

                msg_type = data.get("type")

                if msg_type == "progress":
                    try:
                        val = float(data["data"]["value"]) or 0.0
                        mx = float(data["data"]["max"]) or 1.0
                        progress = max(0.0, min(100.0, (val / mx) * 100.0))
                        job_status[job_id]["progress"] = progress
                    except Exception:
                        pass

                elif msg_type == "executed":
                    d = data.get("data", {})
                    if d.get("prompt_id") == prompt_id:
                        # Final node is SaveImage (id "60") in this workflow
                        if d.get("node") == "60":
                            job_status[job_id] = {"status": "completed", "progress": 100}
                            break

                elif msg_type == "execution_error":
                    d = data.get("data", {})
                    job_status[job_id] = {
                        "status": "error",
                        "error": d.get("exception_message", "Unknown execution error")
                    }
                    break

            elif frame.opcode in (websocket.ABNF.OPCODE_BINARY, websocket.ABNF.OPCODE_CONT):
                # Binary frames are previews or other data. Ignore.
                continue
            elif frame.opcode in (websocket.ABNF.OPCODE_CLOSE, websocket.ABNF.OPCODE_PING, websocket.ABNF.OPCODE_PONG):
                # Handle control frames gracefully
                if frame.opcode == websocket.ABNF.OPCODE_CLOSE:
                    break
                continue

        try:
            ws.close()
        except Exception:
            pass

    except Exception as e:
        job_status[job_id] = {"status": "error", "error": str(e)}

def find_output_image(job_id: str) -> Optional[str]:
    """Find the generated image file"""
    output_path = Path(OUTPUT_DIR)
    
    # The filename pattern is set in the workflow as "QwenEdit/api_{job_id}"
    # ComfyUI typically saves to subdirectories based on the prefix
    qwenedit_dir = output_path / "QwenEdit"
    
    # Look for image files with the job ID in both root and QwenEdit subdirectory
    search_paths = [output_path, qwenedit_dir]
    pattern = f"api_{job_id}"
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
            
        # Look for image files with the job ID
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
            # Try exact pattern match first
            for file_path in search_path.glob(f"*{pattern}*{ext}"):
                return str(file_path)
            
            # Also try without the "api_" prefix in case ComfyUI strips it
            for file_path in search_path.glob(f"*{job_id}*{ext}"):
                return str(file_path)
    
    return None

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Qwen Image Edit API", "status": "running"}

@app.post("/edit-image", response_model=EditImageResponse)
async def edit_image(request: EditImageRequest, background_tasks: BackgroundTasks):
    """Edit image using text prompt"""
    
    # Validate inputs
    if not request.image_url or not request.prompt:
        raise HTTPException(status_code=400, detail="Both image_url and prompt are required")
    
    # Load and modify workflow
    workflow = load_workflow()
    modified_workflow, job_id = modify_workflow(workflow, request)
    
    # Queue workflow with client_id matching websocket listener (job_id)
    queue_response = queue_workflow(modified_workflow, job_id)
    prompt_id = queue_response["prompt_id"]
    
    # Initialize job status
    job_status[job_id] = {"status": "queued", "prompt_id": prompt_id, "progress": 0}
    
    # Start background task to monitor completion
    background_tasks.add_task(wait_for_completion, prompt_id, job_id)
    
    return EditImageResponse(
        job_id=job_id,
        status="queued",
        message="Image editing started"
    )

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = job_status[job_id].copy()
    
    # If completed, try to find the output file
    if status["status"] == "completed":
        image_path = find_output_image(job_id)
        if image_path and os.path.exists(image_path):
            status["image_ready"] = True
            status["download_url"] = f"/download/{job_id}"
            status["image_path"] = image_path
        else:
            status["image_ready"] = False
            status["message"] = "Image editing completed but file not found"
            # Give it a moment and try again - sometimes there's a delay
            await asyncio.sleep(1)
            image_path = find_output_image(job_id)
            if image_path and os.path.exists(image_path):
                status["image_ready"] = True
                status["download_url"] = f"/download/{job_id}"
                status["image_path"] = image_path
                status["message"] = "Image found after retry"
    
    return status

@app.get("/download/{job_id}")
async def download_image(job_id: str):
    """Download edited image"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = job_status[job_id]["status"]
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"Image not ready. Current status: {status}")
    
    image_path = find_output_image(job_id)
    if not image_path:
        raise HTTPException(status_code=404, detail="Image file not found in output directory")
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Image file not found at path: {image_path}")
    
    # Determine the actual file extension
    file_ext = Path(image_path).suffix or ".png"
    filename = f"edited_image_{job_id}{file_ext}"
    
    # Determine media type based on extension
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp"
    }
    media_type = media_type_map.get(file_ext.lower(), "image/png")
    
    return FileResponse(
        image_path,
        media_type=media_type,
        filename=filename
    )

@app.get("/jobs")
async def list_jobs():
    """List all jobs"""
    return {"jobs": job_status}

@app.get("/debug/files")
async def debug_files():
    """Debug endpoint to list output directory contents"""
    output_path = Path(OUTPUT_DIR)
    files = []
    
    if output_path.exists():
        # List files in root output directory
        for item in output_path.iterdir():
            if item.is_file():
                files.append({"path": str(item), "name": item.name, "location": "root"})
            elif item.is_dir():
                # List files in subdirectories
                for subitem in item.rglob("*"):
                    if subitem.is_file():
                        files.append({
                            "path": str(subitem), 
                            "name": subitem.name, 
                            "location": str(subitem.parent.relative_to(output_path))
                        })
    
    return {"output_dir": str(output_path), "files": files}

@app.get("/debug/job/{job_id}")
async def debug_job(job_id: str):
    """Debug endpoint for specific job"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = job_status[job_id].copy()
    
    # Try to find the image file
    image_path = find_output_image(job_id)
    status["searched_image_path"] = image_path
    status["image_exists"] = image_path and os.path.exists(image_path) if image_path else False
    
    # List all files that might match
    output_path = Path(OUTPUT_DIR)
    potential_files = []
    
    if output_path.exists():
        for item in output_path.rglob("*"):
            if item.is_file() and job_id in item.name:
                potential_files.append(str(item))
    
    status["potential_files"] = potential_files
    
    return status

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete job and cleanup files"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Remove from status
    del job_status[job_id]
    
    # Try to cleanup output file
    image_path = find_output_image(job_id)
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass  # File might be in use
    
    return {"message": "Job deleted"}

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    # Start the API server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="info"
    )