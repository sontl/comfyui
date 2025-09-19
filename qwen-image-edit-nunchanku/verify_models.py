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
    
    # Expected model files
    expected_models = {
        "Base Qwen Model": f"{cache_dir}/Qwen--Qwen-Image-Edit",
        "Nunchaku Models": [
            # Only r128 models, 8-step and original (no 4-step, no r64)
            f"{cache_dir}/nunchaku-qwen-image-edit/svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors",
            f"{cache_dir}/nunchaku-qwen-image-edit/svdq-int4_r128-qwen-image-edit.safetensors",
        ]
    }
    
    all_good = True
    
    # Check base model
    base_model_path = expected_models["Base Qwen Model"]
    if os.path.exists(base_model_path):
        logger.info(f"✓ Base Qwen model found: {base_model_path}")
        
        # Check for key files in the base model
        key_files = ["config.json", "model.safetensors.index.json"]
        for key_file in key_files:
            file_path = os.path.join(base_model_path, key_file)
            if os.path.exists(file_path):
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                logger.info(f"  ✓ {key_file}: {size_mb:.2f} MB")
            else:
                logger.warning(f"  ✗ Missing: {key_file}")
                all_good = False
    else:
        logger.error(f"✗ Base Qwen model not found: {base_model_path}")
        all_good = False
    
    # Check Nunchaku models
    logger.info("Checking Nunchaku quantized models:")
    found_models = 0
    total_models = len(expected_models["Nunchaku Models"])
    
    for model_path in expected_models["Nunchaku Models"]:
        if os.path.exists(model_path):
            size_mb = os.path.getsize(model_path) / (1024 * 1024)
            model_name = os.path.basename(model_path)
            logger.info(f"  ✓ {model_name}: {size_mb:.2f} MB")
            found_models += 1
        else:
            model_name = os.path.basename(model_path)
            logger.warning(f"  ✗ Missing: {model_name}")
    
    logger.info(f"Found {found_models}/{total_models} Nunchaku models")
    
    if found_models == 0:
        logger.error("No Nunchaku models found!")
        all_good = False
    elif found_models < total_models:
        logger.warning("Some Nunchaku models are missing, but API should still work")
    
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
    if all_good:
        logger.info("✓ All models verified successfully!")
        return True
    else:
        logger.warning("⚠ Some issues found, but API may still work with available models")
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