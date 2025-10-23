#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一个简单的邮件发送示例脚本，用于演示在 GitHub Actions 中如何利用环境变量发送邮件。

本脚本不会包含任何敏感信息，所有配置均通过环境变量提供。如未配置完整，则脚本会提示并退出。

环境变量：
  - SMTP_HOST：SMTP 服务器地址
  - SMTP_PORT：SMTP 端口（默认为 587）
  - SMTP_USERNAME：SMTP 登录用户名
  - SMTP_PASSWORD：SMTP 登录密码
  - EMAIL_SENDER：发件人邮箱地址
  - EMAIL_RECIPIENT：收件人邮箱地址

运行方式：
  在 GitHub Actions 工作流中调用此脚本，确保上述环境变量已在工作流 `env` 字段中设置（最好通过 Secrets 管理）。
"""
from __future__ import annotations
import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime


def main() -> None:
    # 读取环境变量
    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str | None = os.getenv("SMTP_USERNAME")
    smtp_pass: str | None = os.getenv("SMTP_PASSWORD")
    sender: str | None = os.getenv("EMAIL_SENDER")
    recipient: str | None = os.getenv("EMAIL_RECIPIENT")

    # 检查是否缺少必要的配置
    if not all([smtp_host, smtp_user, smtp_pass, sender, recipient]):
        print("[send_email.py] 未配置完整的邮件环境变量，跳过发送邮件操作。")
        return

    # 构造邮件内容
    msg = EmailMessage()
    msg["Subject"] = "GitHub Actions 定时邮件示例"
    msg["From"] = sender
    msg["To"] = recipient
    # 邮件正文简单包含发送时间（UTC），可根据需要修改内容
    msg.set_content(f"这是来自 GitHub Actions 的一封测试邮件，发送时间：{datetime.utcnow().isoformat()} UTC\n")

    try:
        # 建立安全的连接
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print("[send_email.py] 邮件发送成功。")
    except Exception as exc:  # noqa: BLE001
        print(f"[send_email.py] 邮件发送失败：{exc}")


if __name__ == "__main__":
    main()