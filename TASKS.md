# Tasks

## Done

- Robust NVDA handling on backup/restore:
  - Detect `nvda.exe` and `nvda_slave.exe`, resolve portable installs
  - Gracefully quit NVDA (flush settings), clear lingering slaves
  - Retry the folder rename to ride out transient Windows locks
- Keep rollback after restore; add File > Undo Last Restore
- Prune rollback folders to the newest 3 at startup
- Exclude leftover `nvda.ini*.tmp` files from backups (`build_profile_archive`)
- Fix NVDA not starting: use `os.startfile` (ShellExecute) because `nvda.exe`
  has a UIAccess manifest and `Popen` fails with WinError 740
- Sandboxed unit tests (`tests/test_nvda_utils.py`, 20 tests)
- Live end-to-end test on this machine (stop / restore / undo / start): passed
- Inno Setup installer (`installer/NVDAProfileManager.iss`)
- SCons targets `installer` and `sign`; signing via shared `sign-products.ps1`
- Signing config template `ssign.conf.example` (real `ssign.conf` git-ignored);
  no Certum/ssign material in the repo
- v1.1 released with signed installer

## Open

- GUI accessibility pass for the new Undo menu item and dialogs (keyboard only)
- Consider a "discard rollback" action to free disk sooner
- Manual test matrix on a second machine (portable NVDA, different user)
