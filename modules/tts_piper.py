import subprocess
from pathlib import Path

from .env_check import get_piper_bin
from .text_utils import read_text


def create_voice_with_piper(script_path: str, out_wav: str, model_path: str, piper_bin: str = "piper") -> str:
    """
    Requires Piper installed and a downloaded .onnx voice model.
    Example:
    python app.py tts --script input/script.txt --out input/voice.wav --model voices/en_US-lessac-medium.onnx
    """
    text = read_text(script_path)
    model = Path(model_path).expanduser().resolve()
    config = Path(str(model) + ".json")
    if not model.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy Piper voice model: {model}\n"
            "Hãy chạy INSTALL_PIPER_WINDOWS.bat để tải model mặc định."
        )
    if not config.is_file():
        raise FileNotFoundError(f"Không tìm thấy cấu hình Piper voice: {config}")

    output = Path(out_wav).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    executable = get_piper_bin(piper_bin)
    cmd = [executable, "--model", str(model), "--output-file", str(output)]
    subprocess.run(cmd, input=text, text=True, check=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Piper completed but did not create a valid WAV file: {output}")
    return str(output)
