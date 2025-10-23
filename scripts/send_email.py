#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, smtplib, ssl
from email.mime.text import MIMEText
from email.header import Header

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))  # 587(TLS) / 465(SSL)
USERNAME  = os.getenv("GMAIL_USERNAME")         # demo@gmail.com
APP_PASS  = os.getenv("GMAIL_APP_PASSWORD")     # 16 位 App Password
EMAIL_TO  = os.getenv("EMAIL_TO")               # 收件人

def main():
    missing = [k for k,v in {
        "GMAIL_USERNAME": USERNAME,
        "GMAIL_APP_PASSWORD": APP_PASS,
        "EMAIL_TO": EMAIL_TO
    }.items() if not v]
    if missing:
        print(f"[send_email] 缺少必需的环境变量：{', '.join(missing)}，跳过发送。")
        return

    subject = "GitHub Actions 发信测试"
    body = "这是一封来自 GitHub Actions 的测试邮件。"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = USERNAME
    msg["To"] = EMAIL_TO

    if SMTP_PORT == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(USERNAME, APP_PASS)
            server.sendmail(USERNAME, [EMAIL_TO], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.login(USERNAME, APP_PASS)
            server.sendmail(USERNAME, [EMAIL_TO], msg.as_string())

    print("[send_email] 发送成功。")

if __name__ == "__main__":
    main()