#!/usr/bin/env python3
"""
Script to verify that pre-downloaded models are available and accessible.
"""

import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_models():
    """Verify that all expected models are downloaded and accessible."""
    
    cache_dir = os.getenv("MODEL_CACHE_DIR", "./models")
    logger.info(f"Checking models in cache directory: {cache_dir}")
    
    # Expected Nunchaku quantized model files (self-contained, no base model needed)
    expected_models = [
        # Only r128 models, 8-step and original (no 4-step, no r64)
        f"{cache_dir}/nunchaku-qwen-image-edit/svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors",
        f"{cache_dir}/nunchaku-qwen-image-edit/svdq-int4_r128-qwen-image-edit.safetensors",
    ]
    
    # Check Nunchaku quantized models (self-contained, no base model needed)
    logger.info("Checking Nunchaku quantized models:")
    found_models = 0
    total_models = len(expected_models)
    
    for model_path in expected_models:
        if os.path.exists(model_path):
            size_mb = os.path.getsize(model_path) / (1024 * 1024)
            model_name = os.path.basename(model_path)
            logger.info(f"  ✓ {model_name}: {size_mb:.2f} MB")
            found_models += 1
        else:
            model_name = os.path.basename(model_path)
            logger.warning(f"  ✗ Missing: {model_name}")
    
    logger.info(f"Found {found_models}/{total_models} Nunchaku models")
    
    # Calculate total disk usage
    total_size = 0
    if os.path.exists(cache_dir):
        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
    
    total_size_gb = total_size / (1024 * 1024 * 1024)
    logger.info(f"Total model cache size: {total_size_gb:.2f} GB")
    
    # Summary
    if found_models == total_models:
        logger.info("✓ All Nunchaku models verified successfully!")
        return True
    elif found_models > 0:
        logger.warning(f"⚠ Found {found_models}/{total_models} Nunchaku models - API should still work")
        return True
    else:
        logger.error("✗ No Nunchaku models found!")
        return False

def list_all_files():
    """List all files in the model cache for debugging."""
    cache_dir = os.getenv("MODEL_CACHE_DIR", "./models")
    
    if not os.path.exists(cache_dir):
        logger.error(f"Cache directory does not exist: {cache_dir}")
        return
    
    logger.info(f"Listing all files in {cache_dir}:")
    
    for root, dirs, files in os.walk(cache_dir):
        level = root.replace(cache_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        logger.info(f"{indent}{os.path.basename(root)}/")
        
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            logger.info(f"{subindent}{file} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_all_files()
    else:
        success = verify_models()
        sys.exit(0 if success else 1)