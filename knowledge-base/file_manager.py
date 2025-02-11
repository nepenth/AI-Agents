from pathlib import Path
import asyncio
import aiofiles
import shutil
from typing import AsyncGenerator, Optional
import logging

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    async def write_file(self, path: Path, content: str) -> None:
        """Asynchronously write content to a file."""
        async with aiofiles.open(path, 'w') as f:
            await f.write(content)

    async def read_file(self, path: Path) -> str:
        """Asynchronously read content from a file."""
        async with aiofiles.open(path, 'r') as f:
            return await f.read()

    async def copy_file(self, src: Path, dst: Path) -> None:
        """Copy file using thread pool to avoid blocking."""
        await asyncio.to_thread(shutil.copy2, src, dst)

    async def scan_directory(self, pattern: str = "**/*") -> AsyncGenerator[Path, None]:
        """Asynchronously scan directory for files matching pattern."""
        def _scan():
            return list(self.base_dir.glob(pattern))
        
        for path in await asyncio.to_thread(_scan):
            yield path

    async def ensure_dir(self, path: Path) -> None:
        """Ensure directory exists, create if necessary."""
        await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True) 