"""
Logging configuration for Qwen Image Edit Nunchanku API.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: Optional[str] = None,
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup application logger with console and file handlers.
    
    Args:
        name: Logger name (defaults to root logger)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file path (optional)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)
    
    # Clear existing handlers to avoid duplication
    logger.handlers.clear()
    
    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def setup_uvicorn_logging():
    """
    Configure uvicorn logging to integrate with application logging.
    """
    # Configure uvicorn loggers
    uvicorn_loggers = [
        "uvicorn",
        "uvicorn.error", 
        "uvicorn.access"
    ]
    
    for logger_name in uvicorn_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        
        # Remove default handlers to avoid duplication
        logger.handlers.clear()
        logger.propagate = True


def log_system_info():
    """Log system information at startup."""
    logger = get_logger(__name__)
    
    try:
        import platform
        import torch
        
        logger.info("=== System Information ===")
        logger.info(f"Python version: {platform.python_version()}")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"PyTorch version: {torch.__version__}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            logger.info(f"CUDA version: {torch.version.cuda}")
            logger.info(f"GPU count: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        
        logger.info("=== End System Information ===")
        
    except Exception as e:
        logger.warning(f"Failed to log system info: {e}")


def setup_request_logging():
    """Setup request logging for FastAPI."""
    logger = get_logger("qwen_api.requests")
    
    class RequestLoggingMiddleware:
        def __init__(self, app):
            self.app = app
            
        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                start_time = datetime.now()
                
                # Log request
                logger.info(f"Request: {scope['method']} {scope['path']}")
                
                async def send_wrapper(message):
                    if message["type"] == "http.response.start":
                        end_time = datetime.now()
                        duration = (end_time - start_time).total_seconds()
                        status_code = message["status"]
                        
                        logger.info(f"Response: {status_code} - {duration:.3f}s")
                    
                    await send(message)
                
                await self.app(scope, receive, send_wrapper)
            else:
                await self.app(scope, receive, send)
    
    return RequestLoggingMiddleware


def log_performance_metrics(operation: str, duration: float, **kwargs):
    """
    Log performance metrics for operations.
    
    Args:
        operation: Operation name
        duration: Operation duration in seconds
        **kwargs: Additional metrics to log
    """
    logger = get_logger("qwen_api.performance")
    
    metrics = [f"duration={duration:.3f}s"]
    for key, value in kwargs.items():
        metrics.append(f"{key}={value}")
    
    logger.info(f"PERFORMANCE [{operation}] {' '.join(metrics)}")


def log_gpu_metrics():
    """Log current GPU metrics."""
    logger = get_logger("qwen_api.gpu")
    
    try:
        from utils.gpu_utils import get_gpu_memory_info, get_gpu_utilization
        
        memory_info = get_gpu_memory_info()
        utilization = get_gpu_utilization()
        
        if "error" not in memory_info:
            logger.info(f"GPU Memory: {memory_info.get('allocated_memory', 'N/A')} / "
                       f"{memory_info.get('total_memory', 'N/A')} "
                       f"({memory_info.get('utilization_percent', 'N/A')})")
        
        if utilization is not None:
            logger.info(f"GPU Utilization: {utilization}%")
            
    except Exception as e:
        logger.debug(f"Failed to log GPU metrics: {e}")


class StructuredLogger:
    """
    Structured logger for better log analysis and monitoring.
    """
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def log_request(self, method: str, path: str, **kwargs):
        """Log HTTP request."""
        self.logger.info(f"REQUEST {method} {path}", extra=kwargs)
    
    def log_response(self, status_code: int, duration: float, **kwargs):
        """Log HTTP response."""
        self.logger.info(f"RESPONSE {status_code} {duration:.3f}s", extra=kwargs)
    
    def log_error(self, error: Exception, context: str = "", **kwargs):
        """Log error with context."""
        self.logger.error(f"ERROR [{context}] {type(error).__name__}: {error}", extra=kwargs)
    
    def log_model_operation(self, operation: str, duration: float, **kwargs):
        """Log model operation."""
        self.logger.info(f"MODEL [{operation}] {duration:.3f}s", extra=kwargs)
    
    def log_image_processing(self, operation: str, image_size: tuple, duration: float, **kwargs):
        """Log image processing operation."""
        self.logger.info(f"IMAGE [{operation}] {image_size[0]}x{image_size[1]} {duration:.3f}s", extra=kwargs)


def configure_logging_from_env():
    """Configure logging based on environment variables."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")
    
    # Enable debug logging in development
    if os.getenv("ENVIRONMENT") == "development":
        log_level = "DEBUG"
    
    # Setup main logger
    setup_logger(
        level=log_level,
        log_file=log_file
    )
    
    # Setup uvicorn logging
    setup_uvicorn_logging()
    
    # Log system info at startup
    log_system_info()


def get_log_config() -> dict:
    """
    Get logging configuration dictionary for uvicorn.
    
    Returns:
        Dictionary with logging configuration
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "access": {
                "format": "%(asctime)s - %(levelname)s - %(client_addr)s - %(request_line)s - %(status_code)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout"
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout"
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False}
        }
    }