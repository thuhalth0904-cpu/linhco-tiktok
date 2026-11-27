"""Gửi video và kịch bản qua Gmail.

Biến môi trường: GMAIL_USER (địa chỉ gửi), GMAIL_APP_PASSWORD (mật khẩu ứng dụng 16 ký tự),
MAIL_TO (người nhận, mặc định = GMAIL_USER).
Dùng: python send_mail.py video.mp4 kich-ban.txt
"""
import os
import smtplib
import sys
from email.message import EmailMessage

video, text_file = sys.argv[1], sys.argv[2]
user = os.environ["GMAIL_USER"]
pw = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
to = os.environ.get("MAIL_TO") or user

body = open(text_file, encoding="utf-8").read()
msg = EmailMessage()
stem = os.path.basename(video).removeprefix("linhco-").removesuffix(".mp4")
msg["Subject"] = "Linh Cơ – " + (f"video chủ đề {stem.removeprefix('chu-de-')}" if stem.startswith("chu-de") else f"video lịch {stem}")
msg["From"] = user
msg["To"] = to
msg.set_content(body + "\n\nXem kỹ số liệu trước khi đăng. Thư này gửi tự động từ GitHub Actions.")
size = os.path.getsize(video)
if size > 24 * 1024 * 1024:
    sys.exit(f"Video {size / 1e6:.1f} MB vượt giới hạn tệp đính kèm Gmail")
with open(video, "rb") as f:
    msg.add_attachment(f.read(), maintype="video", subtype="mp4", filename=os.path.basename(video))
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
    s.login(user, pw)
    s.send_message(msg)
print(f"Đã gửi {os.path.basename(video)} ({size / 1e6:.1f} MB) tới {to}")
