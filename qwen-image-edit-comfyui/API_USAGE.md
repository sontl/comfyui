# Qwen Image Edit Plus API Documentation

## Overview

The Qwen Image Edit Plus API provides advanced image editing capabilities using AI models with support for multi-image compositions. You can edit images using natural language prompts and combine elements from up to 3 source images.

## Base URL

```
http://localhost:8189
```

## Authentication

No authentication required for local deployment.

## Endpoints

### Health Check

**GET** `/`

Returns API status and version information.

**Response:**
```json
{
  "message": "Qwen Image Edit Plus API",
  "status": "running",
  "version": "2.0.0",
  "features": ["multi-image-support", "nunchaku-optimization"]
}
```

### Edit Image

**POST** `/edit-image`

Submit an image editing job with support for up to 3 input images.

**Request Body:**
```json
{
  "image1_url": "https://example.com/image1.jpg",
  "image2_url": "https://example.com/image2.jpg",
  "image3_url": "https://example.com/image3.jpg",
  "prompt": "Combine elements from all images",
  "negative_prompt": "blurry, low quality",
  "seed": 12345,
  "steps": 40,
  "cfg": 4.0,
  "megapixels": 1.0
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image1_url` | string | ✅ Yes | - | URL to primary input image |
| `image2_url` | string | ❌ No | null | URL to secondary input image |
| `image3_url` | string | ❌ No | null | URL to tertiary input image |
| `prompt` | string | ✅ Yes | - | Text description of desired edits |
| `negative_prompt` | string | ❌ No | "" | What to avoid in the output |
| `seed` | integer | ❌ No | random | Random seed for reproducibility |
| `steps` | integer | ❌ No | 40 | Number of diffusion steps (1-100) |
| `cfg` | float | ❌ No | 4.0 | Classifier-free guidance scale (1.0-20.0) |
| `megapixels` | float | ❌ No | 1.0 | Target output size in megapixels |

**Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "message": "Image editing started"
}
```

### Get Job Status

**GET** `/status/{job_id}`

Check the status of a submitted job.

**Response:**
```json
{
  "status": "processing",
  "progress": 45.2,
  "prompt_id": "xyz789"
}
```

**Status Values:**
- `queued`: Job is waiting to start
- `processing`: Image is being generated
- `completed`: Image is ready for download
- `error`: Generation failed

**Completed Response:**
```json
{
  "status": "completed",
  "progress": 100,
  "image_ready": true,
  "download_url": "/download/abc123-def456-ghi789",
  "image_path": "/workspace/ComfyUI/output/QwenEdit/api_abc123-def456-ghi789_00001_.png"
}
```

### Download Image

**GET** `/download/{job_id}`

Download the generated image.

**Response:** Binary image data (PNG/JPG/WebP)

### List Jobs

**GET** `/jobs`

List all active jobs and their status.

**Response:**
```json
{
  "jobs": {
    "job_id_1": {
      "status": "completed",
      "progress": 100
    },
    "job_id_2": {
      "status": "processing", 
      "progress": 23.5
    }
  }
}
```

### Delete Job

**DELETE** `/jobs/{job_id}`

Delete a job and cleanup associated files.

**Response:**
```json
{
  "message": "Job deleted"
}
```

## Usage Examples

### Single Image Edit

```bash
curl -X POST "http://localhost:8189/edit-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image1_url": "https://example.com/portrait.jpg",
    "prompt": "Change the background to a forest scene",
    "negative_prompt": "blurry, artifacts",
    "steps": 30,
    "cfg": 3.5
  }'
```

### Multi-Image Composition

```bash
curl -X POST "http://localhost:8189/edit-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image1_url": "https://example.com/person.jpg",
    "image2_url": "https://example.com/dog.jpg",
    "image3_url": "https://example.com/living_room.jpg",
    "prompt": "Place the person from image 1 sitting in the living room from image 3, with the dog from image 2 lying on the floor nearby",
    "negative_prompt": "blurry, distorted, unnatural",
    "steps": 40,
    "cfg": 4.0,
    "megapixels": 1.5
  }'
```

### Check Status and Download

```bash
# Check status
curl "http://localhost:8189/status/abc123-def456-ghi789"

# Download when ready
curl "http://localhost:8189/download/abc123-def456-ghi789" -o edited_image.png
```

## Multi-Image Prompting Guide

### Referencing Images

When using multiple images, reference them explicitly in your prompt:

- ✅ "the person in image 1"
- ✅ "the background from image 2"
- ✅ "combine the foreground of image 1 with image 3"
- ❌ "the person" (ambiguous)

### Composition Examples

**Portrait + Background:**
```json
{
  "image1_url": "portrait.jpg",
  "image2_url": "landscape.jpg", 
  "prompt": "Place the person from image 1 in the landscape from image 2"
}
```

**Object Insertion:**
```json
{
  "image1_url": "room.jpg",
  "image2_url": "furniture.jpg",
  "prompt": "Add the furniture from image 2 to the room in image 1"
}
```

**Style Transfer:**
```json
{
  "image1_url": "photo.jpg",
  "image2_url": "artwork.jpg",
  "prompt": "Apply the artistic style from image 2 to the photo in image 1"
}
```

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "detail": "Both image1_url and prompt are required"
}
```

**404 Not Found:**
```json
{
  "detail": "Job not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Failed to download file from URL: Connection timeout"
}
```

### Troubleshooting

1. **Image Download Fails:**
   - Ensure URLs are publicly accessible
   - Check image format (JPG/PNG/WebP supported)
   - Verify image size (recommended < 10MB)

2. **Generation Fails:**
   - Try reducing steps or cfg values
   - Simplify the prompt
   - Check if images are compatible

3. **Slow Processing:**
   - Reduce megapixels parameter
   - Lower step count for faster results
   - Check GPU memory usage

## Rate Limits

No rate limits for local deployment. For production use, implement appropriate rate limiting based on your infrastructure.

## Debug Endpoints

### List Output Files

**GET** `/debug/files`

List all files in the output directory.

### Debug Job

**GET** `/debug/job/{job_id}`

Get detailed debug information for a specific job.

## Python SDK Example

```python
import requests
import time

class QwenImageEditClient:
    def __init__(self, base_url="http://localhost:8189"):
        self.base_url = base_url
    
    def edit_image(self, image1_url, prompt, **kwargs):
        """Submit image editing job"""
        data = {
            "image1_url": image1_url,
            "prompt": prompt,
            **kwargs
        }
        
        response = requests.post(f"{self.base_url}/edit-image", json=data)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, job_id, timeout=300):
        """Wait for job completion and return result"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_status(job_id)
            
            if status["status"] == "completed":
                return status
            elif status["status"] == "error":
                raise Exception(f"Job failed: {status.get('error')}")
            
            time.sleep(5)
        
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
    
    def get_status(self, job_id):
        """Get job status"""
        response = requests.get(f"{self.base_url}/status/{job_id}")
        response.raise_for_status()
        return response.json()
    
    def download_image(self, job_id, filename):
        """Download generated image"""
        response = requests.get(f"{self.base_url}/download/{job_id}")
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)

# Usage example
client = QwenImageEditClient()

# Submit job
result = client.edit_image(
    image1_url="https://example.com/image.jpg",
    prompt="Add a sunset background",
    steps=30
)

# Wait for completion
status = client.wait_for_completion(result["job_id"])

# Download result
if status["image_ready"]:
    client.download_image(result["job_id"], "edited_image.png")
```