"""登入後視窗（相容舊 import）。"""

from __future__ import annotations

from src.bli.popups import PopupError, close_notice_dialog, skip_newbie_guide

NoticeCloseError = PopupError

__all__ = [
    "NoticeCloseError",
    "PopupError",
    "close_notice_dialog",
    "skip_newbie_guide",
]
