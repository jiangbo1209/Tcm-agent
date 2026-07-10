#!/usr/bin/env python3
"""
TCM PDF Manager TUI - terminal client for the UI/backend upload API.

Configuration:

* ``TCM_API_BASE_URL`` environment variable — base URL of the UI/backend
  (e.g. ``https://api.example.com:8011``). Takes precedence.
* ``~/.tcm-tui.yaml`` — fallback config file. Set ``api_base_url``.
* ``~/.tcm-tui-token`` — cached JWT (written on first successful login).

Usage:

    python data_process/pdf_upload/pdf_manager_tui.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

import requests
import yaml
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

try:
    from tkinter import Tk, filedialog

    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


CONFIG_PATH = Path(os.path.expanduser("~/.tcm-tui.yaml"))
TOKEN_PATH = Path(os.path.expanduser("~/.tcm-tui-token"))

DEFAULT_API_BASE_URL = "http://localhost:8011"
DEFAULT_UPLOAD_BATCH_SIZE = 50

console = Console()

DOCUMENT_TYPE_LABELS = {
    0: "文献",
    1: "病案",
    2: "指南",
}


# --- Configuration ---------------------------------------------------------


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        console.print(f"[yellow]⚠️  读取 {CONFIG_PATH} 失败：{exc}[/yellow]")
        return {}


def get_api_base_url() -> str:
    """Return the UI/backend base URL.

    Priority: env ``TCM_API_BASE_URL`` → ``~/.tcm-tui.yaml`` → default.
    """
    env = os.getenv("TCM_API_BASE_URL", "").strip()
    if env:
        return env.rstrip("/")
    cfg = _load_config()
    url = str(cfg.get("api_base_url", "")).strip()
    if url:
        return url.rstrip("/")
    return DEFAULT_API_BASE_URL


# --- Auth ------------------------------------------------------------------


def _read_cached_token() -> Optional[str]:
    if not TOKEN_PATH.exists():
        return None
    try:
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        return token or None
    except OSError:
        return None


def _save_token(token: str) -> None:
    try:
        TOKEN_PATH.write_text(token, encoding="utf-8")
        TOKEN_PATH.chmod(0o600)
    except OSError as exc:
        console.print(f"[yellow]⚠️  无法保存 token 到 {TOKEN_PATH}：{exc}[/yellow]")


def _clear_token() -> None:
    try:
        TOKEN_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def login(base_url: str) -> str:
    """Prompt for credentials and POST to ``/api/auth/login``."""
    username = Prompt.ask("[cyan]用户名[/cyan]")
    password = Prompt.ask("[cyan]密码[/cyan]", password=True)
    try:
        resp = requests.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]❌ 无法连接 {base_url}：{exc}[/red]")
        sys.exit(1)

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        console.print(f"[red]❌ 登录失败：{resp.status_code} {detail}[/red]")
        sys.exit(1)

    token = resp.json().get("access_token", "")
    if not token:
        console.print("[red]❌ 登录响应缺少 access_token[/red]")
        sys.exit(1)

    _save_token(token)
    console.print("[green]✅ 登录成功[/green]")
    return token


def get_token(base_url: str) -> str:
    cached = _read_cached_token()
    if cached:
        return cached
    return login(base_url)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Service check ---------------------------------------------------------


def check_service(base_url: str) -> bool:
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


# --- Upload ----------------------------------------------------------------


def _upload_batch_size() -> int:
    try:
        return max(1, int(os.getenv("PDF_UPLOAD_BATCH_SIZE", str(DEFAULT_UPLOAD_BATCH_SIZE))))
    except ValueError:
        return DEFAULT_UPLOAD_BATCH_SIZE


def _chunks(items: list[Path], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _normalize_filename(filename: Optional[str]) -> Optional[str]:
    """Best-effort fix for GBK-encoded Windows filenames."""
    if not filename:
        return filename
    try:
        return filename.encode("latin-1").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return filename


def _prompt_file_paths() -> list[str]:
    console.print("[yellow]未检测到图形界面，切换为命令行输入[/yellow]")
    raw = Prompt.ask("请输入 PDF 路径（逗号分隔）或输入目录路径")
    raw = raw.strip()
    if not raw:
        return []

    candidate = Path(raw).expanduser()
    if candidate.exists() and candidate.is_dir():
        return [str(p) for p in sorted(candidate.glob("*.pdf"))]

    return [str(Path(p).expanduser()) for p in raw.split(",") if p.strip()]


def select_pdf_files() -> list[str]:
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    if not TK_AVAILABLE or not has_display:
        return _prompt_file_paths()

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        paths = filedialog.askopenfilenames(
            title="选择要上传的 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
            multiple=True,
        )
    finally:
        root.destroy()
    return list(paths)


def prompt_document_type() -> int:
    table = Table(show_header=True, header_style="bold cyan", title="选择上传数据类型")
    table.add_column("编号", style="magenta")
    table.add_column("类型", style="cyan")
    table.add_column("用途")
    table.add_row("0", "文献", "进入 lit_metadata，参与文献检索和图谱构建")
    table.add_row("1", "病案", "进入 case_metadata，参与病案检索和图谱构建")
    table.add_row("2", "指南", "进入 guideline_metadata，只用于 Agent 回答校验")
    console.print(table)
    choice = Prompt.ask(
        "[cyan]请选择本次上传文件的数据类型[/cyan]",
        choices=["0", "1", "2"],
        default="0",
    )
    return int(choice)


def _document_type_label(document_type: object) -> str:
    try:
        return DOCUMENT_TYPE_LABELS.get(int(document_type), "未知")
    except (TypeError, ValueError):
        return "未知"


def _upload_one_batch(
    batch_files: list[Path],
    document_type: int,
    base_url: str,
    token: str,
) -> list[dict]:
    """Upload a single batch (≤ batch_size) and return per-file result dicts."""
    files_payload: list[tuple[str, tuple[str, Any, str]]] = []
    handles: list[Any] = []
    try:
        for file_path in batch_files:
            handle = open(file_path, "rb")
            handles.append(handle)
            files_payload.append(
                ("files", (file_path.name, handle, "application/pdf"))
            )

        response = requests.post(
            f"{base_url}/api/files/batch-upload",
            files=files_payload,
            data={"document_type": str(document_type)},
            headers=auth_headers(token),
            timeout=max(300, len(batch_files) * 30),
        )
    finally:
        for h in handles:
            h.close()

    if response.status_code == 401:
        _clear_token()
        raise PermissionError("登录已过期，请重新登录")

    if response.status_code != 200:
        detail = response.text[:200] if response.text else ""
        raise RuntimeError(f"HTTP {response.status_code} {detail}")

    data = response.json()
    return data.get("items", []) if isinstance(data, dict) else []


def upload_files(base_url: str, token: str) -> None:
    console.print("[cyan]📁 打开文件选择器...[/cyan]")
    file_paths = select_pdf_files()
    if not file_paths:
        console.print("[yellow]取消上传[/yellow]")
        return

    valid_files: list[Path] = []
    for raw in file_paths:
        path = Path(raw)
        if not path.exists():
            console.print(f"[yellow]⚠️  文件不存在：{raw}[/yellow]")
        elif path.suffix.lower() != ".pdf":
            console.print(f"[yellow]⚠️  非 PDF 文件：{raw}[/yellow]")
        else:
            valid_files.append(path)

    if not valid_files:
        console.print("[red]❌ 没有有效的 PDF 文件[/red]")
        return

    document_type = prompt_document_type()
    document_label = _document_type_label(document_type)

    console.print(
        f"\n[cyan]📤 准备上传 {len(valid_files)} 个文件，类型：{document_label}[/cyan]\n"
    )

    batch_size = _upload_batch_size()
    results: list[dict] = []
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    with progress:
        overall = progress.add_task(
            f"[cyan]上传 {len(valid_files)} 个文件", total=len(valid_files)
        )

        for batch in _chunks(valid_files, batch_size):
            try:
                items = _upload_one_batch(batch, document_type, base_url, token)
            except PermissionError as exc:
                console.print(f"[red]❌ {exc}[/red]")
                return
            except Exception as exc:
                console.print(f"[red]❌ 上传批次失败：{exc}[/red]")
                for f in batch:
                    results.append(
                        {"文件名": f.name, "状态": "❌ 上传失败", "UUID": "-"}
                    )
                    progress.advance(overall)
                continue

            for file_path, item in zip(batch, items):
                status = item.get("status")
                detail = item.get("detail") or ""
                if status == "uploaded":
                    results.append(
                        {
                            "文件名": file_path.name,
                            "状态": "✅ 成功",
                            "UUID": (item.get("file_uuid", "") or "")[:12],
                        }
                    )
                elif status == "skipped":
                    results.append(
                        {"文件名": file_path.name, "状态": "⚠️  已存在", "UUID": "-"}
                    )
                else:
                    results.append(
                        {
                            "文件名": file_path.name,
                            "状态": f"❌ {detail or '上传失败'}",
                            "UUID": "-",
                        }
                    )
                progress.advance(overall)

            # Any files in this batch that didn't get a server response.
            for file_path in batch[len(items):]:
                results.append(
                    {"文件名": file_path.name, "状态": "❌ 上传失败", "UUID": "-"}
                )
                progress.advance(overall)

    console.print("\n[cyan]📊 上传总结[/cyan]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("文件名", style="cyan")
    table.add_column("状态")
    table.add_column("UUID", style="green")
    for r in results:
        table.add_row(r["文件名"], r["状态"], r["UUID"])
    console.print(table)

    success_count = sum(1 for r in results if "✅" in r["状态"])
    console.print(
        f"\n[green]总计：{len(results)} 个文件，成功 {success_count} 个[/green]\n"
    )


# --- List / View -----------------------------------------------------------


def list_files(base_url: str, token: str, page: int = 1, size: int = 50) -> Optional[dict]:
    try:
        response = requests.get(
            f"{base_url}/api/files/?page={page}&size={size}",
            headers=auth_headers(token),
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]❌ 获取文件列表失败：{exc}[/red]")
        return None
    if response.status_code == 401:
        _clear_token()
        console.print("[red]❌ 登录已过期，请重新登录[/red]")
        return None
    if response.status_code == 200:
        return response.json()
    console.print(f"[red]❌ 获取文件列表失败：HTTP {response.status_code}[/red]")
    return None


def _render_file_table(items: list[dict], *, title: str, columns: list[tuple[str, str]]) -> Table:
    table = Table(show_header=True, header_style="bold cyan", title=title)
    for label, style in columns:
        table.add_column(label, style=style)
    for idx, item in enumerate(items, 1):
        row = [str(idx)]
        for label, _style in columns[1:]:
            if label == "文件名":
                row.append(item.get("original_name", "")[:40])
            elif label == "UUID":
                row.append(item.get("file_uuid", "")[:12])
            elif label == "类型":
                row.append(_document_type_label(item.get("document_type")))
            elif label == "上传时间":
                row.append(item.get("upload_time", "")[:19])
            elif label == "文献元数据":
                row.append("✅" if item.get("status_metadata") else "❌")
            elif label == "病案处理":
                row.append("✅" if item.get("status_case") else "❌")
            elif label == "指南元数据":
                row.append("✅" if item.get("status_guidelinemeta") else "❌")
            else:
                row.append(str(item.get(label, "")))
        table.add_row(*row)
    return table


def view_files(base_url: str, token: str) -> None:
    console.print("[cyan]📋 获取文件列表...[/cyan]")
    data = list_files(base_url, token, page=1, size=50)
    if not data:
        return

    items = data.get("items", [])
    if not items:
        console.print("[yellow]⚠️  没有上传的文件[/yellow]")
        return

    table = _render_file_table(
        items,
        title="📁 已上传的文件",
        columns=[
            ("序号", "magenta"),
            ("文件名", "cyan"),
            ("UUID", "green"),
            ("类型", "cyan"),
            ("上传时间", "yellow"),
            ("文献元数据", ""),
            ("病案处理", ""),
            ("指南元数据", ""),
        ],
    )
    console.print(table)
    console.print(f"\n[green]总计：{data.get('total', 0)} 个文件[/green]\n")


# --- Delete ----------------------------------------------------------------


def _parse_selection(choice: str, max_index: int) -> tuple[list[int], Optional[str]]:
    choice = choice.strip()
    if not choice:
        return [], "请输入序号"
    if choice.lower() == "q":
        return [], None
    selected: list[int] = []
    try:
        for part in choice.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start = int(start_text.strip())
                end = int(end_text.strip())
                if start > end:
                    start, end = end, start
                selected.extend(range(start, end + 1))
            else:
                selected.append(int(part))
    except ValueError:
        return [], "输入格式错误，请使用 1、1,2,3 或 1-5"

    selected = sorted(set(selected))
    valid = [i for i in selected if 1 <= i <= max_index]
    if not valid:
        return [], "请输入有效的序号"
    if len(valid) != len(selected):
        return valid, f"已过滤无效序号，仅保留 {len(valid)} 项"
    return valid, None


def delete_files(base_url: str, token: str) -> None:
    console.print("[cyan]📋 获取文件列表...[/cyan]")
    data = list_files(base_url, token, page=1, size=50)
    if not data:
        return

    items = data.get("items", [])
    if not items:
        console.print("[yellow]⚠️  没有可删除的文件[/yellow]")
        return

    table = _render_file_table(
        items,
        title="🗑️ 可删除的文件",
        columns=[
            ("序号", "magenta"),
            ("文件名", "cyan"),
            ("UUID", "green"),
            ("上传时间", "yellow"),
        ],
    )
    console.print(table)
    console.print(
        "\n[cyan]选择要删除的文件（支持多选）：[/cyan]\n"
        "  输入序号：1 或 1,2,3 或 1-5 或 q 取消"
    )

    selected_indices: list[int] = []
    while True:
        choice = Prompt.ask("[yellow]请输入[/yellow]")
        selected_indices, message = _parse_selection(choice, len(items))
        if choice.strip().lower() == "q" and message is None:
            console.print("[yellow]取消删除[/yellow]")
            return
        if message:
            if message == "请输入有效的序号":
                console.print(f"[red]❌ {message}[/red]")
                continue
            console.print(f"[yellow]⚠️  {message}[/yellow]")
        if selected_indices:
            break

    console.print("\n[yellow]📌 将删除以下文件：[/yellow]")
    delete_table = Table(show_header=True, header_style="bold red")
    delete_table.add_column("序号", style="magenta")
    delete_table.add_column("文件名", style="cyan")
    selected_items: list[dict] = []
    for idx in sorted(selected_indices):
        item = items[idx - 1]
        selected_items.append(item)
        delete_table.add_row(str(idx), item.get("original_name", ""))
    console.print(delete_table)

    if not Confirm.ask(
        f"\n[red]确认删除这 {len(selected_items)} 个文件？[/red]", default=False
    ):
        console.print("[yellow]取消删除[/yellow]")
        return

    file_uuids = [item.get("file_uuid", "") for item in selected_items]
    try:
        response = requests.post(
            f"{base_url}/api/files/batch-delete",
            json={"file_uuids": file_uuids},
            headers=auth_headers(token),
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]❌ 删除出错：{exc}[/red]")
        return

    if response.status_code == 401:
        _clear_token()
        console.print("[red]❌ 登录已过期，请重新登录[/red]")
        return
    if response.status_code != 200:
        console.print(f"[red]❌ 批量删除失败 (HTTP {response.status_code})[/red]")
        return

    data = response.json()
    items_resp = data.get("items", [])
    deleted = data.get("deleted", 0)
    total = data.get("total", 0)
    for idx, item in enumerate(items_resp, 1):
        filename = item.get("original_name") or "未知文件"
        status = item.get("status", "failed")
        if status == "deleted":
            console.print(f"[green]✅ [{idx}/{total}] {filename}[/green]")
        elif status == "not_found":
            console.print(
                f"[yellow]⚠️  [{idx}/{total}] {filename} - 文件不存在[/yellow]"
            )
        else:
            detail = item.get("detail") or "删除失败"
            console.print(f"[red]❌ [{idx}/{total}] {filename} - {detail}[/red]")
    console.print(
        f"\n[cyan]📊 删除总结[/cyan] "
        f"[green]✅ 成功：{deleted}[/green] | "
        f"[yellow]⚠️  失败/不存在：{total - deleted}[/yellow]\n"
    )


# --- Menu ------------------------------------------------------------------


def show_menu(base_url: str) -> None:
    console.clear()
    title = Text("TCM PDF 管理工具 (TUI)", justify="center", style="bold cyan")
    subtitle = Text(
        f"API: {base_url}", justify="center", style="dim"
    )
    console.print(
        Panel.fit(Text.assemble(title, "\n", subtitle), border_style="cyan")
    )
    menu_text = """
[cyan]1[/cyan]  上传文件
[cyan]2[/cyan]  查看文件列表
[cyan]3[/cyan]  删除文件（支持多选）
[cyan]0[/cyan]  退出
"""
    console.print(Align(Panel.fit(menu_text, border_style="blue"), align="center"))


def main() -> None:
    base_url = get_api_base_url()
    if not check_service(base_url):
        console.print(
            f"[red]❌ 服务不可用 ({base_url})[/red]\n"
            "请确认 UI/backend 已启动并配置正确的 URL。\n"
            "  设置环境变量: export TCM_API_BASE_URL=https://api.example.com:8011\n"
            "  或编辑配置文件: vi ~/.tcm-tui.yaml"
        )
        sys.exit(1)

    token = get_token(base_url)

    while True:
        show_menu(base_url)
        choice = Prompt.ask("[cyan]请选择操作[/cyan]", choices=["0", "1", "2", "3"])
        if choice == "0":
            console.print("[yellow]👋 再见！[/yellow]\n")
            break
        elif choice == "1":
            console.print()
            upload_files(base_url, token)
        elif choice == "2":
            console.print()
            view_files(base_url, token)
        elif choice == "3":
            console.print()
            delete_files(base_url, token)
        Prompt.ask("\n[cyan]按 Enter 继续[/cyan]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]程序已中止[/yellow]")
        sys.exit(0)
