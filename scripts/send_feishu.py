#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send_feishu.py
==============
通过飞书发送黄金鸡蛋价格比例报告。

支持两种模式（优先使用 Webhook）：
  1. Webhook 模式：只需 FEISHU_WEBHOOK_URL，最简单
  2. App API 模式：需要 FEISHU_APP_ID + FEISHU_APP_SECRET + FEISHU_RECEIVE_ID
"""

import os
import sys
import subprocess
import re
import json
import time
import hmac
import hashlib
import base64
import requests

FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")
FEISHU_WEBHOOK_SECRET = os.getenv("FEISHU_WEBHOOK_SECRET")

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_RECEIVE_ID = os.getenv("FEISHU_RECEIVE_ID")
FEISHU_RECEIVE_ID_TYPE = os.getenv("FEISHU_RECEIVE_ID_TYPE", "chat_id")

GOLD_PRICE_ALERT_THRESHOLD = 960.0

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
SEND_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


def get_report_body():
    """执行 gold_egg_price.py 并返回输出文本"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gold_egg_script = os.path.join(script_dir, "gold_egg_price.py")

    try:
        result = subprocess.run(
            [sys.executable, gold_egg_script],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            body = result.stdout
            if result.stderr:
                body += "\n\n--- 警告信息 ---\n" + result.stderr
        else:
            body = (
                f"执行 gold_egg_price.py 出错（返回码: {result.returncode}）\n\n"
                f"--- 标准输出 ---\n{result.stdout}\n"
                f"--- 错误输出 ---\n{result.stderr}"
            )
    except subprocess.TimeoutExpired:
        body = "执行 gold_egg_price.py 超时（60秒）"
    except Exception as e:
        body = f"执行 gold_egg_price.py 时发生异常: {e}"

    return body


def extract_gold_price(output_text):
    match = re.search(r"黄金价格:\s*([\d]+\.?\d*)\s*元／克", output_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def build_post_content(body_text, gold_price, is_high_price):
    """构建飞书 post（富文本）消息结构"""
    lines = []

    if is_high_price:
        lines.append([
            {"tag": "text", "text": f"⚠️ 高价预警 ⚠️ 当前黄金价格 {gold_price:.2f} 元/克，超出阈值 {GOLD_PRICE_ALERT_THRESHOLD:.2f} 元/克\n"},
        ])

    for line in body_text.strip().split("\n"):
        lines.append([{"tag": "text", "text": line}])

    title = (
        f"⚠️ 高价预警 | 黄金 {gold_price:.2f} 元/克"
        if is_high_price
        else "📊 黄金鸡蛋价格比例报告"
    )

    return {
        "zh_cn": {
            "title": title,
            "content": lines,
        }
    }


# ── 模式 1: Webhook ──

def gen_webhook_sign(secret):
    """生成飞书 Webhook 签名（HMAC-SHA256）"""
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return timestamp, sign


def send_via_webhook(post_content):
    """通过 Webhook URL 直接推送，无需 token / receive_id"""
    payload = {
        "msg_type": "post",
        "content": {"post": post_content},
    }
    if FEISHU_WEBHOOK_SECRET:
        timestamp, sign = gen_webhook_sign(FEISHU_WEBHOOK_SECRET)
        payload["timestamp"] = timestamp
        payload["sign"] = sign

    resp = requests.post(FEISHU_WEBHOOK_URL, json=payload, timeout=15)
    data = resp.json()
    if data.get("code") != 0 and data.get("StatusCode") != 0:
        raise RuntimeError(f"Webhook 发送失败: {data}")
    return data


# ── 模式 2: App API ──

def get_tenant_access_token():
    resp = requests.post(TOKEN_URL, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }, timeout=15)
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 token 失败: {data.get('msg', resp.text)}")
    return data["tenant_access_token"]


def send_via_app_api(token, post_content):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "receive_id": FEISHU_RECEIVE_ID,
        "msg_type": "post",
        "content": json.dumps(post_content),
    }
    resp = requests.post(
        f"{SEND_MSG_URL}?receive_id_type={FEISHU_RECEIVE_ID_TYPE}",
        headers=headers, json=payload, timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"App API 发送失败: {data.get('msg', resp.text)}")
    return data


# ── 主流程 ──

def main():
    use_webhook = bool(FEISHU_WEBHOOK_URL)
    use_app_api = all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_RECEIVE_ID])

    if not use_webhook and not use_app_api:
        print("[send_feishu] 未配置飞书通知方式。")
        print("  方式一（推荐）: 设置 FEISHU_WEBHOOK_URL")
        print("  方式二: 设置 FEISHU_APP_ID + FEISHU_APP_SECRET + FEISHU_RECEIVE_ID")
        return

    body = get_report_body()
    gold_price = extract_gold_price(body)
    is_high_price = gold_price is not None and gold_price > GOLD_PRICE_ALERT_THRESHOLD
    post_content = build_post_content(body, gold_price, is_high_price)

    try:
        if use_webhook:
            send_via_webhook(post_content)
            print("[send_feishu] 通过 Webhook 发送成功。")
        else:
            token = get_tenant_access_token()
            send_via_app_api(token, post_content)
            print("[send_feishu] 通过 App API 发送成功。")
    except Exception as e:
        print(f"[send_feishu] 发送失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
