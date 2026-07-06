from pathlib import Path


def test_memory_module_is_placeholder_only():
    memory_dir = Path(__file__).resolve().parents[1] / "memory"

    assert (memory_dir / ".gitkeep").exists()
