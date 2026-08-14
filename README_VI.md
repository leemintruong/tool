# Ghi chú tương thích pipeline V6

Hướng dẫn hiện hành nằm tại [README.md](README.md). Các lệnh `build`, `render`, `tts`, `subtitle`, `metadata`, `thumbnail` và `pull` từ V6 vẫn được giữ để không làm hỏng quy trình cũ.

Điểm khác trong V7.1:

- model Piper không còn nằm trong Git; chạy `INSTALL_PIPER_WINDOWS.bat` để tải;
- `input/script.txt` và `input/voice.wav` là dữ liệu local, không được commit;
- `output/` không được commit;
- subtitle render được hiệu chỉnh theo tổng thời lượng voice;
- `scenes.json` được dùng để phân bổ media và tạo `render_manifest.json`;
- file output cũ không còn lẫn vào lần render mới.

Kiểm tra toàn bộ lệnh:

```powershell
.\.venv\Scripts\python.exe .\app.py --help
```
