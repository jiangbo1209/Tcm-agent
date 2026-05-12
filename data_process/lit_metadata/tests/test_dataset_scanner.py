from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.dataset_scanner import DatasetScanner


def test_recursive_scan_pdf(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    nested = dataset / "a" / "b"
    nested.mkdir(parents=True)
    pdf = nested / "论文标题.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    scanner = DatasetScanner(SimpleNamespace(DATASET_DIR=str(dataset)))
    files = scanner.scan()

    assert len(files) == 1
    assert files[0].file_name == "论文标题.pdf"
    assert files[0].suffix == ".pdf"


def test_ignore_non_pdf_files(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "论文标题.pdf").write_bytes(b"%PDF-1.4")
    (dataset / "notes.txt").write_text("not pdf", encoding="utf-8")

    files = DatasetScanner(SimpleNamespace(DATASET_DIR=str(dataset))).scan()

    assert [file.file_name for file in files] == ["论文标题.pdf"]


def test_ignore_hidden_files(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    hidden_dir = dataset / ".hidden"
    hidden_dir.mkdir(parents=True)
    (dataset / ".secret.pdf").write_bytes(b"%PDF-1.4")
    (hidden_dir / "论文标题.pdf").write_bytes(b"%PDF-1.4")

    files = DatasetScanner(SimpleNamespace(DATASET_DIR=str(dataset))).scan()

    assert files == []


def test_ignore_temporary_files(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "~$temp.pdf").write_bytes(b"%PDF-1.4")
    (dataset / "normal.pdf").write_bytes(b"%PDF-1.4")

    files = DatasetScanner(SimpleNamespace(DATASET_DIR=str(dataset))).scan()

    assert [file.file_name for file in files] == ["normal.pdf"]


def test_scan_does_not_read_pdf_content(tmp_path: Path, monkeypatch) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "论文标题.pdf").write_bytes(b"this should not be read")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("PDF content should not be read")

    monkeypatch.setattr(Path, "read_bytes", fail_if_called)
    monkeypatch.setattr(Path, "read_text", fail_if_called)

    files = DatasetScanner(SimpleNamespace(DATASET_DIR=str(dataset))).scan()

    assert len(files) == 1
    assert files[0].file_name == "论文标题.pdf"
