<#
.SYNOPSIS
Build the CREST 1.1 Windows desktop package from source.

Prerequisites: Python 3.11+, Node 18+, Rust 1.77+ (MSVC), WebView2 runtime.
Run from anywhere:
  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#>
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

Write-Host '==> [1/5] Installing build dependencies'
python -m pip install -r packaging\requirements-build.txt

Write-Host '==> [2/5] Building React frontend'
Push-Location web
if (-not (Test-Path node_modules)) { npm install }
npm run build
npm run lint
Pop-Location

Write-Host '==> [3/5] Building PyInstaller backend sidecar'
python -m PyInstaller --noconfirm `
  --distpath packaging\build\backend `
  --workpath packaging\build\pyinstaller-work `
  packaging\pyinstaller\crest-backend.spec

Write-Host '==> [4/5] Installing sidecar into the Tauri resources'
New-Item -ItemType Directory -Force -Path src-tauri\binaries | Out-Null
Copy-Item packaging\build\backend\crest-backend.exe src-tauri\binaries\crest-backend.exe -Force
if (-not (Test-Path node_modules\@tauri-apps\cli)) { npm install }

Write-Host '==> [5/5] Building the NSIS installer'
npx tauri build

$installer = Join-Path $root 'src-tauri\target\release\bundle\nsis\CREST_1.1.0_x64-setup.exe'
if (-not (Test-Path $installer)) { throw "Installer not produced at $installer" }
$hash = (Get-FileHash $installer -Algorithm SHA256).Hash
Write-Host "BUILD OK: $installer"
Write-Host "SHA256: $hash"
