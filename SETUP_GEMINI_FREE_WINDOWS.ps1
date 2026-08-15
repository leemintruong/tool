$ErrorActionPreference = "Stop"

if ($PSScriptRoot) {
    Set-Location $PSScriptRoot
}

Write-Host "=== Gemini Free setup for YouTube Auto Factory V7.2 ===" -ForegroundColor Cyan
Write-Host "Create a Gemini API key in Google AI Studio, then return here." -ForegroundColor Yellow
Write-Host "Official page: https://aistudio.google.com/api-keys" -ForegroundColor DarkGray

$openPage = Read-Host "Open the Google AI Studio API key page now? (Y/N)"
if ($openPage -match "^[Yy]") {
    Start-Process "https://aistudio.google.com/api-keys"
}

$secureKey = Read-Host "Paste GEMINI_API_KEY (input is hidden)" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ([string]::IsNullOrWhiteSpace($plainKey) -or $plainKey.Length -lt 20) {
        throw "The API key is empty or too short. No setting was changed."
    }
    [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $plainKey, "User")
    $env:GEMINI_API_KEY = $plainKey
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

Write-Host "GEMINI_API_KEY was saved to your Windows user environment." -ForegroundColor Green
Write-Host "The key was not written into the project or Git." -ForegroundColor Green

if (Test-Path ".\.venv\Scripts\python.exe") {
    & ".\.venv\Scripts\python.exe" ".\app.py" doctor
}

Write-Host "Close all PowerShell windows and open a new one before using batch-rewrite." -ForegroundColor Yellow
