# YouTube Auto Factory MVP V7.1

Công cụ Python chạy local để lấy transcript từ URL YouTube, tạo prompt viết lại có kiểm soát và dựng video từ kịch bản, voice cùng media mà bạn có quyền sử dụng.

## Phạm vi hiện tại

Luồng V7:

```text
YouTube URL
→ metadata và subtitle bằng yt-dlp
→ fallback audio khi không có subtitle
→ faster-whisper nếu cần chép lời
→ transcript_clean.txt
→ rewrite_prompt.txt
→ người dùng viết và duyệt kịch bản mới
→ kiểm tra cụm từ trùng
```

Luồng render hiện có:

```text
script.txt + voice/Piper + media local
→ scene plan
→ subtitle khớp tổng thời lượng audio
→ chọn media theo từ khóa cảnh
→ FFmpeg render
→ final_video.mp4 + thumbnail + metadata
```

V7.1 chưa tự gọi API AI, chưa có hàng đợi render theo project và chưa có giao diện web/WinForms.

## Yêu cầu

- Windows 10 hoặc Windows 11.
- Python 3.10–3.13; khuyến nghị Python 3.12.
- Kết nối mạng cho `yt-dlp`, tải Whisper/Piper và voice model.
- Chỉ tải, xử lý và xuất bản nội dung mà bạn sở hữu hoặc có quyền sử dụng.

## Cài đặt Windows

Mở PowerShell trong thư mục dự án:

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
.\.venv\Scripts\python.exe .\app.py doctor
```

Các thành phần tùy chọn:

```text
INSTALL_DENO_WINDOWS.bat      cải thiện khả năng trích xuất YouTube của yt-dlp
INSTALL_WHISPER_WINDOWS.bat   chép lời khi video không có subtitle
INSTALL_PIPER_WINDOWS.bat     cài Piper và tải voice en_US-lessac-medium
```

## Lấy transcript từ một URL

```powershell
.\.venv\Scripts\python.exe .\app.py ingest `
  --url "https://www.youtube.com/watch?v=VIDEO_ID" `
  --projects-root projects `
  --languages "en,en-US,en-GB,vi"
```

Kết quả chính:

```text
projects\VIDEO_ID\
├── project.json
├── source\metadata.json
├── transcript\transcript_clean.txt
├── transcript\transcript_timed.txt
├── transcript\transcript_segments.json
├── prompts\rewrite_prompt.txt
├── scripts\
├── qa\
└── output\
```

File đưa vào AI là:

```text
projects\VIDEO_ID\prompts\rewrite_prompt.txt
```

## Xử lý nhiều URL

Sao chép file mẫu rồi thêm mỗi URL trên một dòng:

```powershell
Copy-Item .\input\youtube_urls.example.txt .\input\youtube_urls.txt
notepad .\input\youtube_urls.txt
```

Sau đó chạy `RUN_BATCH_INGEST.bat` hoặc:

```powershell
.\.venv\Scripts\python.exe .\app.py batch-ingest --file .\input\youtube_urls.txt
```

## Kiểm tra kịch bản đã viết lại

Lưu kịch bản mới tại:

```text
projects\VIDEO_ID\scripts\rewritten_script.txt
```

Chạy:

```powershell
.\.venv\Scripts\python.exe .\app.py validate-script --project VIDEO_ID
```

Báo cáo nằm trong `projects\VIDEO_ID\qa`. Đây là kiểm tra biên tập bằng cụm từ trùng chính xác, không phải kết luận pháp lý.

## Dựng video với voice có sẵn

```powershell
Copy-Item .\input\script.example.txt .\input\script.txt
```

Thay nội dung `input\script.txt`, đặt voice tại `input\voice.wav`, đặt ảnh/video có quyền sử dụng trong `assets\stock_images`, rồi chạy:

```powershell
.\.venv\Scripts\python.exe .\app.py build `
  --script .\input\script.txt `
  --voice .\input\voice.wav `
  --media .\assets\stock_images `
  --out .\output\video_001 `
  --thumbnail-text "KICKED OUT" `
  --burn-subtitles
```

## Dựng video bằng Piper

Chạy `INSTALL_PIPER_WINDOWS.bat` một lần. Sau đó:

```powershell
.\.venv\Scripts\python.exe .\app.py build `
  --script .\input\script.txt `
  --tts-model .\voices\en_US-lessac-medium.onnx `
  --media .\assets\stock_images `
  --out .\output\video_auto `
  --burn-subtitles
```

Hoặc nhấp đúp `RUN_ALL_PIPER_BUILD.bat`.

## Output render

```text
output\video_001\
├── final_video.mp4
├── subtitles.srt
├── scenes.json
├── render_manifest.json
├── metadata.json
├── thumbnail.jpg
└── segments\
```

`render_manifest.json` ghi lại cảnh, từ khóa, media và thời lượng của từng segment. Subtitle được co giãn theo tổng thời lượng voice thật để không trôi dần khỏi audio.

## Dữ liệu không đưa lên Git

Repository chỉ lưu mã nguồn và file mẫu nhỏ. Các mục sau được `.gitignore` loại trừ:

- `output/` và `projects/`;
- voice/audio/video local;
- model `.onnx`;
- media người dùng tự thêm;
- `.venv`, cache Python và log.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Lệnh hữu ích

```powershell
.\.venv\Scripts\python.exe .\app.py --help
.\.venv\Scripts\python.exe .\app.py doctor
.\.venv\Scripts\python.exe .\app.py list-projects
.\.venv\Scripts\python.exe .\app.py project-status --project VIDEO_ID
.\.venv\Scripts\python.exe .\app.py subtitle --script input\script.txt --audio input\voice.wav --out output\subtitles.srt
```
