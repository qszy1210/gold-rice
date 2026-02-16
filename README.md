# GitHub Actions 示例：定时任务与邮件发送

这个仓库是一个用于学习 **GitHub Actions** 机制的简易示例。它包含了以下内容：

* 一个 Python 脚本，用来演示如何读取环境变量并发送电子邮件（代码仅提供框架，不包含任何实际的邮件内容和帐户信息）。
* 一个简单的 Python 脚本，用于定时打印当前日期和时间。
* 一个黄金和鸡蛋价格抓取脚本（`gold_egg_price.py`），用于从公开网页抓取黄金和鸡蛋价格并计算比例。
* 一个工作流文件（`.github/workflows/main.yml`），展示如何在每次推送时运行工作流，以及如何使用 GitHub Actions 的 `schedule` 事件根据 cron 表达式定时触发工作流。

> **注意：** 为了保护隐私，本示例中不会提供任何具体的邮箱地址、用户名或密码等信息。发送邮件所需的所有敏感信息都应通过 GitHub 的 Secrets 管理功能注入。有关如何在工作流中使用 Secrets，可参考 [GitHub 官方文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)。

## 文件结构

```text
github-actions-demo/
├── .github/
│   └── workflows/
│       └── main.yml          # GitHub Actions 工作流定义
├── scripts/
│   ├── send_email.py         # 演示邮件发送的 Python 脚本
│   ├── scheduled_task.py     # 定时任务示例脚本
│   └── gold_egg_price.py     # 黄金和鸡蛋价格抓取脚本
├── requirements.txt          # Python 依赖包列表
├── .env.example              # 环境变量配置示例（复制为 .env 并填写）
├── .gitignore                # Git 忽略文件配置
└── README.md                 # 项目说明（本文档）
```

## 使用说明

### 本地运行

#### 1. 安装依赖

本项目使用 Python 3，需要安装 `requests` 和 `beautifulsoup4` 依赖包。

**方式一：使用虚拟环境（推荐）**

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**方式二：全局安装**

```bash
pip3 install requests beautifulsoup4
```

#### 2. 运行脚本

安装依赖后，可以运行各个脚本：

```bash
# 运行黄金和鸡蛋价格抓取脚本
python3 scripts/gold_egg_price.py

# 运行定时任务示例
python3 scripts/scheduled_task.py

# 运行邮件发送示例（需要配置环境变量）
python3 scripts/send_email.py
```

**注意：** 如果使用虚拟环境，运行脚本前需要先激活虚拟环境。

#### 3. 本地邮件发送配置（可选）

若要本地运行 `send_email.py`，需配置环境变量。项目提供 `.env.example` 作为模板：

```bash
# 复制示例配置（不要提交 .env，已列入 .gitignore）
cp .env.example .env

# 编辑 .env，填入你的 Gmail 账号、应用专用密码和收件人邮箱
# Gmail 应用专用密码：Google 账号 → 安全性 → 两步验证 → 应用专用密码
```

所需变量：`GMAIL_USERNAME`、`GMAIL_APP_PASSWORD`、`EMAIL_TO`。脚本不会读取 `.env` 文件本身，需在 shell 中 `export` 或使用 `env $(cat .env | xargs) python scripts/send_email.py` 等方式注入。

### GitHub Actions 自动化

1. **克隆或创建仓库：** 将该目录结构放置在你自己的 GitHub 仓库中（例如 `github-actions-demo`）。
2. **准备 Secrets：**
   - 在 GitHub 仓库页面中，进入 **Settings → Secrets and variables → Actions**。
   - 为邮件发送步骤设置以下 Secret（与工作流中使用的名称一致）：
     - `GMAIL_USERNAME`：Gmail 发件人邮箱（如 `your@gmail.com`）
     - `GMAIL_APP_PASSWORD`：Gmail 应用专用密码（16 位，在 Google 账号安全性中生成）
     - `EMAIL_TO`：收件人邮箱，多个地址用逗号分隔（如 `a@example.com,b@example.com`）

   工作流中 SMTP 服务器与端口已固定为 Gmail（`smtp.gmail.com:587`），上述三个 Secret 会注入到环境变量供 `send_email.py` 使用。

3. **推送代码：** 当你将此仓库推送到 GitHub 时，工作流会在默认分支上触发 `push` 事件，从而运行脚本并输出日志。
4. **定时执行：** 工作流还包含一个 `schedule` 事件，当前为 `0 2 * * *`，即每天 02:00 UTC（北京时间 10:00）触发。GitHub 的 `schedule` 使用 UTC 时区，可根据需要调整 cron 表达式。

5. **实际测试：**
   - 若你已经配置了正确的 Secrets，并允许工作流运行，`send_email.py` 会在定时任务或手动触发时尝试发送一封邮件。脚本中有输出提示，告诉你邮件是否发送成功。
   - `scheduled_task.py` 在每次运行时会打印当前的日期和时间，用于演示定时任务效果。

## 工作流内容概览

工作流文件 `.github/workflows/main.yml` 包含两个主要部分：

1. **触发器**：
   ```yaml
   on:
     push:          # 当代码推送到默认分支时触发（提交信息含 run 时才执行）
     workflow_dispatch:  # 手动触发
     schedule:
       - cron: '0 2 * * *'  # 每天 02:00 UTC（北京时间 10:00）
   ```
   `schedule` 事件允许你在指定时间自动运行工作流，GitHub 使用 POSIX cron 语法。

2. **作业**：
   邮件发送步骤使用的环境变量（在对应 step 的 `env` 下配置）：
   ```yaml
   env:
     SMTP_HOST: smtp.gmail.com
     SMTP_PORT: 587
     GMAIL_USERNAME: ${{ secrets.GMAIL_USERNAME }}
     GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
     EMAIL_TO: ${{ secrets.EMAIL_TO }}
   ```
   通过 `env` 字段将 Secrets 注入为环境变量，供 `send_email.py` 使用。

## 脚本说明

### gold_egg_price.py - 黄金和鸡蛋价格抓取

这个脚本从公开网页抓取黄金和鸡蛋价格，并计算它们的比例关系。

**数据源：**
- 黄金价格：上海黄金交易所（Au99.99，24K 黄金）
- 鸡蛋价格：中国鸡蛋产业网

**输出示例：**
```
日期: 2025-10-24
黄金价格: 600.50 元／克
鸡蛋价格: 5.20 元／斤
黄金／鸡蛋 比例: 115.5 – 处于 历史参考区间 80.0-150.0
大米价格: N/A
黄金／大米 比例: N/A
```

**功能特点：**
- 自动处理周末和节假日（查找最近 5 天内的数据）
- 计算黄金/鸡蛋比例，并与历史参考区间对比
- 输出价格是否处于正常区间
- **数据持久化**：自动保存价格数据到 `data/price_history.json`
- **GitHub Actions 优化**：增强的请求头和重试机制，提高在 CI 环境中的成功率

### generate_html.py - HTML 可视化页面生成

这个脚本读取历史价格数据并生成可视化的 HTML 报告页面。

**功能特点：**
- 📊 交互式价格趋势图表（使用 Chart.js）
- 📈 黄金/鸡蛋比例趋势分析
- 📋 最近 30 天的详细数据表格
- 🎨 响应式设计，支持移动设备
- 🔄 自动更新，每天执行一次（北京时间上午 10:00）

**生成的文件：**
- `index.html` - 可视化报告页面（可直接通过浏览器打开或部署到 GitHub Pages）

## GitHub Pages 部署

要在线查看价格追踪页面，可以启用 GitHub Pages：

1. 进入仓库的 **Settings → Pages**
2. 在 **Source** 下选择 **Deploy from a branch**
3. 选择 **master** 分支和 **/ (root)** 目录
4. 点击 **Save**

几分钟后，你的价格追踪页面将在 `https://<你的用户名>.github.io/<仓库名>/` 上线。

## 调整时间与任务

* 如果希望按自己的时区或频率运行，只需修改 `cron` 表达式。例如 `0 13 * * *` 将在每天 13:00 UTC 运行。
* 你也可以扩展 `scheduled_task.py` 和 `send_email.py`，例如访问 Web API、生成报告等。
* 数据文件 `data/price_history.json` 会自动保留最近 365 天的数据

## 参考资料

* [GitHub Actions - 定时任务 (schedule)](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
* [GitHub Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
