"""執行中止旗標：強制停止後可再按執行重跑。"""

from __future__ import annotations

import threading


class StopController:
    def __init__(self) -> None:
        self._event = threading.Event()

    def reset(self) -> None:
        self._event.clear()

    def request_stop(self) -> None:
        self._event.set()

    @property
    def stopped(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise StopRequested("使用者強制停止")


class StopRequested(RuntimeError):
    pass
