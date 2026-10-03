from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


AUTODEV_JSON_FILES = (
    "autonomous_diagnostics.json",
    "autonomous_learning.json",
    "autonomy_governance_b62_b68.json",
    "change_campaigns.json",
    "full_autonomy_runs.json",
    "long_running_autonomy.json",
    "multi_campaign_portfolios.json",
    "multi_file_feature_runs.json",
    "portfolio_director_runs.json",
    "project_intelligence.json",
    "self_directed_development.json",
    "strategic_development.json",
    "strategic_execution.json",
    "strategic_policy_evolution.json",
    "strategic_policy_validation.json",
    "strategic_portfolio.json",
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def compact_autodev_json(
    project_root: str | Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    data_root = (root / "data" / "autodev").resolve(strict=False)
    results: list[dict[str, Any]] = []
    saved_bytes = 0

    for filename in AUTODEV_JSON_FILES:
        path = (data_root / filename).resolve(strict=False)
        path.relative_to(data_root)
        if not path.is_file():
            continue
        source = path.read_bytes()
        source_digest = _digest(source)
        payload = json.loads(source.decode("utf-8"))
        compact = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        potential = max(0, len(source) - len(compact))
        status = "WOULD_COMPACT" if potential else "ALREADY_COMPACT"

        if apply and potential:
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=data_root,
                    prefix=f".{filename}.",
                    suffix=".compact.tmp",
                    delete=False,
                ) as stream:
                    temporary_path = Path(stream.name)
                    stream.write(compact)
                    stream.flush()
                    os.fsync(stream.fileno())
                candidate = json.loads(temporary_path.read_text(encoding="utf-8"))
                if _canonical(candidate) != _canonical(payload):
                    raise ValueError(f"Weryfikacja semantyczna nie powiodła się: {filename}")
                if _digest(path.read_bytes()) != source_digest:
                    status = "SKIPPED_CHANGED_DURING_SCAN"
                else:
                    os.replace(temporary_path, path)
                    temporary_path = None
                    status = "COMPACTED"
                    saved_bytes += potential
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

        results.append({
            "file": filename,
            "status": status,
            "before_bytes": len(source),
            "after_bytes": len(compact) if potential else len(source),
            "saved_bytes": potential if status == "COMPACTED" else 0,
        })

    return {
        "applied": bool(apply),
        "files": results,
        "saved_bytes": saved_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bezpieczna kompakcja aktywnych magazynów AutoDev JARVIS OS.",
    )
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    result = compact_autodev_json(arguments.project_root, apply=arguments.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
