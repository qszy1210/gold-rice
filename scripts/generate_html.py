#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_html.py
================
读取价格历史数据并生成可视化 HTML 页面
"""

import json
import os
import sys
from datetime import datetime

# 数据和输出路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")
OUTPUT_HTML = os.path.join(PROJECT_DIR, "index.html")

def load_price_history():
    """加载历史价格数据"""
    if not os.path.exists(HISTORY_FILE):
        print(f"[错误] 历史数据文件不存在: {HISTORY_FILE}", file=sys.stderr)
        return []

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"[信息] 成功加载 {len(data)} 条历史记录", file=sys.stderr)
            return data
    except Exception as e:
        print(f"[错误] 加载历史数据失败: {e}", file=sys.stderr)
        return []

MA_WINDOW = 20


def _rolling_ma(values, window):
    """对 None 安全的滚动平均：每个位置取过去 window 个有效值的均值（不足则为 None）"""
    out = []
    for i in range(len(values)):
        window_vals = [v for v in values[max(0, i - window + 1): i + 1] if v is not None]
        if len(window_vals) < min(window, 5):  # 至少 5 个样本才出 MA，否则 None
            out.append(None)
        else:
            out.append(sum(window_vals) / len(window_vals))
    return out


def generate_html(history_data):
    """生成 HTML 页面"""

    # ── 数据准备（图表用正序）──
    dates = []
    gold_prices = []
    egg_prices = []
    ratios = []
    for record in reversed(history_data):
        dates.append(record['date'])
        gold_prices.append(record.get('gold_price'))
        egg_prices.append(record.get('egg_price'))
        ratios.append(record.get('gold_egg_ratio'))

    # 滚动 20 日均比（与正序对齐）
    ratios_ma20 = _rolling_ma(ratios, MA_WINDOW)

    # 最新数据
    latest = history_data[0] if history_data else {}
    latest_ma20 = latest.get('ratio_ma20')
    latest_ma20_dev = latest.get('ratio_ma20_deviation_pct')
    latest_ma20_n = latest.get('ratio_ma20_count') or MA_WINDOW
    latest_etf = latest.get('gold_etf_518880')
    latest_etf_premium = latest.get('gold_etf_premium_pct')
    latest_egg_futures = latest.get('egg_price_futures')

    # 20 日均比卡片样式 + 文本
    if latest_ma20 is not None and latest_ma20_dev is not None:
        ma_direction_cls = 'danger' if latest_ma20_dev > 0 else 'success'
        ma_arrow = '↑' if latest_ma20_dev >= 0 else '↓'
        ma_dev_text = f'{ma_arrow} {abs(latest_ma20_dev):.2f}%'
        ma_value_text = f'{latest_ma20:.1f}'
        ma_sub_text = f'MA{latest_ma20_n} · 今日{ma_dev_text}'
    else:
        ma_direction_cls = ''
        ma_value_text = 'N/A'
        ma_sub_text = '历史数据不足'

    # ── 表格行（增加 ETF、期货列）──
    table_rows = []
    for record in history_data[:30]:
        def fmt(v, decimals=2):
            return f"{v:.{decimals}f}" if v is not None else 'N/A'

        gold_price_str = fmt(record.get('gold_price'))
        egg_price_str = fmt(record.get('egg_price'))
        ratio_str = fmt(record.get('gold_egg_ratio'), 1)
        etf_str = fmt(record.get('gold_etf_518880'), 3)
        egg_fut_str = fmt(record.get('egg_price_futures'), 3)
        status_badge = '<span class="error-badge">有错误</span>' if record.get('errors') else '<span class="success-badge">正常</span>'

        table_rows.append(f'''
                    <tr>
                        <td>{record.get('date', 'N/A')}</td>
                        <td>{gold_price_str}</td>
                        <td>{egg_price_str}</td>
                        <td>{ratio_str}</td>
                        <td>{etf_str}</td>
                        <td>{egg_fut_str}</td>
                        <td>{status_badge}</td>
                    </tr>''')

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>黄金/鸡蛋价格追踪 - Gold & Egg Price Tracker</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}

        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}

        .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
        }}

        .stat-label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}

        .stat-value.warning {{
            color: #f39c12;
        }}

        .stat-value.danger {{
            color: #e74c3c;
        }}

        .stat-value.success {{
            color: #27ae60;
        }}

        .stat-subtitle {{
            font-size: 0.75em;
            color: #888;
            margin-top: 6px;
            font-weight: normal;
        }}

        .stat-unit {{
            font-size: 0.6em;
            color: #999;
            margin-left: 5px;
        }}

        .chart-container {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}

        .chart-title {{
            font-size: 1.3em;
            margin-bottom: 20px;
            color: #333;
            text-align: center;
        }}

        canvas {{
            max-height: 400px;
        }}

        .data-table {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}

        tr:hover {{
            background: #f8f9fa;
        }}

        .error-badge {{
            background: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
        }}

        .success-badge {{
            background: #27ae60;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
        }}

        footer {{
            text-align: center;
            color: white;
            margin-top: 40px;
            opacity: 0.8;
        }}

        .update-time {{
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 20px;
            display: inline-block;
            margin-top: 20px;
        }}

        @media (max-width: 768px) {{
            h1 {{
                font-size: 1.8em;
            }}

            .stats-grid {{
                grid-template-columns: 1fr;
            }}

            .chart-container {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🥇 黄金/鸡蛋价格追踪</h1>
            <p class="subtitle">Gold & Egg Price Tracker</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">黄金价格 Gold Price</div>
                <div class="stat-value">
                    {f"{latest.get('gold_price'):.2f}" if latest.get('gold_price') is not None else 'N/A'}
                    <span class="stat-unit">元/克</span>
                </div>
                <div class="stat-subtitle">来源: {latest.get('gold_price_source', 'sge_api')}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">鸡蛋价格 Egg Price</div>
                <div class="stat-value">
                    {f"{latest.get('egg_price'):.2f}" if latest.get('egg_price') is not None else 'N/A'}
                    <span class="stat-unit">元/斤</span>
                </div>
                <div class="stat-subtitle">{
                    f"期货 JD0: {latest_egg_futures:.3f} 元/斤" if latest_egg_futures is not None else '现货报价 (100ppi)'
                }</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">黄金/鸡蛋比例 Gold/Egg Ratio</div>
                <div class="stat-value {'warning' if latest.get('gold_egg_ratio', 0) and latest.get('gold_egg_ratio') > 150 else ''}">
                    {f"{latest.get('gold_egg_ratio'):.1f}" if latest.get('gold_egg_ratio') is not None else 'N/A'}
                </div>
                <div class="stat-subtitle">参考区间 80–150</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">近 {latest_ma20_n} 日均比 MA{latest_ma20_n}</div>
                <div class="stat-value {ma_direction_cls}">
                    {ma_value_text}
                </div>
                <div class="stat-subtitle">{ma_sub_text}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">黄金 ETF 518880</div>
                <div class="stat-value">
                    {f"{latest_etf:.3f}" if latest_etf is not None else 'N/A'}
                    <span class="stat-unit">元/份</span>
                </div>
                <div class="stat-subtitle">{
                    f"折溢价 {latest_etf_premium:+.2f}%" if latest_etf_premium is not None else '华安黄金 ETF'
                }</div>
            </div>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">价格趋势图 Price Trends</h2>
            <canvas id="priceChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">黄金/鸡蛋比例趋势 Gold/Egg Ratio Trend</h2>
            <canvas id="ratioChart"></canvas>
        </div>

        <div class="data-table">
            <h2 class="chart-title">历史数据 Historical Data</h2>
            <table>
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>黄金价格<br>(元/克)</th>
                        <th>鸡蛋价格<br>(元/斤)</th>
                        <th>金/蛋比例</th>
                        <th>黄金 ETF<br>(元/份)</th>
                        <th>鸡蛋期货<br>(元/斤)</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <footer>
            <div class="update-time">
                最后更新: {latest.get('timestamp', 'N/A') if latest else 'N/A'}
            </div>
            <p style="margin-top: 20px;">
                数据来源: 上海黄金交易所 (Au99.99) · 华安黄金 ETF (518880) · 大商所鸡蛋期货 (JD0) · 鸡蛋产业网现货<br>
                自动更新周期: 每天一次（北京时间上午 10:00）
            </p>
        </footer>
    </div>

    <script>
        // 价格趋势图
        const priceCtx = document.getElementById('priceChart').getContext('2d');
        const priceChart = new Chart(priceCtx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates[-30:])},
                datasets: [
                    {{
                        label: '黄金价格 (元/克)',
                        data: {json.dumps(gold_prices[-30:])},
                        borderColor: '#f39c12',
                        backgroundColor: 'rgba(243, 156, 18, 0.1)',
                        yAxisID: 'y',
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: '鸡蛋价格 (元/斤)',
                        data: {json.dumps(egg_prices[-30:])},
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        yAxisID: 'y1',
                        tension: 0.4,
                        fill: true
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                    }}
                }},
                scales: {{
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {{
                            display: true,
                            text: '黄金价格 (元/克)'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {{
                            display: true,
                            text: '鸡蛋价格 (元/斤)'
                        }},
                        grid: {{
                            drawOnChartArea: false,
                        }}
                    }}
                }}
            }}
        }});

        // 比例趋势图
        const ratioCtx = document.getElementById('ratioChart').getContext('2d');
        const ratioChart = new Chart(ratioCtx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates[-30:])},
                datasets: [
                    {{
                        label: '黄金/鸡蛋比例',
                        data: {json.dumps(ratios[-30:])},
                        borderColor: '#9b59b6',
                        backgroundColor: 'rgba(155, 89, 182, 0.1)',
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'MA{MA_WINDOW} 滚动均值',
                        data: {json.dumps(ratios_ma20[-30:])},
                        borderColor: '#2c3e50',
                        borderDash: [3, 3],
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: false
                    }},
                    {{
                        label: '参考上限 (150)',
                        data: Array({len(dates[-30:])}).fill(150),
                        borderColor: '#e74c3c',
                        borderDash: [5, 5],
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false
                    }},
                    {{
                        label: '参考下限 (80)',
                        data: Array({len(dates[-30:])}).fill(80),
                        borderColor: '#27ae60',
                        borderDash: [5, 5],
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                    }}
                }},
                scales: {{
                    y: {{
                        title: {{
                            display: true,
                            text: '比例值'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''

    return html_content

def main():
    """主函数"""
    print("[信息] 开始生成 HTML 页面...", file=sys.stderr)

    # 加载历史数据
    history = load_price_history()

    if not history:
        print("[警告] 没有历史数据，将生成空白页面", file=sys.stderr)

    # 生成 HTML
    html = generate_html(history)

    # 保存到文件
    try:
        with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"[成功] HTML 页面已生成: {OUTPUT_HTML}", file=sys.stderr)
        print(f"生成的文件: {OUTPUT_HTML}")
    except Exception as e:
        print(f"[错误] 保存 HTML 失败: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
