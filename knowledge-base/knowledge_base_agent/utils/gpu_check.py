#!/usr/bin/env python3
import subprocess
import json
import os
import sys
import logging
import requests
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_nvidia_smi():
    """Check if nvidia-smi is available and get GPU information"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        lines = result.stdout.strip().split('\n')
        if not lines or not lines[0].strip():
            logging.warning("nvidia-smi returned empty output")
            return False, "nvidia-smi returned empty output"
            
        gpu_info = []
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            parts = [part.strip() for part in line.split(',')]
            if len(parts) >= 6:
                gpu_info.append({
                    'index': i,
                    'name': parts[0],
                    'memory_total': parts[1],
                    'memory_used': parts[2],
                    'memory_free': parts[3],
                    'temperature': parts[4],
                    'utilization': parts[5]
                })
                
        if gpu_info:
            logging.info(f"Found {len(gpu_info)} GPUs:")
            for gpu in gpu_info:
                logging.info(f"  GPU {gpu['index']}: {gpu['name']} - {gpu['memory_total']}MB total, {gpu['memory_free']}MB free, {gpu['utilization']}% utilization")
            return True, gpu_info
        else:
            return False, "No GPU information found"
    except FileNotFoundError:
        return False, "nvidia-smi not found - NVIDIA drivers may not be installed"
    except subprocess.SubprocessError as e:
        return False, f"Error running nvidia-smi: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def check_cuda_environment():
    """Check CUDA environment variables"""
    cuda_vars = {
        'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES'),
        'LD_LIBRARY_PATH': os.environ.get('LD_LIBRARY_PATH'),
        'NVIDIA_VISIBLE_DEVICES': os.environ.get('NVIDIA_VISIBLE_DEVICES')
    }
    
    logging.info("CUDA Environment Variables:")
    for var, value in cuda_vars.items():
        if value is not None:
            logging.info(f"  {var}={value}")
        else:
            logging.info(f"  {var} is not set")
            
    return cuda_vars

def check_ollama_gpu():
    """Check if Ollama is configured to use GPU"""
    ollama_url = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
    
    try:
        # Check if Ollama is running
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code != 200:
            return False, f"Ollama API returned status {response.status_code}"
            
        models = response.json().get("models", [])
        if not models:
            return False, "No models found in Ollama"
            
        # Try a simple generation to see if GPU is used
        logging.info("Testing simple LLM generation to check for GPU usage...")
        start_time = time.time()
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": models[0]["name"],
                "prompt": "Say 'Hello, I am running on GPU!' if you are running on GPU, otherwise say 'I am running on CPU.'",
                "stream": False,
                "options": {"num_gpu": 1}  # Request GPU usage explicitly
            },
            timeout=60
        )
        
        if response.status_code != 200:
            return False, f"Ollama generate API returned status {response.status_code}"
            
        elapsed = time.time() - start_time
        result = response.json()
        logging.info(f"Response received in {elapsed:.2f} seconds")
        logging.info(f"Response: {result.get('response', '')}")
        
        # Often, we can tell GPU is running by timing - CPU is much slower
        if elapsed < 5:
            gpu_likely = "GPU usage likely (fast response)"
        else:
            gpu_likely = "CPU usage likely (slow response)"
            
        return True, {
            "response": result.get("response", ""),
            "timing": elapsed,
            "assessment": gpu_likely
        }
    except requests.RequestException as e:
        return False, f"Error connecting to Ollama: {e}"
    except Exception as e:
        return False, f"Unexpected error checking Ollama: {e}"

def main():
    """Run all GPU checks"""
    print("\n=== NVIDIA GPU Check ===")
    nvidia_success, nvidia_result = check_nvidia_smi()
    
    print("\n=== CUDA Environment Check ===")
    cuda_vars = check_cuda_environment()
    
    print("\n=== Ollama GPU Check ===")
    ollama_success, ollama_result = check_ollama_gpu()
    
    print("\n=== Summary ===")
    if nvidia_success:
        print("✅ NVIDIA GPUs detected")
    else:
        print(f"❌ NVIDIA GPU check failed: {nvidia_result}")
        
    if ollama_success:
        print("✅ Ollama is running")
        if isinstance(ollama_result, dict) and "assessment" in ollama_result:
            print(f"👉 {ollama_result['assessment']}")
    else:
        print(f"❌ Ollama check failed: {ollama_result}")
        
    print("\nFor Ollama to use GPU:")
    print("1. Ensure NVIDIA drivers are installed and working")
    print("2. Make sure Ollama service has GPU access")
    print("3. Check Ollama service configuration for GPU options")
    print("4. You may need to set CUDA_VISIBLE_DEVICES in Ollama's environment")
    
if __name__ == "__main__":
    main() 