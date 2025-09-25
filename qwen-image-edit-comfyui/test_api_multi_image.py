#!/usr/bin/env python3
"""
Test script for Qwen Image Edit Plus API with multi-image support
"""

import requests
import time
import json
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8189"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        response.raise_for_status()
        result = response.json()
        print(f"✅ Health check passed: {result}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_single_image_edit():
    """Test editing with a single image"""
    print("\nTesting single image edit...")
    
    request_data = {
        "image1_url": "https://picsum.photos/512/512?random=1",
        "prompt": "Add a beautiful sunset in the background",
        "negative_prompt": "blurry, low quality, distorted",
        "steps": 20,
        "cfg": 3.0,
        "megapixels": 1.0
    }
    
    return submit_and_wait(request_data, "single image edit")

def test_multi_image_edit():
    """Test editing with multiple images"""
    print("\nTesting multi-image edit...")
    
    request_data = {
        "image1_url": "https://picsum.photos/512/512?random=2",
        "image2_url": "https://picsum.photos/512/512?random=3", 
        "image3_url": "https://picsum.photos/512/512?random=4",
        "prompt": "Combine elements from all three images into a cohesive scene",
        "negative_prompt": "blurry, low quality, artifacts",
        "steps": 30,
        "cfg": 4.0,
        "megapixels": 1.5
    }
    
    return submit_and_wait(request_data, "multi-image edit")

def test_two_image_edit():
    """Test editing with two images"""
    print("\nTesting two-image edit...")
    
    request_data = {
        "image1_url": "https://picsum.photos/512/512?random=5",
        "image2_url": "https://picsum.photos/512/512?random=6",
        "prompt": "Merge the foreground from image 1 with the background from image 2",
        "negative_prompt": "blurry, low quality",
        "steps": 25,
        "cfg": 3.5
    }
    
    return submit_and_wait(request_data, "two-image edit")

def submit_and_wait(request_data: dict, test_name: str) -> bool:
    """Submit a request and wait for completion"""
    try:
        # Submit request
        print(f"Submitting {test_name} request...")
        response = requests.post(f"{API_BASE_URL}/edit-image", json=request_data)
        response.raise_for_status()
        
        result = response.json()
        job_id = result["job_id"]
        print(f"Job submitted: {job_id}")
        
        # Wait for completion
        max_wait_time = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_response = requests.get(f"{API_BASE_URL}/status/{job_id}")
            status_response.raise_for_status()
            status = status_response.json()
            
            print(f"Status: {status['status']}", end="")
            if "progress" in status:
                print(f" ({status['progress']:.1f}%)")
            else:
                print()
            
            if status["status"] == "completed":
                if status.get("image_ready"):
                    print(f"✅ {test_name} completed successfully!")
                    print(f"Download URL: {API_BASE_URL}{status['download_url']}")
                    
                    # Test download
                    download_response = requests.get(f"{API_BASE_URL}{status['download_url']}")
                    download_response.raise_for_status()
                    
                    filename = f"{test_name.replace(' ', '_')}_{job_id[:8]}.png"
                    with open(filename, 'wb') as f:
                        f.write(download_response.content)
                    print(f"Image saved as: {filename}")
                    return True
                else:
                    print(f"❌ {test_name} completed but image not ready")
                    return False
                    
            elif status["status"] == "error":
                print(f"❌ {test_name} failed: {status.get('error', 'Unknown error')}")
                return False
            
            time.sleep(5)
        
        print(f"❌ {test_name} timed out after {max_wait_time} seconds")
        return False
        
    except Exception as e:
        print(f"❌ {test_name} failed with exception: {e}")
        return False

def test_debug_endpoints():
    """Test debug endpoints"""
    print("\nTesting debug endpoints...")
    
    try:
        # Test files endpoint
        response = requests.get(f"{API_BASE_URL}/debug/files")
        response.raise_for_status()
        files_info = response.json()
        print(f"Output directory: {files_info['output_dir']}")
        print(f"Files found: {len(files_info['files'])}")
        
        # Test jobs endpoint
        response = requests.get(f"{API_BASE_URL}/jobs")
        response.raise_for_status()
        jobs_info = response.json()
        print(f"Active jobs: {len(jobs_info['jobs'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug endpoints failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Qwen Image Edit Plus API Test Suite ===\n")
    
    tests = [
        ("Health Check", test_health_check),
        ("Single Image Edit", test_single_image_edit),
        ("Two Image Edit", test_two_image_edit),
        ("Multi Image Edit", test_multi_image_edit),
        ("Debug Endpoints", test_debug_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        success = test_func()
        results.append((test_name, success))
        
        if success:
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    exit(main())