"""Tạo video TikTok lịch ngày mai từ đầu đến cuối.

Dùng: python build.py [YYYY-MM-DD] [--silent]
Kết quả ở thư mục out/: linhco-YYYY-MM-DD.mp4, kich-ban.txt (kịch bản + mô tả để đăng), script.json.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT_DIR", os.path.join(HERE, "out"))


def run(cmd, **kw):
    print("$", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True, **kw)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    silent = "--silent" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    script_json = os.path.join(OUT, "script.json")
    topic = sys.argv[sys.argv.index("--topic") + 1] if "--topic" in sys.argv else None
    if topic:
        with open(script_json, "w", encoding="utf-8") as f:
            run([sys.executable, os.path.join(HERE, "script.py"), "--topic", topic], stdout=f)
    else:
        day_json = os.path.join(OUT, "day.json")
        with open(day_json, "w", encoding="utf-8") as f:
            run(["node", "--experimental-strip-types", os.path.join(HERE, "day.mjs")] + args[:1], stdout=f)
        with open(script_json, "w", encoding="utf-8") as f:
            run([sys.executable, os.path.join(HERE, "script.py"), day_json], stdout=f)
    script = json.load(open(script_json, encoding="utf-8"))
    iso = script["day"]["iso"]
    special = os.path.join(HERE, "special_days.txt")
    if os.path.exists(special) and iso in open(special, encoding="utf-8").read().split():
        print(f"{iso} là ngày đặc biệt, video làm riêng – bỏ qua", file=sys.stderr)
        return

    voice_dir = os.path.join(OUT, "voice")
    run([sys.executable, os.path.join(HERE, "tts.py"), script_json, voice_dir] + (["--silent"] if silent else []))
    video = os.path.join(OUT, "video.mp4")
    run([sys.executable, os.path.join(HERE, "render.py"), script_json, os.path.join(voice_dir, "timing.json"), video])
    plan = json.load(open(os.path.join(OUT, "video.plan.json")))
    total = plan["total"]
    music = os.path.join(OUT, "music.wav")
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(iso)) % 100000
    run([sys.executable, os.path.join(HERE, "music.py"), f"{total:.2f}", music, str(seed)])

    # Ghép giọng đọc đúng mốc từng cảnh, nhạc tự nhỏ đi khi có giọng, chuẩn âm lượng TikTok.
    inputs, parts = [], []
    for i, sc in enumerate(plan["scenes"]):
        inputs += ["-i", sc["file"]]
        ms = int(sc["voice_at"] * 1000)
        parts.append(f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
    n = len(plan["scenes"])
    filt = ";".join(parts + [
        "".join(f"[v{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad=whole_dur={total:.2f}[voice]",
        f"[{n + 1}:a]aresample=48000,volume=0.30[m]",
        "[voice]asplit=2[vo][sc]",
        "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md]",
        "[vo][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
    ])
    final = os.path.join(OUT, f"linhco-{iso}.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", video] + inputs + ["-i", music, "-filter_complex", filt,
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-t", f"{total:.2f}", "-movflags", "+faststart", final])

    # Gmail chỉ nhận tệp đính kèm dưới 25 MB: video dài nhiều ảnh chi tiết thì nén lại theo bitrate.
    limit = 22 * 1024 * 1024
    if os.path.getsize(final) > limit:
        kbps = int(limit * 8 / 1000 / total) - 220
        tmp = final + ".nen.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", final, "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k",
             "-maxrate", f"{int(kbps * 1.3)}k", "-bufsize", f"{kbps * 2}k", "-pix_fmt", "yuv420p", "-c:a", "copy",
             "-movflags", "+faststart", tmp])
        os.replace(tmp, final)
        print(f"Đã nén còn {os.path.getsize(final) / 1e6:.1f} MB", file=sys.stderr)

    with open(os.path.join(OUT, "kich-ban.txt"), "w", encoding="utf-8") as f:
        f.write((f"VIDEO CHỦ ĐỀ {topic}: {script['title']}" if topic else f"VIDEO LỊCH NGÀY {iso}") + "\n\nLỜI ĐỌC:\n")
        for ln in script["lines"]:
            f.write(f"- {ln['sub']}\n")
        f.write("\n========== TIKTOK ==========\nMÔ TẢ:\n\n" + script["caption"] + "\n")
        yt = script.get("youtube")
        if yt:
            f.write("\n========== YOUTUBE SHORTS ==========\n")
            f.write("TIÊU ĐỀ:\n" + yt["title"] + "\n\nMÔ TẢ:\n" + yt["desc"] + "\n\nTHẺ (tags):\n" + yt["tags"] + "\n")
        f.write("\nKhi đăng: bật nhãn \"Nội dung do AI tạo\" (giọng đọc do AI tạo).\n")
    print(final)


if __name__ == "__main__":
    main()
