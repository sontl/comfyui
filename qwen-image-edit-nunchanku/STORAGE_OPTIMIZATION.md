# Storage Optimization Summary

## Changes Made

To reduce Docker image size and storage requirements, the following optimizations have been implemented:

### 🗂️ **Model Selection Optimization**

#### **Removed Models:**
- ❌ All r64 models (lower quality, not needed)
- ❌ All 4-step models (too fast, quality compromise)

#### **Kept Models:**
- ✅ `svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors` (8-step, rank 128)
- ✅ `svdq-int4_r128-qwen-image-edit.safetensors` (original, rank 128)
- ✅ Base Qwen Image Edit model

### 📊 **Storage Impact**

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| Nunchaku Models | ~8-10 GB | ~2-4 GB | ~6 GB |
| Base Model | ~5-7 GB | ~5-7 GB | 0 GB |
| **Total** | **~15-20 GB** | **~8-11 GB** | **~7-9 GB** |

**Storage Reduction: ~45-50%**

### 🎯 **Quality vs Size Trade-off**

#### **Maintained Quality:**
- **Rank 128**: Highest quality quantization level
- **8-step Lightning**: Optimal balance of speed and quality
- **Original Model**: Full quality fallback option

#### **Removed Lower Priority:**
- **Rank 64**: Lower quality, significant size savings
- **4-step Models**: Too aggressive speed optimization

### ⚙️ **Configuration Updates**

#### **API Configuration:**
```python
{
    "supported_ranks": [128],  # Only r128
    "default_rank": 128,       # Fixed to highest quality
    "default_steps": 8,        # Optimal speed/quality balance
}
```

#### **Model Loading Priority:**
1. **8-step Lightning (r128)** - Primary choice
2. **Original (r128)** - Fallback for maximum quality
3. **HuggingFace Download** - Last resort

### 🔧 **Technical Changes**

#### **Dockerfile:**
- Removed r64 model downloads
- Removed 4-step model downloads
- Kept only essential r128 models

#### **Model Utils:**
- Updated validation to only support rank 128
- Simplified model selection logic
- Enhanced error handling for unsupported ranks

#### **Service Configuration:**
- Fixed supported_ranks to [128]
- Added warnings for unsupported rank requests
- Optimized memory usage for single rank

### 📈 **Benefits**

#### **Storage Benefits:**
- **45-50% smaller** Docker image
- **Faster builds** (fewer downloads)
- **Lower storage costs** in production

#### **Performance Benefits:**
- **Consistent quality** (only high-quality models)
- **Simplified selection** (no rank decision needed)
- **Optimized memory usage** (single rank optimization)

#### **Operational Benefits:**
- **Simpler configuration** (fewer options to manage)
- **Predictable behavior** (consistent model selection)
- **Easier troubleshooting** (fewer variables)

### 🚀 **Recommended Usage**

#### **For Best Quality:**
```python
{
    "rank": 128,           # Only supported rank
    "num_inference_steps": 8,  # Recommended steps
}
```

#### **For Fastest Speed:**
```python
{
    "rank": 128,           # Only supported rank  
    "num_inference_steps": 8,  # Still recommended (lightning model)
}
```

### 🔍 **Verification**

#### **Check Available Models:**
```bash
python3 verify_models.py
```

#### **Expected Output:**
```
✓ Base Qwen model found
✓ svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors: X.X MB
✓ svdq-int4_r128-qwen-image-edit.safetensors: X.X MB
Found 2/2 Nunchaku models
Total model cache size: ~8-11 GB
```

### 📝 **Migration Notes**

#### **Breaking Changes:**
- **Rank 64 no longer supported** - API will warn and use rank 128
- **4-step models removed** - Use 8-step for best performance

#### **Backward Compatibility:**
- API requests with rank 64 will automatically use rank 128
- Existing configurations will work with warnings
- No changes needed for rank 128 usage

This optimization maintains the highest quality while significantly reducing storage requirements, making the Docker image more efficient for production deployment.