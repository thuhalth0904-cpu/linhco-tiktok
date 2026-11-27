"""Soạn kịch bản video ngày từ dữ liệu lịch Linh Cơ.

Mọi số liệu lấy từ day.json (bộ tính chung của app và web); file này chỉ ghép câu theo mẫu.
Mỗi dòng có: scene (cảnh hình), sub (phụ đề hiển thị), tts (câu đưa vào giọng đọc).
Dùng: python script.py day.json > script.json
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = {"mở đầu": "title", "chuyện": "story", "giờ tốt": "hours", "nên làm": "do", "nên tránh": "avoid",
         "tuổi xung": "xung", "hướng": "dir", "kết": "cta"}

# Thay cách đọc cho giọng đọc: tên miền, ký hiệu dễ bị đọc sai.
SAY = [
    ("linhco.vn", "linh cơ chấm vê en"),
    ("UNESCO", "u nét xcô"),
    ("B-52", "B năm mươi hai"),
    ("Paris", "Pa ri"),
    ("AIDS", "ết"),
    ("HIV", "hát i vê"),
    ("–", ", "),
    ("—", ", "),
    ("·", ", "),
    ("/", " tháng "),
]


def say(text: str) -> str:
    for a, b in SAY:
        text = text.replace(a, b)
    return " ".join(text.split())


def lunar_month(m: int, leap: bool) -> str:
    name = {1: "Giêng", 12: "Chạp"}.get(m, str(m))
    return f"tháng {name}{' nhuận' if leap else ''}"


def join_vi(items):
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " và " + items[-1]


def pick(options, seed):
    return options[seed % len(options)]


def lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def load_story(iso):
    """Tìm câu chuyện viết sẵn cho ngày iso trong stories/*.txt."""
    for f in sorted(glob.glob(os.path.join(HERE, "stories", "*.txt"))):
        txt = open(f, encoding="utf-8").read()
        for block in re.split(r"^### NGÀY: ", txt, flags=re.M)[1:]:
            if block.split("\n", 1)[0].strip() != iso:
                continue
            title = (re.search(r"^TIÊU ĐỀ: (.*)$", block, re.M) or [None, ""])[1].strip()
            scenes = [(LABEL[a.strip()], b.strip()) for a, b in re.findall(r"^CẢNH \[([^\]]+)\]: (.*)$", block, re.M)]
            return title, scenes
    return None


def images_for(iso):
    d = os.path.join(HERE, "assets", "days", iso)
    return sorted(glob.glob(os.path.join(d, "*.jpg")))


def build(d: dict) -> dict:
    st = load_story(d["iso"])
    if st:
        title, scenes = st
        lines = []
        for kind, text in scenes:
            ln = {"scene": kind, "sub": text, "tts": say(text)}
            if kind == "title":
                ln["title"] = title
            lines.append(ln)
        hours = [h["chi"] for h in d["goodHours"]]
        do = [x.strip() for x in d["shouldDo"].split(",") if x.strip()]
        avoid = [x.strip() for x in d["shouldAvoid"].split(",") if x.strip()]
        return {"day": d, "lines": lines, "images": images_for(d["iso"]), "title": title,
                "caption": caption(d, title + ("" if title[-1:] in ".!?…" else ".") + " " + scenes[0][1], hours, do, avoid)}
    return build_template(d)


def build_template(d: dict) -> dict:
    s, l = d["solar"], d["lunar"]
    seed = s["year"] * 400 + s["month"] * 31 + s["day"]
    date_sub = f"{d['weekday']}, {s['day']}/{s['month']}/{s['year']}"
    date_say = f"{d['weekday']}, ngày {s['day']} tháng {s['month']}"
    lunar_say = f"ngày {l['day']} {lunar_month(l['month'], l['leap'])} âm lịch"
    hours = [h["chi"] for h in d["goodHours"]]
    do = [x.strip() for x in d["shouldDo"].split(",") if x.strip()][:4]
    avoid = [x.strip() for x in d["shouldAvoid"].split(",") if x.strip()][:4]

    # Điểm nhấn mở đầu, ưu tiên theo mức quan trọng với người xem.
    if l["day"] == 15:
        hook = f"Hôm nay là Rằm {lunar_month(l['month'], l['leap'])}. Đã chuẩn bị gì chưa?"
    elif l["day"] == 1:
        hook = f"Hôm nay là mùng Một {lunar_month(l['month'], l['leap'])}. Xem ngay giờ tốt!"
    elif d.get("tamNuong"):
        hook = "Hôm nay trùng ngày Tam Nương. Việc lớn nên cân nhắc!"
    elif d.get("nguyetKy"):
        hook = "Hôm nay là ngày Nguyệt Kỵ. Cần lưu ý điều gì?"
    elif d.get("solarTermStart"):
        hook = f"Hôm nay bắt đầu tiết {d['solarTerm']}. Ngày này tốt hay xấu?"
    elif d["hoangDao"]:
        hook = pick([f"Hôm nay là ngày hoàng đạo. Làm gì cho thuận?",
                     f"Hôm nay {d['weekday']} có gì tốt? Xem nhanh 30 giây!",
                     f"Hôm nay hợp làm việc gì? Cùng xem nhé!"], seed)
    else:
        hook = pick([f"Hôm nay là ngày hắc đạo. Cần tránh việc gì?",
                     f"Hôm nay {d['weekday']} nên làm gì, kiêng gì?",
                     f"Hôm nay có nên làm việc lớn không? Xem ngay!"], seed)

    lines = [
        {"scene": "hook", "sub": hook},
        {"scene": "date",
         "sub": f"{date_sub}, tức {lunar_say}. Ngày {d['dayCanChi']}, tháng {d['monthCanChi']}, năm {d['yearCanChi']}.",
         "tts": f"{date_say}, tức {lunar_say}. Ngày {d['dayCanChi']}, tháng {d['monthCanChi']}, năm {d['yearCanChi']}."},
        {"scene": "god",
         "sub": (f"Ngày hoàng đạo {d['dayGod']}, trực {d['truc']}." if d["hoangDao"]
                 else f"Ngày hắc đạo {d['dayGod']}, trực {d['truc']}.")
                + (" Trùng ngày Tam Nương." if d.get("tamNuong") else "")
                + (" Ngày Nguyệt Kỵ." if d.get("nguyetKy") else "")},
        {"scene": "hours", "sub": f"Giờ hoàng đạo: {join_vi(hours)}."},
    ]
    if do:
        lines.append({"scene": "do", "sub": f"Nên làm: {lower_first(join_vi(do))}."})
    if avoid:
        lines.append({"scene": "avoid", "sub": f"Nên tránh: {lower_first(join_vi(avoid))}."})
    lines.append({"scene": "dir", "sub": f"Xuất hành hướng {d['hyThan']} gặp Hỷ Thần, hướng {d['taiThan']} gặp Tài Thần."})
    lines.append({"scene": "cta", "sub": pick(["Xem lịch mỗi ngày tại linhco.vn.",
                                               "Lịch âm, giờ tốt mỗi ngày tại linhco.vn.",
                                               "Theo dõi kênh và xem thêm tại linhco.vn."], seed)})
    for ln in lines:
        ln["tts"] = say(ln.get("tts") or ln["sub"])
    return {"day": d, "lines": lines,
            "caption": caption(d, hook, hours, do, avoid)}


def caption(d, hook, hours, do, avoid):
    s, l = d["solar"], d["lunar"]
    return "\n".join([
        f"{hook} 🙏",
        f"📅 {d['weekday']} {s['day']}/{s['month']}/{s['year']} – âm lịch {l['day']}/{l['month']}{' nhuận' if l['leap'] else ''}, ngày {d['dayCanChi']}",
        f"⏰ Giờ hoàng đạo: {', '.join(hours)}",
        f"✅ Nên: {', '.join(do).lower()}" if do else "",
        f"⛔ Tránh: {', '.join(avoid).lower()}" if avoid else "",
        "👉 Xem lịch âm mỗi ngày tại linhco.vn",
        "Nội dung tham khảo theo quan niệm dân gian.",
        "",
        "#lichamhomnay #lichvannien #ngaytot #giohoangdao #xemngaytot #tamlinh #linhco",
    ]).replace("\n\n\n", "\n\n")


TOPIC_LABEL = {"mở đầu": "title", "chuyện": "story", "kết": "cta"}
TOPIC_TAGS = {
    "Giải mộng": "#giaimong #giacmo #tamlinh #dangian",
    "12 con giáp": "#12congiap #tuvi #congiap #tet2027",
    "Giải mã lịch": "#licham #lichvannien #vanhoaviet #tet",
    "Chuyện xưa": "#lichsuvietnam #hanoi #chuyenxua #vanhoaviet",
}


def build_topic(tid):
    """Video chủ đề: đọc topics/*.txt, khối '### VIDEO: <tid>'."""
    for f in sorted(glob.glob(os.path.join(HERE, "topics", "*.txt"))):
        txt = open(f, encoding="utf-8").read()
        for block in re.split(r"^### VIDEO: ", txt, flags=re.M)[1:]:
            if block.split("\n", 1)[0].strip() != tid:
                continue
            title = re.search(r"^TIÊU ĐỀ: (.*)$", block, re.M)[1].strip()
            group = re.search(r"^NHÓM: (.*)$", block, re.M)[1].strip()
            lines = []
            for a, b in re.findall(r"^CẢNH \[([^\]]+)\]: (.*)$", block, re.M):
                ln = {"scene": TOPIC_LABEL[a.strip()], "sub": b.strip(), "tts": say(b.strip())}
                if ln["scene"] == "title":
                    ln["title"] = title
                lines.append(ln)
            imgs = sorted(glob.glob(os.path.join(HERE, "assets", "topics", tid, "*.jpg")))
            cap = "\n".join([f"{title} 🤔", "", lines[0]["sub"], "",
                              "👉 Xem lịch âm, giờ tốt, giải mộng tại linhco.vn", "",
                              TOPIC_TAGS.get(group, "#vanhoaviet") + " #linhco"])
            return {"day": {"iso": f"chu-de-{tid}", "topic": tid, "group": group},
                    "lines": lines, "images": imgs, "title": title, "caption": cap}
    sys.exit(f"Không tìm thấy video chủ đề {tid}")


HOUR_TEXT = {}


def youtube(res):
    """Tiêu đề, mô tả, thẻ riêng cho YouTube Shorts (người xem YouTube hay TÌM theo ngày)."""
    d = res["day"]
    first = res["lines"][0]["sub"]
    if d.get("topic"):
        title = f"{res['title']} | linhco.vn #shorts"
        tags_h = TOPIC_TAGS.get(d["group"], "#vanhoaviet").split()[:2]
        desc = "\n".join([
            first, "",
            f"Chủ đề: {d['group']} – kênh linhco.vn kể chuyện lịch âm và văn hóa Việt.",
            "",
            "🔎 Tra lịch âm, giờ hoàng đạo, giải mộng, văn khấn: https://linhco.vn",
            "🔔 Đăng ký kênh để xem lịch âm mỗi ngày và các câu chuyện văn hóa Việt.",
            "",
            "Nội dung tham khảo theo quan niệm dân gian. Hình ảnh minh họa và giọng đọc do AI tạo.",
            "",
            " ".join(tags_h + ["#shorts"]),
        ])
        tags = ["linhco.vn", d["group"].lower(), "văn hóa việt", "lịch âm", res["title"].lower()]
    else:
        s, l = d["solar"], d["lunar"]
        story = res.get("title") or first
        title = f"Lịch Âm {s['day']:02d}/{s['month']:02d}/{s['year']} – {l['day']}/{l['month']} Âm Lịch, Giờ Hoàng Đạo | {story}"
        if len(title) > 92:
            title = f"Lịch Âm {s['day']:02d}/{s['month']:02d}/{s['year']} – {l['day']}/{l['month']} Âm, Giờ Hoàng Đạo"
        title += " #shorts"
        hours = ", ".join(f"{h['chi']} ({h['range']})" for h in d["goodHours"])
        chi = d["dayCanChi"].split()[-1]
        CHI = "Tý Sửu Dần Mão Thìn Tỵ Ngọ Mùi Thân Dậu Tuất Hợi".split()
        xung = CHI[(CHI.index(chi) + 6) % 12]
        flags = [x for x, k in (("Tam Nương", "tamNuong"), ("Nguyệt Kỵ", "nguyetKy")) if d.get(k)]
        desc = "\n".join([x for x in [
            first, "",
            f"📅 {d['weekday']}, ngày {s['day']}/{s['month']}/{s['year']} dương lịch",
            f"🌙 Âm lịch: ngày {l['day']}/{l['month']}{' nhuận' if l['leap'] else ''} năm {d['yearCanChi']} – ngày {d['dayCanChi']}, tháng {d['monthCanChi']}",
            f"⭐ {'Hoàng đạo' if d['hoangDao'] else 'Hắc đạo'} {d['dayGod']} · Trực {d['truc']} · Tiết {d['solarTerm']}"
            + (f" · {', '.join(flags)}" if flags else ""),
            f"⏰ Giờ hoàng đạo: {hours}",
            f"✅ Nên: {d['shouldDo']}" if d.get("shouldDo") else "",
            f"⛔ Tránh: {d['shouldAvoid']}" if d.get("shouldAvoid") else "",
            f"⚠️ Tuổi xung: {xung}",
            f"🧭 Hỷ Thần: {d['hyThan']} · Tài Thần: {d['taiThan']}",
            "",
            "🔎 Xem lịch âm, giờ hoàng đạo mỗi ngày: https://linhco.vn",
            "🔔 Đăng ký kênh để nhận lịch âm mỗi sáng.",
            "",
            "Nội dung tham khảo theo quan niệm dân gian. Giọng đọc và hình ảnh do AI tạo.",
            "",
            "#lichamhomnay #giohoangdao #shorts",
        ] if x != "" or True]).replace("\n\n\n", "\n\n")
        tags = ["lịch âm hôm nay", f"lịch âm {s['day']}/{s['month']}/{s['year']}", f"lịch âm {s['day']} tháng {s['month']}",
                "giờ hoàng đạo", "ngày tốt xấu", "lịch vạn niên", "xem ngày tốt", f"âm lịch {l['day']}/{l['month']}", "linhco.vn"]
    return {"title": title[:100], "desc": desc[:4900], "tags": ", ".join(tags)}


if __name__ == "__main__":
    if sys.argv[1] == "--topic":
        res = build_topic(sys.argv[2])
    else:
        res = build(json.load(open(sys.argv[1], encoding="utf-8")))
    res["youtube"] = youtube(res)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
