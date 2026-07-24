"""NVDA Process Management Utilities"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import winreg
import zipfile
from typing import Optional, Tuple

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
    """Gracefully stop NVDA using its quit command, escalating only if needed."""
    nvda_exe = find_nvda_executable()

    if nvda_exe:
        try:
            subprocess.run([nvda_exe, '-q'], shell=False, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    # Give the graceful quit a chance to finish before escalating. Terminating
    # immediately after '-q' would race NVDA's own shutdown and cut it off
    # mid-way (`nvda -q` returns as soon as it has *signalled* the quit, not
    # when NVDA has actually exited).
    if wait_for_nvda_exit():
        return True

    # Still running — force it down as a last resort.
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


def remove_tree(path: str) -> None:
    """Delete a directory tree, clearing read-only attributes as it goes.

    A plain ``shutil.rmtree`` aborts with ``PermissionError`` (WinError 5) the moment
    it hits a read-only file, and NVDA ships several (the add-on ``readme`` files).
    On Windows that used to leave a half-deleted NVDA folder behind. The error
    handler here clears the read-only bit and retries the failed operation.
    """
    if not os.path.exists(path):
        return

    def clear_readonly_and_retry(func, failed_path, _exc):
        os.chmod(failed_path, stat.S_IWRITE)
        func(failed_path)

    # onexc replaced the deprecated onerror in Python 3.12; support both.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=clear_readonly_and_retry)
    else:
        shutil.rmtree(
            path,
            onerror=lambda func, p, exc_info: clear_readonly_and_retry(func, p, exc_info),
        )


def safe_restore(nvda_path: str, profile_path: str,
                 descriptor_name: str = 'profile_descriptor.json') -> None:
    """Restore an NVDA profile without ever putting the live configuration at risk.

    The old approach deleted the NVDA folder and *then* extracted the backup, so any
    failure in between — a corrupt archive, a read-only file, a locked handle — left
    the configuration destroyed and unrecoverable.

    This does it the safe way:

    1. Extract the backup into a staging folder on the same volume. A bad archive
       fails here, before the live folder has been touched at all.
    2. Move the current folder aside (a single, atomic directory rename that keeps it
       intact as a rollback point).
    3. Move the staged folder into place. If that fails, the previous folder is moved
       back and nothing is lost.
    4. Only once the swap has succeeded is the set-aside folder deleted.

    Raises on failure, having left the existing configuration untouched (or restored).
    """
    parent = os.path.dirname(os.path.abspath(nvda_path))
    os.makedirs(parent, exist_ok=True)

    # 1. Extract to staging on the same volume (so the later rename is atomic).
    staging = tempfile.mkdtemp(prefix='nvda_restore_', dir=parent)
    try:
        with zipfile.ZipFile(profile_path, 'r') as zipf:
            corrupt = zipf.testzip()
            if corrupt is not None:
                raise RuntimeError(f'Backup archive is corrupt: {corrupt}')
            for member in zipf.namelist():
                if member == descriptor_name:
                    continue
                zipf.extract(member, staging)
    except Exception:
        remove_tree(staging)
        raise

    # 2. Move the current folder aside as a rollback point.
    moved_aside = ''
    if os.path.exists(nvda_path):
        moved_aside = f'{nvda_path}.bak-{time.strftime("%Y%m%d-%H%M%S")}'
        os.rename(nvda_path, moved_aside)

    # 3. Swap the staged folder in; roll back on failure.
    try:
        os.rename(staging, nvda_path)
    except Exception:
        if moved_aside and not os.path.exists(nvda_path):
            os.rename(moved_aside, nvda_path)
        remove_tree(staging)
        raise

    # 4. Success — discard the folder we set aside.
    if moved_aside:
        remove_tree(moved_aside)


def cleanup_stale_restore_dirs(nvda_path: str) -> None:
    """Remove rollback/staging folders left behind by an interrupted restore.

    ``safe_restore`` keeps the previous configuration as ``<nvda>.bak-<timestamp>``
    and extracts the new one into an ``nvda_restore_*`` staging directory. A crash
    (or a kill) between the swap steps can orphan either of them next to the NVDA
    folder. Once the process runs again the live folder is already in place, so
    these leftovers are pure clutter and safe to delete. Called at startup.
    """
    parent = os.path.dirname(os.path.abspath(nvda_path))
    base = os.path.basename(os.path.abspath(nvda_path))
    if not os.path.isdir(parent):
        return

    for name in os.listdir(parent):
        full = os.path.join(parent, name)
        if not os.path.isdir(full):
            continue
        if name.startswith(f'{base}.bak-') or name.startswith('nvda_restore_'):
            try:
                remove_tree(full)
            except OSError:
                pass


def get_executable_path() -> str:
    """Get the path to the current executable or script."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        return os.path.abspath(sys.argv[0])


def is_admin() -> bool:
    """Check if the current process has administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def register_filetype(use_hkcu: bool = False) -> Tuple[bool, str]:
    """Register .nvdaprofile file type association.

    Args:
        use_hkcu: If True, register under HKEY_CURRENT_USER (no admin needed).
                  If False, register under HKEY_CLASSES_ROOT (requires admin).

    Returns:
        Tuple of (success, message)
    """
    exe_path = get_executable_path()

    if not getattr(sys, 'frozen', False):
        return False, "File type registration requires the compiled executable.\nPlease run 'scons build' first."

    if not os.path.exists(exe_path):
        return False, f"Executable not found at: {exe_path}"

    try:
        if use_hkcu:
            root_key = winreg.HKEY_CURRENT_USER
            base_path = r"Software\Classes"
        else:
            if not is_admin():
                return False, "Administrator privileges required for system-wide registration."
            root_key = winreg.HKEY_CLASSES_ROOT
            base_path = ""

        ext_path = f"{base_path}\\.nvdaprofile" if base_path else ".nvdaprofile"
        type_path = f"{base_path}\\NVDAProfile" if base_path else "NVDAProfile"

        # Register file extension
        with winreg.CreateKey(root_key, ext_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "NVDAProfile")

        # Register file type
        with winreg.CreateKey(root_key, type_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "NVDA Profile Backup")

        # Set icon
        with winreg.CreateKey(root_key, f"{type_path}\\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe_path}",0')

        # Set open command
        with winreg.CreateKey(root_key, f"{type_path}\\shell\\open\\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

        location = "current user" if use_hkcu else "system-wide"
        return True, f"File type registered successfully ({location}).\n\nYou may need to restart Explorer or log out/in for changes to take effect."

    except PermissionError:
        return False, "Permission denied. Try running as administrator for system-wide registration."
    except Exception as e:
        return False, f"Failed to register file type: {str(e)}"


def unregister_filetype(use_hkcu: bool = False) -> Tuple[bool, str]:
    """Remove .nvdaprofile file type association.

    Args:
        use_hkcu: If True, remove from HKEY_CURRENT_USER.
                  If False, remove from HKEY_CLASSES_ROOT (requires admin).

    Returns:
        Tuple of (success, message)
    """
    try:
        if use_hkcu:
            root_key = winreg.HKEY_CURRENT_USER
            base_path = r"Software\Classes"
        else:
            if not is_admin():
                return False, "Administrator privileges required for system-wide unregistration."
            root_key = winreg.HKEY_CLASSES_ROOT
            base_path = ""

        ext_path = f"{base_path}\\.nvdaprofile" if base_path else ".nvdaprofile"
        type_path = f"{base_path}\\NVDAProfile" if base_path else "NVDAProfile"

        def delete_key_recursive(root, path):
            try:
                with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    while True:
                        try:
                            subkey = winreg.EnumKey(key, 0)
                            delete_key_recursive(root, f"{path}\\{subkey}")
                        except OSError:
                            break
                winreg.DeleteKey(root, path)
            except FileNotFoundError:
                pass

        delete_key_recursive(root_key, ext_path)
        delete_key_recursive(root_key, type_path)

        location = "current user" if use_hkcu else "system-wide"
        return True, f"File type unregistered successfully ({location})."

    except PermissionError:
        return False, "Permission denied. Try running as administrator."
    except Exception as e:
        return False, f"Failed to unregister file type: {str(e)}"


def is_filetype_registered() -> Tuple[bool, str]:
    """Check if .nvdaprofile file type is registered.

    Returns:
        Tuple of (is_registered, location) where location is 'user', 'system', or ''
    """
    # Check HKCU first
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.nvdaprofile"):
            return True, "user"
    except FileNotFoundError:
        pass

    # Check HKCR
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".nvdaprofile"):
            return True, "system"
    except FileNotFoundError:
        pass

    return False, ""
