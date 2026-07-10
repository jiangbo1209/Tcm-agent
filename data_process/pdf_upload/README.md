# PDF Manager TUI - 终端上传工具

TUI (Terminal User Interface) 是一个独立的命令行客户端，运行在本地电脑，通过 HTTPS + JWT 连接到部署在云服务器的 UI/backend 上传 PDF 文件。

## 功能

- 选择本地 PDF 文件并上传到云存储
- 列出已上传的文件
- 批量删除文件
- JWT 登录 + token 缓存

## 安装

需要 Python 3.10+ 和以下依赖（`environment.yml` 已包含）：

- `requests` — HTTP 客户端
- `rich` — 终端 UI
- `pyyaml` — 读取 `~/.tcm-tui.yaml`
- `tkinter`（可选）— 文件选择对话框（Linux 桌面环境）

## 配置

优先级（从高到低）：

1. 环境变量 `TCM_API_BASE_URL`
2. `~/.tcm-tui.yaml` 中的 `api_base_url`
3. 默认 `http://localhost:8011`

### 示例：环境变量

```bash
export TCM_API_BASE_URL=https://api.example.com:8011
python data_process/pdf_upload/pdf_manager_tui.py
```

### 示例：配置文件

```yaml
# ~/.tcm-tui.yaml
api_base_url: https://api.example.com:8011
```

## 登录

首次启动 TUI 时，UI/backend 必须可访问。TUI 会要求输入用户名和密码，调用 `POST /api/auth/login` 获取 JWT。JWT 缓存在 `~/.tcm-tui-token`（权限 600），后续启动自动复用，过期后会自动要求重新登录。

## 使用

```text
1  上传文件           选择 PDF (TK 弹窗或路径输入) → 选择文档类型 → 上传
2  查看文件列表       拉取最近 50 条
3  删除文件（支持多选）  输入 1,2,3-5 或 q 取消
0  退出
```

上传时显示总进度（`5/20` 文件已上传），不做单文件进度。

## 常见问题

### T: `无法连接 {base_url}`

确认 `TCM_API_BASE_URL` 正确，且云服务器 `:8011` 端口已开放（安全组放行）。

### T: 登录失败

- 用户名密码错误 → 重新输入
- JWT 过期 → 删除 `~/.tcm-tui-token` 后重试

### T: 401 Unauthorized

TUI 收到 401 会自动清除本地 token 并提示重新登录。

### T: 批量上传卡住

默认每批 50 个文件，timeout 是 `max(300, batch_size * 30)` 秒。
可通过环境变量调整：`export PDF_UPLOAD_BATCH_SIZE=20`。
