"""全域路徑與常數。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_FILE = ROOT / "companies.txt"
DOWNLOADS_DIR = ROOT / "downloads"
LOGS_DIR = ROOT / "logs"

BLI_HOME_URL = "https://edesk.bli.gov.tw/"

REPORT_FOLDERS = (
    "勞保名冊",
    "勞保繳費單",
    "勞退公司負擔名冊",
    "勞退個人自提名冊",
    "勞退繳費單",
)

DOWNLOAD_TIMEOUT_MS = 120_000
ACTION_TIMEOUT_MS = 30_000
