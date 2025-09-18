#!/usr/bin/env python3
"""
Qwen Image Edit Nunchanku API
A FastAPI-based image editing service using Qwen Image Edit Nunchanku models.
Provides efficient REST API endpoints for image editing operations.
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.image_edit_service import ImageEditService
from models.api_models import (
    ImageEditRequest,
    ImageEditResponse,
    HealthResponse,
    ModelInfoResponse,
    ErrorResponse,
    BatchImageEditRequest,
    BatchImageEditResponse
)
from utils.error_handler import setup_error_handlers
from utils.logger import setup_logger
from utils.gpu_utils import get_gpu_memory_info

# Global service instance
image_edit_service: Optional[ImageEditService] = None
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global image_edit_service
    
    # Startup
    logger.info("Starting Qwen Image Edit Nunchanku API...")
    
    try:
        # Initialize the image edit service
        image_edit_service = ImageEditService()
        await image_edit_service.initialize()
        logger.info("Image edit service initialized successfully")
        
        # Log GPU information
        gpu_info = get_gpu_memory_info()
        logger.info(f"GPU Memory Info: {gpu_info}")
        
    except Exception as e:
        logger.error(f"Failed to initialize image edit service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Qwen Image Edit Nunchanku API...")
    if image_edit_service:
        await image_edit_service.cleanup()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Qwen Image Edit Nunchanku API",
    description="FastAPI-based image editing service using Qwen Image Edit Nunchanku models",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - basic health check."""
    return HealthResponse(
        status="healthy",
        message="Qwen Image Edit Nunchanku API is running",
        timestamp=time.time()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint."""
    global image_edit_service
    
    gpu_info = get_gpu_memory_info()
    model_loaded = image_edit_service is not None and image_edit_service.is_initialized()
    
    status = "healthy" if model_loaded else "initializing"
    if not torch.cuda.is_available():
        status = "warning"
    
    return HealthResponse(
        status=status,
        model_loaded=model_loaded,
        gpu_available=torch.cuda.is_available(),
        gpu_memory_info=gpu_info,
        timestamp=time.time()
    )


@app.post("/edit-image", response_model=ImageEditResponse)
async def edit_image(request: ImageEditRequest):
    """
    Edit an image based on text prompt using Qwen Image Edit Nunchanku.
    
    Args:
        request: Image edit request containing image data and parameters
        
    Returns:
        ImageEditResponse with edited image and metadata
    """
    global image_edit_service
    
    if not image_edit_service or not image_edit_service.is_initialized():
        raise HTTPException(
            status_code=503, 
            detail="Image edit service not available. Please try again later."
        )
    
    start_time = time.time()
    
    try:
        # Process the image edit request
        result = await image_edit_service.edit_image(request)
        processing_time = time.time() - start_time
        
        return ImageEditResponse(
            success=True,
            edited_image=result["edited_image"],
            processing_time=processing_time,
            model_info=result["model_info"]
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Image edit failed: {e}")
        
        return ImageEditResponse(
            success=False,
            error_message=str(e),
            processing_time=processing_time,
            model_info={}
        )


@app.get("/model-info", response_model=ModelInfoResponse)
async def get_model_info():
    """Get current model configuration and information."""
    global image_edit_service
    
    if not image_edit_service or not image_edit_service.is_initialized():
        raise HTTPException(
            status_code=503,
            detail="Image edit service not available"
        )
    
    model_info = await image_edit_service.get_model_info()
    return ModelInfoResponse(**model_info)


@app.post("/model-config")
async def update_model_config(config: Dict[str, Any]):
    """Update model configuration parameters."""
    global image_edit_service
    
    if not image_edit_service or not image_edit_service.is_initialized():
        raise HTTPException(
            status_code=503,
            detail="Image edit service not available"
        )
    
    try:
        updated_config = await image_edit_service.update_config(config)
        return {"success": True, "updated_config": updated_config}
    except Exception as e:
        logger.error(f"Failed to update model config: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/batch-edit-image", response_model=BatchImageEditResponse)
async def batch_edit_image(request: BatchImageEditRequest):
    """
    Edit multiple images based on text prompt using Qwen Image Edit Nunchanku.
    
    Args:
        request: Batch image edit request containing multiple images and parameters
        
    Returns:
        BatchImageEditResponse with results for each image
    """
    global image_edit_service
    
    if not image_edit_service or not image_edit_service.is_initialized():
        raise HTTPException(
            status_code=503, 
            detail="Image edit service not available. Please try again later."
        )
    
    start_time = time.time()
    results = []
    processed_count = 0
    failed_count = 0
    
    for i, image in enumerate(request.images):
        try:
            # Create individual request for each image
            individual_request = ImageEditRequest(
                image=image,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                num_inference_steps=request.num_inference_steps,
                true_cfg_scale=request.true_cfg_scale,
                seed=request.seed,
                rank=request.rank
            )
            
            # Process the image edit request
            result = await image_edit_service.edit_image(individual_request)
            
            response = ImageEditResponse(
                success=True,
                edited_image=result["edited_image"],
                processing_time=0,  # Will be updated below
                model_info=result["model_info"],
                request_id=f"batch_{i}"
            )
            
            results.append(response)
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Batch image edit failed for image {i}: {e}")
            
            error_response = ImageEditResponse(
                success=False,
                error_message=str(e),
                processing_time=0,
                model_info={},
                request_id=f"batch_{i}"
            )
            
            results.append(error_response)
            failed_count += 1
    
    total_processing_time = time.time() - start_time
    
    # Update processing times for individual results
    avg_time = total_processing_time / len(results) if results else 0
    for result in results:
        result.processing_time = avg_time
    
    return BatchImageEditResponse(
        success=processed_count > 0,
        results=results,
        total_processing_time=total_processing_time,
        processed_count=processed_count,
        failed_count=failed_count
    )


@app.get("/system-info")
async def get_system_info():
    """
    Get comprehensive system information including GPU details.
    
    Returns:
        Dictionary with system information
    """
    try:
        import platform
        import sys
        
        gpu_info = get_gpu_memory_info()
        
        system_info = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "gpu_available": torch.cuda.is_available(),
            "gpu_info": gpu_info if torch.cuda.is_available() else None,
            "api_version": "1.0.0",
            "service_name": "Qwen Image Edit Nunchanku API"
        }
        
        if torch.cuda.is_available():
            system_info["cuda_version"] = torch.version.cuda
            system_info["pytorch_version"] = torch.__version__
            system_info["gpu_count"] = torch.cuda.device_count()
        
        return system_info
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system information")


# Setup error handlers
setup_error_handlers(app)


def main():
    """Main entry point for the application."""
    # Setup logging
    setup_logger()
    
    # Get configuration from environment
    import os
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    logger.info(f"Starting server on {host}:{port}")
    
    # Run the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
        access_log=True
    )


if __name__ == "__main__":
    main()