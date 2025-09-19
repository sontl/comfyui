"""
Image Edit Service for Qwen Image Edit Nunchanku API.
Handles model initialization, loading, and image editing operations.
"""

import asyncio
import gc
import logging
import os
import time
from typing import Any, Dict, Optional

import torch
from diffusers import FlowMatchEulerDiscreteScheduler
from huggingface_hub import hf_hub_download

from models.api_models import ImageEditRequest, ModelInfo
from utils.image_processor import ImageProcessor
from utils.gpu_utils import get_gpu_memory_info, optimize_gpu_memory
from utils.model_utils import load_qwen_pipeline, get_nunchaku_transformer, get_available_model_configs

logger = logging.getLogger(__name__)


class ImageEditService:
    """
    Service class for handling Qwen Image Edit operations using Nunchaku optimization.
    
    This service manages:
    - Model loading and initialization
    - GPU memory optimization  
    - Image editing pipeline execution
    - Configuration management
    """
    
    def __init__(self):
        """Initialize the image edit service."""
        self.pipeline = None
        self.transformer = None
        self.scheduler = None
        self.image_processor = ImageProcessor()
        self._initialized = False
        self._model_config = {
            "model_id": "Qwen/QwenEdit",
            "default_steps": 8,
            "default_rank": 128,
            "max_steps": 50,
            "supported_ranks": [128],  # Only r128 supported
            "enable_cpu_offload": True,
            "memory_optimization": True
        }
        
        # Model cache directory
        self.model_cache_dir = os.getenv("MODEL_CACHE_DIR", "./models")
        os.makedirs(self.model_cache_dir, exist_ok=True)
        
        # Check available models and update config
        self._update_config_from_available_models()
    
    def _update_config_from_available_models(self) -> None:
        """Update model configuration based on available pre-downloaded models."""
        try:
            available_configs = get_available_model_configs(self.model_cache_dir)
            
            # Update supported ranks based on available models
            if available_configs["supported_ranks"]:
                self._model_config["supported_ranks"] = available_configs["supported_ranks"]
                # Use the highest available rank as default
                self._model_config["default_rank"] = max(available_configs["supported_ranks"])
            
            # Update supported steps based on available models
            if available_configs["supported_steps"]:
                # Prefer 8 steps if available, otherwise use the highest available
                if 8 in available_configs["supported_steps"]:
                    self._model_config["default_steps"] = 8
                else:
                    self._model_config["default_steps"] = max(available_configs["supported_steps"])
            
            logger.info(f"Updated model config based on available models: {self._model_config}")
            
        except Exception as e:
            logger.warning(f"Could not update config from available models: {e}")
    
    async def initialize(self) -> None:
        """
        Initialize the image edit service and load models.
        
        Raises:
            RuntimeError: If initialization fails
        """
        if self._initialized:
            logger.info("Service already initialized")
            return
        
        logger.info("Initializing Qwen Image Edit Service...")
        
        try:
            # Check GPU availability
            if not torch.cuda.is_available():
                logger.warning("CUDA not available, using CPU (performance will be degraded)")
            else:
                gpu_info = get_gpu_memory_info()
                logger.info(f"GPU Memory Info: {gpu_info}")
            
            # Initialize models
            await self._load_models()
            
            # Optimize GPU memory
            if torch.cuda.is_available():
                optimize_gpu_memory()
            
            self._initialized = True
            logger.info("Qwen Image Edit Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize service: {e}")
            await self.cleanup()
            raise RuntimeError(f"Service initialization failed: {e}")
    
    async def _load_models(self) -> None:
        """Load and configure the Qwen Image Edit models."""
        logger.info("Loading Qwen Image Edit models...")
        
        try:
            # Load the pipeline with Nunchaku optimization
            self.pipeline = await load_qwen_pipeline(
                model_id=self._model_config["model_id"],
                cache_dir=self.model_cache_dir,
                torch_dtype=torch.float16,
                device_map="auto" if torch.cuda.is_available() else "cpu"
            )
            
            # Get the Nunchaku-optimized transformer
            self.transformer = get_nunchaku_transformer(
                self.pipeline.transformer,
                rank=self._model_config["default_rank"],
                num_steps=self._model_config["default_steps"]
            )
            
            # Update pipeline with optimized transformer
            self.pipeline.transformer = self.transformer
            
            # Configure scheduler
            self.scheduler = FlowMatchEulerDiscreteScheduler.from_config(
                self.pipeline.scheduler.config
            )
            self.pipeline.scheduler = self.scheduler
            
            # Apply memory optimizations
            await self._apply_memory_optimizations()
            
            logger.info("Models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise
    
    async def _apply_memory_optimizations(self) -> None:
        """Apply GPU memory optimizations based on available VRAM."""
        if not torch.cuda.is_available():
            return
        
        gpu_info = get_gpu_memory_info()
        total_memory_gb = float(gpu_info.get("total_memory", "0GB").replace("GB", ""))
        
        logger.info(f"Applying memory optimizations for {total_memory_gb}GB GPU")
        
        if total_memory_gb > 18:
            # High VRAM - enable model CPU offload only
            logger.info("High VRAM detected - enabling model CPU offload")
            self.pipeline.enable_model_cpu_offload()
        else:
            # Lower VRAM - aggressive optimization
            logger.info("Lower VRAM detected - enabling aggressive optimizations")
            
            # Set transformer offloading
            if hasattr(self.transformer, 'set_offload'):
                self.transformer.set_offload(
                    True,
                    use_pin_memory=False,
                    num_blocks_on_gpu=1
                )
            
            # Enable sequential CPU offload
            self.pipeline.enable_sequential_cpu_offload()
            
            # Enable attention slicing
            if hasattr(self.pipeline, 'enable_attention_slicing'):
                self.pipeline.enable_attention_slicing(1)
        
        # Enable memory efficient attention if available
        if hasattr(self.pipeline, 'enable_xformers_memory_efficient_attention'):
            try:
                self.pipeline.enable_xformers_memory_efficient_attention()
                logger.info("Enabled xformers memory efficient attention")
            except Exception as e:
                logger.warning(f"Could not enable xformers attention: {e}")
    
    async def edit_image(self, request: ImageEditRequest) -> Dict[str, Any]:
        """
        Edit an image based on the provided request.
        
        Args:
            request: Image edit request with parameters
            
        Returns:
            Dictionary containing edited image and metadata
            
        Raises:
            RuntimeError: If service not initialized or editing fails
        """
        if not self._initialized:
            raise RuntimeError("Service not initialized")
        
        logger.info(f"Processing image edit request: {request.prompt[:50]}...")
        start_time = time.time()
        
        try:
            # Load and preprocess input image
            input_image = await self.image_processor.load_image(request.image)
            preprocessed_image = await self.image_processor.preprocess_image(
                input_image,
                max_size=2048
            )
            
            # Prepare generation parameters
            generation_kwargs = {
                "image": preprocessed_image,
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "num_inference_steps": request.num_inference_steps,
                "guidance_scale": request.true_cfg_scale,
                "generator": torch.Generator().manual_seed(request.seed) if request.seed else None,
            }
            
            # Update transformer rank if different from current
            if hasattr(self.transformer, 'set_rank') and request.rank != self._model_config["default_rank"]:
                logger.info(f"Updating transformer rank to {request.rank}")
                self.transformer.set_rank(request.rank)
            
            # Clear GPU cache before inference
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Run inference
            inference_start = time.time()
            
            with torch.inference_mode():
                result = self.pipeline(**generation_kwargs)
            
            inference_time = time.time() - inference_start
            
            # Post-process output image
            output_image = result.images[0]
            edited_image_b64 = await self.image_processor.postprocess_image(
                output_image,
                format="JPEG",
                quality=95
            )
            
            # Collect metadata
            total_time = time.time() - start_time
            gpu_info = get_gpu_memory_info() if torch.cuda.is_available() else {}
            
            model_info = ModelInfo(
                steps=request.num_inference_steps,
                rank=request.rank,
                model_version="lightningv1.0",
                inference_time=inference_time,
                gpu_memory_used=gpu_info.get("allocated_memory", "N/A")
            )
            
            logger.info(f"Image edit completed in {total_time:.2f}s (inference: {inference_time:.2f}s)")
            
            return {
                "edited_image": edited_image_b64,
                "model_info": model_info.model_dump()
            }
            
        except Exception as e:
            logger.error(f"Image edit failed: {e}")
            raise RuntimeError(f"Image editing failed: {e}")
        
        finally:
            # Clean up GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
    
    async def get_model_info(self) -> Dict[str, Any]:
        """
        Get current model information and configuration.
        
        Returns:
            Dictionary with model information
        """
        if not self._initialized:
            raise RuntimeError("Service not initialized")
        
        gpu_info = get_gpu_memory_info() if torch.cuda.is_available() else {}
        
        return {
            "model_name": "Qwen Image Edit Nunchanku",
            "model_version": "lightningv1.0",
            "supported_ranks": self._model_config["supported_ranks"],
            "default_steps": self._model_config["default_steps"],
            "max_steps": self._model_config["max_steps"],
            "gpu_memory_usage": gpu_info.get("allocated_memory", "N/A"),
            "model_config": self._model_config.copy()
        }
    
    async def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update model configuration.
        
        Args:
            config: Configuration updates
            
        Returns:
            Updated configuration
        """
        if not self._initialized:
            raise RuntimeError("Service not initialized")
        
        # Validate and update configuration
        for key, value in config.items():
            if key == "default_steps" and isinstance(value, int) and 1 <= value <= 50:
                self._model_config["default_steps"] = value
            elif key == "default_rank" and value == 128:
                self._model_config["default_rank"] = value
                # Update transformer rank if needed
                if hasattr(self.transformer, 'set_rank'):
                    self.transformer.set_rank(value)
            elif key == "default_rank" and value != 128:
                logger.warning(f"Only rank 128 is supported, ignoring rank {value}")
                continue
            elif key == "enable_cpu_offload" and isinstance(value, bool):
                self._model_config["enable_cpu_offload"] = value
                # Apply memory optimization changes
                await self._apply_memory_optimizations()
            elif key == "memory_optimization" and isinstance(value, bool):
                self._model_config["memory_optimization"] = value
            else:
                logger.warning(f"Ignoring invalid config update: {key}={value}")
        
        logger.info(f"Updated model configuration: {config}")
        return self._model_config.copy()
    
    def is_initialized(self) -> bool:
        """Check if the service is initialized and ready."""
        return self._initialized
    
    async def cleanup(self) -> None:
        """Clean up resources and free memory."""
        logger.info("Cleaning up Image Edit Service...")
        
        try:
            # Clear pipeline components
            if self.pipeline:
                del self.pipeline
                self.pipeline = None
            
            if self.transformer:
                del self.transformer
                self.transformer = None
            
            if self.scheduler:
                del self.scheduler
                self.scheduler = None
            
            # Clear GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Force garbage collection
            gc.collect()
            
            self._initialized = False
            logger.info("Service cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the service.
        
        Returns:
            Health status information
        """
        try:
            gpu_available = torch.cuda.is_available()
            gpu_info = get_gpu_memory_info() if gpu_available else {}
            
            # Test basic functionality if initialized
            if self._initialized and self.pipeline:
                test_status = "ready"
            elif self._initialized:
                test_status = "partial"
            else:
                test_status = "not_ready"
            
            return {
                "service_status": test_status,
                "model_loaded": self._initialized,
                "gpu_available": gpu_available,
                "gpu_info": gpu_info,
                "model_config": self._model_config.copy()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service_status": "error",
                "error": str(e),
                "model_loaded": False,
                "gpu_available": torch.cuda.is_available()
            }