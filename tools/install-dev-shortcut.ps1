<#
install-dev-shortcut.ps1

Create or refresh this product's dev Start Menu shortcut so it always points at
the current build. Run right after linking; idempotent, so running it on every
build keeps target, working directory and icon correct.

Shortcut: %APPDATA%\Microsoft\Windows\Start Menu\Programs\slohmaierDev\<Name> (Dev).lnk

Every slohmaier product ships this same script (ControlNav, MouseCross,
AccessShot, TactiPress, TactiDesk, NVDAProfileManager) so dev builds share one
predictable launcher group. A new product gets its own copy and a call from its
build after linking.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$WorkDir,
    [string]$Icon = "",
    [string]$Arguments = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Target)) {
    Write-Warning "install-dev-shortcut: target not found, skipping: $Target"
    exit 1
}

$group = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\slohmaierDev"
New-Item -ItemType Directory -Force -Path $group | Out-Null

$lnk = Join-Path $group ("{0} (Dev).lnk" -f $Name)

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnk)
$sc.TargetPath = $Target
$sc.WorkingDirectory = $WorkDir
if ($Arguments) { $sc.Arguments = $Arguments }
if ($Icon -and (Test-Path -LiteralPath $Icon)) {
    $sc.IconLocation = "$Icon,0"
} else {
    $sc.IconLocation = "$Target,0"
}
$sc.Description = "$Name (Dev)"
$sc.Save()

Write-Host "Start Menu shortcut written: $lnk -> $Target"
