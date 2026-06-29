from data_process.ragflow_sync.main import summarize_results
from data_process.ragflow_sync.main import validate_dataset_ids
from data_process.ragflow_sync.models import SyncResult


def test_summarize_results_counts_actions():
    results = [
        SyncResult("literature", "a", "parsed"),
        SyncResult("literature", "b", "parsed"),
        SyncResult("case", "c", "uploaded"),
        SyncResult("case", "d", "failed"),
        SyncResult("case", "e", "skipped"),
    ]

    summary = summarize_results(results)

    assert summary == {"uploaded": 1, "parsed": 2, "skipped": 1, "failed": 1}


def test_validate_dataset_ids_checks_selected_source_only():
    dataset_ids = {
        "literature": "lit-dataset",
        "case": "",
        "guideline": "guide-dataset",
    }

    assert validate_dataset_ids("literature", dataset_ids) == []
    assert validate_dataset_ids("case", dataset_ids) == ["case"]
    assert validate_dataset_ids("all", dataset_ids) == ["case"]
    assert validate_dataset_ids("guideline", dataset_ids) == []
