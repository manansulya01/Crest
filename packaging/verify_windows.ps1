<#
.SYNOPSIS
Repeatable Windows installation verification for CREST 1.1.

Exercises: silent fresh install, native window + backend lifecycle, loopback
API, CSRF-protected writes, credentials at rest, graceful shutdown, restart
persistence, in-place upgrade, data-preserving uninstall, and single-instance.

Run from the repository root in Windows PowerShell:
  powershell -ExecutionPolicy Bypass -File packaging\verify_windows.ps1
#>
param(
  [string]$Installer = 'src-tauri\target\release\bundle\nsis\CREST_1.1.0_x64-setup.exe',
  [string]$InstallRoot = (Join-Path $env:TEMP 'crest-verify-install'),
  [string]$DataDir = (Join-Path $env:TEMP 'crest-verify-data')
)

$ErrorActionPreference = 'Stop'
$report = [ordered]@{}
$secret = 'sk-verify-DPAPI-secret-773465893210'
$appExe = Join-Path $InstallRoot 'crest-desktop.exe'
$installerPath = (Resolve-Path $Installer).Path

function Stop-Crest {
  Get-Process crest-desktop, crest-backend -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 1
}

function Get-BackendRoots {
  $all = @(Get-CimInstance Win32_Process -Filter "Name='crest-backend.exe'")
  $ids = @($all | ForEach-Object { $_.ProcessId })
  return @($all | Where-Object { $ids -notcontains $_.ParentProcessId })
}

function Wait-Runtime([string]$dir, [int]$seconds = 120) {
  $path = Join-Path $dir 'runtime.json'
  for ($i = 0; $i -lt ($seconds * 5); $i++) {
    if (Test-Path $path) {
      try {
        $candidate = Get-Content $path -Raw | ConvertFrom-Json
        # Reject stale descriptors left by a force-killed instance.
        $null = Invoke-RestMethod "http://127.0.0.1:$($candidate.port)/api/v1/health" -TimeoutSec 3
        return $candidate
      } catch {
        Remove-Item $path -Force -ErrorAction SilentlyContinue
      }
    }
    Start-Sleep -Milliseconds 200
  }
  throw "a live runtime.json did not appear in $dir"
}

function Api([string]$base, [string]$path, [string]$token, [string]$method = 'GET', $body = $null) {
  $headers = @{
    'Origin' = 'http://127.0.0.1:9999'
    'X-Crest-CSRF' = $token
  }
  $args = @{ Method = $method; Uri = "$base$path"; Headers = $headers; TimeoutSec = 30 }
  if ($null -ne $body) {
    $args['Body'] = ($body | ConvertTo-Json -Depth 8)
    $args['ContentType'] = 'application/json'
  }
  return Invoke-RestMethod @args
}

function Assert([bool]$condition, [string]$message) {
  if (-not $condition) { throw "ASSERTION FAILED: $message" }
}

try {
  Stop-Crest
  if (Test-Path $InstallRoot) { Remove-Item $InstallRoot -Recurse -Force }
  if (Test-Path $DataDir) { Remove-Item $DataDir -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $InstallRoot, $DataDir | Out-Null

  # ---- 1. Fresh install -------------------------------------------------
  $p = Start-Process -FilePath $installerPath -ArgumentList '/S', "/D=$InstallRoot" -Wait -PassThru
  $report.fresh_install_exit = $p.ExitCode
  Assert ($p.ExitCode -eq 0) 'silent install exit code'
  Assert (Test-Path $appExe) 'installed application executable'
  Assert (Test-Path (Join-Path $InstallRoot 'binaries\crest-backend.exe')) 'bundled backend sidecar'
  Assert (Test-Path (Join-Path $InstallRoot 'uninstall.exe')) 'uninstaller'
  $report.installed_files = @(Get-ChildItem $InstallRoot -Recurse -File -ErrorAction SilentlyContinue).Count

  # The NSIS template may offer "run after install"; ensure a clean start.
  Stop-Crest

  # ---- 2. Launch, native window, health ---------------------------------
  $env:CREST_DATA_DIR = $DataDir
  $app = Start-Process -FilePath $appExe -PassThru
  $rt = Wait-Runtime $DataDir
  $base = "http://127.0.0.1:$($rt.port)"
  $health = Invoke-RestMethod "$base/api/v1/health"
  $info = Invoke-RestMethod "$base/api/v1/system/info"
  $report.version = $health.version
  $report.schema_version = $health.schema_version
  $report.health_status = $health.status
  $report.credential_backend = $info.credentials.backend
  $report.windows_dpapi = $info.credentials.windows_dpapi
  $report.data_dir = $info.paths.data_dir
  $report.backend_root_count = @(Get-BackendRoots).Count
  Assert ($health.status -eq 'ok') 'health status ok'
  Assert ($health.version -eq '1.1.0') 'version 1.1.0'
  Assert ($health.schema_version -eq 2) 'schema version 2'
  Assert ($info.credentials.backend -eq 'dpapi') 'DPAPI credential backend'
  Assert ($report.backend_root_count -eq 1) 'exactly one backend instance'
  $window = @(Get-Process crest-desktop -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
  $report.native_window_title = if ($window.Count) { $window[0].MainWindowTitle } else { '' }
  Assert ($window.Count -eq 1 -and $window[0].MainWindowTitle -eq 'CREST') 'native CREST window'
  $backendWindows = @(Get-Process crest-backend -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
  $report.backend_visible_windows = $backendWindows.Count
  Assert ($backendWindows.Count -eq 0) 'backend has no terminal/window'

  $appPage = Invoke-WebRequest "$base/app" -UseBasicParsing
  $assetMatch = [regex]::Match($appPage.Content, 'src="(/assets/[^"]+\.js)"')
  Assert ($appPage.StatusCode -eq 200 -and $assetMatch.Success) 'web app served by backend'
  $asset = Invoke-WebRequest "$base$($assetMatch.Groups[1].Value)" -UseBasicParsing
  $report.web_asset_status = $asset.StatusCode
  Assert ($asset.StatusCode -eq 200) 'bundled JS asset served'

  # ---- 3. Single-instance ----------------------------------------------
  $second = Start-Process -FilePath $appExe -PassThru
  Start-Sleep -Seconds 8
  $report.desktop_count_after_second = @(Get-Process crest-desktop -ErrorAction SilentlyContinue).Count
  $report.backend_roots_after_second = @(Get-BackendRoots).Count
  Assert ($report.desktop_count_after_second -eq 1) 'single native instance'
  Assert ($report.backend_roots_after_second -eq 1) 'single backend after second launch'

  # ---- 4. CSRF-protected writes, execution, credential storage ----------
  $csrf = Invoke-RestMethod "$base/api/v1/security/csrf"
  $denied = $false
  try {
    Invoke-RestMethod -Method POST -Uri "$base/api/v1/tasks" -Headers @{ Origin = 'http://127.0.0.1:9999' } `
      -Body '{}' -ContentType 'application/json' -TimeoutSec 15 | Out-Null
  } catch { $denied = ($_.Exception.Response.StatusCode.value__ -eq 403) }
  $report.csrf_without_token_denied = $denied
  Assert $denied 'state-changing request without CSRF token is denied'

  $task = Api $base '/api/v1/tasks' $csrf.token 'POST' @{
    title = 'Windows verification task'
    description = 'Deterministic offline verification'
    risk_class = 'low'
    autonomy_level = 3
    provider = 'mock'
    model = 'mock-fast'
    budget = 1.0
    token_budget = 4096
    timeout_seconds = 30
    acceptance_criteria = @('CREST')
  }
  $result = Api $base "/api/v1/tasks/$($task.id)/execute?wait=true" $csrf.token 'POST'
  $report.task_status = $result.status
  Assert ($result.status -eq 'completed') 'offline task completes through installed app'

  $cred = Api $base '/api/v1/credentials/gemini' $csrf.token 'PUT' @{ api_key = $secret; confirm = $true }
  $report.credential_storage = $cred.storage
  Assert ($cred.storage -eq 'dpapi') 'credential stored with DPAPI'
  Assert (-not ($cred | ConvertTo-Json -Compress).Contains($secret)) 'credential response does not leak secret'
  $credStatus = Invoke-RestMethod "$base/api/v1/credentials"
  Assert ($credStatus.providers | Where-Object { $_.provider_id -eq 'gemini' }).configured 'credential reported configured'
  $dbBytes = [IO.File]::ReadAllBytes((Join-Path $DataDir 'crest.db'))
  $secretBytes = [Text.Encoding]::UTF8.GetBytes($secret)
  $found = $false
  for ($i = 0; $i -le $dbBytes.Length - $secretBytes.Length; $i++) {
    $match = $true
    for ($j = 0; $j -lt $secretBytes.Length; $j++) { if ($dbBytes[$i + $j] -ne $secretBytes[$j]) { $match = $false; break } }
    if ($match) { $found = $true; break }
  }
  $report.secret_in_database = $found
  Assert (-not $found) 'secret not present in database bytes'

  # ---- 5. Graceful shutdown --------------------------------------------
  $null = $window[0].CloseMainWindow()
  for ($i = 0; $i -lt 80; $i++) {
    Start-Sleep -Milliseconds 250
    if (@(Get-Process crest-desktop -ErrorAction SilentlyContinue).Count -eq 0 -and
        @(Get-Process crest-backend -ErrorAction SilentlyContinue).Count -eq 0) { break }
  }
  $report.desktop_after_close = @(Get-Process crest-desktop -ErrorAction SilentlyContinue).Count
  $report.backend_after_close = @(Get-Process crest-backend -ErrorAction SilentlyContinue).Count
  $report.runtime_after_close = Test-Path (Join-Path $DataDir 'runtime.json')
  Assert ($report.desktop_after_close -eq 0) 'native window closed'
  Assert ($report.backend_after_close -eq 0) 'backend stopped with window'
  Assert (-not $report.runtime_after_close) 'runtime descriptor cleaned up'

  # ---- 6. Restart persistence ------------------------------------------
  $app = Start-Process -FilePath $appExe -PassThru
  $rt = Wait-Runtime $DataDir
  $base = "http://127.0.0.1:$($rt.port)"
  $persisted = Invoke-RestMethod "$base/api/v1/tasks/$($task.id)"
  $credStatus2 = Invoke-RestMethod "$base/api/v1/credentials"
  $report.task_after_restart = $persisted.status
  $report.credential_after_restart = @($credStatus2.providers | Where-Object { $_.provider_id -eq 'gemini' })[0].configured
  Assert ($persisted.id -eq $task.id) 'task persisted across restart'
  Assert $report.credential_after_restart 'credential persisted across restart'

  $window2 = @(Get-Process crest-desktop -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
  if ($window2.Count) { $null = $window2[0].CloseMainWindow() }
  for ($i = 0; $i -lt 80; $i++) {
    Start-Sleep -Milliseconds 250
    if (@(Get-Process crest-desktop -ErrorAction SilentlyContinue).Count -eq 0) { break }
  }

  # ---- 7. In-place upgrade ---------------------------------------------
  $up = Start-Process -FilePath $installerPath -ArgumentList '/S', "/D=$InstallRoot" -Wait -PassThru
  $report.upgrade_install_exit = $up.ExitCode
  Assert ($up.ExitCode -eq 0) 'in-place upgrade exit code'
  Stop-Crest
  $app = Start-Process -FilePath $appExe -PassThru
  $rt = Wait-Runtime $DataDir
  $base = "http://127.0.0.1:$($rt.port)"
  $afterUpgrade = Invoke-RestMethod "$base/api/v1/tasks/$($task.id)"
  $credStatus3 = Invoke-RestMethod "$base/api/v1/credentials"
  $report.task_after_upgrade = $afterUpgrade.status
  $report.credential_after_upgrade = @($credStatus3.providers | Where-Object { $_.provider_id -eq 'gemini' })[0].configured
  Assert ($afterUpgrade.id -eq $task.id) 'task preserved through upgrade'
  Assert $report.credential_after_upgrade 'credential preserved through upgrade'

  # ---- 8. Uninstall preserves data -------------------------------------
  $uninstaller = Join-Path $InstallRoot 'uninstall.exe'
  $un = Start-Process -FilePath $uninstaller -ArgumentList '/S' -Wait -PassThru
  Start-Sleep -Seconds 2
  $report.uninstall_exit = $un.ExitCode
  $report.install_root_after_uninstall = Test-Path $appExe
  $report.data_after_uninstall = Test-Path (Join-Path $DataDir 'crest.db')
  Assert (-not $report.install_root_after_uninstall) 'application removed by uninstaller'
  Assert $report.data_after_uninstall 'data directory preserved by uninstaller'

  Stop-Crest
  $report.result = 'PASS'
} catch {
  $report.result = 'FAIL'
  $report.error = $_.Exception.Message
} finally {
  $report.generated_at = (Get-Date).ToString('o')
  $out = Join-Path $PSScriptRoot 'verify_windows_report.json'
  $report | ConvertTo-Json -Depth 8 | Set-Content $out -Encoding UTF8
  Write-Host ($report | ConvertTo-Json -Depth 8)
  if ($report.result -ne 'PASS') { exit 1 }
}
