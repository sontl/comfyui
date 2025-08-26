# FastWAN 2.2-5B Video Generation API

This API provides a simple REST interface to generate videos using the FastWAN 2.2-5B model through ComfyUI.

## Endpoints

### Health Check
```
GET /
```
Returns API status.

### Generate Video
```
POST /generate
```

**Request Body:**
```json
{
  "prompt": "A boldly colored ladybug moves along a verdant leaf to drink from a water droplet.",
  "negative_prompt": "static, blurry, low quality",
  "seed": 123456,
  "steps": 8,
  "cfg": 1.0,
  "width": 1280,
  "height": 704,
  "length": 121,
  "fps": 24
}
```

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "queued",
  "message": "Video generation started"
}
```

### Check Job Status
```
GET /status/{job_id}
```

**Response:**
```json
{
  "status": "completed",
  "progress": 100,
  "video_ready": true,
  "download_url": "/download/{job_id}"
}
```

### Download Video
```
GET /download/{job_id}
```
Returns the generated video file.

### List All Jobs
```
GET /jobs
```

### Delete Job
```
DELETE /jobs/{job_id}
```

## Usage Examples

### Python Example
```python
import requests
import time

# Generate video
response = requests.post("http://localhost:8189/generate", json={
    "prompt": "A cat playing with a ball of yarn in slow motion",
    "steps": 8,
    "fps": 24
})

job_id = response.json()["job_id"]
print(f"Job started: {job_id}")

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8189/status/{job_id}")
    status = status_response.json()
    
    print(f"Status: {status['status']}, Progress: {status.get('progress', 0)}%")
    
    if status["status"] == "completed":
        if status.get("video_ready"):
            # Download video
            video_response = requests.get(f"http://localhost:8189/download/{job_id}")
            with open(f"video_{job_id}.mp4", "wb") as f:
                f.write(video_response.content)
            print("Video downloaded!")
        break
    elif status["status"] == "error":
        print(f"Error: {status.get('error')}")
        break
    
    time.sleep(5)
```

### cURL Example
```bash
# Generate video
curl -X POST "http://localhost:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains with clouds moving",
    "steps": 8,
    "fps": 24
  }'

# Check status (replace JOB_ID with actual job ID)
curl "http://localhost:8189/status/JOB_ID"

# Download video when ready
curl -o "generated_video.mp4" "http://localhost:8189/download/JOB_ID"
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| prompt | string | required | Text description of the video to generate |
| negative_prompt | string | optional | What to avoid in the generation |
| seed | integer | random | Random seed for reproducible results |
| steps | integer | 8 | Number of denoising steps |
| cfg | float | 1.0 | Classifier-free guidance scale |
| width | integer | 1280 | Video width in pixels |
| height | integer | 704 | Video height in pixels |
| length | integer | 121 | Video length in frames |
| fps | integer | 24 | Frames per second |

## Status Values

- `queued`: Job is waiting to be processed
- `processing`: Video generation in progress
- `completed`: Video generation finished successfully
- `error`: An error occurred during generation

## Notes

- The API runs on port 8189 by default
- Generated videos are saved temporarily and can be downloaded once
- Jobs can be deleted to free up storage space
- The API automatically handles workflow execution and file management
