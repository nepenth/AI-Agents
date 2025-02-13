import asyncio
import logging
from typing import List, Optional

async def run_command(cmd: List[str], cwd: Optional[str] = None) -> str:
    """
    Run a shell command asynchronously.
    
    Args:
        cmd: List of command parts
        cwd: Working directory for the command
        
    Returns:
        Command output as string
        
    Raises:
        Exception if command fails
    """
    try:
        logging.debug(f"Running command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode().strip() if stdout else ""
        stderr_str = stderr.decode().strip() if stderr else ""
        
        if process.returncode != 0:
            error_msg = stderr_str if stderr_str else stdout_str if stdout_str else "No output"
            logging.error(f"Command failed: {' '.join(cmd)}")
            logging.error(f"Return code: {process.returncode}")
            logging.error(f"Error output: {error_msg}")
            raise Exception(f"Command failed with code {process.returncode}: {error_msg}")
            
        if stdout_str:
            logging.debug(f"Command output: {stdout_str}")
        return stdout_str
        
    except Exception as e:
        logging.error(f"Failed to run command {' '.join(cmd)}: {e}")
        raise 