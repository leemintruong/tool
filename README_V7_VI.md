# Kiến trúc YouTube Auto Factory V7.1

Hướng dẫn cài và chạy chính nằm tại [README.md](README.md).

## Các service V7

- `factory_core/project_manager.py`: tạo thư mục và quản lý trạng thái project.
- `factory_core/youtube_service.py`: metadata, subtitle và audio fallback qua `yt-dlp`.
- `factory_core/transcript_service.py`: đọc VTT/SRT/TTML/JSON3, bỏ caption lặp và xuất transcript.
- `factory_core/transcription_service.py`: chép lời local bằng `faster-whisper`.
- `factory_core/prompt_service.py`: tạo prompt theo profile trong `config/profiles`.
- `factory_core/originality_service.py`: kiểm tra cụm từ trùng chính xác.
- `factory_core/ingest_service.py`: điều phối toàn bộ luồng URL → transcript → prompt.

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
FAILED
```

## Renderer hiện tại

Renderer trong `modules` vẫn là lớp tương thích với pipeline V6 nhưng đã được sửa để:

- hiệu chỉnh subtitle theo tổng thời lượng audio thật;
- tạo scene plan mà không bỏ mất đoạn cuối;
- phân bổ segment theo trọng số cảnh;
- ưu tiên media có tên file/thư mục khớp từ khóa cảnh;
- tránh chọn lặp liên tiếp khi có nhiều media;
- ghi `render_manifest.json`;
- giữ lại video final cũ nếu render mới thất bại giữa chừng;
- escape đường dẫn subtitle đúng hơn trên Windows.

## Chưa triển khai

- Gọi API AI để viết lại kịch bản.
- Lệnh import/approve/build theo project V7.
- Voice, asset manifest và render queue độc lập cho từng project.
- Giao diện web hoặc WinForms.

Các phần này thuộc giai đoạn V7 hoàn chỉnh tiếp theo, không nằm trong bản V7.1 hiện tại.
