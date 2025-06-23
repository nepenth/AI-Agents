#!/usr/bin/env python3
"""
Hardware Detection and Auto-Configuration for Ollama Optimization

This module automatically detects system hardware and generates optimal
Ollama configuration settings for maximum performance.
"""

import json
import logging
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil


@dataclass
class GPUInfo:
    """Information about a single GPU"""
    index: int
    name: str
    memory_total_mb: int
    memory_free_mb: int
    compute_capability: Optional[str] = None
    driver_version: Optional[str] = None
    cuda_cores: Optional[int] = None


@dataclass
class CPUInfo:
    """Information about the CPU"""
    model_name: str
    physical_cores: int
    logical_cores: int
    base_frequency_ghz: Optional[float] = None
    max_frequency_ghz: Optional[float] = None
    cache_size_mb: Optional[int] = None


@dataclass
class SystemInfo:
    """Complete system information"""
    cpu: CPUInfo
    gpus: List[GPUInfo]
    total_ram_gb: float
    available_ram_gb: float
    os_info: str
    python_version: str


@dataclass
class OllamaConfig:
    """Generated Ollama configuration"""
    # GPU Configuration
    num_gpu: int
    main_gpu: int
    low_vram: bool
    gpu_split: str
    
    # Memory Management
    keep_alive: str
    use_mmap: bool
    use_mlock: bool
    num_threads: int
    
    # Context and Batch
    num_ctx: int
    num_batch: int
    adaptive_batch_size: bool
    
    # Quality Control
    repeat_penalty: float
    repeat_last_n: int
    top_k: int
    min_p: float
    
    # Performance
    max_concurrent_requests: int
    request_timeout: int
    enable_model_preloading: bool
    
    # Model-specific GPU layers
    vision_model_gpu_layers: int
    text_model_gpu_layers: int
    embedding_model_gpu_layers: int
    
    # Justification for settings
    reasoning: Dict[str, str]


class HardwareDetector:
    """Detects system hardware and generates optimal Ollama configuration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def detect_gpus(self) -> List[GPUInfo]:
        """Detect NVIDIA GPUs using nvidia-smi"""
        gpus = []
        
        try:
            # Run nvidia-smi to get GPU information
            cmd = [
                'nvidia-smi', 
                '--query-gpu=index,name,memory.total,memory.free,driver_version',
                '--format=csv,noheader,nounits'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.logger.warning("nvidia-smi failed, no NVIDIA GPUs detected")
                return []
                
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                    
                try:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 5:
                        gpu = GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            memory_total_mb=int(parts[2]),
                            memory_free_mb=int(parts[3]),
                            driver_version=parts[4]
                        )
                        
                        # Detect Tesla P40 specifics
                        if 'Tesla P40' in gpu.name:
                            gpu.cuda_cores = 3840
                            gpu.compute_capability = "6.1"
                            
                        gpus.append(gpu)
                        self.logger.info(f"Detected GPU {gpu.index}: {gpu.name} with {gpu.memory_total_mb}MB")
                        
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Failed to parse GPU line '{line}': {e}")
                    continue
                    
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.warning(f"Failed to run nvidia-smi: {e}")
            
        return gpus
    
    def detect_cpu(self) -> CPUInfo:
        """Detect CPU information"""
        # Get basic CPU info from psutil
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        
        # Try to get CPU model name
        model_name = "Unknown CPU"
        base_freq = None
        max_freq = None
        
        try:
            if platform.system() == "Linux":
                # Read from /proc/cpuinfo
                with open('/proc/cpuinfo', 'r') as f:
                    content = f.read()
                    
                # Extract model name
                model_match = re.search(r'model name\s*:\s*(.+)', content)
                if model_match:
                    model_name = model_match.group(1).strip()
                    
                # Extract frequency information
                freq_match = re.search(r'cpu MHz\s*:\s*([0-9.]+)', content)
                if freq_match:
                    base_freq = float(freq_match.group(1)) / 1000  # Convert to GHz
                    
        except Exception as e:
            self.logger.warning(f"Failed to read CPU info from /proc/cpuinfo: {e}")
            
        # Try psutil for frequency info
        try:
            freq_info = psutil.cpu_freq()
            if freq_info:
                if not base_freq:
                    base_freq = freq_info.current / 1000 if freq_info.current else None
                max_freq = freq_info.max / 1000 if freq_info.max else None
        except Exception as e:
            self.logger.warning(f"Failed to get CPU frequency from psutil: {e}")
            
        cpu_info = CPUInfo(
            model_name=model_name,
            physical_cores=physical_cores or 1,
            logical_cores=logical_cores or 1,
            base_frequency_ghz=base_freq,
            max_frequency_ghz=max_freq
        )
        
        self.logger.info(f"Detected CPU: {cpu_info.model_name} "
                        f"({cpu_info.physical_cores} cores, {cpu_info.logical_cores} threads)")
        
        return cpu_info
    
    def detect_system_info(self) -> SystemInfo:
        """Detect complete system information"""
        # Get memory information
        memory = psutil.virtual_memory()
        total_ram_gb = memory.total / (1024**3)
        available_ram_gb = memory.available / (1024**3)
        
        # Get OS information
        os_info = f"{platform.system()} {platform.release()}"
        python_version = platform.python_version()
        
        # Detect hardware components
        cpu = self.detect_cpu()
        gpus = self.detect_gpus()
        
        system_info = SystemInfo(
            cpu=cpu,
            gpus=gpus,
            total_ram_gb=total_ram_gb,
            available_ram_gb=available_ram_gb,
            os_info=os_info,
            python_version=python_version
        )
        
        self.logger.info(f"System: {os_info}, RAM: {total_ram_gb:.1f}GB total, "
                        f"{len(gpus)} GPUs detected")
        
        return system_info
    
    def generate_ollama_config(self, system_info: SystemInfo, 
                              workload_type: str = "balanced") -> OllamaConfig:
        """
        Generate optimal Ollama configuration based on detected hardware
        
        Args:
            system_info: Detected system information
            workload_type: "performance", "balanced", "memory_efficient", or "cpu_only"
        """
        reasoning = {}
        
        # Analyze GPU configuration
        total_gpu_memory = sum(gpu.memory_total_mb for gpu in system_info.gpus)
        gpu_count = len(system_info.gpus)
        
        if gpu_count == 0:
            # CPU-only configuration
            reasoning["gpu"] = "No NVIDIA GPUs detected, using CPU-only configuration"
            num_gpu = 0
            main_gpu = 0
            low_vram = True
            gpu_split = ""
            
            # CPU optimization
            num_threads = min(system_info.cpu.physical_cores, 16)  # Don't exceed 16 threads
            reasoning["threads"] = f"Using {num_threads} threads (physical cores: {system_info.cpu.physical_cores})"
            
            # Conservative settings for CPU
            num_ctx = 2048
            num_batch = 128
            max_concurrent_requests = 1
            request_timeout = 600  # Longer timeout for CPU
            
        else:
            # GPU configuration
            reasoning["gpu"] = f"Detected {gpu_count} GPUs with {total_gpu_memory}MB total VRAM"
            num_gpu = -1  # Auto-detect layers
            main_gpu = 0  # Use first GPU as primary
            
            # Determine if low VRAM mode is needed
            max_gpu_memory = max(gpu.memory_total_mb for gpu in system_info.gpus)
            low_vram = max_gpu_memory < 16000  # Enable if largest GPU has <16GB
            
            # Multi-GPU configuration
            if gpu_count > 1:
                # For dual Tesla P40s (your system), split evenly
                if gpu_count == 2:
                    gpu_split = "50,50"
                    reasoning["gpu_split"] = "Dual GPU setup, splitting memory 50/50"
                else:
                    gpu_split = ""
                    reasoning["gpu_split"] = f"{gpu_count} GPUs detected, using auto split"
            else:
                gpu_split = ""
            
            # CPU threads (use fewer when GPU is doing the work)
            num_threads = min(8, system_info.cpu.physical_cores // 2)
            reasoning["threads"] = f"Using {num_threads} CPU threads (GPU handling main workload)"
        
        # Memory management based on total GPU memory
        if total_gpu_memory >= 40000:  # 40GB+ (like your dual P40 setup)
            keep_alive = "30m"
            use_mlock = False  # Can cause issues with large models
            reasoning["memory"] = "High VRAM system, extended model retention"
            
        elif total_gpu_memory >= 20000:  # 20-40GB
            keep_alive = "15m"
            use_mlock = False
            reasoning["memory"] = "Mid-high VRAM system, moderate model retention"
            
        elif total_gpu_memory >= 8000:   # 8-20GB
            keep_alive = "5m"
            use_mlock = False
            reasoning["memory"] = "Standard VRAM system, conservative model retention"
            
        else:  # <8GB or CPU-only
            keep_alive = "2m"
            use_mlock = False
            reasoning["memory"] = "Low VRAM or CPU system, quick model unloading"
        
        # Context and batch size optimization
        if workload_type == "performance":
            if total_gpu_memory >= 40000:
                num_ctx = 8192
                num_batch = 2048
                max_concurrent_requests = 2
            elif total_gpu_memory >= 20000:
                num_ctx = 6144
                num_batch = 1024
                max_concurrent_requests = 1
            else:
                num_ctx = 4096
                num_batch = 512
                max_concurrent_requests = 1
                
        elif workload_type == "memory_efficient":
            num_ctx = 2048
            num_batch = 256
            max_concurrent_requests = 1
            
        else:  # balanced
            if total_gpu_memory >= 40000:
                num_ctx = 6144
                num_batch = 1024
                max_concurrent_requests = 1
            elif total_gpu_memory >= 20000:
                num_ctx = 4096
                num_batch = 512
                max_concurrent_requests = 1
            else:
                num_ctx = 2048
                num_batch = 256
                max_concurrent_requests = 1
        
        reasoning["context"] = f"Context: {num_ctx}, Batch: {num_batch} (workload: {workload_type})"
        
        # Quality settings (optimized for your use case)
        repeat_penalty = 1.1
        repeat_last_n = 64
        top_k = 40
        min_p = 0.05
        
        # Performance settings
        use_mmap = True  # Always beneficial
        adaptive_batch_size = workload_type != "performance"  # Disable for max performance
        enable_model_preloading = total_gpu_memory >= 16000  # Only for systems with adequate VRAM
        
        # Model-specific GPU layer settings
        if gpu_count > 0:
            vision_model_gpu_layers = -1
            text_model_gpu_layers = -1
            embedding_model_gpu_layers = -1
        else:
            vision_model_gpu_layers = 0
            text_model_gpu_layers = 0
            embedding_model_gpu_layers = 0
        
        reasoning["models"] = f"Model preloading: {enable_model_preloading}, GPU layers: {vision_model_gpu_layers}"
        
        return OllamaConfig(
            num_gpu=num_gpu,
            main_gpu=main_gpu,
            low_vram=low_vram,
            gpu_split=gpu_split,
            keep_alive=keep_alive,
            use_mmap=use_mmap,
            use_mlock=use_mlock,
            num_threads=num_threads,
            num_ctx=num_ctx,
            num_batch=num_batch,
            adaptive_batch_size=adaptive_batch_size,
            repeat_penalty=repeat_penalty,
            repeat_last_n=repeat_last_n,
            top_k=top_k,
            min_p=min_p,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=240,  # Default value, not applied to env
            enable_model_preloading=enable_model_preloading,
            vision_model_gpu_layers=vision_model_gpu_layers,
            text_model_gpu_layers=text_model_gpu_layers,
            embedding_model_gpu_layers=embedding_model_gpu_layers,
            reasoning=reasoning
        )
    
    def generate_env_file(self, config: OllamaConfig, output_file: str = ".env.ollama_optimized"):
        """Generate .env file with optimized settings"""
        
        env_content = f"""# Ollama Auto-Generated Optimization Configuration
# Generated based on detected hardware specifications
# System: {config.reasoning.get('gpu', 'Unknown')}
# Reasoning: {config.reasoning}

# === GPU & Hardware Control ===
OLLAMA_NUM_GPU={config.num_gpu}
OLLAMA_MAIN_GPU={config.main_gpu}
OLLAMA_LOW_VRAM={str(config.low_vram).lower()}
OLLAMA_GPU_SPLIT={config.gpu_split}
OLLAMA_NUM_THREADS={config.num_threads}

# === Memory Management ===
OLLAMA_KEEP_ALIVE={config.keep_alive}
OLLAMA_USE_MMAP={str(config.use_mmap).lower()}
OLLAMA_USE_MLOCK={str(config.use_mlock).lower()}

# === Context & Batch Processing ===
OLLAMA_NUM_CTX={config.num_ctx}
OLLAMA_NUM_BATCH={config.num_batch}
OLLAMA_ADAPTIVE_BATCH_SIZE={str(config.adaptive_batch_size).lower()}

# === Quality Control ===
OLLAMA_REPEAT_PENALTY={config.repeat_penalty}
OLLAMA_REPEAT_LAST_N={config.repeat_last_n}
OLLAMA_TOP_K={config.top_k}
OLLAMA_MIN_P={config.min_p}

# === Performance Settings ===
MAX_CONCURRENT_REQUESTS={config.max_concurrent_requests}
OLLAMA_ENABLE_MODEL_PRELOADING={str(config.enable_model_preloading).lower()}

# === Model-Specific GPU Layers ===
OLLAMA_VISION_MODEL_GPU_LAYERS={config.vision_model_gpu_layers}
OLLAMA_TEXT_MODEL_GPU_LAYERS={config.text_model_gpu_layers}
OLLAMA_EMBEDDING_MODEL_GPU_LAYERS={config.embedding_model_gpu_layers}

# === Additional Recommended Settings ===
# Set these based on your specific models and requirements
# OLLAMA_SEED=42  # For reproducible results
# OLLAMA_STOP_SEQUENCES=["\\n\\n", "---"]  # Custom stop sequences
"""
        
        with open(output_file, 'w') as f:
            f.write(env_content)
            
        print(f"✅ Generated optimized configuration: {output_file}")
        return output_file


def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-detect hardware and generate Ollama optimization config")
    parser.add_argument("--workload", choices=["performance", "balanced", "memory_efficient", "cpu_only"], 
                       default="balanced", help="Optimization profile")
    parser.add_argument("--output", default=".env.ollama_optimized", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Detect hardware and generate config
    detector = HardwareDetector()
    system_info = detector.detect_system_info()
    config = detector.generate_ollama_config(system_info, args.workload)
    
    if args.json:
        # Output as JSON for programmatic use
        config_dict = {
            "system_info": {
                "cpu_model": system_info.cpu.model_name,
                "cpu_cores": system_info.cpu.physical_cores,
                "total_ram_gb": system_info.total_ram_gb,
                "gpus": [{"name": gpu.name, "memory_mb": gpu.memory_total_mb} for gpu in system_info.gpus]
            },
            "ollama_config": config.__dict__
        }
        print(json.dumps(config_dict, indent=2))
    else:
        # Generate .env file
        detector.generate_env_file(config, args.output)
        
        # Print summary
        print(f"\n🖥️  System Summary:")
        print(f"   CPU: {system_info.cpu.model_name} ({system_info.cpu.physical_cores} cores)")
        print(f"   RAM: {system_info.total_ram_gb:.1f}GB")
        print(f"   GPUs: {len(system_info.gpus)}")
        for gpu in system_info.gpus:
            print(f"     - {gpu.name} ({gpu.memory_total_mb}MB)")
            
        print(f"\n⚙️  Generated Configuration ({args.workload} profile):")
        for key, reason in config.reasoning.items():
            print(f"   {key}: {reason}")


if __name__ == "__main__":
    main() 