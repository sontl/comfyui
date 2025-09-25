#!/usr/bin/env python3
"""
Test script for WAN 2.2-14B LoRAs Image-to-Video API
"""

import requests
import time
import json
import sys
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8189"
TEST_IMAGE_URL = "https://images.unsplash.com/photo-1494790108755-2616b612b786?w=640&h=640&fit=crop&crop=face"

def test_health_check():
    """Test the health check endpoint"""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        response.raise_for_status()
        print(f"✅ Health check passed: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_generate_video():
    """Test video generation from image"""
    print("🎬 Testing video generation...")
    
    # Test request payload
    payload = {
        "image_url": TEST_IMAGE_URL,
        "prompt": "person smiling and looking happy, gentle head movement",
        "negative_prompt": "static, blurry, low quality, distorted face",
        "steps": 4,  # Reduced for faster testing
        "cfg_high_noise": 3.5,
        "cfg_low_noise": 3.5,
        "width": 512,  # Smaller for faster processing
        "height": 512,
        "frames": 49,  # Shorter video for testing
        "fps": 16,
        "seed": 42
    }
    
    try:
        # Submit generation request
        print(f"📤 Submitting request with payload:")
        print(json.dumps(payload, indent=2))
        
        response = requests.post(f"{API_BASE_URL}/generate", json=payload)
        response.raise_for_status()
        
        result = response.json()
        job_id = result["job_id"]
        print(f"✅ Generation started with job ID: {job_id}")
        
        # Monitor progress
        print("⏳ Monitoring progress...")
        max_wait_time = 300  # 5 minutes max
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_response = requests.get(f"{API_BASE_URL}/status/{job_id}")
            status_response.raise_for_status()
            status = status_response.json()
            
            print(f"📊 Status: {status['status']}, Progress: {status.get('progress', 0):.1f}%")
            
            if status["status"] == "completed":
                if status.get("video_ready"):
                    print(f"🎉 Video generation completed!")
                    print(f"📥 Download URL: {API_BASE_URL}{status['download_url']}")
                    
                    # Download the video
                    download_response = requests.get(f"{API_BASE_URL}{status['download_url']}")
                    download_response.raise_for_status()
                    
                    # Save to file
                    output_file = f"test_output_{job_id}.mp4"
                    with open(output_file, "wb") as f:
                        f.write(download_response.content)
                    
                    file_size = len(download_response.content)
                    print(f"💾 Video saved as {output_file} ({file_size:,} bytes)")
                    return True
                else:
                    print("⚠️ Generation completed but video file not ready")
                    return False
                    
            elif status["status"] == "error":
                print(f"❌ Generation failed: {status.get('error', 'Unknown error')}")
                return False
            
            time.sleep(5)  # Check every 5 seconds
        
        print("⏰ Timeout waiting for video generation")
        return False
        
    except Exception as e:
        print(f"❌ Video generation test failed: {e}")
        return False

def test_debug_endpoints():
    """Test debug endpoints"""
    print("🔧 Testing debug endpoints...")
    
    try:
        # Test file listing
        response = requests.get(f"{API_BASE_URL}/debug/files")
        response.raise_for_status()
        files_info = response.json()
        print(f"📁 Output directory: {files_info['output_dir']}")
        print(f"📄 Found {len(files_info['files'])} files")
        
        # Test job listing
        response = requests.get(f"{API_BASE_URL}/jobs")
        response.raise_for_status()
        jobs_info = response.json()
        print(f"💼 Active jobs: {len(jobs_info['jobs'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug endpoints test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting WAN 2.2-14B LoRAs API Tests")
    print("=" * 50)
    
    # Check if API is running
    if not test_health_check():
        print("💥 API is not running. Please start the service first.")
        sys.exit(1)
    
    print()
    
    # Test debug endpoints
    test_debug_endpoints()
    print()
    
    # Test video generation
    success = test_generate_video()
    print()
    
    if success:
        print("🎉 All tests passed!")
        print("✨ The WAN 2.2-14B LoRAs API is working correctly!")
    else:
        print("💥 Some tests failed. Check the logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()