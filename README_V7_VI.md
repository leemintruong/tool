# Kiến trúc YouTube Auto Factory V7.2

Hướng dẫn sử dụng chính nằm tại [README.md](README.md).

## Các service

- `factory_core/project_manager.py`: tạo thư mục, nâng schema cũ và quản lý trạng thái project.
- `factory_core/youtube_service.py`: metadata, subtitle và audio fallback qua yt-dlp.
- `factory_core/transcript_service.py`: đọc subtitle, bỏ caption lặp và xuất transcript.
- `factory_core/transcription_service.py`: chép lời local bằng faster-whisper.
- `factory_core/prompt_service.py`: tạo prompt theo profile YAML.
- `factory_core/gemini_service.py`: gọi Gemini Free bằng HTTPS, không cần SDK, retry lỗi tạm thời và 429.
- `factory_core/rewrite_service.py`: lưu draft, tách title/script, kiểm tra trùng và hủy duyệt cũ khi viết lại.
- `factory_core/originality_service.py`: kiểm tra cụm từ trùng chính xác và ghi SHA-256.
- `factory_core/approval_service.py`: tạo và xác minh `approved_script.txt` cùng `qa/approval.json`.
- `factory_core/build_service.py`: chỉ dựng project sau khi xác minh phê duyệt.
- `factory_core/ingest_service.py`: điều phối URL → transcript → prompt.

## Trạng thái project

```text
PENDING
INGESTING_METADATA
DOWNLOADING_SUBTITLE
DOWNLOADING_REFERENCE_AUDIO
TRANSCRIBING_AUDIO
AUDIO_READY_WHISPER_REQUIRED
NO_TRANSCRIPT_AVAILABLE
WAITING_FOR_REWRITE
REWRITING_WITH_GEMINI
REWRITE_FAILED
WAITING_FOR_APPROVAL
SCRIPT_APPROVED
BUILDING_VIDEO
VIDEO_BUILT
BUILD_FAILED
FAILED
```

## Biên giới an toàn giữa AI và render

```text
rewritten_script.txt
→ người dùng đọc/sửa
→ approve-script
→ approved_script.txt + approval.json
→ xác minh SHA-256
→ build-project
```

Gemini chỉ được phép đi đến `WAITING_FOR_APPROVAL`. Không có lời gọi AI nào tự tạo `approved_script.txt`. `build-project` từ chối khi:

- project chưa ở trạng thái đã duyệt;
- thiếu file duyệt hoặc manifest;
- `approved_script.txt` bị sửa;
- `rewritten_script.txt` thay đổi sau lần duyệt.

Các lệnh `build` và `render` cũ cũng từ chối file nằm trong project nếu không phải bản đã duyệt hợp lệ.

## Gemini Free

- Model mặc định: `gemini-3.1-flash-lite`.
- Endpoint: Gemini `generateContent` qua HTTPS.
- API key: chỉ đọc từ `GEMINI_API_KEY` trong Windows User Environment.
- Không ghi key vào URL, log, JSON, project hoặc Git.
- Batch chạy tuần tự; mặc định chờ 10 giây giữa các project.
- Lỗi 429/5xx được retry; khi hết Free Tier, batch dừng để chạy tiếp sau.
- Raw response được lưu phiên bản trong `scripts/drafts` để phục hồi.

## Renderer

Renderer V7.2 kế thừa các sửa lỗi V7.1:

- subtitle được hiệu chỉnh theo thời lượng audio thật;
- scene plan không bỏ mất đoạn cuối;
- phân bổ segment theo trọng số cảnh;
- ưu tiên media có tên khớp từ khóa;
- tránh media lặp liên tiếp khi có lựa chọn khác;
- ghi `render_manifest.json`;
- giữ video final cũ nếu lần render mới thất bại;
- escape đường dẫn subtitle trên Windows.

## Chưa triển khai

- WinForms hoặc web UI.
- AI tạo/chọn asset theo scene.
- Render queue nhiều project.
- Tự đăng nội dung lên nền tảng.
