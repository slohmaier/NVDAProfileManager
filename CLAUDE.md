# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NVDA Profile Manager is a Python3 wxPython application that manages NVDA screen reader profiles. It allows users to backup and restore their NVDA configuration from `C:\Users\<username>\AppData\Roaming\nvda`.

## Core Functionality

- **Backup**: Creates `.nvdaprofile` files (ZIP archives) containing all NVDA configuration files and
  folders. The archive is built in a same-volume temp file and swapped in with an atomic
  `os.replace`, so a failure midway never corrupts an existing backup at the destination
  (`nvda_utils.build_profile_archive`). Leftover NVDA `*.tmp` files are excluded.
- **Restore**: Replaces the NVDA folder from a `.nvdaprofile` backup atomically — the backup is
  staged, then swapped in, keeping the current folder until the swap succeeds so a failure rolls
  back (`nvda_utils.safe_restore`). The replaced configuration is **retained as a rollback
  folder** (`<nvda>.bak-<timestamp>`) so the restore can be undone via File > Undo Last Restore
  (`nvda_utils.undo_restore`).
- **NVDA Handling**: NVDA saves its settings on exit and keeps its config files open, so both
  backup and restore require NVDA to be closed first (`main.NVDAProfileManager._ensure_nvda_closed`).
  If it is running the user is offered to close it; `nvda_utils.stop_nvda` quits the main process
  (flushing settings) and clears any lingering `nvda_slave.exe` helper, which otherwise holds
  folder handles. Detection covers both processes and portable installs
  (`nvda_utils.get_running_nvda_processes`, `find_nvda_executable`).
- **Profile Descriptor**: Each `.nvdaprofile` contains metadata (username, PC name, creation date)
- **File Viewer**: Tree view to inspect contents of `.nvdaprofile` files before restoring

## Application Structure

The application uses wxPython for the GUI with the following main menu options:
- Create New Profile
- Save Profile
- Save Profile As
- Open Profile

## Development Commands

**Run the application:**
```powershell
python main.py
```

**Install dependencies:**
```powershell
pip install wxPython
```

**Run the tests** (sandboxed, never touch the real NVDA folder):
```powershell
python -m unittest discover -s tests
```

**Build, installer, signing** (all via SCons):
```powershell
scons build       # dist\NVDAProfileManager.exe (+ refreshes the dev Start Menu entry)
scons installer   # signs the exe, compiles + signs the Inno Setup installer
scons sign        # sign the existing exe and installer in place
scons shortcut    # (re)create the dev Start Menu shortcut only
```

**Dev Start Menu entry:** every `scons build` (re)points
`%APPDATA%\...\Start Menu\Programs\slohmaierDev\NVDAProfileManager (Dev).lnk` at
the freshly built `dist\NVDAProfileManager.exe`, via the shared
`tools\install-dev-shortcut.ps1` (the same launcher group used by ControlNav,
MouseCross, TactiDesk, etc.). `scons shortcut` refreshes it on demand.

## Signing

Signing uses the Certum SimplySign cloud certificate through the shared
`sign-products.ps1` in the ownCloud secrets share (the single source of truth).
No Certum/ssign material (seed, certificate, `ssign.exe`) is ever stored in this
repository. The SConstruct reads the tooling location from a local, git-ignored
`ssign.conf` (template: `ssign.conf.example`, keys `sign_dir` and `sign_script`),
falling back to `OWNCLOUD_SIGN_DIR` and then a default path.

`scons installer` signs the payload exe first (so the copy embedded in Setup.exe
is signed), compiles the installer, then signs the Setup.exe. Signing failures
are retried because the Certum backend rate-limits logins.

## Testing

- `tests/test_nvda_utils.py` covers restore/rollback/undo, backup archive helpers
  (incl. `*.tmp` exclusion and empty-dir preservation), cleanup pruning, read-only
  removal, and process detection with a mocked psutil.
- The suite operates only on temp directories. Live NVDA testing (stopping/starting
  NVDA and swapping the real config) is intentionally NOT part of the suite.

## Key Technical Details

- **NVDA Path**: Default profile location is `%APPDATA%\nvda` (typically `C:\Users\<username>\AppData\Roaming\nvda`)
- **File Format**: `.nvdaprofile` is a ZIP archive with a descriptor file containing JSON metadata
- **Restore Process**: `nvda_utils.safe_restore` stages the extraction, moves the current folder
  aside with an atomic rename (retried briefly via `_rename_with_retry` to ride out transient
  Windows locks), swaps the staged folder in, and on success keeps the set-aside folder as a
  rollback point. `nvda_utils.undo_restore` swaps the newest rollback back in.
  Read-only files (NVDA ships read-only add-on readmes) are handled by `nvda_utils.remove_tree`.
- **Starting NVDA**: the installed `nvda.exe` has a UIAccess manifest, so `subprocess.Popen`
  fails with WinError 740. `nvda_utils.start_nvda` uses `os.startfile` (ShellExecute) instead,
  falling back to `Popen`.

## Important Considerations

- Restore and backup require NVDA to be closed; the GUI blocks and offers to close it first
- Rollback folders (`<nvda>.bak-*`) are kept; `cleanup_stale_restore_dirs` prunes them to the
  newest 3 and deletes only orphaned `nvda_restore_*` staging directories
- Include proper error handling for file system operations (permissions, disk space, locked files)
- Prompt for confirmation before destructive operations (restore/undo/delete)
- Use `os.path.expandvars` or `os.getenv('APPDATA')` to handle user-specific paths correctly
