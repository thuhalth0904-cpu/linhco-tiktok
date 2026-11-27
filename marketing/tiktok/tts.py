"""Tạo giọng đọc cho từng dòng kịch bản bằng VieNeu-TTS v3 Turbo (Apache 2.0, chạy CPU).

Giọng có sẵn của VieNeu được phép dùng cho nội dung thương mại (theo trang mô hình).
Dùng: python tts.py script.json out_dir [--silent]
  --silent: không gọi TTS, tạo khoảng lặng theo độ dài chữ (để thử dựng hình cục bộ).
Ghi out_dir/line_XX.wav và out_dir/timing.json (thời lượng từng dòng, giây).
"""
import json
import os
import sys
import wave

import numpy as np

VOICE = os.environ.get("TTS_VOICE", "Mai Anh")  # Nữ · giọng Bắc · phong cách tin tức
SR = 48_000


def write_wav(path, audio, sr):
    a = np.clip(audio, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((a * 32767).astype("<i2").tobytes())


def trim(audio, sr, thresh=0.012):
    """Cắt khoảng lặng đầu/cuối, chừa 60 ms."""
    idx = np.where(np.abs(audio) > thresh)[0]
    if len(idx) == 0:
        return audio
    pad = int(0.06 * sr)
    return audio[max(0, idx[0] - pad): min(len(audio), idx[-1] + pad)]


def main():
    script = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    silent = "--silent" in sys.argv
    os.makedirs(out, exist_ok=True)
    tts = None
    if not silent:
        from vieneu import Vieneu
        tts = Vieneu()
        names = [v[0] if isinstance(v, (list, tuple)) else v for v in tts.list_preset_voices()]
        print("Giọng có sẵn:", ", ".join(map(str, names)), file=sys.stderr)
    timing = []
    for i, ln in enumerate(script["lines"]):
        path = os.path.join(out, f"line_{i:02d}.wav")
        if silent:
            dur = max(1.6, len(ln["tts"]) / 15.0)
            audio = np.zeros(int(dur * SR), dtype=np.float32)
            sr = SR
        else:
            audio = np.asarray(tts.infer(ln["tts"], voice=VOICE), dtype=np.float32).reshape(-1)
            sr = tts.sample_rate
            audio = trim(audio, sr)
        write_wav(path, audio, sr)
        timing.append({"file": path, "dur": round(len(audio) / sr, 3)})
        print(f"[{i}] {timing[-1]['dur']:.2f}s  {ln['tts']}", file=sys.stderr)
    json.dump({"voice": None if silent else VOICE, "lines": timing}, open(os.path.join(out, "timing.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
