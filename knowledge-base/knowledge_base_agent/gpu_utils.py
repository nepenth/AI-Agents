import subprocess
import logging
import json
import time

# Cache to avoid repeated warnings when nvidia-smi is not available
_nvidia_smi_available = None
_last_check_time = 0
_check_interval = 300  # Check every 5 minutes

def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit."""
    return (celsius * 9/5) + 32

def _check_nvidia_smi_available():
    """Check if nvidia-smi is available, with caching to avoid repeated warnings."""
    global _nvidia_smi_available, _last_check_time
    
    current_time = time.time()
    
    # If we've checked recently, return cached result
    if _nvidia_smi_available is not None and (current_time - _last_check_time) < _check_interval:
        return _nvidia_smi_available
    
    # Check if nvidia-smi is available
    try:
        subprocess.check_output(['nvidia-smi', '-L'], stderr=subprocess.STDOUT)
        _nvidia_smi_available = True
        _last_check_time = current_time
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        if _nvidia_smi_available is None:  # Only log warning on first check
            logging.warning("nvidia-smi command not found. GPU stats will not be available.")
        _nvidia_smi_available = False
        _last_check_time = current_time
        return False

def get_gpu_stats():
    """
    Fetches GPU statistics using nvidia-smi.

    Returns:
        A list of dictionaries, where each dictionary contains stats for one GPU,
        or None if nvidia-smi is not found or fails.
        Stats include: utilization.gpu, memory.used, memory.total,
        temperature.gpu (in both C and F), power.draw, clocks.current.graphics, clocks.current.memory.
    """
    # Check if nvidia-smi is available (with caching to avoid repeated warnings)
    if not _check_nvidia_smi_available():
        return None

    try:
        command = [
            'nvidia-smi',
            '--query-gpu=name,index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.current.graphics,clocks.current.memory',
            '--format=csv,noheader,nounits'
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=5) # 5 second timeout

        if process.returncode != 0:
            logging.error(f"nvidia-smi failed with error code {process.returncode}: {stderr.strip()}")
            return None

        gpu_stats_list = []
        lines = stdout.strip().split('\n')
        if not lines or not lines[0].strip(): # Handle empty output
            logging.warning("nvidia-smi returned no data.")
            return None

        for line in lines:
            if not line.strip(): continue
            values = line.split(', ')
            try:
                temp_celsius = float(values[5])
                temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)
                
                stats = {
                    'name': values[0].strip(),
                    'index': int(values[1]),
                    'utilization_gpu': float(values[2]),
                    'memory_used': float(values[3]),
                    'memory_total': float(values[4]),
                    'temperature_gpu': temp_celsius,  # Keep original for backward compatibility
                    'temperature_gpu_celsius': temp_celsius,
                    'temperature_gpu_fahrenheit': temp_fahrenheit,
                    'power_draw': float(values[6]) if values[6].strip().lower() != '[not supported]' else None,
                    'clocks_graphics': int(values[7]) if values[7].strip().lower() != '[not supported]' else None,
                    'clocks_memory': int(values[8]) if values[8].strip().lower() != '[not supported]' else None,
                }
                gpu_stats_list.append(stats)
            except (ValueError, IndexError) as e:
                logging.error(f"Error parsing nvidia-smi output line '{line}': {e}")
                continue # Skip malformed line
        
        return gpu_stats_list if gpu_stats_list else None

    except subprocess.TimeoutExpired:
        logging.error("nvidia-smi command timed out.")
        return None
    except Exception as e:
        logging.exception(f"An unexpected error occurred while fetching GPU stats: {e}")
        return None

if __name__ == '__main__':
    # For testing the function directly
    logging.basicConfig(level=logging.DEBUG)
    stats = get_gpu_stats()
    if stats:
        print(json.dumps(stats, indent=2))
    else:
        print("Could not retrieve GPU stats.") 