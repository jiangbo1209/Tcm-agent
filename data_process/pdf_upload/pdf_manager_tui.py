#!/usr/bin/env python3
"""
TCM PDF 文件管理工具 - TUI 版本
支持上传、查看、删除 PDF 文件
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import requests
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

try:
    from tkinter import Tk, filedialog
except ImportError:
    print("错误：需要 tkinter 支持")
    sys.exit(1)

# API 服务配置
API_BASE_URL = "http://localhost:8001"
UPLOAD_ENDPOINT = f"{API_BASE_URL}/api/files/batch-upload"
LIST_ENDPOINT = f"{API_BASE_URL}/api/files"
DELETE_ENDPOINT = f"{API_BASE_URL}/api/files"
BATCH_DELETE_ENDPOINT = f"{API_BASE_URL}/api/files/batch-delete"
HEALTH_CHECK_URL = f"{API_BASE_URL}/health"

console = Console()


def check_service() -> bool:
    """检查服务是否可用"""
    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _render_file_table(items: list[dict], *, title: str, columns: list[tuple[str, str]]) -> Table:
    """Render a compact file table."""
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
            elif label == "上传时间":
                row.append(item.get("upload_time", "")[:19])
            elif label == "文献元数据":
                row.append("✅" if item.get("status_metadata") else "❌")
            elif label == "病案处理":
                row.append("✅" if item.get("status_case") else "❌")
            else:
                row.append(str(item.get(label, "")))
        table.add_row(*row)

    return table


def _parse_selection(choice: str, max_index: int) -> tuple[list[int], str | None]:
    """Parse selections like 1,2,5-7."""
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
    valid = [index for index in selected if 1 <= index <= max_index]
    if not valid:
        return [], "请输入有效的序号"
    if len(valid) != len(selected):
        return valid, f"已过滤无效序号，仅保留 {len(valid)} 项"
    return valid, None


def select_pdf_files() -> list[str]:
    """弹出文件选择器，选择 PDF 文件"""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_paths = filedialog.askopenfilenames(
        title="选择要上传的 PDF 文件",
        filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        multiple=True,
    )

    root.destroy()
    return list(file_paths)


def upload_files() -> None:
    """上传 PDF 文件"""
    console.print("[cyan]📁 打开文件选择器...[/cyan]")
    file_paths = select_pdf_files()

    if not file_paths:
        console.print("[yellow]取消上传[/yellow]")
        return

    # 验证文件
    valid_files = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            console.print(f"[yellow]⚠️  文件不存在：{file_path}[/yellow]")
        elif not path.suffix.lower() == ".pdf":
            console.print(f"[yellow]⚠️  非 PDF 文件：{file_path}[/yellow]")
        else:
            valid_files.append(path)

    if not valid_files:
        console.print("[red]❌ 没有有效的 PDF 文件[/red]")
        return

    # 上传文件
    console.print(f"\n[cyan]📤 上传 {len(valid_files)} 个文件...[/cyan]\n")

    results = []
    for file_path in valid_files:
        try:
            with open(file_path, "rb") as f:
                files = {"files": (file_path.name, f, "application/pdf")}
                response = requests.post(
                    UPLOAD_ENDPOINT,
                    files=files,
                    timeout=30,
                )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    results.append(
                        {
                            "文件名": file_path.name,
                            "状态": "✅ 成功",
                            "UUID": item.get("file_uuid", "")[:12],
                        }
                    )
                    console.print(f"[green]✅ {file_path.name}[/green]")
                else:
                    results.append(
                        {
                            "文件名": file_path.name,
                            "状态": "⚠️  已存在",
                            "UUID": "-",
                        }
                    )
                    console.print(f"[yellow]⚠️  {file_path.name} 已存在[/yellow]")
            elif response.status_code == 409:
                results.append(
                    {
                        "文件名": file_path.name,
                        "状态": "⚠️  已存在",
                        "UUID": "-",
                    }
                )
                console.print(f"[yellow]⚠️  {file_path.name} 已存在[/yellow]")
            else:
                results.append(
                    {
                        "文件名": file_path.name,
                        "状态": f"❌ HTTP {response.status_code}",
                        "UUID": "-",
                    }
                )
                console.print(
                    f"[red]❌ {file_path.name} - HTTP {response.status_code}[/red]"
                )

        except Exception as e:
            results.append(
                {
                    "文件名": file_path.name,
                    "状态": "❌ 错误",
                    "UUID": "-",
                }
            )
            console.print(f"[red]❌ {file_path.name} - {e}[/red]")

    # 显示总结表格
    console.print("\n[cyan]📊 上传总结[/cyan]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("文件名", style="cyan")
    table.add_column("状态")
    table.add_column("UUID")

    for result in results:
        table.add_row(result["文件名"], result["状态"], result["UUID"])

    console.print(table)

    success_count = sum(1 for r in results if "✅" in r["状态"])
    console.print(
        f"\n[green]总计：{len(results)} 个文件，成功 {success_count} 个[/green]\n"
    )


def list_files(page: int = 1, size: int = 20) -> Optional[dict]:
    """获取文件列表"""
    try:
        response = requests.get(f"{LIST_ENDPOINT}/?page={page}&size={size}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        console.print(f"[red]❌ 获取文件列表失败：{e}[/red]")
    return None


def view_files() -> None:
    """查看文件列表"""
    console.print("[cyan]📋 获取文件列表...[/cyan]")
    data = list_files(page=1, size=50)

    if not data:
        console.print("[red]❌ 无法获取文件列表[/red]")
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
            ("上传时间", "yellow"),
            ("文献元数据", ""),
            ("病案处理", ""),
        ],
    )
    console.print(table)
    total = data.get("total", 0)
    console.print(f"\n[green]总计：{total} 个文件[/green]\n")


def delete_files() -> None:
    """删除文件（支持多选）"""
    console.print("[cyan]📋 获取文件列表...[/cyan]")
    data = list_files(page=1, size=50)

    if not data:
        console.print("[red]❌ 无法获取文件列表[/red]")
        return

    items = data.get("items", [])
    if not items:
        console.print("[yellow]⚠️  没有上传的文件[/yellow]")
        return

    # 显示文件列表，供选择
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

    # 选择要删除的文件（支持多选）
    console.print(
        "\n[cyan]选择要删除的文件（支持多选）：[/cyan]\n"
        "  输入序号：1 或 1,2,3 或 1-5 或 q 取消"
    )

    while True:
        choice = Prompt.ask("[yellow]请输入[/yellow]")
        selected_indices, message = _parse_selection(choice, len(items))

        if message is None and choice.strip().lower() == "q":
            console.print("[yellow]取消删除[/yellow]")
            return

        if message:
            if message == "请输入有效的序号":
                console.print(f"[red]❌ {message}[/red]")
            else:
                console.print(f"[yellow]⚠️  {message}[/yellow]")

        if selected_indices:
            break

    # 显示要删除的文件
    console.print("\n[yellow]📌 将删除以下文件：[/yellow]")
    delete_table = Table(show_header=True, header_style="bold red")
    delete_table.add_column("序号", style="magenta")
    delete_table.add_column("文件名", style="cyan")

    selected_items = []
    for idx in sorted(selected_indices):
        item = items[idx - 1]
        selected_items.append(item)
        delete_table.add_row(str(idx), item.get("original_name", ""))

    console.print(delete_table)

    # 最后确认
    if not Confirm.ask(f"\n[red]确认删除这 {len(selected_items)} 个文件？[/red]", default=False):
        console.print("[yellow]取消删除[/yellow]")
        return

    # 执行批量删除
    try:
        console.print("\n[cyan]🗑️  删除中...[/cyan]\n")
        file_uuids = [item.get("file_uuid", "") for item in selected_items]
        payload = {"file_uuids": file_uuids}

        response = requests.post(
            BATCH_DELETE_ENDPOINT,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            deleted = data.get("deleted", 0)
            total = data.get("total", 0)

            for idx, item in enumerate(items, 1):
                filename = item.get("original_name") or "未知文件"
                status = item.get("status", "failed")

                if status == "deleted":
                    console.print(f"[green]✅ [{idx}/{total}] {filename}[/green]")
                elif status == "not_found":
                    console.print(f"[yellow]⚠️  [{idx}/{total}] {filename} - 文件不存在[/yellow]")
                else:
                    detail = item.get("detail") or "删除失败"
                    console.print(f"[red]❌ [{idx}/{total}] {filename} - {detail}[/red]")

            console.print(f"\n[cyan]📊 删除总结[/cyan]")
            console.print(
                f"[green]✅ 成功：{deleted}[/green] | [yellow]⚠️  失败/不存在：{total - deleted}[/yellow]\n"
            )
        else:
            console.print(f"[red]❌ 批量删除失败 (HTTP {response.status_code})[/red]\n")
    except Exception as e:
        console.print(f"[red]❌ 删除出错：{e}[/red]\n")

def show_menu() -> None:
    """显示主菜单"""
    console.clear()

    title = Text("TCM PDF 文件管理工具", justify="center", style="bold cyan")
    subtitle = Text("上传、查看、批量删除 PDF 文件", justify="center", style="dim")
    console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style="cyan"))

    menu_text = """
[cyan]1[/cyan]  上传文件
[cyan]2[/cyan]  查看文件列表
[cyan]3[/cyan]  删除文件（支持多选）
[cyan]0[/cyan]  退出
"""
    console.print(Align(Panel.fit(menu_text, border_style="blue"), align="center"))


def main() -> None:
    """主函数"""
    if not check_service():
        console.print(
            "[red]❌ 服务不可用！[/red]\n"
            "请先启动服务：\n"
            "  [yellow]uvicorn data_process.pdf_upload.main:app --port 8001 --reload[/yellow]"
        )
        return

    while True:
        show_menu()
        choice = Prompt.ask("[cyan]请选择操作[/cyan]", choices=["0", "1", "2", "3"])

        if choice == "0":
            console.print("[yellow]👋 再见！[/yellow]\n")
            break
        elif choice == "1":
            console.print()
            upload_files()
        elif choice == "2":
            console.print()
            view_files()
        elif choice == "3":
            console.print()
            delete_files()

        Prompt.ask("\n[cyan]按 Enter 继续[/cyan]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]程序已中止[/yellow]")
        sys.exit(0)
