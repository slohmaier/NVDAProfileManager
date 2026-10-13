"""NVDA Process Management Utilities"""

import json
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

# NVDA's main process plus its helper (nvda_slave.exe). The helper is spawned
# for elevated/UIAccess tasks and is known to linger after the main process is
# gone (nvaccess/nvda#3890), still holding handles on the configuration folder.
NVDA_MAIN = 'nvda.exe'
NVDA_SLAVE = 'nvda_slave.exe'
NVDA_PROCESS_NAMES = (NVDA_MAIN, NVDA_SLAVE)


def _process_name(proc) -> str:
    """Return a process's image name in lower case, or '' if unavailable."""
    try:
        name = proc.info.get('name') if proc.info else None
        if not name:
            name = proc.name()
        return (name or '').lower()
    except Exception:
        return ''


def get_running_nvda_processes() -> list:
    """Return the running NVDA processes (main and helper) as psutil objects.

    Returns an empty list when psutil is unavailable; use ``is_nvda_running``
    for a tasklist-based check in that case.
    """
    if psutil is None:
        return []

    found = []
    for proc in psutil.process_iter(['name']):
        try:
            if _process_name(proc) in NVDA_PROCESS_NAMES:
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def find_nvda_executable() -> Optional[str]:
    """Find the NVDA executable path.

    Checks the standard install locations first, then falls back to resolving
    the path from a running NVDA process (via psutil). The latter covers
    portable installs and non-standard locations that the fixed list misses.
    """
    possible_paths = [
        r"C:\Program Files (x86)\NVDA\nvda.exe",
        r"C:\Program Files\NVDA\nvda.exe",
        os.path.join(os.getenv('PROGRAMFILES(X86)', ''), 'NVDA', 'nvda.exe'),
        os.path.join(os.getenv('PROGRAMFILES', ''), 'NVDA', 'nvda.exe'),
    ]

    for path in possible_paths:
        if path and os.path.exists(path):
            return path

    # Resolve from a running process (portable / custom install).
    for proc in get_running_nvda_processes():
        try:
            exe = proc.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if exe and os.path.basename(exe).lower() == NVDA_MAIN:
            return exe
        if exe:
            # The process was the helper; nvda.exe lives beside it.
            candidate = os.path.join(os.path.dirname(exe), NVDA_MAIN)
            if os.path.exists(candidate):
                return candidate

    return None


def is_nvda_running() -> bool:
    """Check if NVDA (main process or helper) is currently running."""
    if psutil is None:
        # Fallback: use tasklist command
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq nvda.exe'],
                capture_output=True, text=True, shell=False
            )
            stdout = result.stdout.lower()
            if NVDA_MAIN in stdout:
                return True
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq {NVDA_SLAVE}'],
                capture_output=True, text=True, shell=False
            )
            return NVDA_SLAVE in result.stdout.lower()
        except Exception:
            return False

    return bool(get_running_nvda_processes())


def get_nvda_process() -> Optional['psutil.Process']:
    """Get the NVDA main process object if running."""
    if psutil is None:
        return None

    for proc in get_running_nvda_processes():
        if _process_name(proc) == NVDA_MAIN:
            return proc

    return None


def stop_nvda(timeout: int = 15) -> bool:
    """Gracefully stop NVDA, escalating only if needed.

    Ask NVDA to quit with ``-q`` (which makes it flush its configuration), wait
    for the main process to exit, then clear any lingering ``nvda_slave.exe``
    helper, which otherwise keeps handles on the configuration folder and blocks
    the restore swap.

    Returns True once no NVDA process remains. Returns False when NVDA could not
    be shut down (e.g. it runs elevated and this process does not, so terminating
    it is denied) — the caller should then ask the user to close it manually or
    run this tool elevated.
    """
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
    if wait_for_nvda_exit(timeout):
        _terminate_slaves()
        return not is_nvda_running()

    # Still running — force the main process down as a last resort.
    denied = False
    main = get_nvda_process()
    if main is not None:
        try:
            main.terminate()
        except psutil.AccessDenied:
            denied = True
        except psutil.NoSuchProcess:
            pass
        except Exception:
            pass

    if not wait_for_nvda_exit(timeout):
        return False

    _terminate_slaves()
    if is_nvda_running() and denied:
        return False
    return not is_nvda_running()


def _terminate_slaves() -> None:
    """Terminate any lingering nvda_slave.exe helper processes."""
    if psutil is None:
        return

    for proc in get_running_nvda_processes():
        if _process_name(proc) != NVDA_SLAVE:
            continue
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Give the slaves a moment to actually exit.
    deadline = time.time() + 5
    while time.time() < deadline:
        if not any(_process_name(p) == NVDA_SLAVE for p in get_running_nvda_processes()):
            return
        time.sleep(0.25)


def wait_for_nvda_exit(timeout: int = 15) -> bool:
    """Wait for NVDA's main process to exit.

    Args:
        timeout: Maximum seconds to wait

    Returns:
        True if the main process exited, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        main = get_nvda_process()
        if main is None:
            # Give a bit more time for file handles to be released
            time.sleep(0.5)
            return True
        time.sleep(0.5)

    return False


def start_nvda() -> bool:
    """Start NVDA screen reader.

    The installed ``nvda.exe`` carries a UIAccess manifest, so launching it with
    ``CreateProcess`` (i.e. ``subprocess.Popen``) fails with WinError 740
    ("requires elevation"). ShellExecute — ``os.startfile`` on Windows — launches
    it the same way the Start Menu does. Falls back to ``Popen`` if ShellExecute
    is unavailable.
    """
    nvda_exe = find_nvda_executable()

    if not nvda_exe:
        return False

    try:
        os.startfile(nvda_exe)
        return True
    except AttributeError:
        pass
    except OSError:
        pass

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


def _rename_with_retry(src: str, dst: str, timeout: float = 15.0,
                       interval: float = 0.5) -> None:
    """``os.rename`` with a bounded retry to ride out transient Windows locks.

    Even after NVDA's processes are gone, Windows can hold directory handles for
    a moment; a bare ``os.rename`` would fail the whole restore. Retrying for a
    short window turns that into a successful operation.
    """
    deadline = time.time() + timeout
    while True:
        try:
            os.rename(src, dst)
            return
        except OSError:
            if time.time() >= deadline:
                raise
            time.sleep(interval)


def _find_latest_backup(nvda_path: str) -> Optional[str]:
    """Return the newest ``<nvda>.bak-*`` rollback folder, or None."""
    parent = os.path.dirname(os.path.abspath(nvda_path))
    base = os.path.basename(os.path.abspath(nvda_path))
    if not os.path.isdir(parent):
        return None

    prefix = f'{base}.bak-'
    candidates = [
        os.path.join(parent, name)
        for name in os.listdir(parent)
        if name.startswith(prefix) and os.path.isdir(os.path.join(parent, name))
    ]
    if not candidates:
        return None
    # The timestamp suffix sorts chronologically.
    return max(candidates, key=lambda p: os.path.basename(p)[len(prefix):])


def has_rollback(nvda_path: str) -> bool:
    """Whether a restorable previous configuration exists for NVDA."""
    return _find_latest_backup(nvda_path) is not None


def _next_backup_path(nvda_path: str) -> str:
    """Return a fresh ``<nvda>.bak-<timestamp>`` path that does not exist yet.

    The timestamp has second resolution, so a restore immediately followed by an
    undo (or two quick restores) could otherwise pick the same name and collide.
    """
    stamp = time.strftime('%Y%m%d-%H%M%S')
    candidate = f'{nvda_path}.bak-{stamp}'
    counter = 1
    while os.path.exists(candidate):
        candidate = f'{nvda_path}.bak-{stamp}-{counter}'
        counter += 1
    return candidate


def safe_restore(nvda_path: str, profile_path: str,
                 descriptor_name: str = 'profile_descriptor.json') -> str:
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
    4. Keep the set-aside folder as a rollback point so the restore can be undone.

    Returns the path of the retained rollback folder ('' if there was no previous
    configuration). Raises on failure, having left the existing configuration
    untouched (or restored).
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
        moved_aside = _next_backup_path(nvda_path)
        _rename_with_retry(nvda_path, moved_aside)

    # 3. Swap the staged folder in; roll back on failure.
    try:
        _rename_with_retry(staging, nvda_path)
    except Exception:
        if moved_aside and not os.path.exists(nvda_path):
            _rename_with_retry(moved_aside, nvda_path)
        remove_tree(staging)
        raise

    # 4. Success — keep the set-aside folder as a rollback point (see undo_restore).
    return moved_aside


def undo_restore(nvda_path: str) -> None:
    """Swap the most recent rollback folder back in as the live configuration.

    The current (just-restored) folder is set aside as a new ``.bak-`` folder
    first, so the undo itself is reversible. Raises if there is no rollback to
    return to.
    """
    backup = _find_latest_backup(nvda_path)
    if not backup:
        raise RuntimeError('No rollback (backup) configuration found to restore.')

    parent = os.path.dirname(os.path.abspath(nvda_path))

    # Set the current configuration aside so the undo can itself be undone.
    current_aside = ''
    if os.path.exists(nvda_path):
        current_aside = _next_backup_path(nvda_path)
        _rename_with_retry(nvda_path, current_aside)

    try:
        _rename_with_retry(backup, nvda_path)
    except Exception:
        if current_aside and not os.path.exists(nvda_path):
            _rename_with_retry(current_aside, nvda_path)
        raise


def cleanup_stale_restore_dirs(nvda_path: str, keep_backups: int = 3) -> None:
    """Clean up folders left behind next to the NVDA configuration folder.

    Staging folders (``nvda_restore_*``) orphaned by an interrupted restore are
    always removed — the live folder is already in place when this runs, so they
    are pure clutter. Rollback folders (``<nvda>.bak-*``) are *kept* since they
    are the user's undo points; only the newest ``keep_backups`` are retained and
    older ones pruned. Called at startup.
    """
    parent = os.path.dirname(os.path.abspath(nvda_path))
    base = os.path.basename(os.path.abspath(nvda_path))
    if not os.path.isdir(parent):
        return

    prefix = f'{base}.bak-'
    backups = []

    for name in os.listdir(parent):
        full = os.path.join(parent, name)
        if not os.path.isdir(full):
            continue
        if name.startswith('nvda_restore_'):
            try:
                remove_tree(full)
            except OSError:
                pass
        elif name.startswith(prefix):
            backups.append(full)

    # Keep the newest N rollback folders; prune the rest (oldest first).
    backups.sort(key=lambda p: os.path.basename(p)[len(prefix):], reverse=True)
    for full in backups[keep_backups:]:
        try:
            remove_tree(full)
        except OSError:
            pass


def build_profile_archive(nvda_path: str, output_path: str, descriptor: dict,
                          exclude_tmp: bool = True) -> bool:
    """Write a ``.nvdaprofile`` ZIP of ``nvda_path`` to ``output_path`` safely.

    The archive is built in a temporary file on the same volume and swapped into
    place with an atomic ``os.replace`` once complete, so an error midway (a file
    locked by a running NVDA, a full disk) leaves any existing archive at
    ``output_path`` untouched.

    ``exclude_tmp`` skips files ending in ``.tmp`` — NVDA leaves
    ``nvda.ini*.tmp`` atomic-write files in the configuration folder, which must
    not be captured in a backup. Empty directories are preserved, since NVDA
    relies on several of them existing (``profiles/``, ``updates/``, ...).

    Returns True on success; raises on failure.
    """
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix='.nvdaprofile.tmp', dir=out_dir)
    os.close(fd)

    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr('profile_descriptor.json', json.dumps(descriptor, indent=2))

            for root, dirs, files in os.walk(nvda_path):
                kept = [
                    f for f in files
                    if not (exclude_tmp and f.lower().endswith('.tmp'))
                ]
                for file in kept:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, nvda_path)
                    zipf.write(file_path, arcname)

                # Preserve empty directories, which the file loop above would
                # otherwise drop.
                if (not kept and not dirs
                        and os.path.abspath(root) != os.path.abspath(nvda_path)):
                    arcname = os.path.relpath(root, nvda_path).replace(os.sep, '/') + '/'
                    zipf.writestr(zipfile.ZipInfo(arcname), '')

        os.replace(tmp_path, output_path)

    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

    return True


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
