"""報表下載流程（目前除錯重點：勞保名冊）。"""

from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import Download, Page

from src.file_manager import move_as_company_file
from src.roc_date import roc_ym_combined, roc_ym_combined_variants, to_roc_year_month


class DownloadItemError(RuntimeError):
    pass


_YM_RE = re.compile(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月")


def _is_deferred_message(text: str) -> bool:
    keys = ("翌日", "隔日", "次日", "2000", "申請後", "翌日下載", "隔日下載")
    return any(k in text for k in keys)


def _quick_dismiss(page: Page) -> None:
    from src.bli.popups import dismiss_all_popups

    dismiss_all_popups(page, rounds=1)


def _wait_visible_click(page: Page, texts: list[str], timeout_ms: int = 8_000) -> None:
    """等文字出現就點可見節點；取代長 sleep。"""
    last: Exception | None = None
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for t in texts:
            try:
                loc = page.get_by_text(t, exact=False)
                n = loc.count()
                for i in range(n):
                    item = loc.nth(i)
                    try:
                        if not item.is_visible():
                            continue
                        item.click(timeout=2_000)
                        _quick_dismiss(page)
                        return
                    except Exception as exc:  # noqa: BLE001
                        last = exc
                menu = page.locator(".menu-item, [class*='menu']").filter(has_text=t)
                for i in range(menu.count()):
                    item = menu.nth(i)
                    try:
                        if not item.is_visible():
                            continue
                        item.click(timeout=2_000)
                        _quick_dismiss(page)
                        return
                    except Exception as exc:  # noqa: BLE001
                        last = exc
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(0.12)
    raise DownloadItemError(f"選單點擊失敗：{texts}（{last}）")


def _click_menu(page: Page, texts: list[str]) -> None:
    _quick_dismiss(page)
    _wait_visible_click(page, texts, timeout_ms=8_000)


def _normalize_ym_text(text: str) -> str | None:
    m = _YM_RE.search((text or "").replace(" ", ""))
    if not m:
        return None
    return f"{int(m.group(1))}年{int(m.group(2)):02d}月"


def _ensure_query_ym_radio(page: Page) -> None:
    """確保「查詢年月」第一個可見 radio 已選。"""
    try:
        radios = page.locator("input[type='radio']")
        for i in range(min(radios.count(), 6)):
            r = radios.nth(i)
            try:
                if not r.is_visible():
                    continue
                if r.is_checked():
                    return
            except Exception:  # noqa: BLE001
                continue
        for i in range(min(radios.count(), 3)):
            r = radios.nth(i)
            try:
                if r.is_visible():
                    r.check(timeout=1_500)
                    return
            except Exception:  # noqa: BLE001
                try:
                    r.click(timeout=1_500, force=True)
                    return
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass


def _find_ym_controls(page: Page) -> list:
    """找出顯示『xxx年xx月』的可見控制（下拉／select／combobox）。"""
    found: list[tuple[str, object, str]] = []

    for i in range(page.locator("select").count()):
        sel = page.locator("select").nth(i)
        try:
            if not sel.is_visible():
                continue
            txt = ""
            try:
                txt = sel.evaluate(
                    """el => {
                      const o = el.options[el.selectedIndex];
                      return (o && o.text) ? o.text.trim() : (el.value || '');
                    }"""
                )
            except Exception:  # noqa: BLE001
                txt = (sel.inner_text() or "").strip()
            has_ym_opt = False
            try:
                for o in sel.locator("option").all()[:8]:
                    if _normalize_ym_text(o.inner_text() or ""):
                        has_ym_opt = True
                        break
            except Exception:  # noqa: BLE001
                pass
            norm = _normalize_ym_text(txt)
            if norm or has_ym_opt:
                found.append(("select", sel, norm or txt))
        except Exception:  # noqa: BLE001
            continue

    candidates = page.locator(
        "[role='combobox'], .ng-select, .mat-select, .mat-mdc-select, "
        "ng-select, mat-select"
    )
    for i in range(min(candidates.count(), 20)):
        el = candidates.nth(i)
        try:
            if not el.is_visible():
                continue
            txt = (el.inner_text() or "").strip().split("\n")[0].strip()
            norm = _normalize_ym_text(txt)
            if norm:
                found.append(("custom", el, norm))
        except Exception:  # noqa: BLE001
            continue

    if len(found) < 2:
        for i in range(min(page.get_by_text(_YM_RE).count(), 12)):
            el = page.get_by_text(_YM_RE).nth(i)
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip()
                norm = _normalize_ym_text(txt)
                if not norm:
                    continue
                tag = el.evaluate("e => e.tagName")
                if tag in ("LABEL", "P", "H1", "H2", "H3"):
                    continue
                found.append(("text", el, norm))
            except Exception:  # noqa: BLE001
                continue

    uniq: list[tuple[str, object, str]] = []
    seen: set = set()
    for kind, el, norm in found:
        try:
            box = el.bounding_box()  # type: ignore[attr-defined]
            key = (
                kind,
                round(box["x"] if box else 0),
                round(box["y"] if box else 0),
                norm,
            )
        except Exception:  # noqa: BLE001
            key = (kind, id(el), norm)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((kind, el, norm))
    return uniq


def _set_one_ym_control(page: Page, kind: str, el, target: str, variants: list[str]) -> bool:
    if kind == "select":
        try:
            options = [o.inner_text().strip() for o in el.locator("option").all()]
            for opt in options:
                if any(v in opt or opt == v for v in variants) or _normalize_ym_text(opt) == target:
                    el.select_option(label=opt)
                    return True
        except Exception:  # noqa: BLE001
            pass
        return False

    try:
        el.click(timeout=2_000)
        time.sleep(0.12)
    except Exception:  # noqa: BLE001
        return False

    for v in variants:
        try:
            opt = page.get_by_text(v, exact=True)
            for i in range(min(opt.count(), 8)):
                item = opt.nth(i)
                if item.is_visible():
                    item.click(timeout=2_000)
                    return True
        except Exception:  # noqa: BLE001
            continue
    try:
        opt = page.get_by_text(target, exact=False)
        for i in range(min(opt.count(), 8)):
            item = opt.nth(i)
            if item.is_visible():
                t = (item.inner_text() or "").strip()
                if _normalize_ym_text(t) == target:
                    item.click(timeout=2_000)
                    return True
    except Exception:  # noqa: BLE001
        pass
    try:
        page.keyboard.press("Escape")
    except Exception:  # noqa: BLE001
        pass
    return False


def ensure_query_year_month(page: Page, year: int, month: int, log_cb=None) -> str:
    """
    查詢年月：比對程式設定；相同則略過，不同則改成目標（起迄同月）。
    目標格式例：115年08月
    """

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    target = roc_ym_combined(year, month)
    variants = roc_ym_combined_variants(year, month)

    try:
        page.get_by_text("查詢年月", exact=False).first.wait_for(
            state="visible", timeout=8_000
        )
    except Exception:  # noqa: BLE001
        pass

    _ensure_query_ym_radio(page)
    controls = _find_ym_controls(page)
    if not controls:
        return _select_roc_year_month_split(page, year, month, log_cb=log_cb)

    pair = controls[:2]
    current = [c[2] for c in pair]
    log(f"查詢年月目前：{' ~ '.join(current)}；目標：{target}")

    if all((_normalize_ym_text(c) or c) == target for c in current):
        log("查詢年月已符合設定，略過修改")
        return "unchanged"

    log(f"查詢年月不符，改為 {target} ~ {target}")
    for kind, el, cur in pair:
        if (_normalize_ym_text(cur) or cur) == target:
            continue
        if not _set_one_ym_control(page, kind, el, target, variants):
            raise DownloadItemError(f"無法將查詢年月從「{cur}」改為「{target}」")

    time.sleep(0.15)
    again = _find_ym_controls(page)[:2]
    again_vals = [c[2] for c in again]
    if again and not all((_normalize_ym_text(c) or c) == target for c in again_vals):
        raise DownloadItemError(
            f"查詢年月改完後回讀不符：現在={' ~ '.join(again_vals)}，目標={target}"
        )
    log("查詢年月已更新")
    return "updated"


def _select_roc_year_month_split(page: Page, year: int, month: int, log_cb=None) -> str:
    """備援：年、月分開的原生 select。"""

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    roc_y, roc_m = to_roc_year_month(year, month)
    target_y = f"{roc_y}年"
    target_m = f"{roc_m:02d}月"
    assigned_year = False
    assigned_month = False
    for i in range(page.locator("select").count()):
        sel = page.locator("select").nth(i)
        try:
            if not sel.is_visible():
                continue
            options = [o.inner_text().strip() for o in sel.locator("option").all()]
        except Exception:  # noqa: BLE001
            continue
        if not assigned_year:
            for opt in options:
                if str(roc_y) in opt and "年" in opt:
                    sel.select_option(label=opt)
                    assigned_year = True
                    break
                if opt == str(roc_y):
                    sel.select_option(label=opt)
                    assigned_year = True
                    break
        if not assigned_month:
            for opt in options:
                if opt in (target_m, f"{roc_m}月", f"{roc_m:02d}"):
                    sel.select_option(label=opt)
                    assigned_month = True
                    break
    if not assigned_year or not assigned_month:
        raise DownloadItemError(
            f"無法帶入查詢年月（目標 {target_y}{target_m}；"
            f"年={'OK' if assigned_year else '失敗'} 月={'OK' if assigned_month else '失敗'}）"
        )
    log(f"已用分開下拉帶入：{target_y}{target_m}")
    return "updated"


def _select_roc_year_month(page: Page, year: int, month: int) -> None:
    ensure_query_year_month(page, year, month)


def _open_function_menu(page: Page) -> None:
    """登入後必須先點左上角「功能選單」。"""
    _quick_dismiss(page)
    last: Exception | None = None
    deadline = time.time() + 8
    while time.time() < deadline:
        candidates = [
            page.get_by_text("功能選單", exact=True),
            page.locator("button:has-text('功能選單')"),
            page.locator("a:has-text('功能選單')"),
        ]
        for loc in candidates:
            try:
                for i in range(min(loc.count(), 8)):
                    item = loc.nth(i)
                    if not item.is_visible():
                        continue
                    box = item.bounding_box()
                    if box and box["x"] > 560 and box["y"] > 220:
                        continue
                    item.click(timeout=2_000)
                    _quick_dismiss(page)
                    return
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(0.12)
    raise DownloadItemError(f"找不到左上角「功能選單」：{last}")


def _select_download_format_labor(page: Page) -> None:
    """下載區下拉：純文字檔(.txt)-格式二(含保費)。"""
    target_keys = ("純文字", "格式二", "含保費")
    preferred = "純文字檔(.txt)-格式二(含保費)"
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            if not sel.is_visible():
                continue
            options = [o.inner_text().strip() for o in sel.locator("option").all()]
        except Exception:  # noqa: BLE001
            continue
        for opt in options:
            if preferred in opt or opt == preferred:
                sel.select_option(label=opt)
                return
        for opt in options:
            if all(k in opt for k in target_keys):
                sel.select_option(label=opt)
                return
        for opt in options:
            if "格式二" in opt and ("txt" in opt.lower() or "純文字" in opt or "含保費" in opt):
                sel.select_option(label=opt)
                return
    try:
        page.get_by_text("純文字檔(.txt)-格式二(含保費)", exact=False).first.click(
            timeout=3_000
        )
        return
    except Exception as exc:  # noqa: BLE001
        raise DownloadItemError(
            "下載區找不到「純文字檔(.txt)-格式二(含保費)」下拉選項"
        ) from exc


def _save_download(download: Download, dest_dir: Path, company_name: str, ext: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f"_tmp_{int(time.time() * 1000)}{ext}"
    download.save_as(tmp)
    return move_as_company_file(tmp, dest_dir, company_name, ext)


def _click_download_and_save(page: Page, dest_dir: Path, company_name: str, ext: str) -> Path:
    _quick_dismiss(page)
    body = page.inner_text("body")
    if _is_deferred_message(body) and ("無法" in body or "請" in body or "申請" in body):
        if page.locator(
            "button:has-text('下載'), input[value='下載'], a:has-text('下載')"
        ).count() == 0:
            raise DownloadItemError("須隔日下載或當次無法取得檔案")

    with page.expect_download(timeout=120_000) as di:
        clicked = False
        for sel in [
            "button:has-text('下載')",
            "input[value='下載']",
            "a:has-text('下載')",
            "text=下載",
        ]:
            try:
                loc = page.locator(sel)
                for i in range(loc.count() - 1, -1, -1):
                    item = loc.nth(i)
                    if item.is_visible():
                        item.click(timeout=3_000)
                        clicked = True
                        break
                if clicked:
                    break
            except Exception:  # noqa: BLE001
                _quick_dismiss(page)
                continue
        if not clicked:
            raise DownloadItemError("找不到下載按鈕")
    path = _save_download(di.value, dest_dir, company_name, ext)
    _quick_dismiss(page)
    return path


def download_labor_roster(
    page: Page,
    year: int,
    month: int,
    dest_dir: Path,
    company_name: str,
    stop=None,
    log_cb=None,
) -> Path:
    """
    功能選單 → 資料查詢作業 → 投保單位被保險人名冊下載…
    → 比對／帶入查詢年月 → 查詢 → 下載區選格式二(含保費) → 下載
    """

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    def chk() -> None:
        if stop is not None:
            stop.check()

    chk()
    log("點擊：功能選單")
    _open_function_menu(page)
    chk()

    log("點擊：資料查詢作業")
    _click_menu(page, ["資料查詢作業"])
    chk()

    log("點擊：投保單位被保險人名冊下載")
    _click_menu(
        page,
        [
            "投保單位被保險人名冊下載（核對投保人員使用）",
            "投保單位被保險人名冊下載",
        ],
    )
    chk()
    try:
        page.get_by_text("查詢年月", exact=False).first.wait_for(
            state="visible", timeout=6_000
        )
    except Exception:  # noqa: BLE001
        time.sleep(0.2)

    log(f"處理查詢年月（目標 {roc_ym_combined(year, month)}）")
    ensure_query_year_month(page, year, month, log_cb=log)
    chk()

    log("點擊：查詢")
    clicked_query = False
    for sel in ["button:has-text('查詢')", "input[value='查詢']", "a:has-text('查詢')"]:
        try:
            loc = page.locator(sel)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible():
                    item.click(timeout=3_000)
                    clicked_query = True
                    break
            if clicked_query:
                break
        except Exception:  # noqa: BLE001
            continue
    if not clicked_query:
        raise DownloadItemError("找不到「查詢」按鍵")

    try:
        page.locator("select").first.wait_for(state="visible", timeout=8_000)
    except Exception:  # noqa: BLE001
        time.sleep(0.25)
    chk()
    _quick_dismiss(page)

    body = page.inner_text("body")
    if _is_deferred_message(body):
        raise DownloadItemError("須隔日下載或資料量限制（勞保名冊）")

    log("下載區下拉：純文字檔(.txt)-格式二(含保費)")
    _select_download_format_labor(page)
    chk()

    log("點擊：下載")
    return _click_download_and_save(page, dest_dir, company_name, ".txt")


def download_pension_roster(
    page: Page,
    year: int,
    month: int,
    dest_dir: Path,
    company_name: str,
    contribution_type: str,
) -> Path:
    _click_menu(page, ["資料查詢作業"])
    _click_menu(page, ["勞工退休金計算名冊下載"])
    ensure_query_year_month(page, year, month)
    picked = False
    for sel in page.locator("select").all():
        try:
            options = [o.inner_text().strip() for o in sel.locator("option").all()]
            for opt in options:
                if contribution_type in opt:
                    sel.select_option(label=opt)
                    picked = True
                    break
            if picked:
                break
        except Exception:  # noqa: BLE001
            continue
    if not picked:
        page.get_by_text(contribution_type, exact=False).first.click(timeout=5_000)
    for sel in ["button:has-text('查詢')", "input[value='查詢']", "text=查詢"]:
        try:
            page.locator(sel).first.click(timeout=5_000)
            break
        except Exception:  # noqa: BLE001
            continue
    time.sleep(0.35)
    body = page.inner_text("body")
    if _is_deferred_message(body):
        raise DownloadItemError(f"須隔日下載（{contribution_type}）")
    try:
        page.get_by_text("身分證號全部顯示", exact=False).first.click(timeout=5_000)
    except Exception:  # noqa: BLE001
        try:
            page.get_by_text("全部顯示", exact=False).first.click(timeout=3_000)
        except Exception:  # noqa: BLE001
            pass
    for sel in page.locator("select").all():
        try:
            options = [o.inner_text().strip() for o in sel.locator("option").all()]
            for opt in options:
                if opt.upper() == "TXT" or "TXT" in opt.upper() or "純文字" in opt:
                    sel.select_option(label=opt)
                    break
        except Exception:  # noqa: BLE001
            continue
    return _click_download_and_save(page, dest_dir, company_name, ".txt")


def download_payment_slips(
    page: Page,
    year: int,
    month: int,
    labor_dir: Path,
    pension_dir: Path,
    company_name: str,
) -> tuple[Path | None, Path | None, list[str]]:
    errors: list[str] = []
    labor_path: Path | None = None
    pension_path: Path | None = None
    _click_menu(page, ["電子帳單"])
    ensure_query_year_month(page, year, month)
    try:
        for sel in page.locator("select").all():
            options = [o.inner_text().strip() for o in sel.locator("option").all()]
            for opt in options:
                if "本單位" in opt:
                    sel.select_option(label=opt)
                    break
    except Exception:  # noqa: BLE001
        pass
    try:
        labor_path = _click_download_and_save(page, labor_dir, company_name, ".pdf")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"勞保繳費單：{exc}")
    try:
        ensure_query_year_month(page, year, month)
        with page.expect_download(timeout=120_000) as di:
            buttons = page.locator(
                "button:has-text('下載'), input[value='下載'], a:has-text('下載')"
            )
            if buttons.count() >= 2:
                buttons.nth(1).click(timeout=5_000)
            else:
                buttons.last.click(timeout=5_000)
        pension_path = _save_download(di.value, pension_dir, company_name, ".pdf")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"勞退繳費單：{exc}")
    return labor_path, pension_path, errors
