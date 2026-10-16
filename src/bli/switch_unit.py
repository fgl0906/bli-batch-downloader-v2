"""切換投保單位：右上人物圖示 → 選保險證號 → 確定 → 回讀確認。"""

from __future__ import annotations

import time

from playwright.sync_api import Page


class SwitchUnitError(RuntimeError):
    pass


def switch_unit(page: Page, insurance_id: str, company_name: str = "") -> None:
    from src.bli.popups import dismiss_all_popups

    dismiss_all_popups(page, rounds=2)
    opened = False
    for sel in [
        "header button",
        "[class*='avatar' i]",
        "[class*='user' i]",
        "button:has(img)",
        "a:has(img)",
        "text=切換",
    ]:
        try:
            loc = page.locator(sel)
            count = loc.count()
            for i in range(min(count, 8)):
                item = loc.nth(i)
                box = item.bounding_box()
                if not box:
                    continue
                if box["x"] > 700 and box["y"] < 120:
                    item.click(timeout=3_000)
                    time.sleep(0.6)
                    if page.get_by_text("保險證號").count() > 0:
                        opened = True
                        break
            if opened:
                break
        except Exception:  # noqa: BLE001
            continue

    if not opened:
        try:
            page.get_by_text("請選擇").first.click(timeout=3_000)
            opened = True
        except Exception as exc:  # noqa: BLE001
            raise SwitchUnitError(f"無法開啟切換單位畫面：{exc}") from exc

    selected = False
    try:
        selects = page.locator("select")
        for i in range(selects.count()):
            sel = selects.nth(i)
            options = sel.locator("option")
            for j in range(options.count()):
                opt = options.nth(j)
                text = (opt.inner_text() or "").strip()
                value = (opt.get_attribute("value") or "").strip()
                if text == insurance_id or value == insurance_id:
                    sel.select_option(value=value if value else text)
                    selected = True
                    break
            if selected:
                break
    except Exception:  # noqa: BLE001
        pass

    if not selected:
        try:
            page.get_by_text("請選擇").first.click(timeout=3_000)
            time.sleep(0.3)
        except Exception:  # noqa: BLE001
            pass
        exact = page.get_by_text(insurance_id, exact=True)
        if exact.count() == 0:
            raise SwitchUnitError(f"下拉找不到完全吻合的保險證號：{insurance_id}")
        exact.first.click()
        selected = True

    clicked_ok = False
    for sel in [
        "button:has-text('確定')",
        "input[value='確定']",
        "a:has-text('確定')",
        "text=確定",
    ]:
        try:
            page.locator(sel).first.click(timeout=5_000)
            clicked_ok = True
            break
        except Exception:  # noqa: BLE001
            continue
    if not clicked_ok:
        raise SwitchUnitError("找不到切換單位的「確定」按鈕")

    time.sleep(1.0)
    if insurance_id not in page.content():
        raise SwitchUnitError(f"切換後頁面未出現保險證號（不完全吻合）：{insurance_id}")
    dismiss_all_popups(page, rounds=2)
