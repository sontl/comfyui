"""
Simplified API data models for Qwen Image Edit Nunchanku API.
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ImageEditRequest(BaseModel):
    image: Union[str, HttpUrl]
    prompt: str
    negative_prompt: str = ""
    num_inference_steps: int = 8
    true_cfg_scale: float = 1.0
    seed: Optional[int] = None
    rank: int = 128
    
    @field_validator('rank')
    @classmethod
    def validate_rank(cls, v):
        if v not in [64, 128]:
            raise ValueError('rank must be either 64 or 128')
        return v


class ModelInfo(BaseModel):
    steps: int
    rank: int
    model_version: str
    inference_time: Optional[float] = None
    gpu_memory_used: Optional[str] = None


class ImageEditResponse(BaseModel):
    success: bool
    edited_image: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float
    model_info: Union[ModelInfo, Dict[str, Any]] = {}
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    message: Optional[str] = None
    model_loaded: Optional[bool] = None
    gpu_available: Optional[bool] = None
    gpu_memory_info: Optional[Dict[str, Any]] = None
    timestamp: float
    uptime: Optional[float] = None


class ModelInfoResponse(BaseModel):
    model_name: str
    model_version: str
    supported_ranks: List[int]
    default_steps: int
    max_steps: int
    gpu_memory_usage: Optional[str] = None
    model_config: Dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
    traceback: Optional[str] = None


class BatchImageEditRequest(BaseModel):
    images: List[Union[str, HttpUrl]]
    prompt: str
    negative_prompt: str = ""
    num_inference_steps: int = 8
    true_cfg_scale: float = 1.0
    seed: Optional[int] = None
    rank: int = 128
    
    @field_validator('rank')
    @classmethod
    def validate_rank(cls, v):
        if v not in [64, 128]:
            raise ValueError('rank must be either 64 or 128')
        return v


class BatchImageEditResponse(BaseModel):
    success: bool
    results: List[ImageEditResponse] = []
    total_processing_time: float
    processed_count: int
    failed_count: int


class GPUInfo(BaseModel):
    device_name: str
    total_memory: str
    allocated_memory: str
    cached_memory: str
    free_memory: str
    utilization: Optional[float] = None


class SystemInfo(BaseModel):
    python_version: str
    pytorch_version: str
    cuda_version: Optional[str] = None
    gpu_info: Optional[GPUInfo] = None
    memory_usage: Dict[str, str]