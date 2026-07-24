# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NVDA Profile Manager is a Python3 wxPython application that manages NVDA screen reader profiles. It allows users to backup and restore their NVDA configuration from `C:\Users\<username>\AppData\Roaming\nvda`.

## Core Functionality

- **Backup**: Creates `.nvdaprofile` files (ZIP archives) containing all NVDA configuration files and folders
- **Restore**: Replaces the NVDA folder from a `.nvdaprofile` backup atomically — the backup is
  staged, then swapped in, keeping the current folder until the swap succeeds so a failure rolls
  back (`nvda_utils.safe_restore`)
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

## Key Technical Details

- **NVDA Path**: Default profile location is `%APPDATA%\nvda` (typically `C:\Users\<username>\AppData\Roaming\nvda`)
- **File Format**: `.nvdaprofile` is a ZIP archive with a descriptor file containing JSON metadata
- **Restore Process**: `nvda_utils.safe_restore` stages the extraction, moves the current folder
  aside with an atomic rename, swaps the staged folder in, and only then deletes the set-aside copy.
  Read-only files (NVDA ships read-only add-on readmes) are handled by `nvda_utils.remove_tree`.

## Important Considerations

- Always verify NVDA is not running before performing restore operations to avoid file locks
- Include proper error handling for file system operations (permissions, disk space, locked files)
- Prompt for confirmation before destructive operations (restore/delete)
- Use `os.path.expandvars` or `os.getenv('APPDATA')` to handle user-specific paths correctly
