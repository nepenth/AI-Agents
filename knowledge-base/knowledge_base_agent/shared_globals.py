import threading
from pathlib import Path
from typing import Optional

stop_flag = threading.Event()
_project_root: Optional[Path] = None

def sg_set_project_root(path: Path) -> None:
    global _project_root
    if not isinstance(path, Path):
        raise TypeError("Project root must be a Path object")
    _project_root = path.resolve()
    # Optionally, could also set the PROJECT_ROOT in config.py here if desired,
    # but it's cleaner if the calling code (e.g., main.py/web.py startup)
    # does both: config.PROJECT_ROOT = path and sg_set_project_root(path)

def sg_get_project_root() -> Path:
    if _project_root is None:
        raise RuntimeError("Project root has not been set. Call sg_set_project_root() first.")
    return _project_root 

def clear_stop_flag() -> None:
    """Resets the global stop_flag, allowing the agent to run."""
    stop_flag.clear()

def set_stop_flag() -> None:
    """Sets the global stop_flag, signaling the agent to stop."""
    stop_flag.set() 