import asyncio
import sys
from pathlib import PureWindowsPath


def _import_colorama():
    try:
        import colorama
        return colorama
    except ImportError:
        return None


colorama = _import_colorama()


def apply_windows_patches() -> None:
    """Inject Windows-specific compatibility patches. Call once at process start."""
    if colorama is not None:
        colorama.init(wrap=True)

    # Python 3.12 already defaults to ProactorEventLoop on Windows,
    # but we set it explicitly as a safety shim against edge cases.
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def normalize_path(path: str) -> str:
    """Return path with backslashes replaced by forward slashes."""
    return PureWindowsPath(path).as_posix()
