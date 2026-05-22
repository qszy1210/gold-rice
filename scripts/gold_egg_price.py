#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gold_egg_price.py
===================
价格数据采集与统计。

主数据源（akshare 官方交易所 API）：
  - 黄金 Au99.99：ak.spot_hist_sge(symbol="Au99.99")          上海黄金交易所现货
  - 黄金 ETF 518880：ak.fund_etf_hist_em(symbol="518880")     华安黄金 ETF（≈ 0.01g / 份）
  - 鸡蛋期货 JD0：ak.futures_zh_daily_sina(symbol="JD0")      大商所主力连续（元/500kg）

兜底数据源（网页爬虫）：
  - SGE 网页表格（Au99.99 收盘价）
  - 100ppi 现货报价文字（元/斤）

输出口径：
  - gold_price       : 元/克（主：SGE API；兜底：SGE 网页）
  - egg_price        : 元/斤（主：100ppi 现货，与历史数据口径一致）
  - egg_price_futures: 元/斤（鸡蛋期货 JD0 收盘 / 1000）
  - gold_etf_518880  : 元/份（518880 ETF 收盘价）
  - gold_etf_premium_pct : ETF 折溢价（>0 溢价，<0 折价）
  - ratio_ma20       : 最近 20 日 gold_egg_ratio 均值（用于偏离监控）
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

GOLD_PRICE_URL_TEMPLATE = "https://www.sge.com.cn/sjzx/quotation_daily_new?start_date={date}&end_date={date}"
EGG_PRICE_URL = "https://egg.100ppi.com/kx/"

GOLD_ETF_SYMBOL = "518880"          # 华安黄金 ETF（份额 ≈ 0.01 克金）
GOLD_ETF_SHARE_PER_GRAM = 100       # 1 克金 ≈ 100 份 ETF
EGG_FUTURES_SYMBOL = "JD0"          # 鸡蛋期货主力连续
EGG_FUTURES_UNIT_PER_JIN = 1000     # 元/500kg ÷ 1000 = 元/斤

MA_WINDOW = 20                      # 比例移动平均窗口

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")

def _akshare():
    """惰性导入 akshare，未安装时返回 None 让上游走 fallback"""
    try:
        import akshare as ak
        return ak
    except Exception as e:
        print(f"[调试] akshare 不可用，将走兜底数据源: {e}", file=sys.stderr)
        return None


def get_gold_price_sge_api():
    """主源：上海黄金交易所 Au99.99 现货最新收盘价（元/克）。失败返回 None。"""
    ak = _akshare()
    if ak is None:
        return None
    try:
        df = ak.spot_hist_sge(symbol="Au99.99")
        if df is None or df.empty:
            return None
        # 列：date, open, close, low, high；按日期排序后取最后一行
        df = df.sort_values("date")
        latest = df.iloc[-1]
        price = float(latest["close"])
        date = latest["date"]
        print(f"[调试] SGE API Au99.99 收盘价: {price} 元/克（{date}）", file=sys.stderr)
        return price
    except Exception as e:
        print(f"[调试] SGE API 获取失败，将走兜底网页源: {e}", file=sys.stderr)
        return None


def get_gold_etf_close():
    """获取华安黄金 ETF 518880 最新收盘价（元/份）。失败返回 None。"""
    ak = _akshare()
    if ak is None:
        return None
    try:
        # 拉最近 30 天足够找最新交易日
        end_date = datetime.date.today().strftime("%Y%m%d")
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y%m%d")
        df = ak.fund_etf_hist_em(
            symbol=GOLD_ETF_SYMBOL, period="daily",
            start_date=start_date, end_date=end_date, adjust="",
        )
        if df is None or df.empty:
            return None
        # 列名是中文："日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ..."
        df = df.sort_values("日期")
        price = float(df.iloc[-1]["收盘"])
        print(f"[调试] ETF {GOLD_ETF_SYMBOL} 收盘价: {price} 元/份", file=sys.stderr)
        return price
    except Exception as e:
        print(f"[调试] 黄金 ETF 获取失败: {e}", file=sys.stderr)
        return None


def get_egg_price_futures_per_jin():
    """获取鸡蛋期货 JD0 主力连续合约最新收盘价，换算为元/斤。失败返回 None。"""
    ak = _akshare()
    if ak is None:
        return None
    try:
        df = ak.futures_zh_daily_sina(symbol=EGG_FUTURES_SYMBOL)
        if df is None or df.empty:
            return None
        # 列：date, open, high, low, close, volume, hold；单位 元/500kg
        df = df.sort_values("date")
        latest = df.iloc[-1]
        close_per_500kg = float(latest["close"])
        price_per_jin = close_per_500kg / EGG_FUTURES_UNIT_PER_JIN
        date = latest["date"]
        print(
            f"[调试] 鸡蛋期货 {EGG_FUTURES_SYMBOL} 收盘 {close_per_500kg} 元/500kg "
            f"→ {price_per_jin:.3f} 元/斤（{date}）",
            file=sys.stderr,
        )
        return price_per_jin
    except Exception as e:
        print(f"[调试] 鸡蛋期货获取失败: {e}", file=sys.stderr)
        return None


def get_gold_price_per_g():
    """对外统一入口：先 akshare 主源，失败回退到 SGE 网页爬虫。"""
    price = get_gold_price_sge_api()
    if price is not None:
        return price, "sge_api"
    print("[调试] 主源 SGE API 失败，启用兜底网页爬虫", file=sys.stderr)
    fallback_price = _gold_price_sge_html_fallback()
    return fallback_price, "sge_html"


def _gold_price_sge_html_fallback():
    """兜底：从上海黄金交易所抓取 Au99.99 每克价格（元/克），保留原实现。"""
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
    """对外统一入口：现货为主（与历史口径一致），失败时不抛异常返回 None。"""
    try:
        price = _egg_price_100ppi_fallback()
        return price, "100ppi"
    except Exception as e:
        print(f"[调试] 100ppi 现货获取失败: {e}", file=sys.stderr)
        return None, "100ppi"


def _egg_price_100ppi_fallback():
    """从"鸡蛋产业网–价格快讯"抓取鸡蛋参考价，转换为元/斤。"""
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

def calc_ratio_ma(history, window=MA_WINDOW):
    """从历史数据取最近 window 天有效的 gold_egg_ratio，返回均值与样本数。
    history 已按日期倒序（最新在前）；当天数据应已存入再调用本函数。"""
    values = []
    for rec in history:
        v = rec.get("gold_egg_ratio")
        if v is not None:
            values.append(v)
        if len(values) >= window:
            break
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def calc_etf_premium_pct(etf_price, gold_price_per_g):
    """ETF 折溢价 % = (实际价 - 理论价) / 理论价 * 100
    理论价 = 克金价 / 100（518880 每份 ≈ 0.01g 金）"""
    if etf_price is None or gold_price_per_g is None or gold_price_per_g <= 0:
        return None
    theoretical = gold_price_per_g / GOLD_ETF_SHARE_PER_GRAM
    if theoretical <= 0:
        return None
    return (etf_price - theoretical) / theoretical * 100


def generate_history_statistics():
    """生成最近30天的历史统计表格"""
    history = load_price_history()
    if not history:
        return "\n--- 最近30天历史统计 ---\n暂无历史数据\n"

    # 获取最近30天的数据
    recent_data = history[:30]

    # 表格头部
    table = []
    table.append("\n" + "="*90)
    table.append("最近30天历史统计")
    table.append("="*90)
    table.append(f"{'日期':<12} {'黄金价格':<12} {'鸡蛋价格':<12} {'金蛋比例':<12} {'状态':<10}")
    table.append("-"*90)

    # 阈值区间
    threshold_low = 80.0
    threshold_high = 150.0

    for record in recent_data:
        date = record['date']
        gold_price = record.get('gold_price')
        egg_price = record.get('egg_price')
        ratio = record.get('gold_egg_ratio')
        errors = record.get('errors', [])

        # 格式化价格
        if gold_price is not None:
            # 如果价格大于950，添加特殊标记
            if gold_price > 950:
                gold_str = f"**{gold_price:.2f}**"
            else:
                gold_str = f"{gold_price:.2f}"
        else:
            gold_str = "N/A"

        if egg_price is not None:
            egg_str = f"{egg_price:.2f}"
        else:
            egg_str = "N/A"

        if ratio is not None:
            ratio_str = f"{ratio:.1f}"
            # 判断状态
            if ratio < threshold_low:
                status = "偏低"
            elif ratio > threshold_high:
                status = "偏高"
            else:
                status = "正常"
        else:
            ratio_str = "N/A"
            status = "N/A"

        # 构建行
        row = f"{date:<12} {gold_str:<12} {egg_str:<12} {ratio_str:<12} {status:<10}"
        table.append(row)

    table.append("-"*90)
    table.append("说明：**数字** 表示黄金价格 > 950元/克；比例正常区间: 80.0-150.0")
    table.append("="*90)

    return "\n".join(table)

def main():
    date_str = datetime.date.today().isoformat()
    error_messages = []

    # ── 黄金现货（主源 + fallback）──
    gold = None
    gold_source = None
    try:
        gold, gold_source = get_gold_price_per_g()
        if gold is None:
            raise ValueError("两种来源（SGE API + 网页）均未取到黄金价格")
    except Exception as e:
        print(f"获取黄金价格失败: {e}", file=sys.stderr)
        error_messages.append(f"获取黄金价格失败: {e}")

    # ── 鸡蛋现货（100ppi）──
    egg, egg_source = get_egg_price_per_jin()
    if egg is None:
        error_messages.append("获取鸡蛋现货价失败")

    # ── 附加数据源（失败不阻塞）──
    gold_etf = get_gold_etf_close()
    gold_etf_premium_pct = calc_etf_premium_pct(gold_etf, gold)
    egg_futures = get_egg_price_futures_per_jin()

    rice = get_rice_price_per_jin()

    ratio_gold_egg = gold / egg if (gold is not None and egg is not None) else None
    ratio_gold_rice = gold / rice if (gold is not None and rice not in (None, 0)) else None

    threshold_gold_egg = (80.0, 150.0)
    threshold_gold_rice = (100.0, 200.0)

    # ── 打印 ──
    print(f"日期: {date_str}")
    if gold is not None:
        print(f"黄金价格: {gold:.2f} 元／克  (来源: {gold_source})")
    else:
        print("黄金价格: N/A")

    if egg is not None:
        print(f"鸡蛋价格: {egg:.2f} 元／斤  (来源: {egg_source})")
    else:
        print("鸡蛋价格: N/A")

    if egg_futures is not None:
        print(f"鸡蛋期货 JD0: {egg_futures:.3f} 元／斤  (大商所主力连续)")
    if gold_etf is not None:
        etf_line = f"黄金 ETF 518880: {gold_etf:.3f} 元／份"
        if gold_etf_premium_pct is not None:
            etf_line += f"  折溢价 {gold_etf_premium_pct:+.2f}%"
        print(etf_line)

    if rice is not None:
        print(f"大米价格: {rice:.2f} 元／斤")
    else:
        print("大米价格: N/A")

    if ratio_gold_egg is not None:
        status_egg = ("低于", "处于", "高于")[
            1 + (ratio_gold_egg > threshold_gold_egg[1]) - (ratio_gold_egg < threshold_gold_egg[0])
        ]
        print(
            f"黄金／鸡蛋 比例: {ratio_gold_egg:.1f} – {status_egg} 历史参考区间 "
            f"{threshold_gold_egg[0]:.1f}-{threshold_gold_egg[1]:.1f}"
        )
    else:
        print("黄金／鸡蛋 比例: N/A")

    if ratio_gold_rice is not None:
        status_rice = ("低于", "处于", "高于")[
            1 + (ratio_gold_rice > threshold_gold_rice[1]) - (ratio_gold_rice < threshold_gold_rice[0])
        ]
        print(
            f"黄金／大米 比例: {ratio_gold_rice:.1f} – {status_rice} 历史参考区间 "
            f"{threshold_gold_rice[0]:.1f}-{threshold_gold_rice[1]:.1f}"
        )
    else:
        print("黄金／大米 比例: N/A")

    if error_messages:
        print("\n--- 警告信息 ---")
        for msg in error_messages:
            print(msg)

    # ── 保存到历史 ──
    price_data = {
        "date": date_str,
        "timestamp": datetime.datetime.now().isoformat(),
        "gold_price": gold,
        "gold_price_source": gold_source,
        "egg_price": egg,
        "egg_price_source": egg_source,
        "egg_price_futures": egg_futures,
        "egg_futures_contract": EGG_FUTURES_SYMBOL if egg_futures is not None else None,
        "gold_etf_518880": gold_etf,
        "gold_etf_premium_pct": gold_etf_premium_pct,
        "rice_price": rice,
        "gold_egg_ratio": ratio_gold_egg,
        "gold_rice_ratio": ratio_gold_rice,
        "errors": error_messages,
    }
    save_price_data(price_data)

    # ── 20 日均比对照（必须在 save 之后，让今日值纳入计算）──
    history = load_price_history()
    ma_value, ma_count = calc_ratio_ma(history, MA_WINDOW)
    if ma_value is not None and ratio_gold_egg is not None:
        deviation_pct = (ratio_gold_egg - ma_value) / ma_value * 100
        direction = "高于" if deviation_pct >= 0 else "低于"
        print(
            f"\n--- 比例统计 ---\n"
            f"最近 {ma_count} 日均比: {ma_value:.1f}\n"
            f"今日相对均值: {direction} {abs(deviation_pct):.2f}% （今日 {ratio_gold_egg:.1f} vs MA{ma_count} {ma_value:.1f}）"
        )
        # 回填到历史最新一条，方便前端/通知直接读
        history[0]["ratio_ma20"] = round(ma_value, 4)
        history[0]["ratio_ma20_deviation_pct"] = round(deviation_pct, 4)
        history[0]["ratio_ma20_count"] = ma_count
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[警告] 回填 ratio_ma20 失败: {e}", file=sys.stderr)

    # 输出最近30天历史统计
    print(generate_history_statistics())

if __name__ == "__main__":
    main()