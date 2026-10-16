"""登入前／登入後需關閉的遮擋視窗（軟處理：回傳狀態，不隨意丟例外）。"""

from __future__ import annotations

import time

from playwright.sync_api import Page


class PopupError(RuntimeError):
    pass


def _visible_text(page: Page, text: str) -> bool:
    try:
        return page.get_by_text(text, exact=False).count() > 0
    except Exception:  # noqa: BLE001
        return False


def _submit_ready(page: Page) -> bool:
    try:
        loc = page.locator("button:has-text('送出'), input[value='送出']").first
        return loc.count() > 0 and loc.is_visible()
    except Exception:  # noqa: BLE001
        return False


def permission_dialog_present(page: Page, wait_sec: float = 3.5) -> bool:
    """方案 C：偵測權限泡泡是否出現（不點擊）。"""
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        try:
            if _visible_text(page, "要求下列權限") or _visible_text(
                page, "其他應用程式和服務"
            ):
                return True
        except Exception:  # noqa: BLE001
            pass
        if _permission_present_via_uia():
            return True
        time.sleep(0.3)
    return False


def _permission_present_via_uia() -> bool:
    try:
        from pywinauto import Desktop  # type: ignore
    except Exception:  # noqa: BLE001
        return False
    keywords = (
        "要求下列權限",
        "其他應用程式和服務",
        "edesk.bli.gov.tw",
        "存取這部裝置",
    )
    try:
        desk = Desktop(backend="uia")
        for w in desk.windows():
            blob = ""
            try:
                blob = w.window_text() or ""
            except Exception:  # noqa: BLE001
                pass
            try:
                for d in w.descendants():
                    try:
                        t = (d.window_text() or "").strip()
                        if t:
                            blob += "\n" + t
                    except Exception:  # noqa: BLE001
                        continue
                    if len(blob) > 3000:
                        break
            except Exception:  # noqa: BLE001
                pass
            if any(k in blob for k in keywords):
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def dismiss_browser_permission_allow(page: Page, wait_sec: float = 8.0) -> str:
    """權限窗 → 點「允許」。回傳 clicked / absent / failed。"""
    deadline = time.time() + wait_sec
    saw_any = False
    while time.time() < deadline:
        try:
            if _visible_text(page, "要求下列權限") or _visible_text(
                page, "其他應用程式和服務"
            ):
                saw_any = True
                for sel in [
                    "button:has-text('允許')",
                    "[role='button']:has-text('允許')",
                    "text=允許",
                ]:
                    try:
                        loc = page.locator(sel).first
                        if loc.count() > 0 and loc.is_visible():
                            loc.click(timeout=2000)
                            time.sleep(0.5)
                            return "clicked"
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass

        uia = _click_allow_via_uia()
        if uia is True:
            return "clicked"
        if uia is None:
            saw_any = True

        if _click_allow_via_screen():
            return "clicked"

        if _click_allow_top_left_only():
            pass

        time.sleep(0.25)

    if saw_any:
        return "failed"
    return "absent"


def _click_allow_via_uia() -> bool | None:
    try:
        from pywinauto import Desktop  # type: ignore
    except Exception:  # noqa: BLE001
        return False

    keywords = (
        "要求下列權限",
        "其他應用程式和服務",
        "edesk.bli.gov.tw",
        "存取這部裝置",
    )
    found_related = False
    try:
        desk = Desktop(backend="uia")
        for w in desk.windows():
            blob = ""
            try:
                blob = w.window_text() or ""
            except Exception:  # noqa: BLE001
                pass
            try:
                for d in w.descendants():
                    try:
                        t = (d.window_text() or "").strip()
                        if t:
                            blob += "\n" + t
                    except Exception:  # noqa: BLE001
                        continue
                    if len(blob) > 5000:
                        break
            except Exception:  # noqa: BLE001
                pass

            if not any(k in blob for k in keywords):
                continue
            found_related = True

            try:
                for b in w.descendants(control_type="Button"):
                    try:
                        name = (b.window_text() or "").strip()
                    except Exception:  # noqa: BLE001
                        continue
                    if name == "允許":
                        b.set_focus()
                        b.click_input()
                        time.sleep(0.5)
                        return True
            except Exception:  # noqa: BLE001
                pass
            try:
                btn = w.child_window(title="允許", control_type="Button")
                if btn.exists(timeout=0.3):
                    btn.click_input()
                    time.sleep(0.5)
                    return True
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        return False

    if found_related:
        return None
    return False


def _click_allow_via_screen() -> bool:
    try:
        import pyautogui  # type: ignore
        from pathlib import Path
    except Exception:  # noqa: BLE001
        return False

    try:
        root = Path(__file__).resolve().parents[2]
        for name in ("allow_btn.png", "允許.png"):
            img = root / name
            if not img.exists():
                continue
            w, h = pyautogui.size()
            region = (0, 0, max(1, int(w * 0.45)), max(1, int(h * 0.40)))
            pos = pyautogui.locateCenterOnScreen(
                str(img), confidence=0.8, region=region
            )
            if pos:
                pyautogui.click(pos)
                time.sleep(0.4)
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _click_allow_top_left_only() -> bool:
    try:
        import pyautogui  # type: ignore
    except Exception:  # noqa: BLE001
        return False

    try:
        pyautogui.FAILSAFE = True
        left, top, win_w, win_h = _chrome_window_rect()
        if win_w > 0 and win_h > 0:
            candidates = [
                (left + int(win_w * 0.16), top + int(win_h * 0.18)),
                (left + int(win_w * 0.14), top + int(win_h * 0.20)),
                (left + int(win_w * 0.18), top + int(win_h * 0.17)),
            ]
        else:
            sw, sh = pyautogui.size()
            candidates = [
                (int(sw * 0.14), int(sh * 0.16)),
                (int(sw * 0.12), int(sh * 0.18)),
            ]

        sw, sh = pyautogui.size()
        for x, y in candidates:
            if x > sw * 0.40 or y > sh * 0.35:
                continue
            pyautogui.click(x, y)
            time.sleep(0.2)
        return True
    except Exception:  # noqa: BLE001
        return False


def _chrome_window_rect() -> tuple[int, int, int, int]:
    try:
        from pywinauto import Desktop  # type: ignore
    except Exception:  # noqa: BLE001
        return (0, 0, 0, 0)

    try:
        desk = Desktop(backend="uia")
        for w in desk.windows():
            try:
                title = (w.window_text() or "").lower()
            except Exception:  # noqa: BLE001
                continue
            raw = w.window_text() or ""
            if "chrome" not in title and "edesk" not in title and "勞保" not in raw:
                continue
            try:
                rect = w.rectangle()
                return (
                    int(rect.left),
                    int(rect.top),
                    int(rect.width()),
                    int(rect.height()),
                )
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return (0, 0, 0, 0)


def _announcement_modal_visible(page: Page) -> bool:
    try:
        dialogs = page.locator(
            "[role='dialog']:has-text('公告'), "
            "[class*='modal' i]:has-text('公告'), "
            "[class*='dialog' i]:has-text('公告')"
        )
        if dialogs.count() > 0 and dialogs.first.is_visible():
            return True
        if _visible_text(page, "最新") and page.locator("text=公告").count() > 0:
            if not _submit_ready(page):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def close_announcement_dialog(page: Page, wait_sec: float = 6.0) -> str:
    deadline = time.time() + wait_sec
    appeared = False
    while time.time() < deadline:
        if _announcement_modal_visible(page):
            appeared = True
            break
        time.sleep(0.35)

    if not appeared:
        return "absent"

    close_selectors = [
        "[role='dialog']:has-text('公告') button >> nth=0",
        "[class*='modal' i]:has-text('公告') button >> nth=0",
        "[class*='dialog' i]:has-text('公告') button >> nth=0",
        "[role='dialog']:has-text('公告') [aria-label*='關閉']",
        "[role='dialog']:has-text('公告') [aria-label*='Close']",
        "button:has-text('×')",
        "button:has-text('✕')",
        "[aria-label='Close']",
        "[aria-label='關閉']",
    ]
    for sel in close_selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.click(timeout=2500)
            time.sleep(0.6)
            if not _announcement_modal_visible(page) or _submit_ready(page):
                return "closed"
        except Exception:  # noqa: BLE001
            continue

    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
        if not _announcement_modal_visible(page) or _submit_ready(page):
            return "closed"
    except Exception:  # noqa: BLE001
        pass

    return "failed"


def _notice_visible(page: Page) -> bool:
    """注意事項是否仍可見（不以 DOM count 判斷，避免隱藏殘留誤判）。"""
    try:
        loc = page.get_by_text("網路申辦作業注意事項", exact=False)
        n = loc.count()
        for i in range(min(n, 8)):
            try:
                if loc.nth(i).is_visible():
                    return True
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return False


def _click_visible(page: Page, selectors: list[str], timeout: int = 2500) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel)
            n = loc.count()
            for i in range(min(n, 12)):
                item = loc.nth(i)
                try:
                    if not item.is_visible():
                        continue
                    item.click(timeout=timeout)
                    return True
                except Exception:  # noqa: BLE001
                    try:
                        item.click(timeout=timeout, force=True)
                        return True
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            continue
    return False


def close_notice_dialog(page: Page, wait_sec: float = 8.0) -> str:
    """登入後「網路申辦作業注意事項」→ 確定／關閉／X。回傳 closed / absent / failed。"""
    deadline = time.time() + wait_sec
    appeared = False
    while time.time() < deadline:
        if _notice_visible(page):
            appeared = True
            break
        time.sleep(0.35)

    if not appeared:
        return "absent"

    # 先在含標題的可見容器內找按鈕，再退回全域可見按鈕
    scoped = [
        "[role='dialog']:has-text('網路申辦作業注意事項') button:has-text('確定')",
        "[role='dialog']:has-text('網路申辦作業注意事項') button:has-text('關閉')",
        "[class*='modal' i]:has-text('網路申辦作業注意事項') button:has-text('確定')",
        "[class*='modal' i]:has-text('網路申辦作業注意事項') button:has-text('關閉')",
        "[class*='dialog' i]:has-text('網路申辦作業注意事項') button:has-text('確定')",
        "[class*='dialog' i]:has-text('網路申辦作業注意事項') button:has-text('關閉')",
        "div:has-text('網路申辦作業注意事項') >> button:has-text('確定')",
        "div:has-text('網路申辦作業注意事項') >> button:has-text('關閉')",
        "div:has-text('網路申辦作業注意事項') >> input[value='確定']",
        "div:has-text('網路申辦作業注意事項') >> input[value='關閉']",
        "div:has-text('網路申辦作業注意事項') >> a:has-text('確定')",
        "div:has-text('網路申辦作業注意事項') >> a:has-text('關閉')",
        "div:has-text('網路申辦作業注意事項') >> button:has-text('×')",
        "div:has-text('網路申辦作業注意事項') >> button:has-text('✕')",
        "div:has-text('網路申辦作業注意事項') >> [aria-label*='關閉']",
        "div:has-text('網路申辦作業注意事項') >> [aria-label*='Close' i]",
        "div:has-text('網路申辦作業注意事項') >> .close",
    ]
    global_btns = [
        "button:has-text('確定')",
        "input[value='確定']",
        "a:has-text('確定')",
        "button:has-text('關閉')",
        "input[value='關閉']",
        "a:has-text('關閉')",
        "button:has-text('×')",
        "button:has-text('✕')",
    ]

    for _ in range(4):
        if not _notice_visible(page):
            return "closed"
        if _click_visible(page, scoped, timeout=3000):
            time.sleep(0.6)
            if not _notice_visible(page):
                return "closed"
            continue
        if _click_visible(page, global_btns, timeout=3000):
            time.sleep(0.6)
            if not _notice_visible(page):
                return "closed"
            continue
        break

    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
        if not _notice_visible(page):
            return "closed"
    except Exception:  # noqa: BLE001
        pass

    # 最後手段：JS 點擊可見「確定／關閉」
    try:
        clicked = page.evaluate(
            """() => {
              const title = [...document.querySelectorAll('*')]
                .find(el => (el.textContent || '').includes('網路申辦作業注意事項')
                      && el.offsetParent !== null);
              const root = title
                ? (title.closest('[role=dialog], .modal, .modal-dialog, .cdk-overlay-pane') || title.parentElement)
                : document.body;
              const texts = ['確定', '關閉', '×', '✕', 'X'];
              const nodes = root.querySelectorAll('button, a, input[type=button], input[type=submit]');
              for (const n of nodes) {
                const t = (n.value || n.innerText || n.textContent || '').trim();
                if (!texts.some(x => t === x || t.includes(x))) continue;
                const r = n.getBoundingClientRect();
                if (r.width < 1 || r.height < 1) continue;
                n.click();
                return true;
              }
              return false;
            }"""
        )
        time.sleep(0.6)
        if clicked and not _notice_visible(page):
            return "closed"
    except Exception:  # noqa: BLE001
        pass

    return "failed" if _notice_visible(page) else "closed"


def dismiss_blocking_overlays(page: Page) -> None:
    """下載／選單前再清一次遮擋（相容舊呼叫名）。"""
    dismiss_all_popups(page, rounds=2)


def dismiss_all_popups(page: Page, rounds: int = 3) -> int:
    """
    全程通用：立即關閉各分頁可能跳出的遮擋彈窗。
    不處理／不點瀏覽器「允許／封鎖」權限泡泡（由使用者在檢測讀卡機前手動處理）。
    回傳大約關閉次數。
    """
    closed = 0
    for _ in range(max(1, rounds)):
        did = False

        # 1) 已知專用視窗
        try:
            if _announcement_modal_visible(page):
                if close_announcement_dialog(page, wait_sec=1.5) in ("closed", "ok"):
                    closed += 1
                    did = True
        except Exception:  # noqa: BLE001
            pass

        try:
            if _notice_visible(page):
                if close_notice_dialog(page, wait_sec=1.5) == "closed":
                    closed += 1
                    did = True
        except Exception:  # noqa: BLE001
            pass

        try:
            if _visible_text(page, "歡迎來到新手導覽") or _visible_text(page, "略過導覽"):
                if skip_newbie_guide(page, wait_sec=1.5) == "skipped":
                    closed += 1
                    did = True
        except Exception:  # noqa: BLE001
            pass

        # 2) 通用 modal／dialog：點安全關閉鈕
        if _close_generic_modals(page):
            closed += 1
            did = True

        # 3) Escape 備援（不影響允許泡泡）
        if did:
            time.sleep(0.25)
            continue
        try:
            if _any_modal_like(page):
                page.keyboard.press("Escape")
                time.sleep(0.3)
                closed += 1
        except Exception:  # noqa: BLE001
            pass
        break

    return closed


_SAFE_CLOSE_TEXTS = (
    "確定",
    "關閉",
    "我知道了",
    "知道了",
    "略過導覽",
    "稍後",
    "×",
    "✕",
    "X",
)

# 絕對不要當「關窗」去點的字（含權限允許、主要業務按鈕）
_NEVER_CLICK_TEXTS = (
    "允許",
    "封鎖",
    "送出",
    "開始導覽",
    "查詢",
    "下載",
    "檢測讀卡機",
    "登出",
)


def _any_modal_like(page: Page) -> bool:
    try:
        for sel in (
            "[role='dialog']",
            ".modal.show",
            ".modal.in",
            "[class*='modal' i][class*='show' i]",
            ".cdk-overlay-pane",
            ".ngx-spinner-overlay",
            "[class*='overlay' i]",
        ):
            loc = page.locator(sel)
            for i in range(min(loc.count(), 6)):
                try:
                    if loc.nth(i).is_visible():
                        return True
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        return False
    return False


def _close_generic_modals(page: Page) -> bool:
    """關閉可見 dialog／modal；略過「允許／封鎖／送出／下載」等危險按鈕。"""
    containers = page.locator(
        "[role='dialog'], "
        ".modal.show, .modal.in, "
        "[class*='modal' i][class*='show' i], "
        ".cdk-overlay-pane, "
        "[class*='dialog' i]"
    )
    try:
        n = containers.count()
    except Exception:  # noqa: BLE001
        return False

    for i in range(min(n, 8)):
        box = containers.nth(i)
        try:
            if not box.is_visible():
                continue
        except Exception:  # noqa: BLE001
            continue

        # 權限相關字樣：不要動（留給使用者手動允許）
        try:
            blob = (box.inner_text(timeout=800) or "")[:800]
        except Exception:  # noqa: BLE001
            blob = ""
        if any(
            k in blob
            for k in ("要求下列權限", "其他應用程式和服務", "存取這部裝置")
        ):
            continue

        # 先試關閉圖示
        for sel in (
            "button.close",
            "[aria-label*='關閉']",
            "[aria-label*='Close' i]",
            ".close",
            "button:has-text('×')",
            "button:has-text('✕')",
        ):
            try:
                btn = box.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=1500, force=True)
                    time.sleep(0.25)
                    return True
            except Exception:  # noqa: BLE001
                continue

        # 再試安全文字按鈕
        try:
            btns = box.locator("button, a, input[type='button'], input[type='submit']")
            for j in range(min(btns.count(), 20)):
                b = btns.nth(j)
                try:
                    if not b.is_visible():
                        continue
                    label = (
                        (b.inner_text(timeout=500) or "")
                        or (b.get_attribute("value") or "")
                        or (b.get_attribute("aria-label") or "")
                    ).strip()
                except Exception:  # noqa: BLE001
                    continue
                if not label:
                    continue
                if any(bad in label for bad in _NEVER_CLICK_TEXTS):
                    continue
                if label in _SAFE_CLOSE_TEXTS or any(
                    t == label or label.startswith(t) for t in ("確定", "關閉", "我知道了", "知道了", "略過")
                ):
                    try:
                        b.click(timeout=1500, force=True)
                        time.sleep(0.25)
                        return True
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            continue

    # 頁面層級：可見「略過導覽／我知道了」等（不在 dialog 容器內時）
    for text in ("略過導覽", "我知道了", "知道了"):
        try:
            loc = page.get_by_text(text, exact=True)
            for j in range(min(loc.count(), 4)):
                item = loc.nth(j)
                if item.is_visible():
                    item.click(timeout=1500, force=True)
                    time.sleep(0.25)
                    return True
        except Exception:  # noqa: BLE001
            continue

    return False


def skip_newbie_guide(page: Page, wait_sec: float = 8.0) -> str:
    deadline = time.time() + wait_sec
    appeared = False
    while time.time() < deadline:
        if _visible_text(page, "歡迎來到新手導覽") or _visible_text(page, "略過導覽"):
            appeared = True
            break
        time.sleep(0.4)

    if not appeared:
        return "absent"

    try:
        cb = page.get_by_text("下一次不顯示", exact=False).first
        if cb.count() > 0:
            cb.click(timeout=1500)
            time.sleep(0.2)
    except Exception:  # noqa: BLE001
        pass

    for sel in [
        "text=略過導覽",
        "button:has-text('略過導覽')",
        "a:has-text('略過導覽')",
        "[role='button']:has-text('略過導覽')",
    ]:
        try:
            page.locator(sel).first.click(timeout=3000)
            time.sleep(0.6)
            if page.get_by_text("歡迎來到新手導覽").count() == 0:
                return "skipped"
            if page.get_by_text("略過導覽").count() == 0:
                return "skipped"
        except Exception:  # noqa: BLE001
            continue

    for sel in [
        "div:has-text('歡迎來到新手導覽') button:has-text('×')",
        "div:has-text('新手導覽') [aria-label='Close']",
        "button:has-text('×')",
    ]:
        try:
            page.locator(sel).first.click(timeout=2000)
            time.sleep(0.5)
            if page.get_by_text("歡迎來到新手導覽").count() == 0:
                return "skipped"
        except Exception:  # noqa: BLE001
            continue

    return "failed"


def prepare_login_page(page: Page) -> str:
    """登入頁：只關公告。"""
    ann = close_announcement_dialog(page)
    if _submit_ready(page) and not _announcement_modal_visible(page):
        return "ok"
    if ann == "failed" or _announcement_modal_visible(page):
        return "blocked"
    return "ok_partial"


def after_detect_card_reader(page: Page, wait_sec: float = 3.0) -> str:
    """輔助自動點左上「允許」。"""
    return dismiss_browser_permission_allow(page, wait_sec=wait_sec)
