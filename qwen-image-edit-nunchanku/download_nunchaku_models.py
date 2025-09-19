#!/usr/bin/env python3
"""
Script to download Nunchaku quantized models (r128 only).
These are self-contained quantized versions of Qwen Image Edit that don't require base model files.
"""

from huggingface_hub import hf_hub_download
import os

def main():
    print('Downloading Nunchaku quantized models (r128 only)...')
    
    # Model configurations to download (r128 only, no 4-step models)
    models = [
        ('nunchaku-tech/nunchaku-qwen-image-edit', 'svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors'),
        ('nunchaku-tech/nunchaku-qwen-image-edit', 'svdq-int4_r128-qwen-image-edit.safetensors'),
    ]
    
    cache_dir = '/app/models'
    os.makedirs(cache_dir, exist_ok=True)
    
    downloaded_count = 0
    failed_count = 0
    
    for repo_id, filename in models:
        try:
            print(f'Downloading {filename}...')
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                cache_dir=cache_dir,
                local_dir=f'{cache_dir}/nunchaku-qwen-image-edit',
                local_dir_use_symlinks=False
            )
            print(f'✓ Downloaded {filename}')
            downloaded_count += 1
        except Exception as e:
            print(f'✗ Warning: Failed to download {filename}: {e}')
            failed_count += 1
            continue
    
    print(f'Nunchaku model downloads completed: {downloaded_count} successful, {failed_count} failed')
    
    if downloaded_count == 0:
        raise RuntimeError("No models were downloaded successfully")

if __name__ == '__main__':
    main()