import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Union

import aiofiles
import aiofiles.os

from ..exceptions import FileOperationError

logger = logging.getLogger(__name__)

async def read_text_async(file_path: Union[str, Path]) -> str:
    """Asynchronously reads text content from a file."""
    path = Path(file_path)
    logger.debug(f"Attempting to read text from: {path}")
    try:
        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            logger.debug(f"Successfully read text from: {path}")
            return content
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
        raise FileOperationError(path, "read", "File not found.", None)
    except IOError as e:
        logger.error(f"IOError reading text from {path}: {e}")
        raise FileOperationError(path, "read", str(e), e)
    except Exception as e:
        logger.error(f"Unexpected error reading text from {path}: {e}")
        raise FileOperationError(path, "read", f"An unexpected error occurred: {type(e).__name__}", e)

async def read_json_async(file_path: Union[str, Path]) -> Any:
    """Asynchronously reads and parses JSON data from a file."""
    path = Path(file_path)
    logger.debug(f"Attempting to read JSON from: {path}")
    try:
        content = await read_text_async(path)
        # json.loads is CPU-bound, run in thread pool
        data = await asyncio.to_thread(json.loads, content)
        logger.debug(f"Successfully parsed JSON from: {path}")
        return data
    except FileOperationError as e:
        # Pass through file operation errors from read_text_async
        raise e
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in file {path}: {e}")
        raise FileOperationError(path, "read/parse JSON", f"Invalid JSON format: {e}", e)
    except Exception as e:
        logger.error(f"Unexpected error reading/parsing JSON from {path}: {e}")
        raise FileOperationError(path, "read/parse JSON", f"An unexpected error occurred: {type(e).__name__}", e)


async def _write_content_atomic_async(file_path: Path, content: Union[str, bytes], mode: str):
    """Helper for atomic writes (text or bytes)."""
    temp_file_path = None
    # Create a temporary file in the same directory to ensure rename is atomic (usually)
    parent_dir = file_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True) # Ensure parent directory exists

    try:
        # Use aiofiles for async temp file creation if possible, or sync with tempfile otherwise
        # Note: aiofiles doesn't have a direct equivalent for NamedTemporaryFile in the same dir easily
        # Using sync tempfile and async write is generally acceptable here.
        fd, temp_path_str = tempfile.mkstemp(dir=str(parent_dir), prefix=f".{file_path.name}_tmp_")
        temp_file_path = Path(temp_path_str)
        os.close(fd) # Close the file descriptor, aiofiles will reopen

        async with aiofiles.open(temp_file_path, mode=mode, encoding='utf-8' if isinstance(content, str) else None) as f:
            await f.write(content)
            await f.flush() # Ensure buffer is written
            # fsync might be needed for guaranteed disk persistence on some OSes, but can be slow
            # await aiofiles.os.fsync(f.fileno())

        # Atomically replace the original file with the temporary file
        await aiofiles.os.replace(temp_file_path, file_path)
        logger.debug(f"Successfully wrote atomically to: {file_path}")

    except Exception as e:
        logger.error(f"Failed atomic write to {file_path}: {e}")
        # Clean up the temporary file if it still exists and rename failed
        if temp_file_path and await aiofiles.os.path.exists(temp_file_path):
            try:
                await aiofiles.os.remove(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as cleanup_err:
                logger.error(f"Error cleaning up temporary file {temp_file_path}: {cleanup_err}")
        # Re-raise as FileOperationError
        raise FileOperationError(file_path, f"atomic write ({mode})", str(e), e)

async def write_text_atomic_async(file_path: Union[str, Path], data: str):
    """Atomically writes text data to a file using a temporary file."""
    path = Path(file_path)
    logger.debug(f"Attempting atomic text write to: {path}")
    await _write_content_atomic_async(path, data, mode='w')

async def write_json_atomic_async(file_path: Union[str, Path], data: Any, indent: Optional[int] = 4):
    """
    Atomically serializes Python object to JSON and writes it to a file.
    """
    path = Path(file_path)
    logger.debug(f"Attempting atomic JSON write to: {path}")
    try:
        # json.dumps is CPU-bound, run in thread pool
        json_string = await asyncio.to_thread(json.dumps, data, indent=indent, ensure_ascii=False)
        await _write_content_atomic_async(path, json_string, mode='w')
    except TypeError as e:
        logger.error(f"TypeError during JSON serialization for {path}: {e}")
        raise FileOperationError(path, "serialize JSON", f"Data not JSON serializable: {e}", e)
    except FileOperationError as e:
        # Pass through errors from the write operation
        raise e
    except Exception as e:
        logger.error(f"Unexpected error writing JSON to {path}: {e}")
        raise FileOperationError(path, "write JSON", f"An unexpected error occurred: {type(e).__name__}", e)

async def ensure_dir_async(dir_path: Union[str, Path]):
    """Asynchronously ensures a directory exists, creating it if necessary."""
    path = Path(dir_path)
    logger.debug(f"Ensuring directory exists: {path}")
    if not await aiofiles.os.path.isdir(path):
        try:
            await aiofiles.os.makedirs(path, exist_ok=True)
            logger.debug(f"Created directory: {path}")
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise FileOperationError(path, "create directory", str(e), e)
