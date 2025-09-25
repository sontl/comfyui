#!/usr/bin/env python3
"""
Test script for Qwen Image Edit API
"""

import requests
import time
import json

# Configuration
API_BASE_URL = "http://localhost:8189"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_image_edit():
    """Test image editing functionality"""
    print("\nTesting image edit...")
    
    # Test request (updated for new API)
    request_data = {
        "image1_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
        "prompt": "change the background to a beautiful sunset over mountains",
        "negative_prompt": "blurry, low quality, distorted",
        "steps": 20,
        "cfg": 3.0,
        "megapixels": 1.0
    }
    
    try:
        # Submit job
        response = requests.post(f"{API_BASE_URL}/edit-image", json=request_data)
        print(f"Submit status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return False
            
        job_data = response.json()
        job_id = job_data["job_id"]
        print(f"Job ID: {job_id}")
        
        # Poll for completion
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = requests.get(f"{API_BASE_URL}/status/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"Status: {status_data['status']}")
                
                if "progress" in status_data:
                    print(f"Progress: {status_data['progress']:.1f}%")
                
                if status_data["status"] == "completed":
                    print("✅ Image editing completed!")
                    
                    # Test download
                    download_response = requests.get(f"{API_BASE_URL}/download/{job_id}")
                    if download_response.status_code == 200:
                        with open(f"test_output_{job_id}.png", "wb") as f:
                            f.write(download_response.content)
                        print(f"✅ Downloaded edited image: test_output_{job_id}.png")
                        return True
                    else:
                        print(f"❌ Download failed: {download_response.status_code}")
                        return False
                        
                elif status_data["status"] == "error":
                    print(f"❌ Job failed: {status_data.get('error', 'Unknown error')}")
                    return False
                    
            time.sleep(5)
        
        print("❌ Timeout waiting for completion")
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_debug_endpoints():
    """Test debug endpoints"""
    print("\nTesting debug endpoints...")
    
    try:
        # Test jobs list
        response = requests.get(f"{API_BASE_URL}/jobs")
        print(f"Jobs list status: {response.status_code}")
        
        # Test files debug
        response = requests.get(f"{API_BASE_URL}/debug/files")
        print(f"Debug files status: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"Debug endpoints failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Qwen Image Edit Plus API Test ===\n")
    
    tests = [
        ("Health Check", test_health_check),
        ("Single Image Edit", test_image_edit),
        ("Debug Endpoints", test_debug_endpoints)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
        print(f"Result: {'✅ PASS' if result else '❌ FAIL'}")
    
    print("\n=== Test Summary ===")
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")

if __name__ == "__main__":
    main()