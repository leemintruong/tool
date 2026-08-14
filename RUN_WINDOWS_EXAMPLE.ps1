$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Chưa có .venv. Hãy chạy SETUP_WINDOWS.ps1 trước."
}
if (-not (Test-Path "input\script.txt")) {
    throw "Chưa có input\script.txt. Hãy copy từ input\script.example.txt rồi thay nội dung mẫu."
}
if (-not (Test-Path "input\voice.wav")) {
    throw "Chưa có input\voice.wav."
}

& $python app.py doctor

& $python app.py build `
  --script input/script.txt `
  --voice input/voice.wav `
  --media assets/stock_images `
  --out output/video_001 `
  --thumbnail-text "KICKED OUT" `
  --burn-subtitles
