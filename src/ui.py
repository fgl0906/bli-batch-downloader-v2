"""Tkinter 操作畫面：憑證、年月、ON/OFF、即時日誌、執行／強制停止。"""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from src.company_list import Company, load_companies
from src.config import COMPANIES_FILE
from src.runner import RunRequest, run_batch
from src.stop_control import StopController, StopRequested


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("勞保局批次下載工具 v2.0.5（僅勞保名冊）")
        self.geometry("780x820")
        self.minsize(720, 700)
        self.resizable(True, True)

        self.companies: list[Company] = []
        self.enabled: dict[str, bool] = {}
        self.toggle_buttons: dict[str, tk.Button] = {}
        self._running = False
        self._stop = StopController()
        self._worker: threading.Thread | None = None

        self.national_id_var = tk.StringVar(value="")
        self.pin_var = tk.StringVar(value="")
        self.year_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就緒")

        self._build()
        self._load_companies()

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill="x", **pad)

        ttk.Label(frm, text="身分證號").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.national_id_var, width=28).grid(
            row=0, column=1, sticky="w", padx=8
        )

        ttk.Label(frm, text="自然人憑證密碼").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.pin_var, show="*", width=28).grid(
            row=1, column=1, sticky="w", padx=8
        )

        ttk.Label(frm, text="下載年月").grid(row=2, column=0, sticky="w")
        ym = ttk.Frame(frm)
        ym.grid(row=2, column=1, sticky="w", padx=8)
        now = datetime.now()
        years = [str(y) for y in range(now.year, now.year - 8, -1)]
        months = [f"{m:02d}" for m in range(1, 13)]
        self.year_var.set(str(now.year))
        self.month_var.set(f"{now.month:02d}")
        ttk.Combobox(ym, textvariable=self.year_var, values=years, width=8, state="readonly").pack(
            side="left"
        )
        ttk.Label(ym, text="年").pack(side="left", padx=4)
        ttk.Combobox(
            ym, textvariable=self.month_var, values=months, width=5, state="readonly"
        ).pack(side="left")
        ttk.Label(ym, text="月").pack(side="left", padx=4)

        tip = ttk.Label(
            self,
            text=(
                "除錯：只下載勞保名冊。"
                "查詢年月會先比對（如115年08月），相同略過、不同才改。"
                "允許請在檢測前自行點。「強制停止」可中止後再執行。"
            ),
            wraplength=740,
        )
        tip.pack(fill="x", padx=10)

        list_frame = ttk.LabelFrame(self, text="子公司（觸擊 ON/OFF）")
        list_frame.pack(fill="both", expand=False, padx=10, pady=8)
        list_frame.configure(height=220)

        canvas = tk.Canvas(list_frame, highlightthickness=0, height=180)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.list_inner = ttk.Frame(canvas)
        self.list_inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=10, pady=6)
        self.run_btn = ttk.Button(btn_row, text="執行", command=self._on_run)
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(
            btn_row, text="強制停止", command=self._on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(btn_row, text="重新載入清單", command=self._load_companies).pack(
            side="left", padx=8
        )
        ttk.Label(btn_row, textvariable=self.status_var).pack(side="left", padx=12)

        log_frame = ttk.LabelFrame(self, text="執行日誌")
        log_frame.pack(fill="both", expand=True, padx=10, pady=8)

        log_btns = ttk.Frame(log_frame)
        log_btns.pack(fill="x", padx=6, pady=4)
        ttk.Button(log_btns, text="清除日誌", command=self._clear_log).pack(side="left")
        ttk.Button(log_btns, text="複製日誌", command=self._copy_log).pack(side="left", padx=8)

        log_wrap = ttk.Frame(log_frame)
        log_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.log_text = tk.Text(log_wrap, height=16, wrap="word", state="disabled")
        log_scroll = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _append_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"

        def write() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            self.status_var.set(msg)

        self.after(0, write)

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_log(self) -> None:
        content = self.log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set("日誌已複製到剪貼簿")

    def _load_companies(self) -> None:
        for w in self.list_inner.winfo_children():
            w.destroy()
        self.toggle_buttons.clear()
        try:
            self.companies = load_companies(COMPANIES_FILE)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("清單錯誤", str(exc))
            self.companies = []
            return

        self.enabled = {c.insurance_id: True for c in self.companies}
        for idx, company in enumerate(self.companies):
            row = ttk.Frame(self.list_inner)
            row.pack(fill="x", pady=3, padx=4)
            btn = tk.Button(
                row,
                text="ON",
                width=6,
                bg="#2e7d32",
                fg="white",
                relief="raised",
                command=lambda cid=company.insurance_id: self._toggle(cid),
            )
            btn.pack(side="left")
            self.toggle_buttons[company.insurance_id] = btn
            label = f"{company.insurance_id}-{company.name}"
            if idx == 0:
                label += "  ← 登入用證號"
            ttk.Label(row, text=label).pack(side="left", padx=8)

        msg = f"已載入 {len(self.companies)} 家（預設全 ON）"
        self.status_var.set(msg)
        self._append_log(msg)

    def _toggle(self, insurance_id: str) -> None:
        self.enabled[insurance_id] = not self.enabled.get(insurance_id, True)
        on = self.enabled[insurance_id]
        btn = self.toggle_buttons[insurance_id]
        if on:
            btn.configure(text="ON", bg="#2e7d32")
        else:
            btn.configure(text="OFF", bg="#9e9e9e")

    def _on_stop(self) -> None:
        if not self._running:
            return
        self._stop.request_stop()
        self._append_log("已要求強制停止…（將關閉瀏覽器）")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("停止中…")

    def _set_idle_buttons(self) -> None:
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _on_run(self) -> None:
        if self._running:
            return
        national_id = self.national_id_var.get().strip()
        pin = self.pin_var.get().strip()
        if not national_id or not pin:
            messagebox.showwarning("資料不足", "請輸入身分證號與自然人憑證密碼")
            return
        if not self.companies:
            messagebox.showwarning("清單空白", "請先準備 companies.txt")
            return

        enabled = [c for c in self.companies if self.enabled.get(c.insurance_id, True)]
        if not enabled:
            messagebox.showwarning("未選擇", "至少需一間公司為 ON")
            return

        year = int(self.year_var.get())
        month = int(self.month_var.get())
        req = RunRequest(
            national_id=national_id,
            pin=pin,
            year=year,
            month=month,
            all_companies=self.companies,
            enabled_companies=enabled,
        )

        self._stop = StopController()
        self._running = True
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("執行中…")
        self._append_log(f"開始執行：{year}/{month:02d}，共 {len(enabled)} 家 ON（僅勞保名冊）")

        def worker() -> None:
            def pause_cb(msg: str) -> bool:
                if self._stop.stopped:
                    return False
                box: dict[str, bool] = {"ok": False}
                done = threading.Event()

                def ask() -> None:
                    if self._stop.stopped:
                        box["ok"] = False
                        done.set()
                        return
                    box["ok"] = bool(
                        messagebox.askokcancel("需要手動處理（瀏覽器會先保持開啟）", msg)
                    )
                    done.set()

                self.after(0, ask)
                done.wait()
                return box["ok"]

            try:
                summary = run_batch(
                    req,
                    progress_cb=self._append_log,
                    pause_cb=pause_cb,
                    stop=self._stop,
                )
                if self._stop.stopped:
                    self.after(0, self._stopped)
                else:
                    self.after(0, lambda: self._finish(summary))
            except StopRequested:
                self.after(0, self._stopped)
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._fail(str(exc)))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _stopped(self) -> None:
        self._running = False
        self._set_idle_buttons()
        self.status_var.set("已強制停止")
        self._append_log("已強制停止。可再按「執行」從頭重跑。")

    def _finish(self, summary) -> None:
        self._running = False
        self._set_idle_buttons()
        self.status_var.set("完成")
        log = str(summary.log_path) if summary.log_path else "(無)"
        self._append_log(
            f"結束｜成功 {len(summary.success_companies)}｜"
            f"部分 {len(summary.partial_companies)}｜"
            f"失敗 {len(summary.failed_companies)}｜"
            f"略過 {summary.skipped_count}"
        )
        msg = (
            f"執行完成\n\n"
            f"成功：{len(summary.success_companies)}\n"
            f"部分成功：{len(summary.partial_companies)}\n"
            f"失敗：{len(summary.failed_companies)}\n"
            f"略過(OFF)：{summary.skipped_count}\n\n"
            f"失敗日誌：\n{log}"
        )
        messagebox.showinfo("批次結果", msg)

    def _fail(self, err: str) -> None:
        self._running = False
        self._set_idle_buttons()
        self.status_var.set("中止")
        self._append_log(f"中止：{err}")
        messagebox.showerror("執行失敗", err)


def run_app() -> None:
    app = App()
    app.mainloop()
