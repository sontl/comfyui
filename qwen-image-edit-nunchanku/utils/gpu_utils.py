"""
GPU utilities for memory management and optimization.
"""

import gc
import logging
import subprocess
from typing import Dict, Optional

import torch

logger = logging.getLogger(__name__)


def get_gpu_memory_info() -> Dict[str, str]:
    """
    Get GPU memory information.
    
    Returns:
        Dictionary with GPU memory stats
    """
    if not torch.cuda.is_available():
        return {"status": "CUDA not available"}
    
    try:
        device = torch.cuda.current_device()
        
        # Get memory info from PyTorch
        allocated = torch.cuda.memory_allocated(device)
        cached = torch.cuda.memory_reserved(device)
        total = torch.cuda.get_device_properties(device).total_memory
        free = total - allocated
        
        # Convert to human readable format
        def bytes_to_mb(bytes_val):
            return f"{bytes_val / 1024 / 1024:.1f}MB"
        
        def bytes_to_gb(bytes_val):
            return f"{bytes_val / 1024 / 1024 / 1024:.1f}GB"
        
        return {
            "device_name": torch.cuda.get_device_name(device),
            "total_memory": bytes_to_gb(total),
            "allocated_memory": bytes_to_gb(allocated),
            "cached_memory": bytes_to_gb(cached),
            "free_memory": bytes_to_gb(free),
            "utilization_percent": f"{(allocated / total) * 100:.1f}%"
        }
        
    except Exception as e:
        logger.error(f"Failed to get GPU memory info: {e}")
        return {"error": str(e)}


def get_gpu_utilization() -> Optional[float]:
    """
    Get GPU utilization percentage using nvidia-smi.
    
    Returns:
        GPU utilization percentage or None if unavailable
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return float(result.stdout.strip())
        
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.debug(f"Could not get GPU utilization: {e}")
    
    return None


def optimize_gpu_memory():
    """
    Optimize GPU memory usage with various PyTorch settings.
    """
    if not torch.cuda.is_available():
        logger.info("CUDA not available, skipping GPU optimization")
        return
    
    try:
        # Clear cache
        torch.cuda.empty_cache()
        
        # Set memory fraction (use 90% of available GPU memory)
        torch.cuda.set_per_process_memory_fraction(0.9)
        
        # Enable memory efficient operations
        if hasattr(torch.backends.cuda, 'enable_flash_sdp'):
            torch.backends.cuda.enable_flash_sdp(True)
        
        if hasattr(torch.backends.cuda, 'enable_math_sdp'):
            torch.backends.cuda.enable_math_sdp(True)
        
        # Set CUDA optimization flags
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        
        logger.info("Applied GPU memory optimizations")
        
    except Exception as e:
        logger.warning(f"Failed to apply GPU optimizations: {e}")


def clear_gpu_memory():
    """
    Clear GPU memory and run garbage collection.
    """
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        
        gc.collect()
        
        logger.debug("Cleared GPU memory and ran garbage collection")
        
    except Exception as e:
        logger.warning(f"Error clearing GPU memory: {e}")


def get_optimal_batch_size(base_batch_size: int = 1) -> int:
    """
    Determine optimal batch size based on available GPU memory.
    
    Args:
        base_batch_size: Base batch size to scale from
        
    Returns:
        Optimal batch size
    """
    if not torch.cuda.is_available():
        return base_batch_size
    
    try:
        device = torch.cuda.current_device()
        total_memory = torch.cuda.get_device_properties(device).total_memory
        total_gb = total_memory / 1024 / 1024 / 1024
        
        # Simple heuristic: larger GPUs can handle larger batches
        if total_gb >= 20:
            return base_batch_size * 4
        elif total_gb >= 12:
            return base_batch_size * 2
        elif total_gb >= 8:
            return base_batch_size
        else:
            return 1  # Conservative for smaller GPUs
            
    except Exception as e:
        logger.warning(f"Failed to determine optimal batch size: {e}")
        return base_batch_size


def monitor_gpu_memory(operation_name: str = "operation"):
    """
    Context manager to monitor GPU memory usage during an operation.
    
    Args:
        operation_name: Name of the operation being monitored
    """
    class GPUMemoryMonitor:
        def __init__(self, op_name):
            self.op_name = op_name
            self.start_memory = None
            
        def __enter__(self):
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                self.start_memory = torch.cuda.memory_allocated()
                logger.debug(f"Starting {self.op_name} - GPU memory: {self.start_memory / 1024 / 1024:.1f}MB")
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if torch.cuda.is_available() and self.start_memory is not None:
                torch.cuda.synchronize()
                end_memory = torch.cuda.memory_allocated()
                diff = end_memory - self.start_memory
                logger.debug(f"Finished {self.op_name} - GPU memory: {end_memory / 1024 / 1024:.1f}MB "
                           f"(change: {diff / 1024 / 1024:+.1f}MB)")
    
    return GPUMemoryMonitor(operation_name)


def setup_cuda_optimizations():
    """
    Setup CUDA optimizations for best performance.
    """
    if not torch.cuda.is_available():
        return
    
    try:
        # Enable TensorFloat-32 (TF32) for better performance on RTX 30xx and newer
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        
        # Enable cuDNN benchmark mode for consistent input sizes
        torch.backends.cudnn.benchmark = True
        
        # Disable deterministic mode for better performance
        torch.backends.cudnn.deterministic = False
        
        logger.info("Applied CUDA performance optimizations")
        
    except Exception as e:
        logger.warning(f"Failed to setup CUDA optimizations: {e}")


def check_gpu_requirements() -> Dict[str, bool]:
    """
    Check if GPU meets requirements for Qwen Image Edit.
    
    Returns:
        Dictionary with requirement check results
    """
    checks = {
        "cuda_available": False,
        "memory_sufficient": False,
        "compute_capability_ok": False,
        "driver_compatible": False
    }
    
    if not torch.cuda.is_available():
        return checks
    
    try:
        device = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(device)
        
        checks["cuda_available"] = True
        
        # Check memory (minimum 6GB recommended)
        total_gb = props.total_memory / 1024 / 1024 / 1024
        checks["memory_sufficient"] = total_gb >= 6
        
        # Check compute capability (minimum 6.0 for modern features)
        compute_capability = props.major + props.minor / 10
        checks["compute_capability_ok"] = compute_capability >= 6.0
        
        # Check driver compatibility (basic check)
        try:
            torch.cuda.synchronize()
            checks["driver_compatible"] = True
        except Exception:
            checks["driver_compatible"] = False
        
        logger.info(f"GPU checks: {checks}")
        
    except Exception as e:
        logger.error(f"GPU requirement check failed: {e}")
    
    return checks


def estimate_memory_usage(image_size: tuple, batch_size: int = 1, rank: int = 128) -> int:
    """
    Estimate GPU memory usage for given parameters.
    
    Args:
        image_size: (width, height) tuple
        batch_size: Number of images in batch
        rank: Model rank
        
    Returns:
        Estimated memory usage in bytes
    """
    width, height = image_size
    pixels = width * height
    
    # Base memory estimates (very rough)
    base_model_memory = 3 * 1024 * 1024 * 1024  # 3GB base model
    
    # Memory per image (depends on resolution)
    memory_per_pixel = 16 if rank == 128 else 12  # bytes per pixel
    image_memory = pixels * memory_per_pixel * batch_size
    
    # Additional overhead
    overhead = 1024 * 1024 * 1024  # 1GB overhead
    
    total_estimate = base_model_memory + image_memory + overhead
    
    return total_estimate