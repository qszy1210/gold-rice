#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, smtplib, ssl, subprocess, sys, re
from email.mime.text import MIMEText
from email.header import Header

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))  # 587(TLS) / 465(SSL)
USERNAME  = os.getenv("GMAIL_USERNAME")         # demo@gmail.com
APP_PASS  = os.getenv("GMAIL_APP_PASSWORD")     # 16 位 App Password
EMAIL_TO  = os.getenv("EMAIL_TO")               # 收件人（可逗号分隔多个地址）

# 黄金价格预警阈值
GOLD_PRICE_ALERT_THRESHOLD = 960.0

def extract_gold_price(output_text):
    """从输出中提取黄金价格"""
    match = re.search(r"黄金价格:\s*([\d]+\.?\d*)\s*元／克", output_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def parse_recipients(raw):
    """将逗号或分号分隔的地址解析为列表"""
    if not raw:
        return []
    parts = re.split(r"[;,]", raw)
    return [p.strip() for p in parts if p and p.strip()]

def main():
    missing = [k for k,v in {
        "GMAIL_USERNAME": USERNAME,
        "GMAIL_APP_PASSWORD": APP_PASS,
        "EMAIL_TO": EMAIL_TO
    }.items() if not v]
    if missing:
        print(f"[send_email] 缺少必需的环境变量：{', '.join(missing)}，跳过发送。")
        return

    recipients = parse_recipients(EMAIL_TO)
    if not recipients:
        print("[send_email] 未解析出有效的收件人地址，跳过发送。")
        return

    # 执行 gold_egg_price.py 并获取输出
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gold_egg_script = os.path.join(script_dir, "gold_egg_price.py")

    try:
        result = subprocess.run(
            [sys.executable, gold_egg_script],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            body = result.stdout
            if result.stderr:
                body += "\n\n--- 警告信息 ---\n" + result.stderr
        else:
            body = f"执行 gold_egg_price.py 时出错（返回码: {result.returncode}）\n\n"
            body += "--- 标准输出 ---\n" + result.stdout
            body += "\n--- 错误输出 ---\n" + result.stderr
    except subprocess.TimeoutExpired:
        body = "执行 gold_egg_price.py 超时（60秒）"
    except Exception as e:
        body = f"执行 gold_egg_price.py 时发生异常: {str(e)}"

    # 检查黄金价格是否超过阈值
    gold_price = extract_gold_price(body)
    is_high_price = gold_price is not None and gold_price > GOLD_PRICE_ALERT_THRESHOLD

    # 根据价格设置邮件主题
    if is_high_price:
        subject = f"⚠️ 高价预警 ⚠️ 黄金价格 {gold_price:.2f} 元/克 - 黄金鸡蛋价格比例报告"
    else:
        subject = "黄金鸡蛋价格比例报告"

    # 如果价格超过阈值，在邮件正文开头添加醒目提醒
    if is_high_price:
        alert_header = f"""
{'='*70}
⚠️⚠️⚠️  黄金价格高价预警  ⚠️⚠️⚠️

当前黄金价格: {gold_price:.2f} 元/克
预警阈值: {GOLD_PRICE_ALERT_THRESHOLD:.2f} 元/克
超出阈值: {gold_price - GOLD_PRICE_ALERT_THRESHOLD:.2f} 元/克

建议关注价格波动，谨慎做出投资决策！
{'='*70}

"""
        body = alert_header + body

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = USERNAME
    msg["To"] = ", ".join(recipients)

    if SMTP_PORT == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(USERNAME, APP_PASS)
            server.sendmail(USERNAME, recipients, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.login(USERNAME, APP_PASS)
            server.sendmail(USERNAME, recipients, msg.as_string())

    print("[send_email] 发送成功。")

if __name__ == "__main__":
    main()
