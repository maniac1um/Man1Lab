"""Run-scoped single-writer lock using stdlib only."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from execution.errors import MalformedLockError, PersistenceIOError, WriterConflictError

LOCK_FILENAME = ".writer.lock"
STALE_LOCK_SECONDS = 3600


@dataclass(frozen=True)
class WriterLockInfo:
    owner_token: str
    pid: int
    acquired_at: str
    host: str = ""


class RunWriterLock:
    """Exclusive writer lock for one execution run directory."""

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir
        self._lock_path = run_dir / LOCK_FILENAME
        self._owner_token = str(uuid.uuid4())
        self._held = False
        self._fd: int | None = None

    @property
    def owner_token(self) -> str:
        return self._owner_token

    def acquire(self) -> None:
        self._run_dir.mkdir(parents=True, exist_ok=True)
        if self._lock_path.is_file():
            info = self._read_lock(require_parseable=True, allow_legacy=False)
            if info is not None and not self._lock_stale(info):
                raise WriterConflictError(
                    f"run writer lock held by pid {info.pid} since {info.acquired_at}"
                )
            if info is not None and self._lock_stale(info):
                self._remove_stale_lock()
        self._create_exclusive_lock()

    def release(self) -> None:
        if not self._held:
            return
        info = self._read_lock(require_parseable=False, allow_legacy=False)
        if info is not None and info.owner_token == self._owner_token:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError as exc:
                raise PersistenceIOError(f"failed to release writer lock: {exc}") from exc
        self._held = False

    def recover_stale(self, *, read_only: bool = False) -> bool:
        """Remove stale lock file; return True if a stale lock was cleared."""
        if not self._lock_path.is_file():
            return False
        info = self._read_lock(require_parseable=False, allow_legacy=True)
        if info is None:
            return False
        if not self._lock_stale(info):
            return False
        if read_only:
            return False
        return self._remove_stale_lock()

    def _create_exclusive_lock(self) -> None:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        payload = {
            "owner_token": self._owner_token,
            "pid": os.getpid(),
            "acquired_at": datetime.now(UTC).isoformat(),
            "host": os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "")),
        }
        encoded = (json.dumps(payload) + "\n").encode("utf-8")
        try:
            fd = os.open(self._lock_path, flags)
        except FileExistsError:
            info = self._read_lock(require_parseable=True, allow_legacy=False)
            if info is not None and not self._lock_stale(info):
                raise WriterConflictError(
                    f"run writer lock held by pid {info.pid} since {info.acquired_at}"
                ) from None
            if info is not None and self._lock_stale(info):
                self._remove_stale_lock()
            try:
                fd = os.open(self._lock_path, flags)
            except FileExistsError as exc:
                raise WriterConflictError("run writer lock contention after stale recovery") from exc
        except OSError as exc:
            raise PersistenceIOError(f"failed to acquire writer lock: {exc}") from exc
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        except OSError as exc:
            os.close(fd)
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise PersistenceIOError(f"failed to write writer lock: {exc}") from exc
        os.close(fd)
        self._fd = None
        self._held = True

    def _remove_stale_lock(self) -> bool:
        try:
            self._lock_path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def _read_lock(self, *, require_parseable: bool, allow_legacy: bool = False) -> WriterLockInfo | None:
        try:
            payload = json.loads(self._lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if require_parseable:
                raise MalformedLockError("writer lock file is malformed") from exc
            return None
        if not isinstance(payload, dict):
            if require_parseable:
                raise MalformedLockError("writer lock file is malformed")
            return None
        owner_token = payload.get("owner_token")
        pid = payload.get("pid")
        acquired_at = payload.get("acquired_at", "")
        if not isinstance(pid, int):
            if require_parseable:
                raise MalformedLockError("writer lock missing pid")
            return None
        if not isinstance(owner_token, str) or not owner_token:
            if allow_legacy:
                owner_token = f"legacy:{pid}:{acquired_at}"
            elif require_parseable:
                raise MalformedLockError("writer lock missing owner_token")
            else:
                return None
        return WriterLockInfo(
            owner_token=owner_token,
            pid=pid,
            acquired_at=str(acquired_at),
            host=str(payload.get("host", "")),
        )

    def _lock_stale(self, info: WriterLockInfo) -> bool:
        if info.owner_token == self._owner_token:
            return False
        if info.pid == os.getpid():
            return False
        local_host = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", ""))
        if info.host and local_host and info.host != local_host:
            return False
        if not _pid_is_running(info.pid):
            return True
        # A live owner never becomes stale merely because a task runs for a long
        # time. Long-running training commonly exceeds the diagnostic age
        # threshold; PID liveness is authoritative for a local lock.
        return False


def _pid_is_running(pid: int) -> bool:
    """Check process liveness without using terminating Windows signals."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            # Access denied means the process exists but cannot be inspected.
            return kernel32.GetLastError() == 5
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
