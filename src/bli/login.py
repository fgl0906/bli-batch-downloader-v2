"""階段1：開頁 → 關公告 → 自然人憑證 → 檢測讀卡機 → 填表 → 登入成功。
允許由使用者在檢測前手動處理；檢測後不跳任何允許確認窗。
"""

from __future__ import annotations

import re
import time
from typing import Callable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.bli.popups import dismiss_all_popups, prepare_login_page
from src.config import BLI_HOME_URL


class LoginError(RuntimeError):
    pass


PauseCb = Callable[[str], bool]
LogCb = Callable[[str], None]


def _select_citizen_cert_tab(page: Page) -> bool:
    """精準點「自然人憑證」，不可命中「行動自然人憑證」。"""
    try:
        page.get_by_text("自然人憑證", exact=True).click(timeout=5000)
        return True
    except Exception:  # noqa: BLE001
        pass
    try:
        page.get_by_role("tab", name="自然人憑證", exact=True).click(timeout=3000)
        return True
    except Exception:  # noqa: BLE001
        pass
    try:
        loc = page.locator("div, button, a, span, li").filter(
            has_text=re.compile(r"^自然人憑證$")
        )
        if loc.count() > 0:
            loc.first.click(timeout=3000)
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _click_first(page: Page, selectors: list[str], timeout: int = 8000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.click(timeout=timeout)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _fill_first(page: Page, selectors: list[str], value: str) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.fill(value, timeout=3000)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _fill_by_label(page: Page, label_text: str, value: str) -> bool:
    try:
        loc = page.get_by_label(re.compile(label_text, re.I), exact=False).first
        if loc.count() > 0:
            loc.fill(value, timeout=3000)
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        row = page.locator(
            f"tr:has-text('{label_text}'), div:has-text('{label_text}')"
        ).first
        inp = row.locator("input").first
        if inp.count() > 0:
            inp.fill(value, timeout=3000)
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _is_logged_in(page: Page) -> bool:
    try:
        post_markers = [
            "網路申辦作業注意事項",
            "歡迎來到新手導覽",
            "略過導覽",
            "資料查詢作業",
            "電子帳單",
            "登出",
        ]
        if any(page.locator(f"text={m}").count() > 0 for m in post_markers):
            return True
        still_login = page.locator("text=投保單位登入").count() > 0 and (
            page.locator("text=檢測讀卡機").count() > 0
            or page.locator("button:has-text('送出')").count() > 0
        )
        if still_login:
            return False
    except Exception:  # noqa: BLE001
        return False
    return False


def login_with_citizen_cert(
    page: Page,
    national_id: str,
    insurance_id: str,
    pin: str,
    pause_cb: PauseCb | None = None,
    log_cb: LogCb | None = None,
    stop=None,
) -> None:
    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    def chk() -> None:
        if stop is not None:
            stop.check()

    chk()
    page.goto(BLI_HOME_URL, wait_until="domcontentloaded")
    time.sleep(0.8)
    log("開啟勞保局網站")
    chk()

    if not _click_first(
        page,
        [
            "text=投保單位網路申報及查詢作業",
            "a:has-text('投保單位網路申報及查詢作業')",
            "text=網路申報及查詢作業",
        ],
        timeout=8000,
    ):
        raise LoginError("找不到「投保單位網路申報及查詢作業」連結")
    log("進入投保單位登入")
    time.sleep(1.2)

    status = prepare_login_page(page)
    log(f"關閉公告：{status}")
    if status == "blocked":
        msg = (
            "無法自動關閉登入前「公告」。\n"
            "請手動關閉後按「確定」繼續；按「取消」中止。"
        )
        if pause_cb and pause_cb(msg):
            prepare_login_page(page)
        else:
            raise LoginError("登入前公告未關閉（已中止）")

    if not _select_citizen_cert_tab(page):
        raise LoginError("找不到精準的「自然人憑證」分頁")
    log("已選擇：自然人憑證")
    time.sleep(0.5)

    if not _click_first(
        page,
        [
            "text=檢測讀卡機",
            "button:has-text('檢測讀卡機')",
            "a:has-text('檢測讀卡機')",
            "input[value='檢測讀卡機']",
        ],
        timeout=5000,
    ):
        raise LoginError("找不到「檢測讀卡機」按鈕")
    log("已點擊：檢測讀卡機")
    time.sleep(0.8)
    # 允許由使用者在「檢測讀卡機」之前手動處理；檢測後不跳任何確認窗

    time.sleep(0.4)
    if not _select_citizen_cert_tab(page):
        raise LoginError("填表前無法切回精準的「自然人憑證」分頁")
    log("填表前已確認：自然人憑證")
    time.sleep(0.3)

    if not _fill_first(
        page,
        [
            "input[placeholder*='身分證']",
            "input[placeholder='請輸入身分證號']",
            "label:has-text('身分證號') + input",
        ],
        national_id,
    ):
        if not _fill_by_label(page, "身分證號", national_id):
            raise LoginError("找不到「身分證號」輸入欄")
    log("已填入身分證號")

    if not _fill_first(
        page,
        [
            "input[placeholder*='檢查碼']",
            "input[placeholder*='9位']",
            "input[placeholder*='保險證號']",
        ],
        insurance_id,
    ):
        if not _fill_by_label(page, "保險證號", insurance_id):
            raise LoginError("找不到「保險證號」輸入欄（無法帶入）")
    log(f"已填入保險證號：{insurance_id}")

    if not _fill_first(
        page,
        [
            "input[placeholder*='6-8']",
            "input[placeholder*='密碼']",
            "input[type='password']",
        ],
        pin,
    ):
        if not _fill_by_label(page, "自然人憑證密碼", pin):
            if not _fill_by_label(page, "pin", pin):
                raise LoginError("找不到「自然人憑證密碼」輸入欄（無法帶入）")
    log("已填入憑證密碼")

    if not _click_first(
        page,
        [
            "button:has-text('送出')",
            "input[value='送出']",
            "a:has-text('送出')",
            "text=送出",
        ],
        timeout=5000,
    ):
        raise LoginError("找不到「送出」按鈕")
    log("已送出登入（若有系統憑證窗請手動確認）")

    deadline = time.time() + 180
    while time.time() < deadline:
        chk()
        try:
            dismiss_all_popups(page, rounds=1)
        except Exception:  # noqa: BLE001
            pass
        if _is_logged_in(page):
            log("登入成功")
            dismiss_all_popups(page, rounds=2)
            return
        time.sleep(1.0)

    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeout:
        pass

    if not _is_logged_in(page):
        raise LoginError("等待登入成功逾時")
    log("登入成功")
    dismiss_all_popups(page, rounds=2)
