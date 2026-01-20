"""NVDA Process Management Utilities"""

import os
import subprocess
import time
from typing import List, Optional

try:
    import psutil
except ImportError:
    psutil = None


def find_nvda_executable() -> Optional[str]:
    """Find the NVDA executable path."""
    possible_paths = [
        r"C:\Program Files (x86)\NVDA\nvda.exe",
        r"C:\Program Files\NVDA\nvda.exe",
        os.path.join(os.getenv('PROGRAMFILES(X86)', ''), 'NVDA', 'nvda.exe'),
        os.path.join(os.getenv('PROGRAMFILES', ''), 'NVDA', 'nvda.exe'),
    ]

    for path in possible_paths:
        if path and os.path.exists(path):
            return path

    return None


def is_nvda_running() -> bool:
    """Check if NVDA is currently running."""
    if psutil is None:
        # Fallback: use tasklist command
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq nvda.exe'],
                capture_output=True, text=True, shell=False
            )
            return 'nvda.exe' in result.stdout.lower()
        except Exception:
            return False

    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'nvda.exe':
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return False


def get_nvda_process() -> Optional['psutil.Process']:
    """Get the NVDA process object if running."""
    if psutil is None:
        return None

    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'nvda.exe':
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return None


def stop_nvda() -> bool:
    """Gracefully stop NVDA using its quit command."""
    nvda_exe = find_nvda_executable()

    if nvda_exe:
        try:
            subprocess.run([nvda_exe, '-q'], shell=False, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    # Also try via process if we have psutil
    if psutil is not None:
        proc = get_nvda_process()
        if proc:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    return wait_for_nvda_exit()


def wait_for_nvda_exit(timeout: int = 10) -> bool:
    """Wait for NVDA to fully exit.

    Args:
        timeout: Maximum seconds to wait

    Returns:
        True if NVDA exited, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if not is_nvda_running():
            # Give a bit more time for file handles to be released
            time.sleep(0.5)
            return True
        time.sleep(0.5)

    return False


def start_nvda() -> bool:
    """Start NVDA screen reader."""
    nvda_exe = find_nvda_executable()

    if not nvda_exe:
        return False

    try:
        subprocess.Popen([nvda_exe], shell=False)
        return True
    except Exception:
        return False


def check_files_locked(folder_path: str) -> List[str]:
    """Check if any files in the folder are locked.

    Args:
        folder_path: Path to the folder to check

    Returns:
        List of locked file paths
    """
    locked_files = []

    if not os.path.exists(folder_path):
        return locked_files

    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                # Try to open file for exclusive access
                with open(filepath, 'r+b'):
                    pass
            except (IOError, PermissionError, OSError):
                locked_files.append(filepath)

    return locked_files


def check_folder_deletable(folder_path: str) -> tuple[bool, List[str]]:
    """Check if the folder can be deleted (no locked files).

    Args:
        folder_path: Path to check

    Returns:
        Tuple of (can_delete, list_of_locked_files)
    """
    locked = check_files_locked(folder_path)
    return len(locked) == 0, locked
