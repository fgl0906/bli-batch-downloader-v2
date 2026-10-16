"""失敗日誌。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class FailureRecord:
    company_id: str
    company_name: str
    stage: str
    reason: str
    year_month: str = ""


@dataclass
class RunSummary:
    success_companies: list[str] = field(default_factory=list)
    partial_companies: list[str] = field(default_factory=list)
    failed_companies: list[str] = field(default_factory=list)
    skipped_count: int = 0
    failures: list[FailureRecord] = field(default_factory=list)
    log_path: Path | None = None


class FailureLogger:
    def __init__(self, logs_dir: Path) -> None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = logs_dir / f"failures_{stamp}.txt"
        self.path.write_text(
            f"# 失敗日誌 {stamp}\n# 時間|年月|證號|公司|階段|原因\n",
            encoding="utf-8",
        )

    def write(self, rec: FailureRecord) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"{now}|{rec.year_month}|{rec.company_id}|{rec.company_name}|"
            f"{rec.stage}|{rec.reason}\n"
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)
