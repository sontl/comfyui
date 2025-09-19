#!/usr/bin/env python3
"""
FastAPI wrapper for ComfyUI InfiniteTalk workflow
Provides a simple REST API to generate talking videos from image and audio
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
WORKFLOW_PATH = "/workspace/workflow-infinitetalk-api.son.json"
OUTPUT_DIR = "/workspace/ComfyUI/output"
INPUT_DIR = "/workspace/ComfyUI/input"
API_PORT = 8189

class GenerateRequest(BaseModel):
    image_url: str
    audio_url: str
    prompt: Optional[str] = "the woman is singing"
    negative_prompt: Optional[str] = "low quality, worst quality, 色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
    seed: Optional[int] = 3
    steps: Optional[int] = 5
    cfg: Optional[float] = 1.0
    width: Optional[int] = 960
    height: Optional[int] = 528
    max_frames: Optional[int] = 101
    fps: Optional[int] = 20

class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str

app = FastAPI(
    title="InfiniteTalk Video Generation API",
    description="REST API wrapper for ComfyUI InfiniteTalk workflow",
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

def modify_workflow(workflow, request: GenerateRequest):
    """Modify workflow with user parameters"""
    job_id = str(uuid.uuid4())
    
    # Download image and audio files
    image_filename = f"image_{job_id}.jpg"
    audio_filename = f"audio_{job_id}.mp3"
    
    downloaded_image = download_file(request.image_url, image_filename)
    downloaded_audio = download_file(request.audio_url, audio_filename)
    
    # Update image input (node 284 - LoadImage)
    workflow["284"]["inputs"]["image"] = downloaded_image
    
    # Update audio inputs (nodes 125 and 343 - LoadAudio)
    workflow["125"]["inputs"]["audio"] = downloaded_audio
    workflow["343"]["inputs"]["audio"] = downloaded_audio
    
    # Update text prompts (node 241 - WanVideoTextEncodeCached)
    workflow["241"]["inputs"]["positive_prompt"] = request.prompt
    workflow["241"]["inputs"]["negative_prompt"] = request.negative_prompt
    
    # Update sampling parameters (node 128 - WanVideoSampler)
    workflow["128"]["inputs"]["seed"] = request.seed
    workflow["128"]["inputs"]["steps"] = request.steps
    workflow["128"]["inputs"]["cfg"] = request.cfg
    
    # Update dimensions (nodes 339, 340 - INTConstant)
    workflow["339"]["inputs"]["value"] = request.width  # Width
    workflow["340"]["inputs"]["value"] = request.height  # Height
    
    # Update max frames (node 341 - INTConstant)
    workflow["341"]["inputs"]["value"] = request.max_frames
    
    # Update FPS in video combine (node 131 - VHS_VideoCombine)
    workflow["131"]["inputs"]["frame_rate"] = request.fps
    
    # Update filename prefix for output
    workflow["131"]["inputs"]["filename_prefix"] = f"InfiniteTalk/api_{job_id}"
    
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
                        # Final node is VHS_VideoCombine (id "131") in this workflow
                        if d.get("node") == "131":
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
    
    # The filename pattern is set in the workflow as "InfiniteTalk/api_{job_id}"
    # ComfyUI typically saves to subdirectories based on the prefix
    infinitetalk_dir = output_path / "InfiniteTalk"
    
    # Look for video files with the job ID in both root and InfiniteTalk subdirectory
    search_paths = [output_path, infinitetalk_dir]
    pattern = f"api_{job_id}"
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
            
        # Look for video files with the job ID
        for ext in [".mp4", ".avi", ".mov", ".webm", ".mkv"]:
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
    return {"message": "InfiniteTalk Video Generation API", "status": "running"}

@app.post("/generate", response_model=GenerateResponse)
async def generate_video(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate talking video from image and audio"""
    
    # Validate URLs
    if not request.image_url or not request.audio_url:
        raise HTTPException(status_code=400, detail="Both image_url and audio_url are required")
    
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
        message="Talking video generation started"
    )

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = job_status[job_id].copy()
    
    # If completed, try to find the output file
    if status["status"] == "completed":
        video_path = find_output_video(job_id)
        if video_path and os.path.exists(video_path):
            status["video_ready"] = True
            status["download_url"] = f"/download/{job_id}"
            status["video_path"] = video_path
        else:
            status["video_ready"] = False
            status["message"] = "Video generation completed but file not found"
            # Give it a moment and try again - sometimes there's a delay
            await asyncio.sleep(1)
            video_path = find_output_video(job_id)
            if video_path and os.path.exists(video_path):
                status["video_ready"] = True
                status["download_url"] = f"/download/{job_id}"
                status["video_path"] = video_path
                status["message"] = "Video found after retry"
    
    return status

@app.get("/download/{job_id}")
async def download_video(job_id: str):
    """Download generated video"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = job_status[job_id]["status"]
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"Video not ready. Current status: {status}")
    
    video_path = find_output_video(job_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Video file not found in output directory")
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at path: {video_path}")
    
    # Determine the actual file extension
    file_ext = Path(video_path).suffix or ".mp4"
    filename = f"generated_video_{job_id}{file_ext}"
    
    # Determine media type based on extension
    media_type_map = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo", 
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska"
    }
    media_type = media_type_map.get(file_ext.lower(), "video/mp4")
    
    return FileResponse(
        video_path,
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
    
    # Try to find the video file
    video_path = find_output_video(job_id)
    status["searched_video_path"] = video_path
    status["video_exists"] = video_path and os.path.exists(video_path) if video_path else False
    
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
    video_path = find_output_video(job_id)
    if video_path and os.path.exists(video_path):
        try:
            os.remove(video_path)
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