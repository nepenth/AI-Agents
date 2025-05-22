@app.route('/api/gpu-status', methods=['GET'])
def get_gpu_status():
    try:
        from knowledge_base_agent.utils.gpu_check import check_nvidia_smi, check_cuda_environment, check_ollama_gpu
        
        gpu_info = {
            'nvidia': {},
            'cuda_env': {},
            'ollama': {}
        }
        
        # Check NVIDIA GPU status
        nvidia_success, nvidia_result = check_nvidia_smi()
        gpu_info['nvidia']['success'] = nvidia_success
        gpu_info['nvidia']['result'] = nvidia_result
        
        # Check CUDA environment
        cuda_vars = check_cuda_environment()
        gpu_info['cuda_env'] = cuda_vars
        
        # Check Ollama
        ollama_success, ollama_result = check_ollama_gpu()
        gpu_info['ollama']['success'] = ollama_success
        gpu_info['ollama']['result'] = ollama_result
        
        return jsonify(gpu_info)
    except Exception as e:
        app.logger.exception(f"Error checking GPU status: {e}")
        return jsonify({'error': str(e)}), 500 