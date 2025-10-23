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

def get_gold_price_per_g():
    """从 Exchange-Rates.org 抓取中国 24K 黄金每克价格（元／克）"""
    url = "https://www.exchange-rates.org/precious-metals/gold-price/china"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    # 查找 “24K Gold Price per Gram” 文本所在行
    # 例如页面里有表格：24K Gold Price per Gram | ¥928.77
    text = soup.get_text()
    m = re.search(r"24K Gold Price per Gram\s*¥\s*([\d,]+\.\d+)", text)
    if not m:
        raise ValueError("无法在页面中找到 24K 黄金每克价格")
    price_str = m.group(1).replace(",", "")
    price = float(price_str)
    return price

def get_egg_price_per_jin():
    """从“鸡蛋产业网–价格快讯”抓取鸡蛋参考价，然后转换为元／斤"""
    url = "https://egg.100ppi.com/kx/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    # 查找 “鸡蛋参考价为X.XX” 或 “鸡蛋为X.XX”
    m = re.search(r"鸡蛋参考价为\s*([\d]+\.\d+)", text)
    if not m:
        # 尝试另一种表达
        m = re.search(r"鸡蛋为\s*([\d]+\.\d+)", text)
    if not m:
        raise ValueError("无法在页面中找到鸡蛋参考价")
    price_per_kg = float(m.group(1))
    price_per_jin = price_per_kg / 2.0
    return price_per_jin

def get_rice_price_per_jin():
    """暂留函数：大米价格抓取。当前实现返回 None。后续如找到可靠源可实现解析。"""
    return None

def main():
    date_str = datetime.date.today().isoformat()
    try:
        gold = get_gold_price_per_g()
    except Exception as e:
        print(f"获取黄金价格失败: {e}", file=sys.stderr)
        gold = None

    try:
        egg = get_egg_price_per_jin()
    except Exception as e:
        print(f"获取鸡蛋价格失败: {e}", file=sys.stderr)
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

if __name__ == "__main__":
    main()