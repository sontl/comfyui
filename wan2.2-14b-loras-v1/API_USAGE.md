# WAN 2.2-14B LoRAs Image-to-Video API Usage

This document provides comprehensive usage examples for the WAN 2.2-14B LoRAs Image-to-Video API.

## Overview

The API converts static images into animated videos using advanced diffusion models with LoRA fine-tuning. It accepts an image URL and text prompt to generate smooth, realistic animations.

## Base URL

```
http://localhost:8189  # Local development
http://your-instance-ip:8189  # Deployed instance
```

## Authentication

No authentication required for this API.

## Endpoints

### 1. Health Check

**GET** `/`

Check if the API service is running.

```bash
curl http://localhost:8189/
```

**Response:**
```json
{
  "message": "WAN 2.2-14B LoRAs Image-to-Video API",
  "status": "running"
}
```

### 2. Generate Video

**POST** `/generate`

Generate a video from an input image and text prompt.

**Request Body:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "prompt": "person smiling and waving",
  "negative_prompt": "static, blurry, low quality",
  "steps": 6,
  "cfg_high_noise": 3.5,
  "cfg_low_noise": 3.5,
  "width": 640,
  "height": 640,
  "frames": 81,
  "fps": 16,
  "seed": 1
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_url` | string (URL) | ✅ | - | URL of the input image to animate |
| `prompt` | string | ✅ | - | Text description of desired animation |
| `negative_prompt` | string | ❌ | Default provided | What to avoid in animation |
| `steps` | integer | ❌ | 6 | Diffusion steps (1-20, higher=better quality) |
| `cfg_high_noise` | float | ❌ | 3.5 | CFG scale for high noise model (1.0-10.0) |
| `cfg_low_noise` | float | ❌ | 3.5 | CFG scale for low noise model (1.0-10.0) |
| `width` | integer | ❌ | 640 | Output width (256-1024, divisible by 32) |
| `height` | integer | ❌ | 640 | Output height (256-1024, divisible by 32) |
| `frames` | integer | ❌ | 81 | Number of frames (16-121) |
| `fps` | integer | ❌ | 16 | Frames per second (8-30) |
| `seed` | integer | ❌ | 1 | Random seed for reproducibility |

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Image-to-video generation started"
}
```

### 3. Check Status

**GET** `/status/{job_id}`

Check the status of a video generation job.

```bash
curl http://localhost:8189/status/550e8400-e29b-41d4-a716-446655440000
```

**Response (Processing):**
```json
{
  "status": "processing",
  "progress": 45.2,
  "input_image": "550e8400-e29b-41d4-a716-446655440000_input.jpg"
}
```

**Response (Completed):**
```json
{
  "status": "completed",
  "progress": 100,
  "video_ready": true,
  "download_url": "/download/550e8400-e29b-41d4-a716-446655440000",
  "video_path": "/workspace/ComfyUI/output/wan22_t2v/wan22_t2v_550e8400-e29b-41d4-a716-446655440000_00001.mp4"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "error": "Failed to process image: Invalid image format"
}
```

### 4. Download Video

**GET** `/download/{job_id}`

Download the generated video file.

```bash
curl http://localhost:8189/download/550e8400-e29b-41d4-a716-446655440000 -o video.mp4
```

**Response:** Binary video file (MP4 format)

### 5. List Jobs

**GET** `/jobs`

List all active jobs and their status.

```bash
curl http://localhost:8189/jobs
```

**Response:**
```json
{
  "jobs": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "status": "completed",
      "progress": 100,
      "input_image": "550e8400-e29b-41d4-a716-446655440000_input.jpg"
    }
  }
}
```

### 6. Delete Job

**DELETE** `/jobs/{job_id}`

Delete a job and clean up associated files.

```bash
curl -X DELETE http://localhost:8189/jobs/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "message": "Job deleted"
}
```

## Usage Examples

### Basic Example

```bash
# 1. Generate video
curl -X POST "http://localhost:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://images.unsplash.com/photo-1494790108755-2616b612b786?w=640",
    "prompt": "person smiling and nodding"
  }'

# Response: {"job_id": "abc123...", "status": "queued", "message": "..."}

# 2. Check status (repeat until completed)
curl "http://localhost:8189/status/abc123..."

# 3. Download video when ready
curl "http://localhost:8189/download/abc123..." -o result.mp4
```

### Advanced Example with Custom Parameters

```bash
curl -X POST "http://localhost:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/portrait.jpg",
    "prompt": "elegant woman turning head slowly with gentle smile",
    "negative_prompt": "fast motion, jerky movement, blurry, distorted",
    "steps": 8,
    "cfg_high_noise": 4.0,
    "cfg_low_noise": 3.0,
    "width": 768,
    "height": 768,
    "frames": 121,
    "fps": 24,
    "seed": 42
  }'
```

### Python Example

```python
import requests
import time

# Generate video
response = requests.post("http://localhost:8189/generate", json={
    "image_url": "https://example.com/image.jpg",
    "prompt": "person waving hello",
    "steps": 6,
    "frames": 81
})

job_id = response.json()["job_id"]
print(f"Job started: {job_id}")

# Wait for completion
while True:
    status = requests.get(f"http://localhost:8189/status/{job_id}").json()
    print(f"Status: {status['status']}, Progress: {status.get('progress', 0):.1f}%")
    
    if status["status"] == "completed":
        # Download video
        video_data = requests.get(f"http://localhost:8189/download/{job_id}")
        with open("output.mp4", "wb") as f:
            f.write(video_data.content)
        print("Video saved as output.mp4")
        break
    elif status["status"] == "error":
        print(f"Error: {status['error']}")
        break
    
    time.sleep(5)
```

### JavaScript Example

```javascript
async function generateVideo(imageUrl, prompt) {
  // Start generation
  const response = await fetch('http://localhost:8189/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_url: imageUrl,
      prompt: prompt,
      steps: 6,
      frames: 81
    })
  });
  
  const { job_id } = await response.json();
  console.log(`Job started: ${job_id}`);
  
  // Poll for completion
  while (true) {
    const statusResponse = await fetch(`http://localhost:8189/status/${job_id}`);
    const status = await statusResponse.json();
    
    console.log(`Status: ${status.status}, Progress: ${status.progress || 0}%`);
    
    if (status.status === 'completed') {
      // Download video
      const videoResponse = await fetch(`http://localhost:8189/download/${job_id}`);
      const videoBlob = await videoResponse.blob();
      
      // Create download link
      const url = URL.createObjectURL(videoBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'generated_video.mp4';
      a.click();
      
      break;
    } else if (status.status === 'error') {
      console.error(`Error: ${status.error}`);
      break;
    }
    
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}

// Usage
generateVideo('https://example.com/image.jpg', 'person smiling and waving');
```

## Image Requirements

### Supported Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- GIF (.gif) - first frame used

### Recommended Specifications
- **Resolution**: 512x512 to 1024x1024 pixels
- **Aspect Ratio**: Square (1:1) works best
- **File Size**: Under 10MB
- **Content**: Clear, well-lit portraits or objects
- **Quality**: High resolution, minimal compression artifacts

### Best Practices
- Use images with clear subjects
- Avoid heavily compressed or low-quality images
- Ensure good lighting and contrast
- Center the main subject in the frame

## Prompt Guidelines

### Effective Prompts
- **Specific actions**: "person nodding slowly", "gentle smile appearing"
- **Movement descriptions**: "turning head left", "eyes blinking naturally"
- **Emotional expressions**: "happy expression", "surprised look"
- **Camera movements**: "slight zoom in", "gentle pan"

### Avoid
- Overly complex scenes
- Multiple conflicting actions
- Abstract concepts
- Very fast or dramatic movements

### Example Prompts
```
Good prompts:
- "person smiling and looking at camera"
- "gentle head turn to the right with soft expression"
- "woman laughing naturally with eyes closing slightly"
- "man nodding in agreement with confident smile"

Avoid:
- "person doing backflips while juggling fire"
- "abstract art transformation"
- "rapid scene changes"
```

## Performance Tips

### Optimization Settings
- **Fast generation**: `steps=4, frames=49`
- **Balanced quality**: `steps=6, frames=81` (default)
- **High quality**: `steps=8, frames=121`

### Memory Management
- Smaller resolutions (512x512) use less GPU memory
- Fewer frames reduce processing time
- Lower CFG values (2.0-3.0) are faster

### Expected Processing Times
| Configuration | RTX 4090 | RTX 3080 |
|---------------|----------|----------|
| Fast (4 steps, 49 frames) | ~30 seconds | ~60 seconds |
| Default (6 steps, 81 frames) | ~60 seconds | ~120 seconds |
| High Quality (8 steps, 121 frames) | ~120 seconds | ~240 seconds |

## Error Handling

### Common Errors

**400 Bad Request**
```json
{
  "detail": "Failed to download image: HTTP 404 Not Found"
}
```
- Check image URL is accessible
- Verify image format is supported

**404 Not Found**
```json
{
  "detail": "Job not found"
}
```
- Verify job ID is correct
- Job may have been deleted or expired

**500 Internal Server Error**
```json
{
  "detail": "Failed to queue workflow: Connection refused"
}
```
- ComfyUI service may be down
- Check service logs

### Troubleshooting

1. **Image download fails**
   - Ensure URL is publicly accessible
   - Check image format and size
   - Try a different image URL

2. **Generation takes too long**
   - Reduce steps, frames, or resolution
   - Check GPU memory usage
   - Monitor system resources

3. **Poor quality results**
   - Increase steps (6-8)
   - Adjust CFG values (3.0-5.0)
   - Use higher resolution input images
   - Improve prompt specificity

## Rate Limits

- No built-in rate limiting
- Concurrent jobs limited by GPU memory
- Recommended: 1-2 concurrent jobs per RTX 4090

## Debug Endpoints

### List Output Files
```bash
curl http://localhost:8189/debug/files
```

### Debug Specific Job
```bash
curl http://localhost:8189/debug/job/{job_id}
```

These endpoints help troubleshoot file location and job status issues.