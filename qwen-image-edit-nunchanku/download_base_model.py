#!/usr/bin/env python3
"""
Script to download the base Qwen Image Edit model.
"""

from huggingface_hub import snapshot_download
import os

def main():
    print('Downloading base Qwen Image Edit model...')
    
    try:
        snapshot_download(
            repo_id='Qwen/Qwen-Image-Edit',
            cache_dir='/app/models',
            local_dir='/app/models/Qwen--Qwen-Image-Edit',
            local_dir_use_symlinks=False
        )
        print('Base model download completed successfully')
    except Exception as e:
        print(f'Error downloading base model: {e}')
        raise

if __name__ == '__main__':
    main()