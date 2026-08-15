# YouTube Auto Factory MVP V7.2

Công cụ Python chạy local trên Windows để thu thập transcript từ nhiều URL YouTube, tạo prompt, dùng Gemini Free viết bản nháp mới, kiểm tra trùng, yêu cầu người dùng duyệt rồi mới dựng video.

Chỉ tải, xử lý và xuất bản nội dung mà bạn sở hữu hoặc có quyền sử dụng. Kiểm tra độ trùng của công cụ là hỗ trợ biên tập, không phải kết luận pháp lý hoặc bảo đảm chống khiếu nại nền tảng.

## Luồng V7.2

```text
Nhiều URL YouTube
→ metadata + subtitle bằng yt-dlp
→ audio + faster-whisper nếu không có subtitle
→ transcript_clean.txt + rewrite_prompt.txt
→ Gemini Free tạo rewritten_script.txt
→ kiểm tra cụm từ trùng
→ WAITING_FOR_APPROVAL
→ người dùng đọc, sửa và chạy approve-script
→ SCRIPT_APPROVED
→ build-project tạo voice/video
```

Gemini không tự duyệt và không tự dựng. `build-project` chỉ đọc `approved_script.txt` có chữ ký SHA-256 hợp lệ. Nếu sửa kịch bản sau khi duyệt, công cụ bắt buộc duyệt lại.

## Yêu cầu

- Windows 10 hoặc Windows 11 64-bit.
- Python 3.10–3.13; khuyến nghị Python 3.12.
- Kết nối mạng cho yt-dlp, Whisper, Piper và Gemini API.
- Gemini API key từ Google AI Studio nếu dùng viết lại tự động.

## 1. Cài core

Mở PowerShell trong thư mục dự án:

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
.\.venv\Scripts\python.exe .\app.py doctor
```

Các thành phần bổ sung:

```text
INSTALL_DENO_WINDOWS.bat          cải thiện khả năng trích xuất YouTube
INSTALL_WHISPER_WINDOWS.bat       chép lời khi video không có subtitle
INSTALL_PIPER_WINDOWS.bat         cài Piper và voice en_US-lessac-medium
SETUP_GEMINI_FREE_WINDOWS.bat     lưu API key an toàn trong Windows User Environment
```

## 2. Thiết lập Gemini Free

Tạo API key tại [Google AI Studio](https://aistudio.google.com/api-keys), sau đó chạy:

```powershell
.\SETUP_GEMINI_FREE_WINDOWS.bat
```

Nhập key trong ô ẩn, đóng toàn bộ PowerShell rồi mở lại. Kiểm tra:

```powershell
cd "C:\Users\OS\Desktop\youtube_auto_factory_v7_2"
.\.venv\Scripts\python.exe .\app.py doctor
```

Kết quả cần có:

```text
gemini_api_key: SET
gemini_model_default: gemini-3.1-flash-lite
project_engine: 7.2.0
```

API key không được ghi vào repository. Model mặc định `gemini-3.1-flash-lite` được chọn vì có Free Tier; có thể đổi bằng `--model`. Hạn mức miễn phí do Google quyết định và có thể thay đổi. Theo điều khoản Free Tier của Google, dữ liệu gửi lên có thể được dùng để cải thiện sản phẩm; không gửi dữ liệu riêng tư hoặc bí mật.

## 3. Nhập nhiều nguồn YouTube

Tạo danh sách local:

```powershell
Copy-Item .\input\youtube_urls.example.txt .\input\youtube_urls.txt
notepad .\input\youtube_urls.txt
```

Mỗi dòng là một URL:

```text
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
https://www.youtube.com/watch?v=VIDEO_ID_3
```

Chạy:

```powershell
.\RUN_BATCH_INGEST.bat
```

Hoặc dùng lệnh đầy đủ:

```powershell
.\.venv\Scripts\python.exe .\app.py batch-ingest `
  --file .\input\youtube_urls.txt `
  --projects-root projects `
  --languages "en,en-US,en-GB,vi"
```

Mỗi URL tạo một thư mục `projects\VIDEO_ID` riêng.

## 4. Gemini viết lại một hoặc nhiều project

Một project:

```powershell
.\.venv\Scripts\python.exe .\app.py rewrite --project VIDEO_ID
```

Toàn bộ project đang ở `WAITING_FOR_REWRITE` hoặc `REWRITE_FAILED`:

```powershell
.\RUN_BATCH_REWRITE_GEMINI.bat
```

Tương đương:

```powershell
.\.venv\Scripts\python.exe .\app.py batch-rewrite `
  --projects-root projects `
  --delay-seconds 10
```

Batch chạy tuần tự để phù hợp Free Tier. Nếu hết quota, batch dừng và giữ nguyên các project còn lại để chạy tiếp sau. Không dùng Gemini Batch API vì chế độ đó không thuộc Free Tier.

Các tùy chọn hữu ích:

```powershell
# Chỉ viết lại hai project được chọn
.\.venv\Scripts\python.exe .\app.py batch-rewrite `
  --project VIDEO_ID_1 --project VIDEO_ID_2

# Thay bản nháp cũ và hủy phê duyệt cũ
.\.venv\Scripts\python.exe .\app.py rewrite `
  --project VIDEO_ID --force

# Đổi model
.\.venv\Scripts\python.exe .\app.py rewrite `
  --project VIDEO_ID --model gemini-3.1-flash-lite
```

Kết quả chính:

```text
projects\VIDEO_ID\
├── scripts\title.txt
├── scripts\rewritten_script.txt
├── scripts\drafts\...txt
├── qa\gemini_rewrite.json
├── qa\originality_report.json
└── qa\originality_report.txt
```

Trạng thái sau khi AI chạy thành công luôn là `WAITING_FOR_APPROVAL`.

## 5. Đọc, sửa và duyệt

Mở kịch bản:

```powershell
notepad .\projects\VIDEO_ID\scripts\rewritten_script.txt
```

Kiểm tra lại độ trùng:

```powershell
.\.venv\Scripts\python.exe .\app.py validate-script --project VIDEO_ID
```

Sau khi tự đọc và chấp nhận nội dung:

```powershell
.\.venv\Scripts\python.exe .\app.py approve-script --project VIDEO_ID
```

Hoặc chạy `RUN_APPROVE_PROJECT.bat` và nhập ID. Lệnh này tạo:

```text
scripts\approved_script.txt
qa\approval.json
```

Nếu mức trùng là `HIGH`, phê duyệt bị chặn. Hãy viết lại hoặc sửa kịch bản trước. `--allow-high-overlap` chỉ dành cho trường hợp đã kiểm tra thủ công và tự chấp nhận rủi ro.

Hủy duyệt:

```powershell
.\.venv\Scripts\python.exe .\app.py revoke-approval --project VIDEO_ID
```

## 6. Dựng project đã duyệt

Cài Piper một lần:

```powershell
.\INSTALL_PIPER_WINDOWS.bat
```

Đặt ảnh/video được phép sử dụng trong một thư mục media rồi chạy:

```powershell
.\.venv\Scripts\python.exe .\app.py build-project `
  --project VIDEO_ID `
  --media .\assets\stock_images `
  --tts-model .\voices\en_US-lessac-medium.onnx `
  --burn-subtitles
```

Hoặc dùng voice có sẵn:

```powershell
.\.venv\Scripts\python.exe .\app.py build-project `
  --project VIDEO_ID `
  --media .\assets\stock_images `
  --voice .\input\voice.wav `
  --burn-subtitles
```

Output mặc định:

```text
projects\VIDEO_ID\output\
├── final_video.mp4
├── voice.wav
├── subtitles.srt
├── scenes.json
├── render_manifest.json
├── metadata.json
├── thumbnail.jpg
└── segments\
```

Các lệnh `build` và `render` cũ vẫn hoạt động cho file ngoài project. Nếu trỏ chúng vào `projects\...\scripts`, bộ khóa duyệt vẫn được áp dụng.

## Trạng thái project quan trọng

```text
WAITING_FOR_REWRITE       đã có prompt, chờ AI
REWRITING_WITH_GEMINI     Gemini đang xử lý
REWRITE_FAILED            gọi AI thất bại, có thể chạy lại
WAITING_FOR_APPROVAL      đã có bản nháp, chưa được dựng
SCRIPT_APPROVED           người dùng đã duyệt
BUILDING_VIDEO            đang dựng
VIDEO_BUILT               dựng thành công
BUILD_FAILED              dựng lỗi nhưng vẫn giữ bản duyệt
```

Xem danh sách:

```powershell
.\.venv\Scripts\python.exe .\app.py list-projects
.\.venv\Scripts\python.exe .\app.py project-status --project VIDEO_ID
```

## Dữ liệu không đưa lên Git

`.gitignore` loại trừ:

- `projects/`, `output/`, voice, audio, video và model ONNX;
- API key, `.env`, `credentials.json` và file `*.key`;
- media local, cache Python và log.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Chưa triển khai

- Giao diện WinForms hoặc web.
- Tự tạo hoặc tải hình minh họa theo từng scene.
- Hàng đợi dựng video nhiều project.
- Tự đăng lên Facebook hoặc YouTube.
