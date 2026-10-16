"""讀取 companies.txt（唯讀，永不寫回）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Company:
    insurance_id: str
    name: str


def load_companies(path: Path) -> list[Company]:
    if not path.exists():
        raise FileNotFoundError(f"找不到清單檔：{path}")

    companies: list[Company] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            _, line = line.split("|", 1)
            line = line.strip()
        if "-" not in line:
            raise ValueError(f"清單格式錯誤（需 保險證號-公司名稱）：{raw}")
        insurance_id, name = line.split("-", 1)
        insurance_id = insurance_id.strip()
        name = name.strip()
        if not insurance_id or not name:
            raise ValueError(f"清單欄位空白：{raw}")
        companies.append(Company(insurance_id=insurance_id, name=name))

    if not companies:
        raise ValueError("清單沒有任何有效公司列")
    return companies
