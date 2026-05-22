#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send_feishu.py
==============
通过飞书发送黄金鸡蛋价格比例报告。
直接读取 price_history.json 构建结构化消息，排版适配飞书客户端。

支持两种模式（优先使用 Webhook）：
  1. Webhook 模式：只需 FEISHU_WEBHOOK_URL
  2. App API 模式：需要 FEISHU_APP_ID + FEISHU_APP_SECRET + FEISHU_RECEIVE_ID
"""

import os
import sys
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
RATIO_LOW = 80.0
RATIO_HIGH = 150.0
TREND_DAYS = 7
MA_PERIOD = 20

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
SEND_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_price(val, suffix=""):
    if val is None:
        return "—"
    return f"{val:.2f}{suffix}"


def fmt_ratio(val):
    if val is None:
        return "—"
    return f"{val:.1f}"


def ratio_status(val):
    if val is None:
        return ""
    if val < RATIO_LOW:
        return "偏低 ↓"
    if val > RATIO_HIGH:
        return "偏高 ↑"
    return "正常 ✓"


def delta_str(cur, prev):
    """计算较前一日变动"""
    if cur is None or prev is None:
        return ""
    diff = cur - prev
    sign = "+" if diff >= 0 else ""
    return f"  {sign}{diff:.2f}"


def calc_ma(history, field, period):
    """从历史数据中取最近 period 个有效值计算移动平均线"""
    values = []
    for rec in history:
        v = rec.get(field)
        if v is not None:
            values.append(v)
        if len(values) == period:
            break
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def ma_signal(price, ma_val):
    """根据当前价格与 MA 的偏离度给出做 T 信号"""
    if price is None or ma_val is None:
        return "", ""
    pct = (price - ma_val) / ma_val * 100
    if pct > 1.5:
        return f"📈 高于 MA{MA_PERIOD}　{pct:+.2f}%", "💡 偏高，可考虑适当卖出"
    if pct < -1.5:
        return f"📉 低于 MA{MA_PERIOD}　{pct:+.2f}%", "💡 偏低，可考虑适当买入"
    if pct > 0.5:
        return f"📈 略高于 MA{MA_PERIOD}　{pct:+.2f}%", "🔍 接近均线偏上，观望为主"
    if pct < -0.5:
        return f"📉 略低于 MA{MA_PERIOD}　{pct:+.2f}%", "🔍 接近均线偏下，可关注"
    return f"➡️ 贴近 MA{MA_PERIOD}　{pct:+.2f}%", "🔍 在均线附近，暂无明显信号"


def build_feishu_message(history):
    """从历史数据构建飞书 post 消息"""
    if not history:
        return _simple_post("📊 黄金鸡蛋价格比例报告", "暂无数据")

    today = history[0]
    yesterday = history[1] if len(history) > 1 else {}

    gold = today.get("gold_price")
    egg = today.get("egg_price")
    ratio = today.get("gold_egg_ratio")
    errors = today.get("errors", [])

    is_high_price = gold is not None and gold > GOLD_PRICE_ALERT_THRESHOLD

    lines = []

    # ── 今日核心数据 ──
    date_display = today["date"].replace("-", ".")
    lines.append([{"tag": "text", "text": f"📅 {date_display}"}])
    lines.append([{"tag": "text", "text": ""}])

    gold_delta = delta_str(gold, yesterday.get("gold_price"))
    egg_delta = delta_str(egg, yesterday.get("egg_price"))

    lines.append([{"tag": "text", "text": f"💰 黄金　{fmt_price(gold)} 元/克{gold_delta}"}])
    lines.append([{"tag": "text", "text": f"🥚 鸡蛋　{fmt_price(egg)} 元/斤{egg_delta}"}])

    # 附加数据：鸡蛋期货、黄金 ETF 折溢价（小字）
    egg_futures = today.get("egg_price_futures")
    if egg_futures is not None:
        lines.append([{"tag": "text", "text": f"🛢 鸡蛋期货 JD0　{egg_futures:.3f} 元/斤"}])
    etf_price = today.get("gold_etf_518880")
    etf_premium = today.get("gold_etf_premium_pct")
    if etf_price is not None:
        etf_line = f"📈 黄金 ETF 518880　{etf_price:.3f} 元/份"
        if etf_premium is not None:
            etf_line += f"　折溢价 {etf_premium:+.2f}%"
        lines.append([{"tag": "text", "text": etf_line}])

    ratio_line = f"📐 比例　{fmt_ratio(ratio)}"
    status = ratio_status(ratio)
    if status:
        ratio_line += f"　{status}"
    lines.append([{"tag": "text", "text": ratio_line}])

    lines.append([{"tag": "text", "text": f"📏 参考区间　{RATIO_LOW:.0f} — {RATIO_HIGH:.0f}"}])

    # 比例 vs 最近 20 日均值偏离
    ma_val = today.get("ratio_ma20")
    ma_dev = today.get("ratio_ma20_deviation_pct")
    ma_n = today.get("ratio_ma20_count") or 20
    if ma_val is not None and ma_dev is not None:
        direction = "↑" if ma_dev >= 0 else "↓"
        lines.append(
            [{"tag": "text",
              "text": f"📊 近 {ma_n} 日均比　{ma_val:.1f}　今日{direction} {abs(ma_dev):.2f}%"}]
        )

    # ── MA20 均线分析 ──
    ma_val, ma_count = calc_ma(history, "gold_price", MA_PERIOD)
    if ma_val is not None and gold is not None:
        deviation_line, suggestion = ma_signal(gold, ma_val)
        lines.append([{"tag": "text", "text": ""}])
        lines.append([{"tag": "text", "text": f"━━━ MA{MA_PERIOD} 均线分析（{ma_count}日）━━━"}])
        lines.append([{"tag": "text", "text": f"📊 MA{MA_PERIOD}　{ma_val:.2f} 元/克"}])
        lines.append([{"tag": "text", "text": deviation_line}])
        if suggestion:
            lines.append([{"tag": "text", "text": suggestion}])

    if errors:
        lines.append([{"tag": "text", "text": ""}])
        for err in errors:
            lines.append([{"tag": "text", "text": f"⚠️ {err}"}])

    # ── 近 N 日走势 ──
    recent = history[:TREND_DAYS]
    if len(recent) > 1:
        lines.append([{"tag": "text", "text": ""}])
        lines.append([{"tag": "text", "text": f"━━━ 近{len(recent)}日走势 ━━━"}])

        for rec in recent:
            d = rec["date"][5:]
            g = fmt_price(rec.get("gold_price"))
            e = fmt_price(rec.get("egg_price"))
            r = fmt_ratio(rec.get("gold_egg_ratio"))
            lines.append([{"tag": "text", "text": f"{d}　金 {g}　蛋 {e}　比 {r}"}])

    # ── 标题 ──
    if is_high_price:
        title = f"⚠️ 高价预警 | 黄金 {gold:.2f} 元/克"
    else:
        title = "📊 黄金鸡蛋价格比例报告"

    return {
        "zh_cn": {
            "title": title,
            "content": lines,
        }
    }


def _simple_post(title, text):
    return {
        "zh_cn": {
            "title": title,
            "content": [[{"tag": "text", "text": text}]],
        }
    }


# ── Webhook 发送 ──

def gen_webhook_sign(secret):
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return timestamp, sign


def send_via_webhook(post_content):
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


# ── App API 发送 ──

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

    try:
        history = load_history()
    except Exception as e:
        print(f"[send_feishu] 读取历史数据失败: {e}", file=sys.stderr)
        history = []

    post_content = build_feishu_message(history)

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
