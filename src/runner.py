"""編排：階段1登入 → 階段2關彈窗 → 僅下載勞保名冊（除錯用）。支援強制停止。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from src.bli.browser import BrowserSession
from src.bli.downloads import download_labor_roster
from src.bli.login import LoginError, login_with_citizen_cert
from src.bli.popups import dismiss_all_popups
from src.bli.switch_unit import SwitchUnitError, switch_unit
from src.company_list import Company
from src.config import DOWNLOADS_DIR, LOGS_DIR
from src.failure_log import FailureLogger, FailureRecord, RunSummary
from src.file_manager import ensure_month_folders
from src.roc_date import format_ym_folder
from src.stop_control import StopController, StopRequested

ProgressCb = Callable[[str], None]
PauseCb = Callable[[str], bool]


@dataclass
class RunRequest:
    national_id: str
    pin: str
    year: int
    month: int
    all_companies: list[Company]
    enabled_companies: list[Company]


def _clear_popups(page, progress: ProgressCb, label: str = "清彈窗") -> None:
    n = dismiss_all_popups(page, rounds=1)
    if n:
        progress(f"{label}：已關閉約 {n} 個")


def _download_labor_only(
    *,
    page,
    company: Company,
    year: int,
    month: int,
    folders: dict,
    ym: str,
    logger: FailureLogger,
    summary: RunSummary,
    progress: ProgressCb,
    stop: StopController,
) -> None:
    try:
        stop.check()
        _clear_popups(page, progress, "下載前清彈窗")
        progress(f"下載勞保名冊：{company.name}")
        download_labor_roster(
            page,
            year,
            month,
            folders["勞保名冊"],
            company.name,
            stop=stop,
            log_cb=progress,
        )
        stop.check()
        summary.success_companies.append(company.name)
        progress(f"完成：{company.name}（勞保名冊）")
    except StopRequested:
        raise
    except Exception as exc:  # noqa: BLE001
        rec = FailureRecord(company.insurance_id, company.name, "勞保名冊", str(exc), ym)
        logger.write(rec)
        summary.failures.append(rec)
        summary.failed_companies.append(company.name)
        progress(f"失敗 勞保名冊：{exc}")
    finally:
        try:
            _clear_popups(page, progress, "下載後清彈窗")
        except Exception:  # noqa: BLE001
            pass


def run_batch(
    req: RunRequest,
    progress_cb: ProgressCb | None = None,
    pause_cb: PauseCb | None = None,
    stop: StopController | None = None,
) -> RunSummary:
    def progress(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    def pause(msg: str) -> bool:
        if pause_cb:
            return pause_cb(msg)
        return False

    stop = stop or StopController()
    summary = RunSummary()
    summary.skipped_count = max(0, len(req.all_companies) - len(req.enabled_companies))
    logger = FailureLogger(LOGS_DIR)
    summary.log_path = logger.path
    ym = format_ym_folder(req.year, req.month)
    folders = ensure_month_folders(DOWNLOADS_DIR, ym)
    login_id = req.all_companies[0].insurance_id
    session = BrowserSession(DOWNLOADS_DIR / "_browser_tmp" / ym)

    try:
        stop.check()
        progress("階段1：啟動瀏覽器…")
        page = session.start()
        progress("階段1：登入流程開始…")
        try:
            login_with_citizen_cert(
                page,
                req.national_id,
                login_id,
                req.pin,
                pause_cb=pause_cb,
                log_cb=progress,
                stop=stop,
            )
        except StopRequested:
            progress("已強制停止（登入階段）")
            raise
        except LoginError as exc:
            logger.write(FailureRecord("", "", "登入", str(exc), ym))
            summary.failures.append(FailureRecord("", "", "登入", str(exc), ym))
            progress(f"登入失敗：{exc}")
            pause(f"登入失敗：{exc}\n\n按「確定」後將關閉瀏覽器。")
            return summary

        stop.check()
        progress("階段2：關閉登入後彈窗…")
        _clear_popups(page, progress, "登入後清彈窗")
        time.sleep(0.35)
        stop.check()
        _clear_popups(page, progress, "登入後再清一次")

        progress("除錯模式：只下載勞保名冊…")
        for company in req.enabled_companies:
            stop.check()
            _clear_popups(page, progress, "處理前清彈窗")
            progress(f"處理：{company.name}（{company.insurance_id}）")
            if company.insurance_id == login_id:
                progress(f"登入單位，不切換：{company.name}")
            else:
                try:
                    stop.check()
                    switch_unit(page, company.insurance_id, company.name)
                    progress(f"已切換單位：{company.insurance_id}")
                    _clear_popups(page, progress, "切換後清彈窗")
                except StopRequested:
                    raise
                except SwitchUnitError as exc:
                    rec = FailureRecord(
                        company.insurance_id, company.name, "切換單位", str(exc), ym
                    )
                    logger.write(rec)
                    summary.failures.append(rec)
                    summary.failed_companies.append(company.name)
                    progress(f"切換失敗：{exc}")
                    continue

            _download_labor_only(
                page=page,
                company=company,
                year=req.year,
                month=req.month,
                folders=folders,
                ym=ym,
                logger=logger,
                summary=summary,
                progress=progress,
                stop=stop,
            )

    except StopRequested:
        progress("已強制停止")
        logger.write(FailureRecord("", "", "強制停止", "使用者按下強制停止", ym))
    finally:
        progress("關閉瀏覽器…")
        session.close()

    return summary
