#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
示例定时任务脚本。在每次运行时打印当前的日期和时间。

GitHub Actions 的 `schedule` 事件使用 UTC 时区运行，本脚本使用本地时区输出当前时间。
"""
from __future__ import annotations
from datetime import datetime


def main() -> None:
    now = datetime.now()
    print(f"[scheduled_task.py] 当前时间：{now.isoformat()}")
    printf("定时任务执行完成。")


if __name__ == "__main__":
    main()