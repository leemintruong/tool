# Thiết lập môi trường Windows

## Phiên bản hỗ trợ

- Windows 10/11 64-bit.
- Python 3.10–3.13; khuyến nghị 3.12.

## Cài core

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
.\.venv\Scripts\python.exe .\app.py doctor
```

`SETUP_WINDOWS.ps1` tạo `.venv`, cài `requirements.txt` và kiểm tra FFmpeg, yt-dlp, Whisper, Deno cùng Piper. `imageio-ffmpeg` cung cấp FFmpeg dự phòng nên không bắt buộc thêm FFmpeg thủ công vào `PATH`.

## Thành phần tùy chọn

```text
INSTALL_DENO_WINDOWS.bat
INSTALL_WHISPER_WINDOWS.bat
INSTALL_PIPER_WINDOWS.bat
```

Piper được cài trong `.venv` và voice model được tải vào `voices`. Không cần commit executable hoặc model lên Git.

## Chuẩn bị input local

```powershell
Copy-Item .\input\script.example.txt .\input\script.txt
Copy-Item .\input\youtube_urls.example.txt .\input\youtube_urls.txt
```

Các file local này cùng `input\voice.wav`, `projects` và `output` đều được Git bỏ qua.
