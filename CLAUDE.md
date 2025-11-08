# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NVDA Profile Manager is a Python3 wxPython application that manages NVDA screen reader profiles. It allows users to backup and restore their NVDA configuration from `C:\Users\<username>\AppData\Roaming\nvda`.

## Core Functionality

- **Backup**: Creates `.nvdaprofile` files (ZIP archives) containing all NVDA configuration files and folders
- **Restore**: Deletes existing NVDA folder and restores from a `.nvdaprofile` backup
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
- **Restore Process**: The restore operation is destructive - it deletes the existing NVDA folder before extraction

## Important Considerations

- Always verify NVDA is not running before performing restore operations to avoid file locks
- Include proper error handling for file system operations (permissions, disk space, locked files)
- Prompt for confirmation before destructive operations (restore/delete)
- Use `os.path.expandvars` or `os.getenv('APPDATA')` to handle user-specific paths correctly
