#!/usr/bin/env python3
"""
FastAPI wrapper for ComfyUI FastWAN 2.2-5B workflow
Provides a simple REST API to generate videos from text prompts
"""

import json
import os
import uuid
import asyncio
import time
from pathlib import Path
from typing import Optional

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
API_PORT = 8189

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    steps: Optional[int] = 8
    cfg: Optional[float] = 1.0
    width: Optional[int] = 1280
    height: Optional[int] = 704
    length: Optional[int] = 121
    fps: Optional[int] = 24

class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str

app = FastAPI(
    title="FastWAN 2.2-5B Video Generation API",
    description="REST API wrapper for ComfyUI FastWAN 2.2-5B workflow",
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

def modify_workflow(workflow, request: GenerateRequest):
    """Modify workflow with user parameters"""
    # Update positive prompt (node 6)
    workflow["6"]["inputs"]["text"] = request.prompt
    
    # Update negative prompt if provided (node 7)
    if request.negative_prompt:
        workflow["7"]["inputs"]["text"] = request.negative_prompt
    
    # Update sampling parameters (node 3)
    if request.seed:
        workflow["3"]["inputs"]["seed"] = request.seed
    if request.steps:
        workflow["3"]["inputs"]["steps"] = request.steps
    if request.cfg:
        workflow["3"]["inputs"]["cfg"] = request.cfg
    
    # Update video dimensions and length (node 55)
    if request.width:
        workflow["55"]["inputs"]["width"] = request.width
    if request.height:
        workflow["55"]["inputs"]["height"] = request.height
    if request.length:
        workflow["55"]["inputs"]["length"] = request.length
    
    # Update FPS (node 57)
    if request.fps:
        workflow["57"]["inputs"]["fps"] = request.fps
    
    # Generate unique filename prefix
    job_id = str(uuid.uuid4())
    workflow["58"]["inputs"]["filename_prefix"] = f"FastWan/api_{job_id}"
    
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
                        # Final node is SaveVideo (id "58") in this workflow
                        if d.get("node") == "58":
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

def find_output_video(job_id: str) -> Optional[str]:
    """Find the generated video file"""
    output_path = Path(OUTPUT_DIR)
    pattern = f"api_{job_id}*"
    
    # Look for video files with the job ID
    for ext in [".mp4", ".avi", ".mov", ".webm"]:
        for file_path in output_path.glob(f"*{pattern}*{ext}"):
            return str(file_path)
    
    return None

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "FastWAN 2.2-5B Video Generation API", "status": "running"}

@app.post("/generate", response_model=GenerateResponse)
async def generate_video(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate video from text prompt"""
    
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
    
    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message="Video generation started"
    )

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = job_status[job_id]
    
    # If completed, try to find the output file
    if status["status"] == "completed":
        video_path = find_output_video(job_id)
        if video_path:
            status["video_ready"] = True
            status["download_url"] = f"/download/{job_id}"
        else:
            status["video_ready"] = False
            status["message"] = "Video generation completed but file not found"
    
    return status

@app.get("/download/{job_id}")
async def download_video(job_id: str):
    """Download generated video"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready")
    
    video_path = find_output_video(job_id)
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    filename = f"generated_video_{job_id}.mp4"
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename
    )

@app.get("/jobs")
async def list_jobs():
    """List all jobs"""
    return {"jobs": job_status}

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete job and cleanup files"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Remove from status
    del job_status[job_id]
    
    # Try to cleanup output file
    video_path = find_output_video(job_id)
    if video_path and os.path.exists(video_path):
        try:
            os.remove(video_path)
        except OSError:
            pass  # File might be in use
    
    return {"message": "Job deleted"}

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Start the API server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="info"
    )
