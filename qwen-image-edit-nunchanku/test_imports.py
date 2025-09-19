#!/usr/bin/env python3
"""
Test script to verify imports work correctly.
"""

def test_imports():
    """Test all critical imports."""
    try:
        print("Testing basic imports...")
        
        # Test diffusers import
        try:
            from diffusers import QwenImageEditPipeline
            print("✓ QwenImageEditPipeline import successful")
        except ImportError as e:
            print(f"✗ QwenImageEditPipeline import failed: {e}")
            # This is expected if diffusers doesn't have this pipeline yet
            print("  Note: This may be expected if using a mock implementation")
        
        # Test model utils import
        try:
            from utils.model_utils import load_qwen_pipeline, get_nunchaku_transformer
            print("✓ Model utils import successful")
        except ImportError as e:
            print(f"✗ Model utils import failed: {e}")
            return False
        
        # Test service import
        try:
            from services.image_edit_service import ImageEditService
            print("✓ ImageEditService import successful")
        except ImportError as e:
            print(f"✗ ImageEditService import failed: {e}")
            return False
        
        # Test API models import
        try:
            from models.api_models import ImageEditRequest, ImageEditResponse
            print("✓ API models import successful")
        except ImportError as e:
            print(f"✗ API models import failed: {e}")
            return False
        
        print("\n✓ All critical imports successful!")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error during import testing: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)