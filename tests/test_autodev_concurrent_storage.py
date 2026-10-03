from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.ai.software_engineer.full_autonomy_store import FullAutonomyStore
from app.ai.software_engineer.multi_file_run_store import MultiFileRunStore


def test_full_autonomy_store_keeps_parallel_runs(tmp_path) -> None:
    stores = [FullAutonomyStore(tmp_path, max_records=50) for _ in range(8)]

    def save(index: int) -> None:
        stores[index % len(stores)].save({
            "run_id": f"full-{index}",
            "status": "COMPLETED",
        })

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(40)))

    recent = FullAutonomyStore(tmp_path, max_records=50).list_recent(limit=50)
    assert {item["run_id"] for item in recent} == {
        f"full-{index}" for index in range(40)
    }


def test_multi_file_store_keeps_parallel_runs(tmp_path) -> None:
    stores = [MultiFileRunStore(tmp_path, max_records=50) for _ in range(8)]

    def save(index: int) -> None:
        stores[index % len(stores)].save({
            "run_id": f"multi-{index}",
            "status": "COMPLETED",
        })

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(40)))

    recent = MultiFileRunStore(tmp_path, max_records=50).list_recent(limit=50)
    assert {item["run_id"] for item in recent} == {
        f"multi-{index}" for index in range(40)
    }
