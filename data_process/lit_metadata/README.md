# paper_info_crawler

工程化的论文信息爬取工具，从 PostgreSQL 的 `core_file` 表读取待处理文件（不读取 PDF 正文），用文件名清洗后的标题去三个学术资源站搜索并入库：**e读 → CNKI → NSTL**。

## 三个数据源

| 顺序 | 站点 | 说明 |
|---|---|---|
| 1 | **e读 (yidu.calis.edu.cn)** | 公开 HTTP API，无登录、无验证码 |
| 2 | **NSTL (nstl.gov.cn)** | 公开 HTTP API，可由 `ENABLE_NSTL` 关闭 |
| 3 | **CNKI (kns.cnki.net)** | POST API + EndNote 导出。首次或 cookie 过期时**会弹出 Chromium 让用户手动过一次滑块验证**，5 分钟 TTL 内复用。可由 `ENABLE_CNKI` 关闭。 |

三个站点都走同一套**标题完全匹配**策略，只有 normalize 后与清洗标题完全相等才会写库；否则进 `failed_records`。

## 功能说明

- 从 PostgreSQL `core_file` 表读取 `status_metadata=false` 的 PDF 记录，用 `original_name` 作为搜索输入，`file_uuid` 作为唯一标识。
- 用 `FilenameCleaner` 保守清洗：去编号前缀、去下载标记、去外层书名号。
- 用 `ExactTitleMatcher` 严格匹配：normalize 后必须 `cleaned_title == result_title`。
- 爬取 title / authors / abstract / keywords / paper_type / journal / pub_year / source_url。
- 成功或 partial 记录写入 `lit_metadata`，并把对应 `core_file.status_metadata` 更新为 `true`；失败写入 `failed_records`，运行结束导出 `outputs/failed_records.csv`（UTF-8-SIG）。
- 默认低并发、随机停顿 2~5s，不绕过验证码、不破解登录。CNKI 的 Playwright 引导是用户**手动**点按钮完成的，不属于绕过。

## 环境要求

- Python 3.10+
- PostgreSQL async 通过 `asyncpg` 支持，已包含在 `requirements.txt`。
- CNKI 启用时需要 Playwright 能找到一个浏览器。**国内网络推荐用系统已装的 Edge / Chrome**（见下），不需要下载 Chromium。

## Windows PowerShell 安装

```powershell
cd paper_info_crawler
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install msedge       # 仅 CNKI 启用时需要；不下载浏览器，注册系统 Edge
copy .env.example .env
python run.py
```

## macOS/Linux 安装

```bash
cd paper_info_crawler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium     # 仅 CNKI 启用时需要
cp .env.example .env
python run.py
```

## 浏览器三选一（仅 CNKI 用）

CNKI 启用时只在弹 cookie 引导窗口的那一下用一次浏览器。三种供你选：

| 方式 | 命令 | `.env` 配置 | 适用 |
|---|---|---|---|
| 系统 Edge | `playwright install msedge` | `CNKI_BROWSER_CHANNEL=msedge` | **Windows 默认选这个**，无需下载 |
| 系统 Chrome | `playwright install chrome` | `CNKI_BROWSER_CHANNEL=chrome` | 已装 Chrome 时也可 |
| 下载 Chromium | `playwright install chromium` | `CNKI_BROWSER_CHANNEL=`（留空） | 海外网络；国内可能拉不下来 |

国内拉不下来 Chromium 时可设镜像：`$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"`（最新 playwright 版本可能没镜像，建议直接走 Edge）。

## 配置 .env

```env
DATABASE_URL=postgresql+asyncpg://postgres:<url-encoded-password>@172.16.150.45:5432/papers_records
OUTPUT_DIR=./outputs
CORE_FILE_PENDING_LIMIT=0
CRAWLER_TIMEOUT=30
CRAWLER_MAX_RETRIES=2
CRAWLER_CONCURRENCY=1
REQUEST_DELAY_MIN=2.0
REQUEST_DELAY_MAX=5.0
ENABLE_NSTL=true
LOG_LEVEL=INFO
EXPORT_FAILED_CSV=true
YIDU_BASE_URL=https://yidu.calis.edu.cn
NSTL_BASE_URL=https://www.nstl.gov.cn
USER_AGENT=Mozilla/5.0
SKIP_EXISTING_RECORDS=true
ENABLE_CNKI=true
CNKI_BASE_URL=https://kns.cnki.net
CNKI_COOKIE_TTL_SEC=300
CNKI_HEADLESS_BOOTSTRAP=false
CNKI_BROWSER_CHANNEL=msedge
CNKI_HUMAN_PAUSE_MIN=0.8
CNKI_HUMAN_PAUSE_MAX=2.4
```

`CORE_FILE_PENDING_LIMIT=0` 表示不限制读取数量；设为正整数时只处理指定数量的待处理记录。

把 `ENABLE_CNKI=false` 即可完全停用 CNKI 链路（也不会触发 Playwright）。

## 数据库配置

需要把 `.env` 配成 PostgreSQL 连接串：

```env
DATABASE_URL=postgresql+asyncpg://postgres:<url-encoded-password>@172.16.150.45:5432/papers_records
```

如果密码里有 `@`，连接串里要写成 `%40`。例如密码 `abc@123` 在连接串中应写成 `abc%40123`。不要把真实密码提交到仓库文档。

程序从 `core_file` 表读取待处理文件：

```sql
select * from public.core_file
where status_metadata = false
  and lower(file_type) = 'pdf';
```

字段使用规则：

- `file_uuid`：唯一标识符。
- `original_name`：作为文件名输入，清洗后用于搜索论文标题。
- `storage_path`：作为记录中的文件路径。
- `status_metadata`：成功写入 `lit_metadata` 后更新为 `true`；失败时保持 `false`，便于后续重试。

## 运行

```bash
python run.py
# 或
python -m app.main
```

**首次启用 CNKI 时**：会自动弹一个浏览器窗口（按 `CNKI_BROWSER_CHANNEL` 决定是 Edge / Chrome / Chromium）到知网首页，请等页面正常加载（如有滑块先滑完），然后点**右上角的红框绿按钮"确认完成验证"**。窗口会关闭，cookie 落到 `outputs/cnki_debug/cnki_cookies.json`，后续 5 分钟内的 CNKI 请求自动复用，不会再弹窗。

## 查看结果

成功 / partial 写入远程 PostgreSQL 的 `lit_metadata`：

```sql
select file_uuid, original_name, source_site, paper_type, journal, pub_year, crawl_status
from public.lit_metadata
order by created_at desc
limit 10;

select file_uuid, original_name, status_metadata
from public.core_file
order by upload_time desc
limit 10;
```

## 失败 CSV

```text
outputs/failed_records.csv
```

字段：`file_name`、`file_path`、`cleaned_title`、`attempted_sites`、`failure_reason`、`error_message`、`suggested_action`、`created_at`。

## 标题完全匹配规则

只做：全角空格替换、首尾 strip、连续空格压缩。**不**去标点、不去括号、不去副标题。匹配等价于：

```python
normalize(cleaned_title) == normalize(result_title)
```

## 爬虫顺序与合规

- 顺序：`yidu → cnki → nstl`。前一站出 success 立即返回，不再继续。NSTL 排在最后因为其数据不含摘要。
- 每次请求前随机等待 `REQUEST_DELAY_MIN` 到 `REQUEST_DELAY_MAX` 秒。
- 遇到 403/429/captcha/login 立即写失败记录。**CNKI 的 captcha 是例外**——它会弹 Playwright 让用户**手动**过一次后继续。
- 不使用 `rapidfuzz` / 模糊匹配，不破解滑块。

## 测试

```bash
pytest
```

测试不联网。

## 常见问题

### CNKI 浏览器窗口一直不关
必须点**右上角红框里的绿按钮**。关窗口或按回车都不行。

### 每条 CNKI 都弹 403
Cookie 失效太快。把 `CRAWLER_CONCURRENCY` 降到 1，加大 `REQUEST_DELAY_MIN/MAX`。

### 不想用 CNKI
`.env` 设 `ENABLE_CNKI=false`，省去 Playwright 依赖（也可以直接不装）。

### `playwright install chromium` 在国内拉不下来
改用 `playwright install msedge` 并在 `.env` 把 `CNKI_BROWSER_CHANNEL=msedge`。系统 Edge 直接拿来用，不下载二进制。

### 数据库锁
`CRAWLER_CONCURRENCY ≤ 3`；或换 `postgresql+asyncpg://...`。
