# Ollama Performance Optimization Guide

## 🚀 Overview

This guide provides comprehensive performance optimization settings for your Knowledge Base Agent's Ollama integration. These optimizations can dramatically improve processing speed, reduce memory usage, and enhance output quality.

## 📊 Quick Performance Gains

### **High-Impact Settings** (Set these first!)

```bash
# === GPU Optimization (Most Important) ===
OLLAMA_NUM_GPU=-1                    # Auto-detect GPU layers
OLLAMA_MAIN_GPU=0                    # Use primary GPU
OLLAMA_KEEP_ALIVE=10m                # Keep models loaded longer
OLLAMA_USE_MMAP=true                 # Faster model loading
OLLAMA_ADAPTIVE_BATCH_SIZE=true      # Auto-adjust batch size

# === Quality Improvements ===
OLLAMA_REPEAT_PENALTY=1.1           # Reduce repetitive output
OLLAMA_TOP_K=40                     # Better token selection
OLLAMA_MIN_P=0.05                   # Quality threshold
```

## 🖥️ Hardware-Specific Configurations

### **High-End System (32GB+ GPU Memory)**
```bash
# GPU Configuration
OLLAMA_NUM_GPU=-1                    # Use all GPU layers
OLLAMA_NUM_BATCH=2048               # Large batch size
OLLAMA_NUM_CTX=8192                 # Extended context
OLLAMA_NUM_THREADS=0                # Auto CPU threads
OLLAMA_USE_MMAP=true
OLLAMA_USE_MLOCK=false              # May cause issues with large models

# Memory Management
OLLAMA_KEEP_ALIVE=30m               # Keep models loaded longer
OLLAMA_LOW_VRAM=false               # Full performance mode

# Performance Tuning
MAX_CONCURRENT_REQUESTS=2            # Higher concurrency
REQUEST_TIMEOUT=300                  # Longer timeout for complex tasks
```

### **Mid-Range System (16-24GB GPU Memory)**
```bash
# GPU Configuration
OLLAMA_NUM_GPU=-1                    # Use available GPU layers
OLLAMA_NUM_BATCH=1024               # Moderate batch size
OLLAMA_NUM_CTX=4096                 # Standard context
OLLAMA_USE_MMAP=true
OLLAMA_LOW_VRAM=false

# Memory Management
OLLAMA_KEEP_ALIVE=15m               # Moderate keep alive
OLLAMA_ADAPTIVE_BATCH_SIZE=true     # Auto-adjust for memory

# Performance Tuning
MAX_CONCURRENT_REQUESTS=1            # Conservative concurrency
REQUEST_TIMEOUT=240
```

### **Budget System (8-12GB GPU Memory)**
```bash
# GPU Configuration
OLLAMA_NUM_GPU=-1                    # Use available layers
OLLAMA_NUM_BATCH=512                # Smaller batch size
OLLAMA_NUM_CTX=2048                 # Reduced context
OLLAMA_LOW_VRAM=true                # Memory-efficient mode
OLLAMA_USE_MMAP=true

# Memory Management
OLLAMA_KEEP_ALIVE=5m                # Shorter keep alive
OLLAMA_ADAPTIVE_BATCH_SIZE=true

# Performance Tuning
MAX_CONCURRENT_REQUESTS=1
REQUEST_TIMEOUT=180
```

### **CPU-Only System**
```bash
# CPU Configuration
OLLAMA_NUM_GPU=0                    # Force CPU-only
OLLAMA_NUM_THREADS=8                # Use 8 CPU threads (adjust for your CPU)
OLLAMA_NUM_BATCH=128                # Small batch size
OLLAMA_NUM_CTX=2048                 # Limited context
OLLAMA_USE_MMAP=true

# Memory Management
OLLAMA_KEEP_ALIVE=2m                # Quick unload
OLLAMA_LOW_VRAM=true

# Performance Tuning
MAX_CONCURRENT_REQUESTS=1
REQUEST_TIMEOUT=600                 # Longer timeout for CPU processing
```

## 🎯 Task-Specific Optimizations

### **Synthesis Generation** (High Quality)
```bash
# Quality Settings
OLLAMA_REPEAT_PENALTY=1.2           # Reduce repetition
OLLAMA_TOP_K=30                     # Focused generation
OLLAMA_MIN_P=0.1                    # Higher quality threshold
OLLAMA_NUM_CTX=8192                 # Extended context for synthesis

# Reproducibility
OLLAMA_SEED=42                      # Consistent results
```

### **Categorization** (Speed + Consistency)
```bash
# Speed Settings
OLLAMA_NUM_CTX=2048                 # Smaller context for speed
OLLAMA_TOP_K=20                     # Faster token selection
OLLAMA_REPEAT_PENALTY=1.0           # No penalty needed

# Consistency
OLLAMA_SEED=123                     # Reproducible categorization
```

### **Vision Processing**
```bash
# Vision-Specific Settings
OLLAMA_VISION_MODEL_GPU_LAYERS=-1   # Use all GPU for vision
OLLAMA_NUM_BATCH=256                # Smaller batches for images
OLLAMA_KEEP_ALIVE=15m               # Keep vision model loaded
```

### **Embeddings**
```bash
# Embedding Optimization
OLLAMA_EMBEDDING_MODEL_GPU_LAYERS=-1  # Use GPU for embeddings
OLLAMA_NUM_BATCH=1024               # Larger batches for embeddings
OLLAMA_KEEP_ALIVE=10m               # Keep embedding model loaded
```

## 🔧 All Available Environment Variables

### **GPU & Hardware Control**
| Variable | Default | Description | Recommended Values |
|----------|---------|-------------|-------------------|
| `OLLAMA_NUM_GPU` | `-1` | GPU layers to load (-1=auto, 0=CPU) | `-1` (auto) |
| `OLLAMA_MAIN_GPU` | `0` | Primary GPU device | `0` |
| `OLLAMA_LOW_VRAM` | `false` | Low VRAM mode | `true` for <16GB GPU |
| `OLLAMA_GPU_SPLIT` | `""` | Multi-GPU memory split | `"50,50"` for dual GPU |
| `OLLAMA_NUM_THREADS` | `0` | CPU threads (0=auto) | `0` or CPU core count |

### **Memory Management**
| Variable | Default | Description | Recommended Values |
|----------|---------|-------------|-------------------|
| `OLLAMA_KEEP_ALIVE` | `5m` | Model memory retention | `10m`-`30m` for GPU |
| `OLLAMA_USE_MMAP` | `true` | Memory mapping | `true` |
| `OLLAMA_USE_MLOCK` | `false` | Lock memory (avoid swap) | `false` unless needed |

### **Context & Batch Processing**
| Variable | Default | Description | Recommended Values |
|----------|---------|-------------|-------------------|
| `OLLAMA_NUM_CTX` | `0` | Context window size | `4096`-`8192` |
| `OLLAMA_NUM_BATCH` | `0` | Batch size (0=auto) | `512`-`2048` |
| `OLLAMA_NUM_KEEP` | `0` | Tokens to keep on context overflow | `0` |
| `OLLAMA_ADAPTIVE_BATCH_SIZE` | `true` | Auto-adjust batch size | `true` |

### **Quality Control**
| Variable | Default | Description | Recommended Values |
|----------|---------|-------------|-------------------|
| `OLLAMA_REPEAT_PENALTY` | `1.1` | Repetition penalty | `1.0`-`1.2` |
| `OLLAMA_REPEAT_LAST_N` | `64` | Tokens to check for repetition | `64`-`128` |
| `OLLAMA_TOP_K` | `40` | Top-K sampling | `20`-`50` |
| `OLLAMA_MIN_P` | `0.05` | Minimum probability threshold | `0.05`-`0.1` |

### **Advanced Options**
| Variable | Default | Description | Recommended Values |
|----------|---------|-------------|-------------------|
| `OLLAMA_SEED` | `-1` | Random seed (-1=random) | `42` for reproducibility |
| `OLLAMA_STOP_SEQUENCES` | `[]` | Global stop sequences | `["\\n\\n", "---"]` |
| `OLLAMA_ROPE_FREQUENCY_BASE` | `0.0` | RoPE frequency base | Model-specific |
| `OLLAMA_ROPE_FREQUENCY_SCALE` | `0.0` | RoPE frequency scale | Model-specific |

### **Model-Specific GPU Layers**
| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_VISION_MODEL_GPU_LAYERS` | `-1` | GPU layers for vision model |
| `OLLAMA_TEXT_MODEL_GPU_LAYERS` | `-1` | GPU layers for text model |
| `OLLAMA_EMBEDDING_MODEL_GPU_LAYERS` | `-1` | GPU layers for embedding model |

### **Concurrency & Performance**
| Variable | Default | Description | Recommended Values |
|----------|---------|-------------|-------------------|
| `OLLAMA_CONCURRENT_REQUESTS_PER_MODEL` | `1` | Concurrent requests per model | `1`-`2` |
| `OLLAMA_ENABLE_MODEL_PRELOADING` | `true` | Pre-load models at startup | `true` |

## 📈 Performance Monitoring

### **Check GPU Usage**
```bash
# Monitor GPU usage during processing
watch -n 1 nvidia-smi

# Check Ollama GPU detection
curl http://localhost:11434/api/tags
```

### **Test Performance Settings**
```bash
# Test model performance
time curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model",
    "prompt": "Test prompt",
    "stream": false,
    "options": {
      "num_gpu": -1,
      "num_batch": 1024
    }
  }'
```

## 🎛️ Optimization Strategies

### **1. Start with GPU Optimization**
1. Set `OLLAMA_NUM_GPU=-1` for auto-detection
2. Enable `OLLAMA_USE_MMAP=true` for faster loading
3. Set appropriate `OLLAMA_KEEP_ALIVE` based on usage patterns

### **2. Tune Batch Size**
- Start with `OLLAMA_ADAPTIVE_BATCH_SIZE=true`
- Monitor GPU memory usage
- Manually set `OLLAMA_NUM_BATCH` if needed

### **3. Optimize Context Window**
- Use larger context (`8192`) for synthesis tasks
- Use smaller context (`2048`) for quick categorization
- Balance quality vs. speed based on use case

### **4. Quality Tuning**
- Adjust `OLLAMA_REPEAT_PENALTY` to reduce repetitive output
- Use `OLLAMA_SEED` for reproducible results
- Set `OLLAMA_TOP_K` based on desired creativity level

### **5. Memory Management**
- Enable `OLLAMA_LOW_VRAM` for memory-constrained systems
- Adjust `OLLAMA_KEEP_ALIVE` based on model switching frequency
- Use `OLLAMA_USE_MLOCK` only if swapping is a problem

## 🚨 Troubleshooting

### **High Memory Usage**
```bash
OLLAMA_LOW_VRAM=true
OLLAMA_NUM_BATCH=256
OLLAMA_KEEP_ALIVE=2m
```

### **Slow Performance**
```bash
OLLAMA_NUM_GPU=-1
OLLAMA_USE_MMAP=true
OLLAMA_ADAPTIVE_BATCH_SIZE=true
OLLAMA_KEEP_ALIVE=15m
```

### **Inconsistent Results**
```bash
OLLAMA_SEED=42
OLLAMA_TOP_K=30
OLLAMA_REPEAT_PENALTY=1.1
```

### **Multi-GPU Issues**
```bash
OLLAMA_MAIN_GPU=0
OLLAMA_GPU_SPLIT="70,30"  # Adjust based on GPU memory
```

## 📋 Example Complete Configuration

```bash
# .env file for high-performance setup
# === Core Ollama Settings ===
OLLAMA_URL=http://localhost:11434
OLLAMA_SUPPORTS_JSON_MODE=true

# === GPU Optimization ===
OLLAMA_NUM_GPU=-1
OLLAMA_MAIN_GPU=0
OLLAMA_LOW_VRAM=false
OLLAMA_USE_MMAP=true
OLLAMA_USE_MLOCK=false

# === Memory & Performance ===
OLLAMA_KEEP_ALIVE=15m
OLLAMA_NUM_CTX=6144
OLLAMA_NUM_BATCH=1024
OLLAMA_ADAPTIVE_BATCH_SIZE=true
OLLAMA_ENABLE_MODEL_PRELOADING=true

# === Quality Control ===
OLLAMA_REPEAT_PENALTY=1.1
OLLAMA_REPEAT_LAST_N=64
OLLAMA_TOP_K=40
OLLAMA_MIN_P=0.05

# === System Settings ===
MAX_CONCURRENT_REQUESTS=1
REQUEST_TIMEOUT=240
GPU_TOTAL_MEM=24000  # Your GPU memory in MB
```

Start with these settings and adjust based on your specific hardware and performance requirements! 🚀 