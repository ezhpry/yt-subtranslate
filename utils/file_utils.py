import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Replace characters unsafe for directory/file names with underscores."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist, return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
