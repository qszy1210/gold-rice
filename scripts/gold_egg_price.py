#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gold_egg_price.py
===================
这个脚本从公开网页抓取：
  - 黄金（24K）价格：人民币 元／克
  - 鸡蛋价格：人民币 元／斤 （假设网页单位为元／公斤）
  - （可选后续）大米价格：人民币 元／斤
然后计算：
  - 黄金／鸡蛋 比例
  - 黄金／大米 比例（如有数据）
并将结果输出，包括日期、各项价格、比例、及是否处于参考区间。
"""

import requests
from bs4 import BeautifulSoup
import datetime
import re
import sys
import time
import random
import json
import os

# ============ 公共变量：数据源 URL 模板 ============
# 上海黄金交易所每日行情数据（Au99.99 为 24K 黄金）
GOLD_PRICE_URL_TEMPLATE = "https://www.sge.com.cn/sjzx/quotation_daily_new?start_date={date}&end_date={date}"

# 鸡蛋价格数据源（中国鸡蛋产业网）
EGG_PRICE_URL = "https://egg.100ppi.com/kx/"

# 数据存储路径
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")

def get_gold_price_per_g():
    """从上海黄金交易所抓取 Au99.99（24K 黄金）每克价格（元／克）"""
    # 尝试最近5天的数据（考虑周末和节假日）
    for days_ago in range(5):
        query_date = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
        url = GOLD_PRICE_URL_TEMPLATE.format(date=query_date)

        # 使用更完整的浏览器请求头，模拟真实浏览器
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.sge.com.cn/",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }

        # 最多重试3次
        for retry in range(3):
            try:
                # 添加随机延迟，避免触发反爬虫（1-3秒）
                if retry > 0:
                    time.sleep(random.uniform(1, 3))

                resp = requests.get(url, headers=headers, timeout=20)
                resp.raise_for_status()
                html = resp.text

                # 调试：输出部分 HTML 内容以便排查问题
                if "daily_new_table" not in html:
                    print(f"[调试] {query_date} 页面中未找到 daily_new_table，HTML 长度: {len(html)}", file=sys.stderr)
                    if retry == 2:  # 最后一次重试时输出前500字符
                        print(f"[调试] HTML 预览: {html[:500]}", file=sys.stderr)
                    continue

                soup = BeautifulSoup(html, "html.parser")

                # 查找表格中的 Au99.99 行（24K 黄金）
                # 在 HTML 中，数据在 <table class="daily_new_table"> 的 <tbody> 中
                table = soup.find("table", class_="daily_new_table")
                if not table:
                    print(f"[调试] {query_date} 未找到表格 (重试 {retry+1}/3)", file=sys.stderr)
                    continue

                tbody = table.find("tbody")
                if not tbody:
                    print(f"[调试] {query_date} 未找到 tbody (重试 {retry+1}/3)", file=sys.stderr)
                    continue

                # 查找包含 Au99.99 的行（支持 Au99.99, iAu99.99 等变体）
                rows = tbody.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 6:
                        # 第二列是合约代码
                        contract = cells[1].get_text(strip=True)
                        # 部分匹配：只要包含 "Au99.99" 就认为是目标合约
                        if "Au99.99" in contract:
                            # 第六列是收盘价
                            closing_price_text = cells[5].get_text(strip=True)
                            # 移除可能的千分位逗号
                            closing_price_text = closing_price_text.replace(",", "")
                            if closing_price_text and closing_price_text != "-":
                                price = float(closing_price_text)
                                print(f"[调试] 使用 {query_date} 的黄金价格数据，合约: {contract}", file=sys.stderr)
                                return price

                # 如果找到表格但没有 Au99.99 数据，尝试下一天
                print(f"[调试] {query_date} 表格中未找到 Au99.99 数据", file=sys.stderr)
                break

            except requests.exceptions.RequestException as e:
                print(f"[调试] {query_date} 请求失败 (重试 {retry+1}/3): {e}", file=sys.stderr)
                if retry == 2:  # 最后一次重试失败
                    continue
            except Exception as e:
                print(f"[调试] {query_date} 解析失败: {e}", file=sys.stderr)
                break

    raise ValueError("无法在页面中找到 Au99.99 的收盘价")

def get_egg_price_per_jin():
    """从"鸡蛋产业网–价格快讯"抓取鸡蛋参考价，然后转换为元／斤"""
    url = EGG_PRICE_URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://egg.100ppi.com/",
    }

    # 最多重试3次
    for retry in range(3):
        try:
            if retry > 0:
                time.sleep(random.uniform(1, 2))

            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text()

            # 查找 "鸡蛋参考价为X.XX" 或 "鸡蛋为X.XX"
            m = re.search(r"鸡蛋参考价为\s*([\d]+\.\d+)", text)
            if not m:
                # 尝试另一种表达
                m = re.search(r"鸡蛋为\s*([\d]+\.\d+)", text)
            if not m:
                print(f"[调试] 鸡蛋价格未找到 (重试 {retry+1}/3)", file=sys.stderr)
                continue

            price_per_kg = float(m.group(1))
            price_per_jin = price_per_kg / 2.0
            return price_per_jin

        except requests.exceptions.RequestException as e:
            print(f"[调试] 鸡蛋价格请求失败 (重试 {retry+1}/3): {e}", file=sys.stderr)
            if retry == 2:
                raise ValueError("无法在页面中找到鸡蛋参考价")

    raise ValueError("无法在页面中找到鸡蛋参考价")

def get_rice_price_per_jin():
    """暂留函数：大米价格抓取。当前实现返回 None。后续如找到可靠源可实现解析。"""
    return None

def load_price_history():
    """加载历史价格数据"""
    if not os.path.exists(HISTORY_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        return []

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[警告] 加载历史数据失败: {e}", file=sys.stderr)
        return []

def save_price_data(data):
    """保存价格数据到历史记录"""
    history = load_price_history()

    # 检查是否已存在当天的数据，如果存在则更新
    date_str = data['date']
    existing_index = None
    for i, record in enumerate(history):
        if record['date'] == date_str:
            existing_index = i
            break

    if existing_index is not None:
        history[existing_index] = data
        print(f"[信息] 更新 {date_str} 的数据", file=sys.stderr)
    else:
        history.append(data)
        print(f"[信息] 添加 {date_str} 的新数据", file=sys.stderr)

    # 按日期排序（最新的在前）
    history.sort(key=lambda x: x['date'], reverse=True)

    # 只保留最近 365 天的数据
    history = history[:365]

    # 保存到文件
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"[信息] 数据已保存到 {HISTORY_FILE}", file=sys.stderr)
    except Exception as e:
        print(f"[错误] 保存数据失败: {e}", file=sys.stderr)

def main():
    date_str = datetime.date.today().isoformat()
    error_messages = []

    try:
        gold = get_gold_price_per_g()
    except Exception as e:
        print(f"获取黄金价格失败: {e}", file=sys.stderr)
        error_messages.append(f"获取黄金价格失败: {e}")
        gold = None

    try:
        egg = get_egg_price_per_jin()
    except Exception as e:
        print(f"获取鸡蛋价格失败: {e}", file=sys.stderr)
        error_messages.append(f"获取鸡蛋价格失败: {e}")
        egg = None

    try:
        rice = get_rice_price_per_jin()
    except Exception as e:
        rice = None

    ratio_gold_egg = gold / egg if (gold is not None and egg is not None) else None
    ratio_gold_rice = gold / rice if (gold is not None and rice not in (None,0)) else None

    # 参考阈值区间
    threshold_gold_egg = (80.0, 150.0)
    threshold_gold_rice = (100.0, 200.0)

    print(f"日期: {date_str}")
    if gold is not None:
        print(f"黄金价格: {gold:.2f} 元／克")
    else:
        print("黄金价格: N/A")

    if egg is not None:
        print(f"鸡蛋价格: {egg:.2f} 元／斤")
    else:
        print("鸡蛋价格: N/A")

    if rice is not None:
        print(f"大米价格: {rice:.2f} 元／斤")
    else:
        print("大米价格: N/A")

    if ratio_gold_egg is not None:
        status_egg = ("低于", "处于", "高于")[1 + (ratio_gold_egg > threshold_gold_egg[1]) - (ratio_gold_egg < threshold_gold_egg[0])]
        print(f"黄金／鸡蛋 比例: {ratio_gold_egg:.1f} – {status_egg} 历史参考区间 {threshold_gold_egg[0]:.1f}-{threshold_gold_egg[1]:.1f}")
    else:
        print("黄金／鸡蛋 比例: N/A")

    if ratio_gold_rice is not None:
        status_rice = ("低于", "处于", "高于")[1 + (ratio_gold_rice > threshold_gold_rice[1]) - (ratio_gold_rice < threshold_gold_rice[0])]
        print(f"黄金／大米 比例: {ratio_gold_rice:.1f} – {status_rice} 历史参考区间 {threshold_gold_rice[0]:.1f}-{threshold_gold_rice[1]:.1f}")
    else:
        print("黄金／大米 比例: N/A")

    # 如果有错误信息，输出到 stderr 和 stdout
    if error_messages:
        print("\n--- 警告信息 ---")
        for msg in error_messages:
            print(msg)

    # 保存数据到历史记录
    price_data = {
        'date': date_str,
        'timestamp': datetime.datetime.now().isoformat(),
        'gold_price': gold,
        'egg_price': egg,
        'rice_price': rice,
        'gold_egg_ratio': ratio_gold_egg,
        'gold_rice_ratio': ratio_gold_rice,
        'errors': error_messages
    }
    save_price_data(price_data)

if __name__ == "__main__":
    main()