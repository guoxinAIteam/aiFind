"""可靠性工具：指数退避重试 + 任务级进程内串行锁。

保持零依赖：不强制引入 tenacity。必要时仅标注注释，不在此文件中
强行使用三方库。
"""
from __future__ import annotations

import asyncio
import random
import threading
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Type


class RetryExhaustedError(RuntimeError):
    pass


def retry_with_backoff(
    fn: Callable[[], Any],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    jitter: float = 0.2,
) -> Any:
    """同步的指数退避重试；失败耗尽后抛 RetryExhaustedError。

    careful：仅对网络/瞬时异常退避。参数错误类异常应由调用方预先过滤。
    """
    attempt = 0
    last_exc: Optional[BaseException] = None
    while attempt <= retries:
        try:
            return fn()
        except retry_on as e:
            last_exc = e
            if attempt == retries:
                break
            delay = min(max_delay, base_delay * (2**attempt))
            delay *= 1 + random.uniform(-jitter, jitter)
            time.sleep(max(0.0, delay))
            attempt += 1
    raise RetryExhaustedError(
        f"重试 {retries + 1} 次仍失败: {last_exc}"
    ) from last_exc


# ----- 按 task_id 的进程内串行锁 ---------------------------------------------

_TASK_LOCKS: Dict[int, threading.Lock] = {}
_TASK_LOCKS_GUARD = threading.Lock()


def task_lock(task_id: int) -> threading.Lock:
    """返回同一 task_id 的共享 Lock。外部用 `with task_lock(tid): ...`。

    进程内可用；多进程部署后应替换为 Redis 分布式锁。
    """
    with _TASK_LOCKS_GUARD:
        lock = _TASK_LOCKS.get(task_id)
        if lock is None:
            lock = threading.Lock()
            _TASK_LOCKS[task_id] = lock
        return lock
