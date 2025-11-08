# NVDA Profile Manager

A Python wxPython application for managing NVDA screen reader profiles.

## Features

- **Backup NVDA Profiles**: Create `.nvdaprofile` backup files from your NVDA configuration
- **Restore Profiles**: Restore NVDA configuration from `.nvdaprofile` backups
- **Profile Inspection**: View contents of `.nvdaprofile` files in a tree view
- **Profile Metadata**: Each backup includes username, PC name, and creation date

## Requirements

- Python 3.x
- wxPython

## Installation

```powershell
pip install wxPython
```

## Usage

```powershell
python main.py
```

## Profile Location

The application manages profiles located at:
`C:\Users\<username>\AppData\Roaming\nvda`

## File Format

`.nvdaprofile` files are ZIP archives containing:
- All NVDA configuration files and folders
- A descriptor file with profile metadata (username, PC name, creation date)
