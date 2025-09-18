"""
Unit tests for Qwen Image Edit Nunchanku API.
"""

import asyncio
import base64
import io
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from models.api_models import ImageEditRequest, ImageEditResponse, HealthResponse
from services.image_edit_service import ImageEditService
from utils.image_processor import ImageProcessor
from utils.gpu_utils import get_gpu_memory_info
from utils.error_handler import QwenAPIException, ImageProcessingException


class TestImageProcessor:
    """Test cases for ImageProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create ImageProcessor instance for testing."""
        return ImageProcessor()
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample PIL image for testing."""
        # Create a simple RGB image
        image = Image.new('RGB', (100, 100), color='red')
        return image
    
    @pytest.fixture
    def sample_image_base64(self, sample_image):
        """Create base64 encoded sample image."""
        buffer = io.BytesIO()
        sample_image.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def test_init(self, processor):
        \"\"\"Test ImageProcessor initialization.\"\"\"
        assert processor.max_download_size == 50 * 1024 * 1024
        assert 'JPEG' in processor.supported_formats
        assert 'PNG' in processor.supported_formats
    
    @pytest.mark.asyncio
    async def test_load_image_from_base64(self, processor, sample_image_base64):
        \"\"\"Test loading image from base64 string.\"\"\"
        loaded_image = await processor.load_image(sample_image_base64)
        
        assert isinstance(loaded_image, Image.Image)
        assert loaded_image.mode == 'RGB'
        assert loaded_image.size == (100, 100)
    
    @pytest.mark.asyncio
    async def test_load_image_from_data_url(self, processor, sample_image_base64):
        \"\"\"Test loading image from data URL.\"\"\"
        data_url = f\"data:image/jpeg;base64,{sample_image_base64}\"
        loaded_image = await processor.load_image(data_url)
        
        assert isinstance(loaded_image, Image.Image)
        assert loaded_image.mode == 'RGB'
    
    @pytest.mark.asyncio
    async def test_load_image_invalid_base64(self, processor):
        \"\"\"Test loading image from invalid base64.\"\"\"
        with pytest.raises(ValueError, match=\"Failed to decode base64 image\"):
            await processor.load_image(\"invalid_base64_string\")
    
    @pytest.mark.asyncio
    async def test_preprocess_image(self, processor, sample_image):
        \"\"\"Test image preprocessing.\"\"\"
        # Test resizing
        processed = await processor.preprocess_image(sample_image, max_size=50)
        assert max(processed.size) <= 50
        assert processed.size[0] % 2 == 0  # Width should be even
        assert processed.size[1] % 2 == 0  # Height should be even
    
    @pytest.mark.asyncio
    async def test_postprocess_image(self, processor, sample_image):
        \"\"\"Test image postprocessing.\"\"\"
        base64_result = await processor.postprocess_image(sample_image, format=\"JPEG\", quality=85)
        
        assert isinstance(base64_result, str)
        assert len(base64_result) > 0
        
        # Verify we can decode it back
        decoded_bytes = base64.b64decode(base64_result)
        decoded_image = Image.open(io.BytesIO(decoded_bytes))
        assert decoded_image.format == 'JPEG'
    
    @pytest.mark.asyncio
    async def test_validate_image(self, processor, sample_image):
        \"\"\"Test image validation.\"\"\"
        # Valid image should pass
        assert await processor.validate_image(sample_image) == True
        
        # Create invalid image (too large)
        large_image = Image.new('RGB', (5000, 5000))
        with pytest.raises(ValueError, match=\"Image dimensions too large\"):
            await processor.validate_image(large_image)
    
    def test_get_image_info(self, processor, sample_image):
        \"\"\"Test getting image information.\"\"\"
        info = processor.get_image_info(sample_image)
        
        assert info['size'] == (100, 100)
        assert info['mode'] == 'RGB'
        assert info['megapixels'] == 0.01


class TestImageEditService:
    \"\"\"Test cases for ImageEditService class.\"\"\"
    
    @pytest.fixture
    def service(self):
        \"\"\"Create ImageEditService instance for testing.\"\"\"
        return ImageEditService()
    
    @pytest.fixture
    def mock_pipeline(self):
        \"\"\"Create mock pipeline for testing.\"\"\"
        pipeline = Mock()
        pipeline.transformer = Mock()
        pipeline.scheduler = Mock()
        
        # Mock pipeline call
        result_mock = Mock()
        result_mock.images = [Image.new('RGB', (512, 512), color='blue')]
        pipeline.return_value = result_mock
        
        return pipeline
    
    def test_init(self, service):
        \"\"\"Test ImageEditService initialization.\"\"\"
        assert service.pipeline is None
        assert service.transformer is None
        assert service._initialized == False
        assert service._model_config['default_steps'] == 8
        assert service._model_config['default_rank'] == 128
    
    @pytest.mark.asyncio
    async def test_initialize_service(self, service):
        \"\"\"Test service initialization.\"\"\"
        with patch('services.image_edit_service.load_qwen_pipeline') as mock_load, \\n             patch('services.image_edit_service.get_nunchaku_transformer') as mock_nunchaku:
            
            # Setup mocks
            mock_pipeline = Mock()
            mock_pipeline.transformer = Mock()
            mock_load.return_value = mock_pipeline
            mock_nunchaku.return_value = Mock()
            
            # Test initialization
            await service.initialize()
            
            assert service._initialized == True
            assert mock_load.called
            assert mock_nunchaku.called
    
    def test_is_initialized(self, service):
        \"\"\"Test checking if service is initialized.\"\"\"
        assert service.is_initialized() == False
        service._initialized = True
        assert service.is_initialized() == True
    
    @pytest.mark.asyncio
    async def test_get_model_info_not_initialized(self, service):
        \"\"\"Test getting model info when not initialized.\"\"\"
        with pytest.raises(RuntimeError, match=\"Service not initialized\"):
            await service.get_model_info()
    
    @pytest.mark.asyncio
    async def test_cleanup(self, service):
        \"\"\"Test service cleanup.\"\"\"
        # Set up some mock components
        service.pipeline = Mock()
        service.transformer = Mock()
        service._initialized = True
        
        await service.cleanup()
        
        assert service.pipeline is None
        assert service.transformer is None
        assert service._initialized == False


class TestAPIModels:
    \"\"\"Test cases for API data models.\"\"\"
    
    def test_image_edit_request_valid(self):
        \"\"\"Test valid ImageEditRequest.\"\"\"
        request_data = {
            \"image\": \"data:image/jpeg;base64,/9j/4AAQSkZJRg==\",
            \"prompt\": \"change the color to blue\",
            \"num_inference_steps\": 8,
            \"rank\": 128
        }
        
        request = ImageEditRequest(**request_data)
        assert request.prompt == \"change the color to blue\"
        assert request.num_inference_steps == 8
        assert request.rank == 128
    
    def test_image_edit_request_invalid_rank(self):
        \"\"\"Test ImageEditRequest with invalid rank.\"\"\"
        request_data = {
            \"image\": \"data:image/jpeg;base64,/9j/4AAQSkZJRg==\",
            \"prompt\": \"test prompt\",
            \"rank\": 256  # Invalid rank
        }
        
        with pytest.raises(ValueError, match=\"rank must be either 64 or 128\"):
            ImageEditRequest(**request_data)
    
    def test_image_edit_request_invalid_steps(self):
        \"\"\"Test ImageEditRequest with invalid steps.\"\"\"
        request_data = {
            \"image\": \"data:image/jpeg;base64,/9j/4AAQSkZJRg==\",
            \"prompt\": \"test prompt\",
            \"num_inference_steps\": 0  # Invalid steps
        }
        
        with pytest.raises(ValueError):
            ImageEditRequest(**request_data)
    
    def test_image_edit_response(self):
        \"\"\"Test ImageEditResponse model.\"\"\"
        response_data = {
            \"success\": True,
            \"edited_image\": \"base64_encoded_image\",
            \"processing_time\": 2.5,
            \"model_info\": {\"steps\": 8, \"rank\": 128}
        }
        
        response = ImageEditResponse(**response_data)
        assert response.success == True
        assert response.processing_time == 2.5
    
    def test_health_response(self):
        \"\"\"Test HealthResponse model.\"\"\"
        response_data = {
            \"status\": \"healthy\",
            \"model_loaded\": True,
            \"gpu_available\": True,
            \"timestamp\": 1234567890.0
        }
        
        response = HealthResponse(**response_data)
        assert response.status == \"healthy\"
        assert response.model_loaded == True


class TestAPIEndpoints:
    \"\"\"Test cases for API endpoints.\"\"\"
    
    @pytest.fixture
    def client(self):
        \"\"\"Create test client.\"\"\"
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        \"\"\"Test root endpoint.\"\"\"
        response = client.get(\"/\")
        assert response.status_code == 200
        data = response.json()
        assert \"status\" in data
        assert \"message\" in data
    
    def test_health_endpoint(self, client):
        \"\"\"Test health check endpoint.\"\"\"
        response = client.get(\"/health\")
        assert response.status_code == 200
        data = response.json()
        assert \"status\" in data
        assert \"timestamp\" in data
    
    @patch('main.image_edit_service')
    def test_edit_image_service_not_ready(self, mock_service, client):
        \"\"\"Test image edit when service is not ready.\"\"\"
        mock_service.is_initialized.return_value = False
        
        request_data = {
            \"image\": \"data:image/jpeg;base64,/9j/4AAQSkZJRg==\",
            \"prompt\": \"test prompt\"
        }
        
        response = client.post(\"/edit-image\", json=request_data)
        assert response.status_code == 503
    
    def test_edit_image_invalid_request(self, client):
        \"\"\"Test image edit with invalid request.\"\"\"
        request_data = {
            \"image\": \"invalid_image_data\",
            \"prompt\": \"\"  # Empty prompt
        }
        
        response = client.post(\"/edit-image\", json=request_data)
        assert response.status_code == 422  # Validation error


class TestErrorHandling:
    \"\"\"Test cases for error handling.\"\"\"
    
    def test_qwen_api_exception(self):
        \"\"\"Test QwenAPIException.\"\"\"
        exc = QwenAPIException(\"Test error\", \"TEST_ERROR\")
        assert exc.message == \"Test error\"
        assert exc.error_code == \"TEST_ERROR\"
        assert exc.request_id is not None
    
    def test_image_processing_exception(self):
        \"\"\"Test ImageProcessingException.\"\"\"
        exc = ImageProcessingException(\"Image processing failed\")
        assert exc.error_code == \"IMAGE_PROCESSING_ERROR\"
        assert \"Image processing failed\" in str(exc)


class TestGPUUtils:
    \"\"\"Test cases for GPU utilities.\"\"\"
    
    def test_get_gpu_memory_info(self):
        \"\"\"Test getting GPU memory info.\"\"\"
        info = get_gpu_memory_info()
        assert isinstance(info, dict)
        # Should always return a dict, even if CUDA is not available
    
    @patch('torch.cuda.is_available', return_value=False)
    def test_get_gpu_memory_info_no_cuda(self, mock_cuda):
        \"\"\"Test GPU memory info when CUDA is not available.\"\"\"
        info = get_gpu_memory_info()
        assert \"status\" in info
        assert info[\"status\"] == \"CUDA not available\"


@pytest.mark.integration
class TestIntegration:
    \"\"\"Integration tests for the complete API.\"\"\"
    
    @pytest.fixture
    def client(self):
        \"\"\"Create test client.\"\"\"
        return TestClient(app)
    
    @pytest.fixture
    def sample_image_request(self):
        \"\"\"Create sample image edit request.\"\"\"
        # Create a simple test image
        img = Image.new('RGB', (256, 256), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            \"image\": f\"data:image/jpeg;base64,{image_b64}\",
            \"prompt\": \"change the color to blue\",
            \"num_inference_steps\": 4,
            \"rank\": 64
        }
    
    def test_api_documentation(self, client):
        \"\"\"Test API documentation endpoints.\"\"\"
        # Test OpenAPI docs
        response = client.get(\"/docs\")
        assert response.status_code == 200
        
        # Test ReDoc
        response = client.get(\"/redoc\")
        assert response.status_code == 200
        
        # Test OpenAPI JSON
        response = client.get(\"/openapi.json\")
        assert response.status_code == 200
        data = response.json()
        assert \"openapi\" in data
        assert \"info\" in data
    
    @pytest.mark.slow
    def test_complete_workflow(self, client, sample_image_request):
        \"\"\"Test complete image editing workflow.\"\"\"
        # Note: This test requires the service to be properly initialized
        # In a real environment, you'd want to mock the service or use a test environment
        
        # Health check
        health_response = client.get(\"/health\")
        assert health_response.status_code == 200
        
        # Model info (might fail if service not initialized)
        model_response = client.get(\"/model-info\")
        # Don't assert success here as service might not be initialized in test
        
        # Image edit request (will likely fail without proper service setup)
        edit_response = client.post(\"/edit-image\", json=sample_image_request)
        # In test environment, this will likely return 503 (service not available)
        assert edit_response.status_code in [200, 503]


if __name__ == \"__main__\":
    # Run tests with pytest
    pytest.main([__file__, \"-v\"])