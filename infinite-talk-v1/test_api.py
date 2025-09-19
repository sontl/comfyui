#!/usr/bin/env python3
"""
Test script for InfiniteTalk API
Demonstrates how to generate talking videos from image and audio URLs
"""

import requests
import time
import json

# Configuration
API_BASE_URL = "http://localhost:8189"

def test_api():
    """Test the InfiniteTalk API with sample image and audio"""
    
    # Sample request - replace with your own image and audio URLs
    request_data = {
        "image_url": "https://example.com/portrait.jpg",  # Replace with actual image URL
        "audio_url": "https://example.com/speech.mp3",    # Replace with actual audio URL
        "prompt": "the person is speaking clearly",
        "steps": 5,
        "cfg": 1.0,
        "width": 960,
        "height": 528,
        "max_frames": 101,
        "fps": 20
    }
    
    print("🎬 Testing InfiniteTalk API")
    print(f"API URL: {API_BASE_URL}")
    
    # Health check
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"✅ API Health: {response.json()}")
    except Exception as e:
        print(f"❌ API Health Check Failed: {e}")
        return
    
    # Start generation
    print("\n🚀 Starting video generation...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/generate",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        job_id = result["job_id"]
        print(f"✅ Job started: {job_id}")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
    except Exception as e:
        print(f"❌ Failed to start generation: {e}")
        return
    
    # Monitor progress
    print(f"\n⏳ Monitoring job {job_id}...")
    while True:
        try:
            response = requests.get(f"{API_BASE_URL}/status/{job_id}")
            response.raise_for_status()
            status = response.json()
            
            print(f"Status: {status['status']}", end="")
            if "progress" in status:
                print(f" - Progress: {status['progress']:.1f}%")
            else:
                print()
            
            if status["status"] == "completed":
                print("✅ Generation completed!")
                if status.get("video_ready"):
                    print(f"📥 Download URL: {API_BASE_URL}/download/{job_id}")
                    
                    # Download the video
                    print("⬇️ Downloading video...")
                    video_response = requests.get(f"{API_BASE_URL}/download/{job_id}")
                    video_response.raise_for_status()
                    
                    filename = f"talking_video_{job_id}.mp4"
                    with open(filename, "wb") as f:
                        f.write(video_response.content)
                    print(f"✅ Video saved as: {filename}")
                else:
                    print("⚠️ Video not ready yet, trying again...")
                break
                
            elif status["status"] == "error":
                print(f"❌ Generation failed: {status.get('error', 'Unknown error')}")
                break
                
            time.sleep(5)  # Wait 5 seconds before checking again
            
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            break

def list_jobs():
    """List all jobs"""
    try:
        response = requests.get(f"{API_BASE_URL}/jobs")
        response.raise_for_status()
        jobs = response.json()
        print("\n📋 All Jobs:")
        print(json.dumps(jobs, indent=2))
    except Exception as e:
        print(f"❌ Failed to list jobs: {e}")

if __name__ == "__main__":
    print("InfiniteTalk API Test Script")
    print("=" * 40)
    
    # Update these URLs with real image and audio files
    print("⚠️  IMPORTANT: Update the image_url and audio_url in the script")
    print("   with real URLs pointing to:")
    print("   - A portrait image (JPG/PNG)")
    print("   - An audio file (MP3/WAV)")
    print()
    
    choice = input("Continue with test? (y/n): ").lower()
    if choice == 'y':
        test_api()
        list_jobs()
    else:
        print("Test cancelled. Please update the URLs first.")