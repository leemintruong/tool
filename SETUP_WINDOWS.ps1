# YouTube Auto Factory MVP V7.1 - Windows setup (ASCII-safe)
$ErrorActionPreference = "Stop"

if ($PSScriptRoot) {
    Set-Location $PSScriptRoot
}

Write-Host "=== YouTube Auto Factory MVP V7.1 - Windows Setup ===" -ForegroundColor Cyan
Write-Host "Project folder: $PSScriptRoot" -ForegroundColor DarkGray

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PythonRuntime {
    param([string]$Command, [string[]]$PrefixArgs = @())
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & $Command @PrefixArgs -c "import sys; ok=(3,10) <= sys.version_info[:2] <= (3,13); print(sys.executable); raise SystemExit(0 if ok else 1)" *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch { return $false }
    finally { $ErrorActionPreference = $previousPreference }
}

function Find-PythonRuntime {
    $result = @{ Command = $null; Args = @() }
    foreach ($version in @("-3.12", "-3.13", "-3.11", "-3.10", "-3")) {
        if ((Test-Command "py") -and (Test-PythonRuntime -Command "py" -PrefixArgs @($version))) {
            $result.Command = "py"; $result.Args = @($version); return $result
        }
    }
    foreach ($name in @("python", "python3")) {
        if ((Test-Command $name) -and (Test-PythonRuntime -Command $name)) {
            $result.Command = $name; return $result
        }
    }
    $knownPaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
        (Join-Path ${env:ProgramFiles} "Python313\python.exe"),
        (Join-Path ${env:ProgramFiles} "Python312\python.exe"),
        (Join-Path ${env:ProgramFiles} "Python311\python.exe"),
        (Join-Path ${env:ProgramFiles} "Python310\python.exe")
    )
    foreach ($candidate in $knownPaths) {
        if ((Test-Path $candidate) -and (Test-PythonRuntime -Command $candidate)) {
            $result.Command = $candidate; return $result
        }
    }
    return $result
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$useExistingVenv = $false
if ((Test-Path $venvPython) -and (Test-PythonRuntime -Command $venvPython)) {
    Write-Host "Existing .venv detected. Reusing it." -ForegroundColor Green
    $useExistingVenv = $true
}
elseif (Test-Path $venvPython) {
    throw "The existing .venv is broken. Rename or delete .venv and run setup again."
}

if (-not $useExistingVenv) {
    $runtime = Find-PythonRuntime
    $pythonCmd = $runtime.Command
    $pythonArgs = $runtime.Args
    if (-not $pythonCmd) {
        Write-Host "No usable Python runtime was found. Installing Python 3.12..." -ForegroundColor Yellow
        if (-not (Test-Command "winget")) {
            throw "Python and winget are unavailable. Install Python 3.12 manually and run setup again."
        }
        & winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw "Python installation failed." }
        $runtime = Find-PythonRuntime
        $pythonCmd = $runtime.Command
        $pythonArgs = $runtime.Args
        if (-not $pythonCmd) {
            $directPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
            if ((Test-Path $directPython) -and (Test-PythonRuntime -Command $directPython)) {
                $pythonCmd = $directPython; $pythonArgs = @()
            }
        }
        if (-not $pythonCmd) {
            throw "Python was installed but cannot be found in this session. Restart PowerShell and rerun setup."
        }
    }
    Write-Host "Creating .venv..." -ForegroundColor Cyan
    & $pythonCmd @pythonArgs -m venv ".venv"
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv." }
}

if (-not (Test-Path ".\requirements.txt")) { throw "requirements.txt was not found." }
if (-not (Test-Path ".\app.py")) { throw "app.py was not found." }

Write-Host "Virtual environment Python:" -ForegroundColor Cyan
& $venvPython --version

Write-Host "Upgrading pip tools..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

Write-Host "Installing project requirements..." -ForegroundColor Cyan
& $venvPython -m pip install -r ".\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "requirements installation failed." }

foreach ($folder in @("projects", "input", "output", "assets")) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
}

$piperExe = Join-Path $PSScriptRoot ".venv\Scripts\piper.exe"
if (-not (Test-Path $piperExe)) {
    Write-Host "Piper is optional and is not installed yet." -ForegroundColor Yellow
    Write-Host "Run INSTALL_PIPER_WINDOWS.bat before using --tts-model." -ForegroundColor Yellow
}

Write-Host "Running environment doctor..." -ForegroundColor Cyan
& $venvPython ".\app.py" doctor
if ($LASTEXITCODE -ne 0) { throw "Environment doctor failed." }

Write-Host "" 
Write-Host "SETUP COMPLETED." -ForegroundColor Green
Write-Host "Run RUN_INGEST_SAMPLE.bat to test URL-to-TXT." -ForegroundColor Cyan
Write-Host "Run INSTALL_PIPER_WINDOWS.bat once before building with Piper TTS." -ForegroundColor Cyan
