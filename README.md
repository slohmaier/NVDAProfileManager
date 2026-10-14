# NVDA Profile Manager

A Python wxPython application for managing NVDA screen reader profiles.

## Features

- **Backup NVDA Profiles**: Create `.nvdaprofile` backup files from your NVDA configuration
- **Restore Profiles**: Restore NVDA configuration from `.nvdaprofile` backups
- **Undo Restore**: Bring back the configuration that was replaced by the last restore
- **NVDA-aware**: Backups and restores require NVDA to be closed; the app offers to close it,
  waits for it to fully exit before touching the configuration folder, and starts NVDA again
  automatically when it is done — so you resume with your screen reader running
- **Profile Inspection**: View contents of `.nvdaprofile` files in a tree view
- **Profile Metadata**: Each backup includes username, PC name, and creation date

## Safe Restore

Restore replaces the NVDA folder atomically: the backup is staged first, then swapped in, so a
failure leaves your current configuration untouched. The replaced configuration is kept as a
rollback folder, so you can revert with **File > Undo Last Restore**. The newest three rollback
folders are retained.

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

## Testing

```powershell
python -m unittest discover -s tests
```

The tests are sandboxed and never touch the real NVDA configuration folder.

## Profile Location

The application manages profiles located at:
`C:\Users\<username>\AppData\Roaming\nvda`

## File Format

`.nvdaprofile` files are ZIP archives containing:
- All NVDA configuration files and folders
- A descriptor file with profile metadata (username, PC name, creation date)
