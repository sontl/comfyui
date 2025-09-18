"""
Image processing utilities for Qwen Image Edit Nunchanku API.
Handles image loading, preprocessing, postprocessing, and format conversion.
"""

import base64
import io
import logging
from typing import Optional, Tuple, Union
from urllib.parse import urlparse

import numpy as np
import requests
from PIL import Image, ImageOps
import cv2

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Utility class for image processing operations.
    
    Handles:
    - Loading images from URLs or base64 data
    - Image preprocessing (resizing, normalization)  
    - Image postprocessing (format conversion, encoding)
    - Format validation and conversion
    """
    
    def __init__(self):
        """Initialize the image processor."""
        self.max_download_size = 50 * 1024 * 1024  # 50MB max download
        self.supported_formats = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
        self.max_image_pixels = 89478485  # PIL default limit
        
        # Set PIL max image pixels
        Image.MAX_IMAGE_PIXELS = self.max_image_pixels
    
    async def load_image(self, image_input: Union[str, bytes]) -> Image.Image:
        """
        Load an image from various input formats.
        
        Args:
            image_input: Base64 string, data URL, HTTP URL, or raw bytes
            
        Returns:
            PIL Image object
            
        Raises:
            ValueError: If image format is unsupported or loading fails
            RuntimeError: If download fails or image is corrupted
        """
        try:
            if isinstance(image_input, str):
                # Handle data URLs (data:image/jpeg;base64,...)
                if image_input.startswith('data:image/'):
                    return await self._load_from_data_url(image_input)
                
                # Handle HTTP/HTTPS URLs
                elif image_input.startswith(('http://', 'https://')):
                    return await self._load_from_url(image_input)
                
                # Handle plain base64 strings
                else:
                    return await self._load_from_base64(image_input)
            
            elif isinstance(image_input, bytes):
                return await self._load_from_bytes(image_input)
            
            else:
                raise ValueError(f"Unsupported image input type: {type(image_input)}")
                
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            raise ValueError(f"Failed to load image: {e}")
    
    async def _load_from_data_url(self, data_url: str) -> Image.Image:
        """Load image from data URL format."""
        try:
            # Extract the base64 part after the comma
            if ',' not in data_url:
                raise ValueError("Invalid data URL format")
            
            header, data = data_url.split(',', 1)
            
            # Decode base64 data
            image_data = base64.b64decode(data)
            return await self._load_from_bytes(image_data)
            
        except Exception as e:
            raise ValueError(f"Failed to decode data URL: {e}")
    
    async def _load_from_url(self, url: str) -> Image.Image:
        """Load image from HTTP/HTTPS URL."""
        try:
            # Validate URL
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP/HTTPS URLs are supported")
            
            # Download image with size limit
            response = requests.get(
                url,
                timeout=30,
                stream=True,
                headers={'User-Agent': 'QwenImageEdit/1.0'}
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                raise ValueError(f"URL does not point to an image (content-type: {content_type})")
            
            # Read with size limit
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > self.max_download_size:
                    raise ValueError(f"Image too large (max {self.max_download_size // 1024 // 1024}MB)")
            
            return await self._load_from_bytes(content)
            
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download image from URL: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load image from URL: {e}")
    
    async def _load_from_base64(self, b64_string: str) -> Image.Image:
        """Load image from base64 string."""
        try:
            image_data = base64.b64decode(b64_string)
            return await self._load_from_bytes(image_data)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image: {e}")
    
    async def _load_from_bytes(self, image_bytes: bytes) -> Image.Image:
        """Load image from raw bytes."""
        try:
            # Create PIL Image from bytes
            image = Image.open(io.BytesIO(image_bytes))
            
            # Validate format
            if image.format not in self.supported_formats:
                logger.warning(f"Image format {image.format} may not be fully supported")
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Verify image is not corrupted
            image.verify()
            
            # Reload image since verify() may have consumed it
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            logger.info(f"Loaded image: {image.size[0]}x{image.size[1]} {image.mode}")
            return image
            
        except Exception as e:
            raise ValueError(f"Failed to process image bytes: {e}")
    
    async def preprocess_image(
        self,
        image: Image.Image,
        max_size: Optional[int] = None,
        maintain_aspect_ratio: bool = True
    ) -> Image.Image:
        """
        Preprocess image for model input.
        
        Args:
            image: Input PIL Image
            max_size: Maximum dimension (width or height)
            maintain_aspect_ratio: Whether to maintain aspect ratio when resizing
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            processed_image = image.copy()
            
            # Apply auto-orientation based on EXIF data
            processed_image = ImageOps.exif_transpose(processed_image)
            
            # Resize if necessary
            if max_size and max(processed_image.size) > max_size:
                processed_image = await self._resize_image(
                    processed_image, 
                    max_size, 
                    maintain_aspect_ratio
                )
            
            # Ensure image dimensions are even (required by some models)
            width, height = processed_image.size
            if width % 2 != 0:
                width -= 1
            if height % 2 != 0:
                height -= 1
            
            if (width, height) != processed_image.size:
                processed_image = processed_image.resize((width, height), Image.Resampling.LANCZOS)
            
            logger.info(f"Preprocessed image to {processed_image.size[0]}x{processed_image.size[1]}")
            return processed_image
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            raise ValueError(f"Image preprocessing failed: {e}")
    
    async def _resize_image(
        self, 
        image: Image.Image, 
        max_size: int, 
        maintain_aspect_ratio: bool
    ) -> Image.Image:
        """Resize image while optionally maintaining aspect ratio."""
        width, height = image.size
        
        if maintain_aspect_ratio:
            # Calculate new dimensions maintaining aspect ratio
            if width > height:
                new_width = max_size
                new_height = int((height * max_size) / width)
            else:
                new_height = max_size
                new_width = int((width * max_size) / height)
        else:
            # Square resize
            new_width = new_height = max_size
        
        # Ensure dimensions are even
        new_width = new_width - (new_width % 2)
        new_height = new_height - (new_height % 2)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    async def postprocess_image(
        self,
        image: Image.Image,
        format: str = "JPEG",
        quality: int = 95,
        optimize: bool = True
    ) -> str:
        """
        Postprocess and encode image to base64.
        
        Args:
            image: PIL Image to encode
            format: Output format (JPEG, PNG, WEBP)
            quality: Compression quality (1-100, only for JPEG/WEBP)
            optimize: Whether to optimize the output
            
        Returns:
            Base64 encoded image string
        """
        try:
            # Validate format
            format = format.upper()
            if format not in self.supported_formats:
                logger.warning(f"Unsupported format {format}, using JPEG")
                format = "JPEG"
            
            # Convert image if necessary
            output_image = image.copy()
            
            # Handle alpha channel for JPEG
            if format == "JPEG" and output_image.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', output_image.size, (255, 255, 255))
                if output_image.mode == 'P':
                    output_image = output_image.convert('RGBA')
                background.paste(output_image, mask=output_image.split()[-1] if output_image.mode in ('RGBA', 'LA') else None)
                output_image = background
            
            # Prepare save parameters
            save_kwargs = {'format': format, 'optimize': optimize}
            
            if format in ('JPEG', 'WEBP'):
                save_kwargs['quality'] = quality
            
            # Save to bytes buffer
            buffer = io.BytesIO()
            output_image.save(buffer, **save_kwargs)
            image_bytes = buffer.getvalue()
            
            # Encode to base64
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            
            logger.info(f"Encoded image: {len(image_bytes)} bytes -> {len(base64_string)} base64 chars")
            return base64_string
            
        except Exception as e:
            logger.error(f"Image postprocessing failed: {e}")
            raise ValueError(f"Image postprocessing failed: {e}")
    
    def get_image_info(self, image: Image.Image) -> dict:
        """
        Get information about an image.
        
        Args:
            image: PIL Image
            
        Returns:
            Dictionary with image information
        """
        try:
            return {
                "size": image.size,
                "mode": image.mode,
                "format": getattr(image, 'format', None),
                "has_transparency": image.mode in ('RGBA', 'LA', 'P'),
                "megapixels": round((image.size[0] * image.size[1]) / 1000000, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get image info: {e}")
            return {}
    
    async def validate_image(self, image: Image.Image) -> bool:
        """
        Validate image for processing.
        
        Args:
            image: PIL Image to validate
            
        Returns:
            True if image is valid for processing
            
        Raises:
            ValueError: If image is invalid
        """
        try:
            # Check dimensions
            width, height = image.size
            if width < 1 or height < 1:
                raise ValueError("Image dimensions must be positive")
            
            if width > 4096 or height > 4096:
                raise ValueError("Image dimensions too large (max 4096x4096)")
            
            # Check pixel count
            total_pixels = width * height
            if total_pixels > self.max_image_pixels:
                raise ValueError(f"Image has too many pixels (max {self.max_image_pixels})")
            
            # Check mode
            if image.mode not in ('RGB', 'RGBA', 'L', 'P'):
                raise ValueError(f"Unsupported image mode: {image.mode}")
            
            return True
            
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            raise ValueError(f"Image validation failed: {e}")
    
    async def convert_opencv_to_pil(self, cv_image: np.ndarray) -> Image.Image:
        """
        Convert OpenCV image (numpy array) to PIL Image.
        
        Args:
            cv_image: OpenCV image as numpy array
            
        Returns:
            PIL Image
        """
        try:
            # Convert BGR to RGB if needed
            if len(cv_image.shape) == 3 and cv_image.shape[2] == 3:
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            
            return Image.fromarray(cv_image)
            
        except Exception as e:
            logger.error(f"OpenCV to PIL conversion failed: {e}")
            raise ValueError(f"OpenCV to PIL conversion failed: {e}")
    
    async def convert_pil_to_opencv(self, pil_image: Image.Image) -> np.ndarray:
        """
        Convert PIL Image to OpenCV format (numpy array).
        
        Args:
            pil_image: PIL Image
            
        Returns:
            OpenCV image as numpy array
        """
        try:
            # Convert to RGB if not already
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Convert to numpy array
            cv_image = np.array(pil_image)
            
            # Convert RGB to BGR for OpenCV
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
            
            return cv_image
            
        except Exception as e:
            logger.error(f"PIL to OpenCV conversion failed: {e}")
            raise ValueError(f"PIL to OpenCV conversion failed: {e}")