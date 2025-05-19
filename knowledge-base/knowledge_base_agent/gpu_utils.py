import subprocess
import logging
import json

def get_gpu_stats():
    """
    Fetches GPU statistics using nvidia-smi.

    Returns:
        A list of dictionaries, where each dictionary contains stats for one GPU,
        or None if nvidia-smi is not found or fails.
        Stats include: utilization.gpu, memory.used, memory.total,
        temperature.gpu, power.draw, clocks.current.graphics, clocks.current.memory.
    """
    try:
        # Check if nvidia-smi is available
        subprocess.check_output(['nvidia-smi', '-L'], stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.warning("nvidia-smi command not found. GPU stats will not be available.")
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
                stats = {
                    'name': values[0].strip(),
                    'index': int(values[1]),
                    'utilization_gpu': float(values[2]),
                    'memory_used': float(values[3]),
                    'memory_total': float(values[4]),
                    'temperature_gpu': float(values[5]),
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