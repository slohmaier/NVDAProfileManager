@echo off
:: Register .nvdaprofile file type association
:: Must be run as Administrator

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script requires Administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%dist\NVDAProfileManager.exe"

:: Check if exe exists
if not exist "%EXE_PATH%" (
    echo ERROR: NVDAProfileManager.exe not found at:
    echo %EXE_PATH%
    echo.
    echo Please run 'scons build' first to create the executable.
    pause
    exit /b 1
)

echo Registering .nvdaprofile file association...
echo.

:: Register file extension
reg add "HKCR\.nvdaprofile" /ve /d "NVDAProfile" /f
if %errorlevel% neq 0 goto :error

:: Register file type
reg add "HKCR\NVDAProfile" /ve /d "NVDA Profile Backup" /f
if %errorlevel% neq 0 goto :error

:: Set icon
reg add "HKCR\NVDAProfile\DefaultIcon" /ve /d "\"%EXE_PATH%\",0" /f
if %errorlevel% neq 0 goto :error

:: Set open command
reg add "HKCR\NVDAProfile\shell\open\command" /ve /d "\"%EXE_PATH%\" \"%%1\"" /f
if %errorlevel% neq 0 goto :error

echo.
echo SUCCESS: File association registered!
echo.
echo .nvdaprofile files will now open with NVDA Profile Manager.
echo You may need to restart Explorer or log out/in for changes to take effect.
echo.
pause
exit /b 0

:error
echo.
echo ERROR: Failed to register file association.
echo Please ensure you are running as Administrator.
pause
exit /b 1
