"""下載檔案歸檔與檔名清洗。"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from src.config import REPORT_FOLDERS

_INVALID = re.compile(r'[\\/:*?"<>|]+')


def sanitize_filename(name: str) -> str:
    cleaned = _INVALID.sub("_", name).strip().rstrip(".")
    return cleaned or "未命名"


def ensure_month_folders(base: Path, year_month: str) -> dict[str, Path]:
    root = base / year_month
    mapping: dict[str, Path] = {}
    for folder in REPORT_FOLDERS:
        p = root / folder
        p.mkdir(parents=True, exist_ok=True)
        mapping[folder] = p
    return mapping


def wait_new_file(directory: Path, before: set[str], timeout_sec: float = 120) -> Path:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        current = {p.name for p in directory.iterdir() if p.is_file()}
        new_names = current - before
        ready = [
            directory / n
            for n in new_names
            if not n.endswith(".crdownload")
            and not n.endswith(".tmp")
            and not n.endswith(".part")
        ]
        if ready:
            candidate = max(ready, key=lambda p: p.stat().st_mtime)
            size1 = candidate.stat().st_size
            time.sleep(0.6)
            if candidate.exists() and candidate.stat().st_size == size1 and size1 > 0:
                return candidate
        time.sleep(0.4)
    raise TimeoutError("等待下載檔案逾時")


def move_as_company_file(src: Path, dest_dir: Path, company_name: str, ext: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{sanitize_filename(company_name)}{ext}"
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return dest
