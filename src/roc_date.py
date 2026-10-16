"""西元／民國年月換算。"""

from __future__ import annotations


def to_roc_year_month(year: int, month: int) -> tuple[int, int]:
    if month < 1 or month > 12:
        raise ValueError(f"月份無效：{month}")
    return year - 1911, month


def format_ym_folder(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def roc_year_label(roc_year: int) -> str:
    return f"{roc_year}年"


def roc_month_label(month: int) -> str:
    return f"{month:02d}月"


def roc_month_label_short(month: int) -> str:
    return f"{month}月"


def roc_ym_combined(year: int, month: int) -> str:
    """網站查詢年月下拉常見格式：115年08月。"""
    roc_y, roc_m = to_roc_year_month(year, month)
    return f"{roc_y}年{roc_m:02d}月"


def roc_ym_combined_variants(year: int, month: int) -> list[str]:
    roc_y, roc_m = to_roc_year_month(year, month)
    return [
        f"{roc_y}年{roc_m:02d}月",
        f"{roc_y}年{roc_m}月",
        f"民國{roc_y}年{roc_m:02d}月",
    ]

