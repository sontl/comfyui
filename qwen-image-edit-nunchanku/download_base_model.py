#!/usr/bin/env python3
"""
Script to download only essential files from the base Qwen Image Edit model.
"""

from huggingface_hub import hf_hub_download
import os

def main():
    print('Downloading essential Qwen Image Edit model files...')
    
    # Only download essential files, not the entire repository
    essential_files = [
        'config.json',
        'model.safetensors.index.json',
        'tokenizer.json',
        'tokenizer_config.json',
        'generation_config.json'
    ]
    
    repo_id = 'Qwen/Qwen-Image-Edit'
    local_dir = '/app/models/Qwen--Qwen-Image-Edit'
    os.makedirs(local_dir, exist_ok=True)
    
    downloaded_count = 0
    
    for filename in essential_files:
        try:
            print(f'Downloading {filename}...')
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                cache_dir='/app/models',
                local_dir=local_dir,
                local_dir_use_symlinks=False
            )
            print(f'✓ Downloaded {filename}')
            downloaded_count += 1
        except Exception as e:
            print(f'Warning: Could not download {filename}: {e}')
            continue
    
    print(f'Base model download completed: {downloaded_count}/{len(essential_files)} files downloaded')
    
    if downloaded_count == 0:
        print('Warning: No base model files downloaded, but Nunchaku models should be sufficient')

if __name__ == '__main__':
    main()