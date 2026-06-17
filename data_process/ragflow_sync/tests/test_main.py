from data_process.ragflow_sync.main import summarize_results
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
