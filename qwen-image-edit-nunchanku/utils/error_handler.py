"""
Error handling utilities for Qwen Image Edit Nunchanku API.
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from models.api_models import ErrorResponse

logger = logging.getLogger(__name__)


class QwenAPIException(Exception):
    """Base exception for Qwen API errors."""
    
    def __init__(self, message: str, error_code: str = "QWEN_ERROR", details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.request_id = str(uuid.uuid4())


class ModelNotLoadedException(QwenAPIException):
    """Raised when model is not loaded or available."""
    
    def __init__(self, message: str = "Model not loaded"):
        super().__init__(message, "MODEL_NOT_LOADED")


class ImageProcessingException(QwenAPIException):
    """Raised when image processing fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "IMAGE_PROCESSING_ERROR", details)


class ModelInferenceException(QwenAPIException):
    """Raised when model inference fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "MODEL_INFERENCE_ERROR", details)


class GPUMemoryException(QwenAPIException):
    """Raised when GPU memory issues occur."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "GPU_MEMORY_ERROR", details)


class ValidationException(QwenAPIException):
    """Raised when request validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


def create_error_response(
    error: Exception,
    request_id: Optional[str] = None,
    include_traceback: bool = False
) -> ErrorResponse:
    """
    Create standardized error response.
    
    Args:
        error: Exception that occurred
        request_id: Request ID for tracking
        include_traceback: Whether to include traceback in response
        
    Returns:
        ErrorResponse object
    """
    if isinstance(error, QwenAPIException):
        error_type = error.error_code
        detail = error.message
        req_id = error.request_id
    elif isinstance(error, ValidationError):
        error_type = "VALIDATION_ERROR"
        detail = str(error)
        req_id = request_id or str(uuid.uuid4())
    elif isinstance(error, HTTPException):
        error_type = f"HTTP_{error.status_code}"
        detail = error.detail
        req_id = request_id or str(uuid.uuid4())
    else:
        error_type = type(error).__name__
        detail = str(error)
        req_id = request_id or str(uuid.uuid4())
    
    response = ErrorResponse(
        error=error_type,
        detail=detail,
        timestamp=datetime.now(),
        request_id=req_id
    )
    
    if include_traceback:
        response.traceback = traceback.format_exc()
    
    return response


async def qwen_exception_handler(request: Request, exc: QwenAPIException):
    """Handle QwenAPIException instances."""
    logger.error(f"QwenAPIException: {exc.error_code} - {exc.message}")
    
    error_response = create_error_response(exc)
    
    # Determine HTTP status code based on error type
    status_code_map = {
        "MODEL_NOT_LOADED": 503,
        "IMAGE_PROCESSING_ERROR": 400,
        "MODEL_INFERENCE_ERROR": 500,
        "GPU_MEMORY_ERROR": 507,
        "VALIDATION_ERROR": 422
    }
    
    status_code = status_code_map.get(exc.error_code, 500)
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    logger.error(f"Validation error: {exc}")
    
    # Format validation errors
    formatted_errors = []
    for error in exc.errors():
        formatted_errors.append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    error_response = create_error_response(
        exc,
        include_traceback=False
    )
    error_response.detail = f"Validation failed: {formatted_errors}"
    
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump()
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    
    error_response = create_error_response(exc)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
    logger.error(traceback.format_exc())
    
    error_response = create_error_response(
        exc,
        include_traceback=False  # Don't expose internal tracebacks in production
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


def setup_error_handlers(app: FastAPI):
    """
    Setup error handlers for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # Custom exception handlers
    app.add_exception_handler(QwenAPIException, qwen_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers configured")


def handle_gpu_memory_error(func):
    """
    Decorator to handle GPU memory errors gracefully.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function with GPU memory error handling
    """
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except RuntimeError as e:
            error_msg = str(e).lower()
            if "out of memory" in error_msg or "cuda" in error_msg:
                # Clear GPU memory and retry once
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                logger.warning(f"GPU memory error, cleared cache and retrying: {e}")
                
                try:
                    return await func(*args, **kwargs)
                except Exception as retry_error:
                    raise GPUMemoryException(
                        f"GPU memory error persisted after retry: {retry_error}",
                        details={"original_error": str(e), "retry_error": str(retry_error)}
                    )
            else:
                raise
    
    return wrapper


def safe_execute(func, *args, default=None, **kwargs):
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Function arguments
        default: Default value to return on error
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Safe execution failed for {func.__name__}: {e}")
        return default


class ErrorTracker:
    """Track and analyze errors for monitoring and debugging."""
    
    def __init__(self):
        self.error_counts = {}
        self.recent_errors = []
        self.max_recent_errors = 100
    
    def track_error(self, error: Exception, context: Dict[str, Any] = None):
        """
        Track an error occurrence.
        
        Args:
            error: Exception that occurred
            context: Additional context information
        """
        error_type = type(error).__name__
        
        # Update error counts
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Add to recent errors
        error_info = {
            "type": error_type,
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {}
        }
        
        self.recent_errors.append(error_info)
        
        # Keep only recent errors
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
        
        logger.debug(f"Tracked error: {error_type} (total: {self.error_counts[error_type]})")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "error_counts": self.error_counts.copy(),
            "recent_errors": self.recent_errors[-10:],  # Last 10 errors
            "total_errors": sum(self.error_counts.values())
        }
    
    def clear_stats(self):
        """Clear error statistics."""
        self.error_counts.clear()
        self.recent_errors.clear()


# Global error tracker instance
error_tracker = ErrorTracker()


def log_and_track_error(error: Exception, context: Dict[str, Any] = None):
    """
    Log and track an error.
    
    Args:
        error: Exception that occurred
        context: Additional context information
    """
    logger.error(f"Error occurred: {type(error).__name__}: {error}")
    
    if context:
        logger.error(f"Error context: {context}")
    
    error_tracker.track_error(error, context)


def create_error_context(request_id: str = None, **kwargs) -> Dict[str, Any]:
    """
    Create error context dictionary.
    
    Args:
        request_id: Request ID
        **kwargs: Additional context fields
        
    Returns:
        Error context dictionary
    """
    context = {
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id or str(uuid.uuid4())
    }
    context.update(kwargs)
    return context